<<<<<<< Updated upstream
"""
Feature flags for spike management
Toggle expensive features during high load
"""
import os
from typing import Dict, Any

class FeatureFlags:
    def __init__(self):
        self._flags = {
            "FEATURE_POINTS": os.getenv("FEATURE_POINTS", "true").lower() == "true",
            "FEATURE_MATCH_HYBRID": os.getenv("FEATURE_MATCH_HYBRID", "true").lower() == "true",
            "FEATURE_ATTESTATION_INCLUDED_IN_MATCH": os.getenv("FEATURE_ATTESTATION_INCLUDED_IN_MATCH", "true").lower() == "true",
            "PAYMENT_PREFERRED_ADAPTER": os.getenv("PAYMENT_PREFERRED_ADAPTER", "authnet"),
            "PAYMENT_DISABLE_AUTHNET": os.getenv("PAYMENT_DISABLE_AUTHNET", "false").lower() == "true",
            "PAYMENT_DISABLE_NMI": os.getenv("PAYMENT_DISABLE_NMI", "false").lower() == "true",
        }
        
    def is_enabled(self, flag: str) -> bool:
        """Check if feature flag is enabled"""
        return self._flags.get(flag, False)
        
    def get_value(self, flag: str) -> str:
        """Get feature flag value"""
        if flag in ["PAYMENT_PREFERRED_ADAPTER"]:
            return self._flags.get(flag, "authnet")
        return str(self._flags.get(flag, ""))
        
    def all_flags(self) -> Dict[str, Any]:
        """Get all feature flags for debugging"""
        return self._flags.copy()

# Global feature flags instance
feature_flags = FeatureFlags()

# Convenience functions
def points_enabled() -> bool:
    """Check if points system is enabled"""
    return feature_flags.is_enabled("FEATURE_POINTS")

def match_hybrid_enabled() -> bool:
    """Check if MATCH hybrid flow is enabled"""
    return feature_flags.is_enabled("FEATURE_MATCH_HYBRID")

def attestation_in_match_enabled() -> bool:
    """Check if attestation is included in MATCH packages"""
    return feature_flags.is_enabled("FEATURE_ATTESTATION_INCLUDED_IN_MATCH")

def get_preferred_payment_adapter() -> str:
    """Get preferred payment adapter"""
    return feature_flags.get_value("PAYMENT_PREFERRED_ADAPTER")

def is_payment_adapter_disabled(adapter: str) -> bool:
    """Check if payment adapter is disabled"""
    if adapter == "authnet":
        return feature_flags.is_enabled("PAYMENT_DISABLE_AUTHNET")
    elif adapter == "nmi":
        return feature_flags.is_enabled("PAYMENT_DISABLE_NMI")
    return False
=======
class FeatureFlags:
    def all_flags(self):
        return {"ai_dynamic": True}

feature_flags = FeatureFlags()
>>>>>>> Stashed changes
