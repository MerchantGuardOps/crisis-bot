<<<<<<< Updated upstream
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import asyncpg, os, hashlib
from typing import Optional
from services.partners.recommender import PSPRecommendations
from services.partners.tracker import PartnerTracker

router = APIRouter(prefix="/partners", tags=["partners"])

def get_pool(request: Request) -> asyncpg.pool.Pool:
    return request.app.state.pg_pool  # your app should set this on startup

def get_recs() -> PSPRecommendations:
    return PSPRecommendations("config/partners.yaml")

def get_tracker(request: Request) -> PartnerTracker:
    base = os.environ.get("BASE_URL", "http://localhost:8000")
    secret = os.environ.get("PARTNER_REDIRECT_SECRET", "devsecret-change-me")
    return PartnerTracker(request.app.state.pg_pool, base, secret)

@router.get("/recommendations")
async def recommendations(
    user_id: str,
    match_listed: bool = False,
    violation_risk: Optional[float] = 0.0,
    needs_entity: bool = False,
    recs: PSPRecommendations = Depends(get_recs)
):
    picks = recs.choose_for_context(
        match_listed=match_listed,
        violation_risk=violation_risk or 0.0,
        needs_entity=needs_entity,
        limit=4
    )
    return {"disclosure": recs.disclosure_short(), "recommendations": picks}

@router.get("/pipeline")
async def pipeline_report(tracker: PartnerTracker = Depends(get_tracker)):
    return await tracker.pipeline_report()

# Public signed redirect (logs internally, then 302)
@router.get("/go/{provider}")
async def go_provider(
    provider: str,
    user_id: str,
    source: str,
    tracker: PartnerTracker = Depends(get_tracker),
    recs: PSPRecommendations = Depends(get_recs),
):
    # Build a signed URL and return it, so callers can use it directly (optional)
    url = tracker.signed_redirect_url(provider, user_id, source)
    return {"url": url}

# Actual redirect endpoint used by buttons
async def redirect_provider(
    request: Request,
    provider: str,
    u: str,   # user_id
    s: str,   # signature
    t: str,   # timestamp
    source: str,
    tracker: PartnerTracker = Depends(get_tracker),
    recs: PSPRecommendations = Depends(get_recs),
):
    # Verify signature
    if not tracker.verify(provider, u, source, t, s):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Find provider URL
    pmap = {p["id"]: p for p in recs.list_visible()}
    if provider not in pmap:
        raise HTTPException(status_code=404, detail="Unknown provider")

    # Optional IP hashing for uniqueness/fraud checks
    ip = request.client.host if request.client else ""
    ip_hash = hashlib.sha256((ip + "pepper").encode("utf-8")).hexdigest() if ip else None
    ua = request.headers.get("user-agent")

    await tracker.log_click(user_id=u, provider=provider, source=source, user_agent=ua, ip_hash=ip_hash)
    return RedirectResponse(url=pmap[provider]["url"])
=======
from fastapi import APIRouter

router = APIRouter()

def init_partner_routes(app, affiliate_tracker):
    """Initialize partner routes stub"""
    pass

@router.get("/partners/health")
async def partners_health():
    return {"status": "partners_ok"}
>>>>>>> Stashed changes
