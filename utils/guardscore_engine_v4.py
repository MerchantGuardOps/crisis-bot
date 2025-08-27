# utils/guardscore_engine_v4.py
"""
GuardScore™ Engine v4.0 - Market-First Scoring with v4 Features
Enhanced with authoritative feature mapping and per-market models
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from utils.feature_registry_v4 import feature_registry_v4, map_golden_answers_to_features

logger = logging.getLogger(__name__)

@dataclass
class MarketVisa:
    """Per-market compliance visa"""
    market: str
    status: str  # "Ready", "Pending", "Blocked"
    score: int
    confidence: float
    alerts: List[str]
    recommendations: List[str]

@dataclass
class GuardScorePassport:
    """Complete compliance passport with market visas"""
    merchant_id: str
    overall_score: int
    confidence: float
    market_visas: Dict[str, MarketVisa]
    issued_at: datetime
    expires_at: datetime
    signature: str
    features_used: List[str]
    model_version: str = "v4.0"

class GuardScoreEngineV4:
    """
    Enhanced GuardScore engine using v4 feature mapping
    
    Key improvements:
    - Market-first routing (US_CARDS → VAMP, BR_PIX → PIX_MED, EU → SCA)
    - Confidence-weighted scoring using v4 ranges
    - Behavioral signal integration
    - Prescriptive recommendations mapped to features
    """
    
    def __init__(self, signing_key: str = "dev-key-v4"):
        self.signing_key = signing_key.encode()
        self.feature_registry = feature_registry_v4
        
        # v4 Market thresholds (from feature mapping)
        self.market_thresholds = {
            'US_CARDS': {
                'vamp_dispute_early_warning': 0.0065,  # 0.65%
                'vamp_dispute_breach': 0.01,  # 1%
                'chargeback_breach': 0.01,  # 1%
            },
            'BR_PIX': {
                'pix_dispute_watch': 0.0045,  # 0.45%
                'pix_med_breach': 0.006,  # 0.6%
            },
            'EU_CARDS_SCA': {
                'sca_auth_warning': 0.90,  # 90% auth rate
                'sca_auth_critical': 0.88,  # 88% auth rate
            }
        }
        
        # v4 Prescriptive mapping
        self.prescriptive_actions = {
            'vamp.cb_dispute_rate_m': {
                'condition': lambda x: x > 0.0065,
                'action': 'Implement comprehensive dispute SOP',
                'estimated_gain': '+10-15 pts',
                'kit_recommendation': 'builders_standard'
            },
            'ops.dispute_sop_level': {
                'condition': lambda x: x in ['NONE', 'BASIC'],
                'action': 'Upgrade dispute documentation and response procedures',
                'estimated_gain': '+15 pts',
                'kit_recommendation': 'builders_standard'
            },
            'pix.dispute_rate_m': {
                'condition': lambda x: x > 0.0045,
                'action': 'Strengthen PIX MED 2.0 compliance procedures',
                'estimated_gain': '+8-12 pts',
                'kit_recommendation': 'global_founder'
            },
            'eu.auth_rate_m': {
                'condition': lambda x: x < 0.92,
                'action': 'Optimize SCA exemption strategy and 3-DS flow',
                'estimated_gain': '+10-15 pts',
                'kit_recommendation': 'global_founder'
            }
        }
    
    def calculate_guardscore_v4(self, 
                               answers: Dict[str, Any], 
                               has_csv: bool = False,
                               session_data: Dict = None) -> GuardScorePassport:
        """
        Calculate GuardScore using v4 feature mapping
        
        Args:
            answers: Raw answers from Golden Question Bank
            has_csv: Whether user uploaded CSV (confidence boost)
            session_data: Behavioral signals
            
        Returns:
            Complete GuardScore passport with market visas
        """
        
        # Map answers to features using v4 registry
        feature_result = map_golden_answers_to_features(answers, has_csv, session_data)
        features = feature_result['features']
        confidence_scores = feature_result['confidence']
        avg_confidence = feature_result['avg_confidence']
        
        # Determine active markets from MKT_1
        active_markets = features.get('markets_served.list', ['US_CARDS'])
        if not isinstance(active_markets, list):
            active_markets = [active_markets]
        
        # Market share weights from MKT_2
        market_shares = features.get('markets_served.shares', {})
        
        # Calculate per-market scores
        market_visas = {}
        weighted_scores = []
        
        for market in active_markets:
            market_score = self._calculate_market_score_v4(market, features, confidence_scores)
            market_visa = self._create_market_visa(market, market_score, features, confidence_scores)
            market_visas[market] = market_visa
            
            # Weight by market share
            weight = market_shares.get(market, 1.0 / len(active_markets))
            weighted_scores.append((market_score['score'], weight))
        
        # Calculate overall weighted score
        if weighted_scores:
            overall_score = sum(score * weight for score, weight in weighted_scores)
            overall_score = max(10, min(100, int(overall_score)))
        else:
            overall_score = 50  # Default
        
        # Create passport
        passport = GuardScorePassport(
            merchant_id=session_data.get('merchant_id', 'unknown') if session_data else 'unknown',
            overall_score=overall_score,
            confidence=avg_confidence,
            market_visas=market_visas,
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=180),  # 6 months
            signature='',  # Will be set below
            features_used=list(features.keys()),
            model_version="v4.0"
        )
        
        # Sign the passport
        passport.signature = self._sign_passport(passport)
        
        return passport
    
    def _calculate_market_score_v4(self, market: str, features: Dict[str, Any], 
                                  confidence_scores: Dict[str, float]) -> Dict[str, Any]:
        """Calculate score for specific market using v4 features"""
        
        # Get market-specific features
        market_features = self.feature_registry.get_market_features(market)
        
        # Base profile score
        profile_score = self._calculate_profile_score_v4(features, market)
        
        # Market-specific risk factors
        risk_score = self._calculate_risk_score_v4(market, features)
        
        # Confidence factor
        relevant_confidences = [confidence_scores.get(f, 0.3) for f in market_features if f in confidence_scores]
        avg_confidence = sum(relevant_confidences) / len(relevant_confidences) if relevant_confidences else 0.3
        confidence_factor = 0.7 + (avg_confidence - 0.3) * 0.5  # Scale 0.3-0.95 → 0.7-1.0
        
        # Combine scores
        raw_score = (profile_score * 0.4 + risk_score * 0.6) * confidence_factor
        final_score = max(10, min(100, int(raw_score)))
        
        return {
            'score': final_score,
            'profile_score': profile_score,
            'risk_score': risk_score,
            'confidence_factor': confidence_factor,
            'avg_confidence': avg_confidence
        }
    
    def _calculate_profile_score_v4(self, features: Dict[str, Any], market: str) -> float:
        """Calculate profile score using v4 business profile features"""
        
        score = 50.0  # Base score
        
        # Industry adjustments (BP_1)
        industry = features.get('profile.industry')
        if industry == 'ECOM':
            score += 5
        elif industry in ['CBD', 'CRYPTO']:
            score -= 10
        elif industry == 'GAMING':
            score -= 5
        
        # Business stage (BP_2)
        stage = features.get('profile.stage')
        if stage == 'MATURE':
            score += 8
        elif stage == 'GROWTH':
            score += 3
        elif stage == 'EARLY':
            score -= 5
        
        # Entity status (BP_3)
        entity = features.get('profile.entity_status')
        if entity in ['LLC', 'CORP']:
            score += 5
        
        # Platform bonus (BP_5)
        platform = features.get('profile.platform')
        if platform in ['Shopify', 'WooCommerce']:
            score += 3
        
        # Policies complete (BP_6)
        if features.get('ops.policies_complete'):
            score += 8
        
        # Refund SLA (BP_7)
        refund_sla = features.get('ops.refund_sla_days')
        if refund_sla and refund_sla <= 7:
            score += 5
        
        # Multi-PSP intent (BP_8)
        if features.get('ops.multi_psp_intent'):
            score += 3
        
        # Prior suspensions penalty (BP_9)
        if features.get('ops.prior_suspensions'):
            score -= 15
        
        # 3DS plan (BP_10) - market-specific
        if market in ['US_CARDS', 'EU_CARDS_SCA'] and features.get('ops.step_up_3ds_plan'):
            score += 8
        
        # AML/KYC documentation (BP_11)
        aml_level = features.get('ops.aml_kyc_documentation')
        if aml_level == 'COMPLETE':
            score += 10
        elif aml_level == 'PARTIAL':
            score += 3
        
        return max(10, min(90, score))
    
    def _calculate_risk_score_v4(self, market: str, features: Dict[str, Any]) -> float:
        """Calculate market-specific risk score using v4 features"""
        
        score = 50.0  # Base risk score
        
        if market == 'US_CARDS':
            # VAMP-specific scoring
            dispute_rate = features.get('vamp.cb_dispute_rate_m', 0)
            cb_rate = features.get('vamp.cb_rate_m', 0)
            
            # Dispute rate impact
            if dispute_rate > 0.01:  # Above 1% VAMP threshold
                score -= 30
            elif dispute_rate > 0.0065:  # Early warning
                score -= 15
            elif dispute_rate < 0.003:  # Very good
                score += 10
            
            # Chargeback rate impact
            if cb_rate > 0.01:
                score -= 25
            elif cb_rate > 0.0065:
                score -= 10
            elif cb_rate < 0.005:
                score += 8
            
            # SOP level (VAMP_3)
            sop_level = features.get('ops.dispute_sop_level')
            if sop_level == 'COMPREHENSIVE':
                score += 15
            elif sop_level == 'STRONG':
                score += 10
            elif sop_level == 'BASIC':
                score += 3
            elif sop_level == 'NONE':
                score -= 10
            
            # Compliance experience (VAMP_4)
            experience = features.get('ops.compliance_experience')
            if experience == 'EXPERT':
                score += 8
            elif experience == 'INTERMEDIATE':
                score += 3
            elif experience == 'FIRST_TIME':
                score -= 5
        
        elif market == 'BR_PIX':
            # PIX-specific scoring
            pix_dispute_rate = features.get('pix.dispute_rate_m', 0)
            
            if pix_dispute_rate > 0.006:  # MED threshold
                score -= 35
            elif pix_dispute_rate > 0.0045:  # Watch threshold
                score -= 15
            elif pix_dispute_rate < 0.002:
                score += 12
            
            # PIX MED SOP (PIX_3)
            if features.get('pix.med_sop_present'):
                score += 15
            else:
                score -= 10
        
        elif market == 'EU_CARDS_SCA':
            # SCA-specific scoring
            auth_rate = features.get('eu.auth_rate_m', 0.85)
            
            if auth_rate < 0.88:  # Critical
                score -= 30
            elif auth_rate < 0.92:  # Warning
                score -= 15
            elif auth_rate > 0.95:  # Excellent
                score += 15
            
            # SCA strategy (EU_1)
            sca_strategy = features.get('eu.sca_strategy')
            if sca_strategy == 'EXEMPTIONS_PLAN':
                score += 20
            elif sca_strategy == 'STEP_UP':
                score += 10
            elif sca_strategy == 'BASIC':
                score += 3
            elif sca_strategy == 'NONE':
                score -= 15
        
        return max(10, min(90, score))
    
    def _create_market_visa(self, market: str, score_data: Dict[str, Any], 
                           features: Dict[str, Any], confidence_scores: Dict[str, float]) -> MarketVisa:
        """Create market-specific visa with alerts and recommendations"""
        
        score = score_data['score']
        confidence = score_data['avg_confidence']
        
        # Determine status
        if score >= 70 and confidence >= 0.6:
            status = "Ready ✅"
        elif score >= 50:
            status = "Pending ⚠️"
        else:
            status = "Blocked ❌"
        
        # Generate alerts
        alerts = self._generate_market_alerts(market, features)
        
        # Generate recommendations
        recommendations = self._generate_market_recommendations(market, features)
        
        return MarketVisa(
            market=market,
            status=status,
            score=score,
            confidence=confidence,
            alerts=alerts,
            recommendations=recommendations
        )
    
    def _generate_market_alerts(self, market: str, features: Dict[str, Any]) -> List[str]:
        """Generate market-specific alerts based on v4 thresholds"""
        
        alerts = []
        thresholds = self.market_thresholds.get(market, {})
        
        if market == 'US_CARDS':
            dispute_rate = features.get('vamp.cb_dispute_rate_m', 0)
            if dispute_rate >= thresholds.get('vamp_dispute_breach', 0.01):
                alerts.append("🚨 VAMP BREACH RISK: Dispute rate above 1% threshold")
            elif dispute_rate >= thresholds.get('vamp_dispute_early_warning', 0.0065):
                alerts.append("⚠️ VAMP Early Warning: Approaching dispute threshold")
        
        elif market == 'BR_PIX':
            pix_rate = features.get('pix.dispute_rate_m', 0)
            if pix_rate >= thresholds.get('pix_med_breach', 0.006):
                alerts.append("🚨 PIX MED BREACH: Dispute rate above 0.6% threshold")
            elif pix_rate >= thresholds.get('pix_dispute_watch', 0.0045):
                alerts.append("⚠️ PIX Watch: Monitor dispute trend closely")
        
        elif market == 'EU_CARDS_SCA':
            auth_rate = features.get('eu.auth_rate_m', 0.85)
            if auth_rate <= thresholds.get('sca_auth_critical', 0.88):
                alerts.append("🚨 SCA Critical: Authorization rate below 88%")
            elif auth_rate <= thresholds.get('sca_auth_warning', 0.90):
                alerts.append("⚠️ SCA Warning: Authorization rate declining")
        
        return alerts
    
    def _generate_market_recommendations(self, market: str, features: Dict[str, Any]) -> List[str]:
        """Generate market-specific recommendations using v4 prescriptive mapping"""
        
        recommendations = []
        
        # Check each prescriptive feature
        for feature_name, action_config in self.prescriptive_actions.items():
            if feature_name in features:
                value = features[feature_name]
                if action_config['condition'](value):
                    rec = f"{action_config['action']} (Est. {action_config['estimated_gain']})"
                    recommendations.append(rec)
        
        # Market-specific recommendations
        if market == 'US_CARDS':
            if not features.get('ops.step_up_3ds_plan'):
                recommendations.append("Enable 3-DS step-up for high-risk transactions (+12-18 pts)")
        
        elif market == 'BR_PIX':
            if not features.get('pix.med_sop_present'):
                recommendations.append("Implement PIX MED 2.0 evidence documentation (+15 pts)")
        
        elif market == 'EU_CARDS_SCA':
            sca_strategy = features.get('eu.sca_strategy')
            if sca_strategy in ['NONE', 'BASIC']:
                recommendations.append("Develop comprehensive SCA exemption strategy (+20 pts)")
        
        return recommendations[:3]  # Limit to top 3
    
    def _sign_passport(self, passport: GuardScorePassport) -> str:
        """Create HMAC signature for passport integrity"""
        
        # Create signing payload
        payload = {
            'merchant_id': passport.merchant_id,
            'overall_score': passport.overall_score,
            'confidence': passport.confidence,
            'issued_at': passport.issued_at.isoformat(),
            'model_version': passport.model_version,
            'features_used': sorted(passport.features_used)
        }
        
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.signing_key,
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_passport(self, passport: GuardScorePassport) -> bool:
        """Verify passport signature integrity"""
        
        expected_signature = self._sign_passport(passport)
        return hmac.compare_digest(passport.signature, expected_signature)

# Global instance
guardscore_engine_v4 = GuardScoreEngineV4()

def calculate_guardscore_from_answers(answers: Dict[str, Any], 
                                    has_csv: bool = False,
                                    session_data: Dict = None) -> GuardScorePassport:
    """
    Convenience function for calculating GuardScore from Golden Question answers
    
    Usage:
        answers = {
            'VAMP_1': 0.008,
            'VAMP_2': 0.012, 
            'VAMP_3': 'COMPREHENSIVE',
            'MKT_1': ['US_CARDS']
        }
        passport = calculate_guardscore_from_answers(answers, has_csv=True)
    """
    return guardscore_engine_v4.calculate_guardscore_v4(answers, has_csv, session_data)