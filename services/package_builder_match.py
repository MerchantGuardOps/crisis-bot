import io
import json
import zipfile
import datetime
import os
from typing import Dict, List
from .mor_prefill import get_prefilled_data
from .success_rates import load_provider_stats
from .provider_priority import get_application_order, rank_with_runtime_signals

async def build_match_package(pool, intake: dict, include_prevention_guide: bool = False) -> bytes:
    """
    Build the complete MATCH Liberation ($499) package as a ZIP file.
    
    Args:
        pool: Database connection pool
        intake: Merchant intake data
        include_prevention_guide: If True, includes the 5-page prevention guide
    
    Returns:
        ZIP file as bytes
    """
    # Get provider order and current success rates
    base_order = get_application_order(intake)
    runtime_stats = await load_provider_stats(pool)
    final_order = rank_with_runtime_signals(base_order, runtime_stats)
    
    # Generate pre-filled applications for all providers
    prefilled_apps = {}
    for provider in final_order:
        prefilled_data = get_prefilled_data(provider, intake)
        prefilled_apps[f"{provider}.json"] = prefilled_data
    
    # Build ZIP in memory
    buf = io.BytesIO()
    
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Core documentation
        _add_file_to_zip(z, "templates/MATCH_Survival_Playbook_2025.pdf", 
                        "docs/MATCH_Survival_Playbook_2025.pdf")
        
        # Optional prevention guide (for $199 package)
        if include_prevention_guide:
            _add_file_to_zip(z, "templates/MATCH_Prevention_Guide.pdf", 
                            "docs/MATCH_Prevention_Guide.pdf")
        
        # Emergency contacts and support
        _add_file_to_zip(z, "templates/emergency_contacts.yaml", 
                        "contacts/emergency_contacts.yaml")
        
        # Crypto/USDC provider matrix
        _add_file_to_zip(z, "config/crypto_providers.yaml", 
                        "config/crypto_providers.yaml")
        
        # Rejection response scripts
        _add_file_to_zip(z, "templates/rejection_responses/fastspring.md", 
                        "scripts/rejection/fastspring.md")
        _add_file_to_zip(z, "templates/rejection_responses/durango.md", 
                        "scripts/rejection/durango.md")
        _add_file_to_zip(z, "templates/rejection_responses/paymentcloud.md", 
                        "scripts/rejection/paymentcloud.md")
        
        # MATCH removal templates
        _add_file_to_zip(z, "templates/match_removal/visa.md", 
                        "scripts/match_removal/visa.md")
        
        # Pre-filled applications (JSON format for easy copying)
        for filename, data in prefilled_apps.items():
            z.writestr(f"applications/{filename}", 
                      json.dumps(data, indent=2, default=str))
        
        # Current provider rankings and success rates
        z.writestr("analytics/provider_order.json", 
                  json.dumps({
                      "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
                      "recommended_order": final_order,
                      "base_rules": base_order,
                      "merchant_profile": {
                          "business_model": intake.get("commerce", {}).get("business_model"),
                          "match_listed": intake.get("processing", {}).get("match_listed"),
                          "monthly_volume": intake.get("processing", {}).get("volume_monthly")
                      }
                  }, indent=2))
        
        z.writestr("analytics/current_success_rates.json", 
                  json.dumps({
                      "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
                      "disclaimer": "Based on recent merchant outcomes. Past performance does not guarantee future results.",
                      "provider_stats": runtime_stats
                  }, indent=2))
        
        # Implementation timeline and checklist
        z.writestr("timeline/implementation_plan.md", _generate_implementation_plan(final_order))
        
        # Master README
        z.writestr("README.md", _generate_readme(intake, final_order, include_prevention_guide))
    
    return buf.getvalue()

