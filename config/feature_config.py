# config/feature_config.py
import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FeatureConfig:
    """
    Centralized feature configuration loader for MerchantGuard
    Loads from features.yaml with environment overrides
    """
    
    def __init__(self, config_path: str = None, environment: str = None):
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self.config_path = config_path or self._get_default_config_path()
        self._config = None
        self._load_config()
    
    def _get_default_config_path(self) -> str:
        """Get default config path"""
        current_dir = Path(__file__).parent
        return str(current_dir / 'features.yaml')
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            # Apply environment overrides
            self._apply_environment_overrides()
            
            logger.info(f"Loaded feature config v{self.version} for {self.environment}")
            
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            self._config = self._get_default_config()
    
    def _apply_environment_overrides(self):
        """Apply environment-specific overrides"""
        if 'environments' in self._config and self.environment in self._config['environments']:
            env_overrides = self._config['environments'][self.environment]
            self._deep_merge(self._config, env_overrides)
    
    def _deep_merge(self, base: Dict, overrides: Dict):
        """Deep merge override values into base config"""
        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _get_default_config(self) -> Dict:
        """Fallback default configuration"""
        return {
            "version": "4.0",
            "global": {
                "brand_name": "MerchantGuard",
                "website_url": "https://merchantguard.ai"
            },
            "pricing": {
                "kits": {"unified_price": 499},
                "addons": {"reviewed_passport": 199, "application_pack": 99}
            },
            "passport": {"validity_days": 180},
            "experiments": {},
            "security": {"rate_limits": {}}
        }
    
    @property
    def version(self) -> str:
        """Get config version"""
        return self._config.get('version', '4.0')
    
    @property 
    def brand_name(self) -> str:
        """Get brand name"""
        return self._config.get('global', {}).get('brand_name', 'MerchantGuard')
    
    @property
    def formal_name(self) -> str:
        """Get formal product name"""
        return self._config.get('global', {}).get('formal_name', 'GuardScore™ Compliance Passport')
    
    @property
    def shorthand(self) -> str:
        """Get shorthand product name"""
        return self._config.get('global', {}).get('shorthand', 'Compliance Passport')
    
    # Pricing configuration
    def get_kit_price(self, kit_type: str = None) -> int:
        """Get kit price (unified pricing)"""
        return self._config.get('pricing', {}).get('kits', {}).get('unified_price', 499)
    
    def get_addon_price(self, addon_type: str) -> int:
        """Get add-on price"""
        addons = self._config.get('pricing', {}).get('addons', {})
        return addons.get(addon_type, 0)
    
    def get_renewal_price(self) -> int:
        """Get renewal price"""
        return self._config.get('pricing', {}).get('renewals', {}).get('passport_renewal', 99)
    
    # Passport configuration
    def get_passport_validity_days(self) -> int:
        """Get passport validity period"""
        return self._config.get('passport', {}).get('validity_days', 180)
    
    def get_passport_tier_config(self, tier: str) -> Dict:
        """Get configuration for passport tier"""
        tiers = self._config.get('passport', {}).get('tiers', {})
        return tiers.get(tier, {})
    
    # Guide configuration
    def get_guide_config(self, guide_slug: str) -> Dict:
        """Get configuration for a specific guide"""
        guides = self._config.get('guides', {})
        return guides.get(guide_slug, {})
    
    def get_all_guides(self) -> Dict:
        """Get all guide configurations"""
        return self._config.get('guides', {})
    
    # Kit configuration  
    def get_kit_config(self, kit_slug: str) -> Dict:
        """Get configuration for a specific kit"""
        kits = self._config.get('kits', {})
        return kits.get(kit_slug, {})
    
    def get_all_kits(self) -> Dict:
        """Get all kit configurations"""
        return self._config.get('kits', {})
    
    def get_kit_addons(self, kit_slug: str) -> list:
        """Get available add-ons for a kit"""
        kit_config = self.get_kit_config(kit_slug)
        return kit_config.get('addons_available', [])
    
    # Data-Verified configuration
    def is_data_verified_enabled(self) -> bool:
        """Check if Data-Verified feature is enabled"""
        return self._config.get('data_verified', {}).get('enabled', True)
    
    def get_platform_config(self, platform: str) -> Dict:
        """Get configuration for e-commerce platform"""
        platforms = self._config.get('data_verified', {}).get('platforms', {})
        return platforms.get(platform, {})
    
    def get_data_verified_scoring(self) -> Dict:
        """Get Data-Verified scoring configuration"""
        return self._config.get('data_verified', {}).get('scoring', {})
    
    # Experiment/Feature flag methods
    def is_experiment_enabled(self, experiment_name: str) -> bool:
        """Check if experiment is enabled"""
        experiments = self._config.get('experiments', {})
        return experiments.get(experiment_name, False)
    
    def get_experiment_variant(self, experiment_name: str) -> str:
        """Get experiment variant"""
        experiments = self._config.get('experiments', {})
        return experiments.get(experiment_name, 'control')
    
    # Messaging configuration
    def get_message(self, message_type: str, variant: str = None) -> str:
        """Get configured message text"""
        messaging = self._config.get('messaging', {})
        
        if variant:
            return messaging.get(message_type, {}).get(variant, '')
        
        # Handle different message structures
        message_config = messaging.get(message_type)
        if isinstance(message_config, str):
            return message_config
        elif isinstance(message_config, dict):
            return message_config.get('default', '')
        
        return ''
    
    def get_cta_text(self, persona: str) -> str:
        """Get CTA text for specific persona"""
        ctas = self._config.get('messaging', {}).get('cta', {})
        return ctas.get(persona, 'Get Started →')
    
    def get_upsell_message(self, upsell_type: str) -> str:
        """Get upsell message"""
        upsells = self._config.get('messaging', {}).get('upsells', {})
        return upsells.get(upsell_type, '')
    
    # Analytics configuration
    def is_analytics_enabled(self) -> bool:
        """Check if analytics is enabled"""
        return self._config.get('analytics', {}).get('enabled', True)
    
    def get_analytics_backend(self) -> str:
        """Get analytics backend"""
        return self._config.get('analytics', {}).get('backend', 'mixpanel')
    
    def should_track_event(self, event_name: str) -> bool:
        """Check if event should be tracked"""
        core_events = self._config.get('analytics', {}).get('core_events', [])
        return event_name in core_events
    
    def get_conversion_funnel(self, funnel_name: str) -> list:
        """Get conversion funnel steps"""
        funnels = self._config.get('analytics', {}).get('conversion_funnels', {})
        return funnels.get(funnel_name, [])
    
    # Security configuration
    def get_rate_limit(self, limit_type: str) -> int:
        """Get rate limit value"""
        limits = self._config.get('security', {}).get('rate_limits', {})
        return limits.get(limit_type, 100)  # Default limit
    
    def get_max_file_size_mb(self) -> int:
        """Get max file upload size"""
        upload = self._config.get('security', {}).get('file_upload', {})
        return upload.get('max_file_size_mb', 50)
    
    def get_allowed_extensions(self) -> list:
        """Get allowed file extensions"""
        upload = self._config.get('security', {}).get('file_upload', {})
        return upload.get('allowed_extensions', ['.csv'])
    
    # PSP pilot configuration
    def is_psp_pilots_enabled(self) -> bool:
        """Check if PSP pilot features are enabled"""
        return self._config.get('psp_pilots', {}).get('enabled', True)
    
    def get_pilot_types(self) -> list:
        """Get available pilot types"""
        return self._config.get('psp_pilots', {}).get('pilot_types', [])
    
    def get_vamp_threshold(self) -> float:
        """Get VAMP early warning threshold"""
        vamp = self._config.get('psp_pilots', {}).get('vamp_prevention', {})
        return vamp.get('early_warning_threshold', 0.65)
    
    # Localization
    def get_supported_languages(self) -> list:
        """Get supported language codes"""
        return self._config.get('localization', {}).get('supported_languages', ['en'])
    
    def get_default_language(self) -> str:
        """Get default language"""
        return self._config.get('localization', {}).get('default_language', 'en')
    
    def get_disclaimer_translation(self, language: str) -> str:
        """Get disclaimer in specific language"""
        translations = self._config.get('localization', {}).get('disclaimer_translations', {})
        return translations.get(language, translations.get('en', ''))
    
    # Utility methods
    def get_raw_config(self) -> Dict:
        """Get raw configuration dict (for debugging)"""
        return self._config.copy()
    
    def reload_config(self):
        """Reload configuration from file"""
        self._load_config()
    
    def validate_config(self) -> list:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check required sections
        required_sections = ['global', 'pricing', 'passport', 'kits', 'guides']
        for section in required_sections:
            if section not in self._config:
                issues.append(f"Missing required section: {section}")
        
        # Check kit pricing consistency
        if 'pricing' in self._config and 'kits' in self._config:
            unified_price = self._config['pricing']['kits']['unified_price']
            for kit_name, kit_config in self._config['kits'].items():
                kit_price = kit_config.get('price', 0)
                if kit_price != unified_price:
                    issues.append(f"Kit {kit_name} price {kit_price} doesn't match unified price {unified_price}")
        
        # Check guide-kit upsell mappings
        if 'guides' in self._config and 'kits' in self._config:
            kit_slugs = set(self._config['kits'].keys())
            for guide_name, guide_config in self._config['guides'].items():
                upsell_kit = guide_config.get('upsell_kit')
                if upsell_kit and upsell_kit not in kit_slugs:
                    issues.append(f"Guide {guide_name} upsells to non-existent kit: {upsell_kit}")
        
        return issues

