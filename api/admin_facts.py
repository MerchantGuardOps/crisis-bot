from __future__ import annotations
import os, json, hashlib, datetime, asyncio, textwrap
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncpg
import httpx

try:
    from jsonschema import Draft202012Validator
    _has_jsonschema = True
except Exception:
    _has_jsonschema = False

# Optional GCS publish
_GCS_ENABLED = False
try:
    from google.cloud import storage
    _GCS_ENABLED = True
except Exception:
    _GCS_ENABLED = False

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- ENV / CONFIG ---
ADMIN_API_TOKENS = set([t.strip() for t in os.getenv("ADMIN_API_TOKENS","").split(",") if t.strip()])
FACTS_GCS_BUCKET = os.getenv("FACTS_GCS_BUCKET")  # optional
BASE_URL = os.getenv("BASE_URL","https://merchantguard.ai")
SITEMAP_URL = f"{BASE_URL}/sitemap-ai.xml"
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY")  # optional IndexNow key
FEATURE_AI_DYNAMIC = os.getenv("FEATURE_AI_DYNAMIC","true").lower() == "true"

# Injected in startup: app.state.pg_pool
def get_pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "pg_pool", None)
    if not pool:
        raise HTTPException(500, "DB pool not initialized")
    return pool

# --- AUTH GUARD ---
def require_admin(request: Request):
    # 1) Prefer IAP/identity proxy headers if present (already allowed by infra)
    # 2) Fallback to header token: X-Admin-Token: <token> or cookie 'mg_admin'
    hdr = request.headers.get("X-Admin-Token") or request.cookies.get("mg_admin")
    if not ADMIN_API_TOKENS:
        # If unset, deny by default (safer)
        raise HTTPException(403, "Admin tokens not configured")
    if hdr not in ADMIN_API_TOKENS:
        raise HTTPException(403, "Forbidden")
    return True

# --- UTILS ---
def canonicalize_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",",":"))

def compute_etag(obj: Any) -> str:
    return hashlib.sha256(canonicalize_json(obj).encode("utf-8")).hexdigest()

async def _fetch_one(pool: asyncpg.Pool, q: str, *args):
    async with pool.acquire() as con:
        return await con.fetchrow(q, *args)

async def _exec(pool: asyncpg.Pool, q: str, *args):
    async with pool.acquire() as con:
        return await con.execute(q, *args)

async def _fetch_all(pool: asyncpg.Pool, q: str, *args):
    async with pool.acquire() as con:
        return await con.fetch(q, *args)

async def _upsert_fact(pool: asyncpg.Pool, doc_id: str, title: str, category: str, json_content: dict,
                       schema_uri: Optional[str], status: str, actor: str, note: Optional[str]) -> Dict[str,Any]:
    etag = compute_etag(json_content)
    async with pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow("""
                INSERT INTO ai_facts (doc_id, title, category, json_content, schema_uri, status, etag, updated_by, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())
                ON CONFLICT (doc_id) DO UPDATE
                SET title=EXCLUDED.title,
                    category=EXCLUDED.category,
                    json_content=EXCLUDED.json_content,
                    schema_uri=EXCLUDED.schema_uri,
                    status=EXCLUDED.status,
                    etag=EXCLUDED.etag,
                    updated_by=EXCLUDED.updated_by,
                    updated_at=NOW()
                RETURNING doc_id, title, category, json_content, schema_uri, status, etag, updated_by, updated_at, published_at
            """, doc_id, title, category, json_content, schema_uri, status, etag, actor)
            await con.execute("""
                INSERT INTO ai_facts_revisions (doc_id, etag, json_content, updated_by, note)
                VALUES ($1, $2, $3, $4, $5)
            """, doc_id, etag, json_content, actor, note or "")
            return dict(row)

async def _publish(pool: asyncpg.Pool, doc_id: str, actor: str, targets: List[str], responses: Dict[str,Any]):
    await _exec(pool, """
        UPDATE ai_facts SET status='published', published_at=NOW() WHERE doc_id=$1
    """, doc_id)
    await _exec(pool, """
        INSERT INTO ai_facts_publish_log (doc_id, etag, actor, targets, responses)
        SELECT doc_id, etag, $2, $3::jsonb, $4::jsonb FROM ai_facts WHERE doc_id=$1
    """, doc_id, actor, json.dumps(targets), json.dumps(responses))

