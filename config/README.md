# Configuration Files - Usage Guide

## Overview
These JSON configuration files power the entire VAMP compliance system, making updates instant without code changes.

## Files Structure

### `/config/thresholds.json`
**Complete VAMP compliance data:**
- Regional thresholds (US/EU/CEMEA/LAC/AP)
- PSP shadow thresholds (0.3%, 0.5%, 0.7%, 0.9%)
- Currency conversions ($8 USD → €7.3, R$44, etc.)
- 3-month rule logic
- Mastercard ECM comparison data

### `/config/exemptions.json`
**Country-specific exemptions:**
- Brazil/Chile/India domestic transaction exemptions
- Cross-border validation logic
- Currency detection rules
- Compliance audit trails

### `/config/providers.json`
**PSP-safe provider data:**
- Generic placeholder providers
- No active provider names (all set to `"active": false`)
- Contract trap warnings

## Usage Examples

### Calculator Integration
```javascript
// Load all configs
const [thresholds, exemptions] = await Promise.all([
  fetch('/config/thresholds.json').then(r => r.json()),
  fetch('/config/exemptions.json').then(r => r.json())
]);

// Check if country has domestic exemption
const isDomesticExempt = exemptions.country_exemptions.domestic_only
  .some(country => country.country_code === userCountry);

// Get regional threshold
const regionThreshold = thresholds.merchant_thresholds.regions[userRegion].current_threshold;

// Calculate PSP risk level
const pspRisk = getPSPRiskLevel(disputeRatio, thresholds.psp_internal_thresholds);
```

### Article Generation
```javascript
// Get penalty amounts in local currency
const penalties = thresholds.currency_conversions.approximate_rates;
const localPenalty = penalties[userCurrency]?.amount || thresholds.currency_conversions.usd_base;

// Generate country-specific content
if (exemptions.country_exemptions.domestic_only.find(c => c.country_code === 'BR')) {
  content += "Brazilian domestic transactions are exempt until local program announced.";
}
```

### Compliance Alerts
```javascript
// PSP termination warning
if (disputeRatio >= 0.9) {
  alert = "CRITICAL: You're at PSP termination level. Most processors cut merchants at 0.9%.";
} else if (disputeRatio >= 0.7) {
  alert = "WARNING: Reserves and rate increases likely at 0.7%+.";
}
```

## Benefits

1. **Instant Updates**: Change thresholds/penalties without touching code
2. **Multi-Currency**: Automatic currency conversions for global merchants  
3. **Regional Compliance**: Different rules for different regions/countries
4. **PSP Intelligence**: Real-world termination thresholds vs official VAMP limits
5. **Audit Trail**: Complete compliance documentation and source tracking

## Maintenance

- Update `last_updated` field when making changes
- Test calculator/articles after config updates
- Keep exemptions.json current with Visa announcements
- Monitor currency exchange rates quarterly

---

*This config-driven approach ensures the VAMP system stays accurate and compliant as regulations evolve.*