def _add_file_to_zip(zipf: zipfile.ZipFile, source_path: str, zip_path: str):
    """Safely add file to ZIP if it exists"""
    try:
        if os.path.exists(source_path):
            zipf.write(source_path, zip_path)
        else:
            # Add placeholder if file doesn't exist
            zipf.writestr(zip_path + ".PLACEHOLDER", 
                         f"File not found: {source_path}\nThis should be replaced with actual content.")
    except Exception as e:
        zipf.writestr(zip_path + ".ERROR", f"Error adding file: {str(e)}")

def _generate_implementation_plan(provider_order: List[str]) -> str:
    """Generate implementation timeline markdown"""
    return f"""# MATCH Liberation Implementation Plan

## Immediate Actions (Day 1)

1. **Set up USDC payment acceptance** (24-72h to cash flow)
   - Review `config/crypto_providers.yaml`
   - Choose provider: Coinbase Commerce (fastest) or Stripe Crypto (easiest)
   - Complete KYC and integration

2. **Submit first PSP application**
   - Start with: **{provider_order[0]}** (highest probability)
   - Use pre-filled data in `applications/{provider_order[0]}.json`
   - Expected timeframe: Check provider documentation

## Week 1

3. **Submit applications 2-3**
   - {provider_order[1] if len(provider_order) > 1 else 'N/A'}
   - {provider_order[2] if len(provider_order) > 2 else 'N/A'}

4. **Prepare rejection responses**
   - Review scripts in `scripts/rejection/`
   - Customize for your specific situation

## Week 2-4

5. **Follow up on applications**
   - Track responses in Telegram check-ins
   - Use emergency contacts if needed
   - Submit additional applications if rejections occur

## Month 2-3

6. **MATCH removal process** (if applicable)
   - Use templates in `scripts/match_removal/`
   - Begin formal removal procedures once approved
   - Document everything for future reference

## Success Metrics

- **Immediate**: USDC payments active within 72 hours
- **Week 2**: At least one PSP approval
- **Month 3**: MATCH removal initiated (if applicable)

Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
"""

def _generate_readme(intake: dict, provider_order: List[str], has_prevention_guide: bool) -> str:
    """Generate master README for the package"""
    business_model = intake.get("commerce", {}).get("business_model", "Unknown")
    is_match = intake.get("processing", {}).get("match_listed", False)
    
    return f"""# MATCH Liberation Package

Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Business Profile: {business_model.title()}{' (MATCH Listed)' if is_match else ''}

## What's Included

### 📚 Documentation
- **MATCH Survival Playbook (30 pages)**: Complete recovery strategy guide
{f"- **MATCH Prevention Guide (5 pages)**: Prevention strategies" if has_prevention_guide else ""}
- **Implementation Plan**: Step-by-step timeline

### 🏦 Pre-filled Applications
Your applications are pre-filled and ready to submit:
{chr(10).join([f"- {provider}.json (Priority {i+1})" for i, provider in enumerate(provider_order)])}

### 🚨 Emergency Resources
- Emergency contacts for urgent situations
- Rejection response templates
- MATCH removal letter templates

### 💰 USDC/Crypto Setup
- Provider comparison matrix
- Setup instructions for immediate cash flow

### 📊 Current Data
- Live provider success rates (updated from merchant outcomes)
- Recommended application order for your profile

## Quick Start

1. **TODAY**: Set up USDC payments (see `config/crypto_providers.yaml`)
2. **Day 1-2**: Submit first application using `applications/{provider_order[0]}.json`
3. **Week 1**: Submit applications 2-3 from the priority list
4. **Week 2**: Use Telegram check-ins to track progress and get support

## Support

- Weekly Telegram check-ins for progress tracking
- Emergency contact list in `contacts/emergency_contacts.yaml`
- Community support through MerchantGuard channels

## Important Disclaimers

This is a DIY (Do-It-Yourself) product. You submit all applications yourself using the provided templates and data. MerchantGuard provides tools, templates, and guidance—not application submission services.

Success rates are based on recent merchant outcomes and are provided for informational purposes only. Individual results may vary based on your specific business profile and market conditions.

---

**MerchantGuard™** | Built by merchants, for merchants
"""