# Global configuration instance
_config_instance = None

def get_config(environment: str = None) -> FeatureConfig:
    """Get global configuration instance"""
    global _config_instance
    
    if _config_instance is None:
        _config_instance = FeatureConfig(environment=environment)
    
    return _config_instance

def reload_config():
    """Reload global configuration"""
    global _config_instance
    if _config_instance:
        _config_instance.reload_config()

# Usage examples:
"""
from config.feature_config import get_config

# Get configuration instance
config = get_config()

# Check pricing
kit_price = config.get_kit_price()  # 499
reviewed_price = config.get_addon_price('reviewed_passport')  # 199

# Check experiments
if config.is_experiment_enabled('data_verified_upgrade'):
    # Show Data-Verified upsell
    pass

# Get messaging
cta_text = config.get_cta_text('builders')  # "Issue my Compliance Passport"
upsell_msg = config.get_upsell_message('data_verified')

# Check security limits
rate_limit = config.get_rate_limit('passport_generation_per_user_per_day')  # 3
max_file_size = config.get_max_file_size_mb()  # 50

# Kit configuration
kit_config = config.get_kit_config('builders_standard')
available_addons = config.get_kit_addons('builders_standard')

# Validate configuration
issues = config.validate_config()
if issues:
    print("Configuration issues:", issues)
"""