async def _load_fact(pool: asyncpg.Pool, doc_id: str) -> Optional[Dict[str,Any]]:
    row = await _fetch_one(pool, "SELECT * FROM ai_facts WHERE doc_id=$1", doc_id)
    return dict(row) if row else None

# --- SCHEMA VALIDATION ---
def _load_schema_local(schema_uri: Optional[str]) -> Optional[dict]:
    if not schema_uri: 
        return None
    # schema_uri can be a file path under ./schemas/...
    if schema_uri.startswith("schemas/") and os.path.exists(schema_uri):
        with open(schema_uri,"r",encoding="utf-8") as f:
            return json.load(f)
    return None

def validate_against_schema(doc: dict, schema: Optional[dict]) -> List[str]:
    if not schema or not _has_jsonschema:
        return []
    errs = []
    validator = Draft202012Validator(schema)
    for e in validator.iter_errors(doc):
        errs.append(f"{'/'.join([str(x) for x in e.path])}: {e.message}")
    return errs

# --- CRAWLER PINGS / REBUILD ---
async def ping_crawlers() -> Dict[str, Any]:
    # Google sitemap ping
    out = {}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            g = await client.get("https://www.google.com/ping", params={"sitemap": SITEMAP_URL})
            out["google"] = {"status": g.status_code}
        except Exception as e:
            out["google"] = {"error": str(e)}
        # IndexNow (Bing/Yandex) optional
        if INDEXNOW_KEY:
            try:
                payload = {
                    "host": BASE_URL.replace("https://","").replace("http://",""),
                    "key": INDEXNOW_KEY,
                    "keyLocation": f"{BASE_URL}/{INDEXNOW_KEY}.txt",
                    "urlList": [f"{BASE_URL}/ai/facts/"]
                }
                b = await client.post("https://api.indexnow.org/IndexNow", json=payload)
                out["indexnow"] = {"status": b.status_code}
            except Exception as e:
                out["indexnow"] = {"error": str(e)}
    return out

async def rebuild_ai_index(app) -> Dict[str,Any]:
    """
    Hook your existing scripts/ai_build_match_index.py here if you wish.
    For now, we simulate a rebuild tick.
    """
    # If you want, spawn subprocess:
    # import asyncio, sys
    # p = await asyncio.create_subprocess_exec(sys.executable, "scripts/ai_build_match_index.py")
    # await p.wait()
    return {"rebuild": "ok", "ts": datetime.datetime.utcnow().isoformat()}

# --- OPTIONAL GCS EXPORT ---
async def export_to_gcs(doc_id: str, content: dict) -> Dict[str, Any]:
    if not _GCS_ENABLED or not FACTS_GCS_BUCKET:
        return {"gcs": "disabled"}
    client = storage.Client()
    bucket = client.bucket(FACTS_GCS_BUCKET)
    blob = bucket.blob(f"ai/facts/{doc_id}.json")
    data = canonicalize_json(content).encode("utf-8")
    blob.cache_control = "public, max-age=300, must-revalidate"
    blob.content_type = "application/json"
    blob.upload_from_string(data)
    blob.patch()
    return {"gcs": "uploaded", "bucket": FACTS_GCS_BUCKET, "path": f"ai/facts/{doc_id}.json"}

# ======================
# Admin UI (HTML pages)
# ======================

@router.get("/admin/facts", response_class=HTMLResponse)
async def facts_list(request: Request, ok: bool = Depends(require_admin), pool: asyncpg.Pool = Depends(get_pool)):
    rows = await _fetch_all(pool, """
      SELECT doc_id, title, category, status, etag, updated_by, updated_at, published_at
      FROM ai_facts ORDER BY category, doc_id
    """)
    return templates.TemplateResponse("admin/facts_list.html", {
        "request": request,
        "rows": [dict(r) for r in rows],
        "base_url": BASE_URL
    })

@router.get("/admin/facts/{doc_id}", response_class=HTMLResponse)
async def facts_editor(request: Request, doc_id: str, ok: bool = Depends(require_admin),
                       pool: asyncpg.Pool = Depends(get_pool)):
    row = await _load_fact(pool, doc_id)
    if not row:
        # fresh doc stub
        row = {
            "doc_id": doc_id, "title": doc_id, "category": "match",
            "json_content": {"id": doc_id, "last_updated": datetime.datetime.utcnow().date().isoformat()},
            "schema_uri": None, "status":"draft", "etag":"", "updated_by":"", "updated_at": None
        }
    # load schema if local
    schema = None
    if row.get("schema_uri"):
        schema = _load_schema_local(row["schema_uri"])
    return templates.TemplateResponse("admin/facts_editor.html", {
        "request": request, "fact": row, "schema": schema,
        "dynamic_endpoint": f"/ai/facts/{doc_id}.json"
    })

