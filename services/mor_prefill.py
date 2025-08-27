def prefill_fastspring(intake):
    """Generate pre-filled FastSpring application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "website": intake["site"]["url"],
        "business_model": intake["commerce"]["business_model"],
        "avg_ticket": intake["processing"]["avg_ticket"],
        "country": intake["legal"]["country"],
        "descriptor_preview": intake["compliance"]["descriptor_preview"],
        "policies": {
            "refund_sla": intake["compliance"]["refund_sla"],
            "tos_url": intake["site"]["tos_url"],
            "privacy_url": intake["site"]["privacy_url"]
        },
        "risk_note": f"3DS default-on; RDR/Ethoca auto-accept ≤ ${intake['risk']['auto_accept_threshold']}; refunds ≤24h"
    }

def prefill_durango(intake):
    """Generate pre-filled Durango Merchant Services application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "dba": intake["legal"].get("dba"),
        "entity_type": intake["legal"].get("entity_type"),
        "monthly_volume": intake["processing"]["volume_monthly"],
        "dispute_rate_30d": intake["metrics"]["dispute_rate_30d"],
        "match_listed": intake["processing"]["match_listed"],
        "explanation": intake["risk"]["remediation_summary"],
        "controls": ["3DS", "AVS/CVV", "RDR/Ethoca", "refunds ≤24h"]
    }

def prefill_paymentcloud(intake):
    """Generate pre-filled PaymentCloud application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "website": intake["site"]["url"],
        "business_model": intake["commerce"]["business_model"],
        "monthly_volume": intake["processing"]["volume_monthly"],
        "avg_ticket": intake["processing"]["avg_ticket"],
        "dispute_rate": intake["metrics"]["dispute_rate_30d"],
        "descriptor": intake["compliance"]["descriptor_preview"],
        "risk_controls": {
            "fraud_protection": "3DS + AVS/CVV",
            "chargeback_tools": "RDR/Ethoca enabled",
            "refund_sla": f"{intake['compliance']['refund_sla']} hours"
        }
    }

def prefill_emb(intake):
    """Generate pre-filled EMerchant Broker application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "business_type": intake["commerce"]["business_model"],
        "monthly_volume": intake["processing"]["volume_monthly"],
        "dispute_rate": intake["metrics"]["dispute_rate_30d"],
        "match_listed": intake["processing"]["match_listed"],
        "risk_mitigation": intake["risk"]["remediation_summary"],
        "website": intake["site"]["url"],
        "processing_history": "See attached documentation"
    }

def prefill_paddle(intake):
    """Generate pre-filled Paddle application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "website": intake["site"]["url"],
        "business_model": intake["commerce"]["business_model"],
        "monthly_volume": intake["processing"]["volume_monthly"],
        "avg_ticket": intake["processing"]["avg_ticket"],
        "country": intake["legal"]["country"],
        "product_category": "SaaS/Digital Services"
    }

def prefill_soar(intake):
    """Generate pre-filled Soar Payments application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "monthly_volume": intake["processing"]["volume_monthly"],
        "industry": intake["commerce"]["business_model"],
        "processing_history": "MATCH listed" if intake["processing"]["match_listed"] else "Clean history",
        "website": intake["site"]["url"],
        "risk_score": "High" if intake["processing"]["match_listed"] else "Medium"
    }

def prefill_host(intake):
    """Generate pre-filled Host Merchant Services application data"""
    return {
        "legal_name": intake["legal"]["name"],
        "monthly_volume": intake["processing"]["volume_monthly"],
        "business_model": intake["commerce"]["business_model"],
        "avg_ticket": intake["processing"]["avg_ticket"],
        "website": intake["site"]["url"],
        "risk_level": "High" if intake["processing"]["match_listed"] else "Standard"
    }

# Provider prefill function mapping
PREFILL_FUNCTIONS = {
    'fastspring': prefill_fastspring,
    'durango': prefill_durango,
    'paymentcloud': prefill_paymentcloud,
    'emb': prefill_emb,
    'paddle': prefill_paddle,
    'soar': prefill_soar,
    'host': prefill_host
}

def get_prefilled_data(provider: str, intake: dict):
    """Get pre-filled application data for a specific provider"""
    prefill_func = PREFILL_FUNCTIONS.get(provider)
    if not prefill_func:
        return {"error": f"No prefill function for provider: {provider}"}
    
    try:
        return prefill_func(intake)
    except KeyError as e:
        return {"error": f"Missing required intake field: {e}"}
    except Exception as e:
        return {"error": f"Prefill error: {str(e)}"}