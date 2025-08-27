# utils/guardscore_engine.py
from __future__ import annotations

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os

logger = logging.getLogger(__name__)

class GuardScoreEngine:
    """
    Market-aware GuardScore calculation with confidence weighting
    Implements: score = profile × data_factor × market_multiplier
    """
    
    def __init__(self):
        self.markets_config_path = Path("config/markets.yaml")
        self._markets_config = None
        self._load_markets_config()
    
    def _load_markets_config(self):
        """Load market configuration"""
        try:
            with open(self.markets_config_path, 'r', encoding='utf-8') as f:
                self._markets_config = yaml.safe_load(f)
            logger.info(f"Loaded markets config v{self._markets_config['version']}")
        except Exception as e:
            logger.error(f"Failed to load markets config: {e}")
            raise
    
    def calculate_market_score(
        self, 
        market: str, 
        feature_data: Dict[str, Any], 
        confidence_data: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """Calculate GuardScore for specific market"""
        
        if market not in self._markets_config['markets']:
            logger.warning(f"Unknown market: {market}")
            market = 'OTHER'
        
        market_config = self._markets_config['markets'][market]
        
        # 1. Calculate base profile score
        profile_score = self._calculate_profile_score(feature_data, market)
        
        # 2. Apply data confidence factor
        confidence_factor = self._calculate_confidence_factor(
            feature_data, confidence_data or {}, market
        )
        
        # 3. Apply market-specific multipliers
        market_multiplier = self._calculate_market_multipliers(
            feature_data, market_config
        )
        
        # 4. Final market score
        raw_score = profile_score * confidence_factor * market_multiplier
        market_score = max(10, min(100, int(raw_score)))
        
        # 5. Determine visa status
        visa_status = self._determine_visa_status(market_score, market_config)
        
        # 6. Generate alerts if needed
        alerts = self._check_market_alerts(feature_data, market_config)
        
        return {
            'market': market,
            'score': market_score,
            'components': {
                'profile_score': profile_score,
                'confidence_factor': confidence_factor,
                'market_multiplier': market_multiplier
            },
            'visa_status': visa_status,
            'alerts': alerts,
            'thresholds': market_config['thresholds'],
            'program': market_config['program']
        }
    
    def calculate_overall_guardscore(
        self, 
        feature_data: Dict[str, Any], 
        market_shares: Dict[str, float] = None,
        confidence_data: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """Calculate overall GuardScore across all markets"""
        
        selected_markets = feature_data.get('markets_served.selected', ['OTHER'])
        market_shares = market_shares or self._default_market_shares(selected_markets)
        
        # Calculate per-market scores
        market_scores = {}
        total_weighted_score = 0
        
        for market in selected_markets:
            market_result = self.calculate_market_score(market, feature_data, confidence_data)
            market_scores[market] = market_result
            
            # Weight by GMV share
            weight = market_shares.get(market, 1.0 / len(selected_markets))
            total_weighted_score += market_result['score'] * weight
        
        overall_score = int(total_weighted_score)
        
        # Aggregate alerts
        all_alerts = []
        for market_result in market_scores.values():
            all_alerts.extend(market_result['alerts'])
        
        # Determine overall risk level
        risk_level = self._get_risk_level(overall_score)
        
        # Calculate confidence score
        overall_confidence = self._calculate_overall_confidence(confidence_data or {})
        
        return {
            'overall_score': overall_score,
            'risk_level': risk_level,
            'confidence_score': overall_confidence,
            'market_scores': market_scores,
            'market_shares': market_shares,
            'alerts': all_alerts,
            'calculation_timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_profile_score(self, feature_data: Dict[str, Any], market: str) -> float:
        """Calculate base profile score"""
        score = 50.0  # Base score
        
        # Market diversity bonus
        markets = feature_data.get('markets_served.selected', [])
        if len(markets) > 1:
            score += min(len(markets) * 5, 15)
        
        # Industry risk adjustment
        industry = feature_data.get('profile.industry')
        industry_adjustments = {
            'SAAS': +12,
            'ECOM': +8,
            'CRYPTO': -8,
            'CBD': -12,
            'OTHER': 0
        }
        score += industry_adjustments.get(industry, 0)
        
        # Business stage
        stage = feature_data.get('profile.stage')
        stage_adjustments = {
            'MATURE': +15,
            'GROWTH': +10,
            'EARLY': +5
        }
        score += stage_adjustments.get(stage, 0)
        
        # Market-specific factors
        if market == 'US_CARDS':
            score += self._vamp_profile_adjustments(feature_data)
        elif market == 'BR_PIX':
            score += self._pix_profile_adjustments(feature_data)
        elif market == 'EU_CARDS_SCA':
            score += self._sca_profile_adjustments(feature_data)
        
        # Operational factors
        if feature_data.get('risk.prior_suspensions') == 'YES':
            score -= 15
        
        # Policy coverage
        policies = feature_data.get('ops.policies', [])
        if len(policies) >= 3:  # Good policy coverage
            score += 8
        
        return max(20, min(80, score))
    
    def _vamp_profile_adjustments(self, feature_data: Dict[str, Any]) -> float:
        """VAMP-specific profile adjustments"""
        adjustment = 0
        
        # Dispute rate (if provided)
        if 'vamp.monthly_dispute_rate' in feature_data:
            dispute_rate = float(feature_data.get('vamp.monthly_dispute_rate', 0))
            if dispute_rate < 0.005:
                adjustment += 15
            elif dispute_rate < 0.0065:
                adjustment += 8
            elif dispute_rate > 0.01:
                adjustment -= 20
        
        # Chargeback rate
        if 'vamp.chargeback_rate' in feature_data:
            cb_rate = float(feature_data.get('vamp.chargeback_rate', 0))
            if cb_rate < 0.005:
                adjustment += 12
            elif cb_rate < 0.0065:
                adjustment += 5
            elif cb_rate > 0.01:
                adjustment -= 25
        
        # SOP documentation
        sop_level = feature_data.get('ops.dispute_sop_level')
        sop_adjustments = {
            'Comprehensive': +15,
            'Strong': +10,
            'Basic': +3,
            'None': -8
        }
        adjustment += sop_adjustments.get(sop_level, 0)
        
        # Compliance experience
        experience = feature_data.get('profile.compliance_experience')
        exp_adjustments = {
            'Expert': +8,
            'Intermediate': +3,
            'First-time': -2
        }
        adjustment += exp_adjustments.get(experience, 0)
        
        return adjustment
    
    def _pix_profile_adjustments(self, feature_data: Dict[str, Any]) -> float:
        """PIX-specific profile adjustments"""
        adjustment = 0
        
        # PIX dispute rate
        if 'pix.dispute_rate' in feature_data:
            pix_rate = float(feature_data.get('pix.dispute_rate', 0))
            if pix_rate < 0.003:
                adjustment += 12
            elif pix_rate < 0.0045:
                adjustment += 6
            elif pix_rate > 0.006:
                adjustment -= 18
        
        # PIX MED SOP
        if feature_data.get('pix.sop_present'):
            adjustment += 10
        else:
            adjustment -= 8
        
        return adjustment
    
    def _sca_profile_adjustments(self, feature_data: Dict[str, Any]) -> float:
        """SCA-specific profile adjustments"""
        adjustment = 0
        
        # SCA strategies
        sca_strategies = feature_data.get('eu.sca_strategy', [])
        if 'EXEMPTIONS' in sca_strategies:
            adjustment += 8
        if 'FRICTIONLESS' in sca_strategies:
            adjustment += 6
        if len(sca_strategies) >= 2:
            adjustment += 5  # Multi-strategy bonus
        
        # Auth rate estimate
        if 'eu.auth_rate_estimate' in feature_data:
            auth_rate = float(feature_data.get('eu.auth_rate_estimate', 0))
            if auth_rate >= 0.93:
                adjustment += 12
            elif auth_rate >= 0.90:
                adjustment += 6
            elif auth_rate < 0.85:
                adjustment -= 15
        
        return adjustment
    
    def _calculate_confidence_factor(
        self, 
        feature_data: Dict[str, Any], 
        confidence_data: Dict[str, float], 
        market: str
    ) -> float:
        """Calculate confidence-based score factor"""
        base_confidence = self._markets_config['confidence']['sources']['self_attested']
        
        # Data source confidence boosts
        sources_config = self._markets_config['confidence']['sources']
        boosters_config = self._markets_config['confidence']['boosters']
        penalties_config = self._markets_config['confidence']['penalties']
        
        total_confidence = base_confidence
        
        # CSV upload boost
        platform = feature_data.get('platform.primary')
        if platform == 'Shopify' and confidence_data.get('csv_uploaded'):
            total_confidence += sources_config['csv_shopify'] - base_confidence
        elif platform == 'WooCommerce' and confidence_data.get('csv_uploaded'):
            total_confidence += sources_config['csv_woocommerce'] - base_confidence
        
        # Process boosters
        if feature_data.get('ops.dispute_sop_level') == 'Comprehensive':
            total_confidence += boosters_config['comprehensive_sop']
        
        if confidence_data.get('data_recency_days', 90) <= 30:
            total_confidence += boosters_config['data_recency_30d']
        
        # Apply penalties
        if confidence_data.get('data_recency_days', 30) >= 90:
            total_confidence += penalties_config['stale_data_90d']
        
        # Convert confidence to score factor (0.5 to 1.3)
        return 0.5 + (total_confidence * 0.8)
    
    def _calculate_market_multipliers(
        self, 
        feature_data: Dict[str, Any], 
        market_config: Dict[str, Any]
    ) -> float:
        """Calculate market-specific multipliers"""
        multipliers = market_config.get('multipliers', {})
        
        total_multiplier = multipliers.get('profile_weight', 1.0)
        
        # Data verification boost
        if feature_data.get('data_verified'):
            total_multiplier *= multipliers.get('data_verified_boost', 1.0)
        
        # SOP boost
        if feature_data.get('ops.dispute_sop_level') == 'Comprehensive':
            boost_key = 'comprehensive_sop_boost'
            if boost_key in multipliers:
                total_multiplier *= multipliers[boost_key]
        
        # Prior suspension penalty
        if feature_data.get('risk.prior_suspensions') == 'YES':
            penalty_key = 'prior_suspension_penalty'
            if penalty_key in multipliers:
                total_multiplier *= multipliers[penalty_key]
        
        return total_multiplier
    
    def _determine_visa_status(self, score: int, market_config: Dict[str, Any]) -> Dict[str, Any]:
        """Determine visa status for market"""
        requirements = market_config.get('visa_requirements', {})
        stamps_config = self._markets_config['visa_stamps']
        
        if score >= requirements.get('ready', 80):
            status = 'ready'
        elif score >= requirements.get('pending', 50):
            status = 'pending'
        else:
            status = 'blocked'
        
        stamp_config = stamps_config[status]
        
        return {
            'status': status,
            'badge': stamp_config['badge'],
            'color': stamp_config['color'],
            'description': stamp_config['description'],
            'score_threshold': requirements.get(status, 0),
            'valid_until': (datetime.utcnow() + timedelta(days=stamp_config['validity_days'])).isoformat()
        }
    
    def _check_market_alerts(
        self, 
        feature_data: Dict[str, Any], 
        market_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for market-specific alerts"""
        alerts = []
        alerts_config = market_config.get('alerts', {})
        
        for alert_id, alert_config in alerts_config.items():
            threshold = alert_config['threshold']
            
            # Check different alert types
            if 'dispute' in alert_id:
                current_rate = float(feature_data.get('vamp.monthly_dispute_rate', 0))
                if current_rate >= threshold:
                    alerts.append({
                        'id': alert_id,
                        'level': 'warning' if 'warn' in alert_id else 'critical',
                        'message': alert_config['message'],
                        'action': alert_config['action'],
                        'current_value': current_rate,
                        'threshold': threshold,
                        'triggered_at': datetime.utcnow().isoformat()
                    })
            
            # Add more alert types as needed
        
        return alerts
    
    def _default_market_shares(self, markets: List[str]) -> Dict[str, float]:
        """Default equal market shares"""
        if not markets:
            return {'OTHER': 1.0}
        
        share = 1.0 / len(markets)
        return {market: share for market in markets}
    
    def _get_risk_level(self, score: int) -> str:
        """Convert score to risk level"""
        if score >= 85:
            return "very_low"
        elif score >= 70:
            return "low"
        elif score >= 55:
            return "medium"
        elif score >= 35:
            return "high"
        else:
            return "very_high"
    
    def _calculate_overall_confidence(self, confidence_data: Dict[str, float]) -> float:
        """Calculate overall confidence score"""
        base_confidence = 0.30
        
        if confidence_data.get('csv_uploaded'):
            base_confidence += 0.25
        
        if confidence_data.get('comprehensive_sop'):
            base_confidence += 0.10
        
        return min(0.95, base_confidence)
    
    def generate_passport_data(
        self, 
        user_id: int, 
        feature_data: Dict[str, Any],
        market_shares: Dict[str, float] = None,
        confidence_data: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """Generate complete passport data with crypto signature"""
        
        # Calculate GuardScore
        score_result = self.calculate_overall_guardscore(
            feature_data, market_shares, confidence_data
        )
        
        # Generate passport ID
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        passport_id = f"MGP_{user_id}_{timestamp}"
        
        # Create passport data
        passport_data = {
            'passport_id': passport_id,
            'user_id': user_id,
            'guardscore': score_result['overall_score'],
            'risk_level': score_result['risk_level'],
            'confidence_score': score_result['confidence_score'],
            'tier': 'data_verified' if confidence_data.get('csv_uploaded') else 'self_attested',
            'markets_served': list(score_result['market_scores'].keys()),
            'market_visas': {
                market: result['visa_status'] 
                for market, result in score_result['market_scores'].items()
            },
            'alerts': score_result['alerts'],
            'issued_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=180)).isoformat(),
            'version': '4.0'
        }
        
        # Add HMAC signature
        passport_data['signature'] = self._sign_passport(passport_data)
        passport_data['portal_url'] = f"https://merchantguard.ai/passport/{passport_id}"
        
        return passport_data
    
    def _sign_passport(self, passport_data: Dict[str, Any]) -> str:
        """Generate HMAC signature for passport"""
        # Use a secret key (in production, store securely)
        secret_key = os.getenv('PASSPORT_SIGNING_KEY', 'dev-signing-key-change-in-prod')
        
        # Create canonical string for signing
        canonical_data = {
            'passport_id': passport_data['passport_id'],
            'user_id': passport_data['user_id'],
            'guardscore': passport_data['guardscore'],
            'tier': passport_data['tier'],
            'issued_at': passport_data['issued_at'],
            'expires_at': passport_data['expires_at']
        }
        
        canonical_string = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            secret_key.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def verify_passport_signature(self, passport_data: Dict[str, Any]) -> bool:
        """Verify passport HMAC signature"""
        stored_signature = passport_data.get('signature')
        if not stored_signature:
            return False
        
        # Remove signature for verification
        passport_copy = passport_data.copy()
        del passport_copy['signature']
        
        expected_signature = self._sign_passport(passport_copy)
        return hmac.compare_digest(stored_signature, expected_signature)

# Global instance
guardscore_engine = GuardScoreEngine()