@router.post("/admin/facts/{doc_id}/validate")
async def validate_doc(request: Request, doc_id: str, ok: bool = Depends(require_admin)):
    body = await request.json()
    content = body.get("json_content", {})
    schema = body.get("schema")
    errs = validate_against_schema(content, schema)
    return {"ok": len(errs)==0, "errors": errs}

@router.post("/admin/facts/{doc_id}/save")
async def save_doc(request: Request, doc_id: str, ok: bool = Depends(require_admin),
                   pool: asyncpg.Pool = Depends(get_pool)):
    body = await request.json()
    title     = body.get("title") or doc_id
    category  = body.get("category") or "misc"
    content   = body.get("json_content") or {}
    schema_uri= body.get("schema_uri")
    actor     = body.get("actor") or "admin"
    note      = body.get("note") or ""
    # optional client-side schema included
    schema = body.get("schema")
    errs = validate_against_schema(content, schema)
    if errs:
        return JSONResponse({"ok": False, "errors": errs}, status_code=400)
    row = await _upsert_fact(pool, doc_id, title, category, content, schema_uri, "draft", actor, note)
    return {"ok": True, "doc": row}

@router.post("/admin/facts/{doc_id}/publish")
async def publish_doc(request: Request, doc_id: str, ok: bool = Depends(require_admin),
                      pool: asyncpg.Pool = Depends(get_pool)):
    body      = await request.json()
    actor     = body.get("actor") or "admin"
    export_gcs= bool(body.get("export_gcs", False))
    ping      = bool(body.get("ping_crawlers", True))
    rebuild   = bool(body.get("rebuild_index", True))

    row = await _load_fact(pool, doc_id)
    if not row:
        raise HTTPException(404, "Document not found")
    # Optionally export to GCS
    responses = {}
    targets = ["dynamic"]
    if export_gcs:
        g = await export_to_gcs(doc_id, row["json_content"])
        responses.update(g); targets.append("gcs")
    # async crawler ping + rebuild
    if ping:
        responses["crawler_ping"] = await ping_crawlers(); targets.append("crawler_ping")
    if rebuild:
        responses["rebuild"] = await rebuild_ai_index(request.app); targets.append("rebuild")

    await _publish(pool, doc_id, actor, targets, responses)
    return {"ok": True, "published": {"doc_id": doc_id}, "responses": responses}

# ============================
# Public facts (dynamic JSON)
# ============================

@router.get("/ai/facts/{doc_id}.json")
async def serve_fact(doc_id: str, request: Request, pool: asyncpg.Pool = Depends(get_pool)):
    if not FEATURE_AI_DYNAMIC:
        # Optionally 404 if you keep static files only
        raise HTTPException(404, "Dynamic facts disabled")
    row = await _load_fact(pool, doc_id)
    if not row or row["status"] not in ("published", "draft"):
        raise HTTPException(404, "Not found")

    body = row["json_content"]
    etag = row["etag"]
    # HTTP caching
    inm = request.headers.get("If-None-Match")
    if inm and inm.strip('"') == etag:
        return Response(status_code=304)
    headers = {
        "ETag": f'"{etag}"',
        "Cache-Control": "public, max-age=300, must-revalidate",
        "Content-Type": "application/json; charset=utf-8"
    }
    return JSONResponse(body, headers=headers)

# ============================
# AI Sitemap (Dynamic)
# ============================

@router.get("/sitemap-ai-dynamic.xml", response_class=PlainTextResponse)
async def ai_sitemap_dynamic(pool: asyncpg.Pool = Depends(get_pool)):
    rows = await _fetch_all(pool, "SELECT doc_id, updated_at FROM ai_facts WHERE status='published'")
    items = []
    for r in rows:
        loc = f"{BASE_URL}/ai/facts/{r['doc_id']}.json"
        lastmod = (r["updated_at"] or datetime.datetime.utcnow()).strftime("%Y-%m-%d")
        items.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    xml = "<?xml version='1.0' encoding='UTF-8'?>\n" \
          "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>\n" + \
          "\n".join(items) + "\n</urlset>"
    return xml