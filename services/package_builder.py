"""MATCH Recovery package builder - generates ZIP with all materials"""

import io, json, zipfile, datetime, yaml, os
from typing import Dict
from services.success_rates import load_provider_stats
from services.provider_priority import get_application_order, rank_with_runtime_signals
from generators.mor_prefill import prefill_fast_spring, prefill_paddle
from generators.highrisk_prefill import prefill_durango, prefill_paymentcloud, prefill_emb, prefill_soar, prefill_host

PREFILLERS = {
  "fastspring": prefill_fast_spring,
  "paddle": prefill_paddle,
  "durango": prefill_durango,
  "paymentcloud": prefill_paymentcloud,
  "emb": prefill_emb,
  "soar": prefill_soar,
  "host": prefill_host
}

def _read(path): 
    """Safely read file content"""
    try:
        with open(path,'r') as f: 
            return f.read()
    except FileNotFoundError:
        return f"Template not found: {path}"

def _readyaml(path):
    """Safely read YAML file"""
    try:
        with open(path,'r') as f: 
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

async def build_match_package(pg_pool, intake: Dict, repo_root=".") -> bytes:
    """
    Build complete MATCH Liberation package as ZIP
    
    Returns: ZIP bytes containing:
    - Pre-filled applications in priority order
    - Emergency contacts
    - Rejection response templates
    - MATCH removal templates
    - Crypto provider matrix
    - Observed success rates
    """
    
    # Load all templates and configs
    provider_map = _readyaml(os.path.join(repo_root, "config/provider_field_maps.yaml"))
    crypto_matrix = _read(os.path.join(repo_root, "config/crypto_providers.yaml"))
    contacts      = _read(os.path.join(repo_root, "templates/emergency_contacts.yaml"))
    rej_fast      = _read(os.path.join(repo_root, "templates/rejection_responses/fastspring.md"))
    rej_drg       = _read(os.path.join(repo_root, "templates/rejection_responses/durango.md"))
    rm_list       = _read(os.path.join(repo_root, "templates/match_removal/listing_acquirer.md"))
    rm_pci        = _read(os.path.join(repo_root, "templates/match_removal/pci_code12.md"))

    # Determine application order with runtime optimization
    base = get_application_order(intake)
    stats = await load_provider_stats(pg_pool)
    order = rank_with_runtime_signals(base, stats)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # Package README
        info = (
          "MATCH Liberation Package — Contents\n\n"
          "🚀 IMMEDIATE (24-72h):\n"
          "• MoR applications (FastSpring, Paddle)\n"
          "• USDC payment setup guide\n\n"
          "💼 TRADITIONAL RECOVERY (2-12 weeks):\n"
          "• 5 pre‑filled high‑risk applications\n"
          "• Emergency escalation contacts\n"
          "• Rejection recovery scripts\n"
          "• MATCH removal templates\n\n"
          "📊 DATA:\n"
          "• Observed success rates (updated nightly)\n"
          "• Provider comparison matrix\n\n"
          "All pre-filled from your intake data.\n"
          "Submit, follow up, track outcomes."
        )
        z.writestr("README.txt", info)

        # Provider order with observed stats
        z.writestr("providers/order.json", json.dumps({
            "recommended_order": order, 
            "observed_stats": stats,
            "base_order_logic": "SaaS: MoR first. MATCH: High-risk first."
        }, indent=2))

        # Pre-filled applications
        z.writestr("applications/README.md", "# Pre-filled Applications\n\nSubmit in the recommended order for best results.\n")
        
        for i, pid in enumerate(order, 1):
            prefiller = PREFILLERS.get(pid)
            if not prefiller: 
                continue
            try:
                payload = prefiller(intake)
                provider_info = provider_map.get('providers', {}).get(pid, {})
                
                # Enhanced application with metadata
                enhanced_payload = {
                    "provider": pid,
                    "priority_rank": i,
                    "provider_info": provider_info,
                    "pre_filled_data": payload,
                    "submission_notes": f"Best for: {provider_info.get('best_for', 'Various')}\nTypical timeframe: {provider_info.get('typical_timeframe', 'Varies')}"
                }
                
                z.writestr(f"applications/{i:02d}_{pid}.json", json.dumps(enhanced_payload, indent=2))
            except Exception as e:
                z.writestr(f"applications/{i:02d}_{pid}_ERROR.json", json.dumps({
                    "error": str(e),
                    "provider": pid,
                    "note": "Check intake data completeness"
                }, indent=2))

        # Emergency contacts and escalation
        z.writestr("contacts/emergency_contacts.yaml", contacts)
        z.writestr("contacts/README.md", "# Emergency Contacts\n\nUse when applications stall or need escalation.\n")

        # Rejection recovery scripts
        z.writestr("rejection_recovery/fastspring_appeal.md", rej_fast)
        z.writestr("rejection_recovery/durango_appeal.md", rej_drg)
        z.writestr("rejection_recovery/README.md", "# Rejection Recovery\n\nCustomize with your specific situation and resubmit.\n")

        # MATCH removal templates
        z.writestr("match_removal/listing_acquirer_request.md", rm_list)
        z.writestr("match_removal/pci_code12_request.md", rm_pci)
        z.writestr("match_removal/README.md", "# MATCH Removal\n\nAddress to LISTING ACQUIRER (not Mastercard directly).\nCode 12 (PCI) has best removal odds after remediation.\n")

        # Crypto/USDC setup guide
        z.writestr("crypto_setup/providers.yaml", crypto_matrix)
        z.writestr("crypto_setup/README.md", "# USDC Immediate Setup\n\nGet selling again in 24-72h while traditional apps process.\n\n**Best Options:**\n1. Coinbase Commerce (1%, instant)\n2. Stripe Crypto (1.5%, existing KYC)\n3. BitPay (1-2%, good for physical)\n")

        # Observed statistics snapshot
        snapshot = {
          "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
          "data_source": "Real MerchantGuard user outcomes",
          "providers_with_data": list(stats.keys()) if stats else [],
          "observed_success_rates": stats,
          "note": "Rates update nightly as users report outcomes"
        }
        z.writestr("analytics/success_rates.json", json.dumps(snapshot, indent=2))

        # Package metadata
        meta = {
            "package_type": "MATCH_LIBERATION_HYBRID",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "merchant_id": intake.get("merchant_id", "unknown"),
            "intake_version": intake.get("version", "1.0"),
            "total_applications": len(order),
            "immediate_options": ["MoR", "USDC"],
            "traditional_recovery": True,
            "includes_attestation": True
        }
        z.writestr("_meta.json", json.dumps(meta, indent=2))

    buf.seek(0)
    return buf.getvalue()