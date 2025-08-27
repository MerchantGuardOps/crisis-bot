# utils/alert_engine.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum

from utils.guardscore_engine import guardscore_engine
from analytics.question_analytics import analytics

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning" 
    CRITICAL = "critical"

class AlertEngine:
    """
    Market-aware alert engine for VAMP, PIX MED, and SCA early warnings
    """
    
    def __init__(self):
        self.markets_config = guardscore_engine._markets_config
        self.alert_history = {}  # In production, use Redis/database
    
    async def check_user_alerts(
        self, 
        user_id: int, 
        feature_data: Dict[str, Any],
        confidence_data: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """Check all alerts for user across markets"""
        
        all_alerts = []
        markets = feature_data.get('markets_served.selected', ['OTHER'])
        
        for market in markets:
            market_alerts = await self._check_market_alerts(
                user_id, market, feature_data, confidence_data
            )
            all_alerts.extend(market_alerts)
        
        # Check for portfolio-level alerts
        portfolio_alerts = await self._check_portfolio_alerts(
            user_id, feature_data, confidence_data
        )
        all_alerts.extend(portfolio_alerts)
        
        return all_alerts
    
    async def _check_market_alerts(
        self,
        user_id: int,
        market: str, 
        feature_data: Dict[str, Any],
        confidence_data: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """Check market-specific alerts"""
        
        alerts = []
        
        if market == 'US_CARDS':
            alerts.extend(await self._check_vamp_alerts(user_id, feature_data))
        elif market == 'BR_PIX':
            alerts.extend(await self._check_pix_alerts(user_id, feature_data))
        elif market == 'EU_CARDS_SCA':
            alerts.extend(await self._check_sca_alerts(user_id, feature_data))
        
        return alerts
    
    async def _check_vamp_alerts(
        self, 
        user_id: int, 
        feature_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check VAMP-specific alerts for US Cards"""
        
        alerts = []
        market_config = self.markets_config['markets']['US_CARDS']
        thresholds = market_config['thresholds']
        alert_configs = market_config['alerts']
        
        # Check dispute rate
        dispute_rate = float(feature_data.get('vamp.monthly_dispute_rate', 0))
        
        # VAMP Early Warning
        if dispute_rate >= alert_configs['vamp_early_warn']['threshold']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='vamp_early_warn',
                level=AlertLevel.WARNING,
                market='US_CARDS',
                message=alert_configs['vamp_early_warn']['message'],
                action=alert_configs['vamp_early_warn']['action'],
                current_value=dispute_rate,
                threshold=alert_configs['vamp_early_warn']['threshold'],
                details={
                    'metric': 'Monthly Dispute Rate',
                    'trend': 'increasing',  # Would calculate from historical data
                    'days_to_threshold': self._estimate_days_to_breach(dispute_rate, 0.01),
                    'recommended_actions': [
                        'Review dispute SOP documentation',
                        'Enable 3-DS step-up for high-risk transactions',
                        'Improve customer service response times',
                        'Consider tightening refund policies'
                    ]
                }
            )
            alerts.append(alert)
        
        # VAMP Breach Risk
        if dispute_rate >= alert_configs['vamp_breach_risk']['threshold']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='vamp_breach_risk',
                level=AlertLevel.CRITICAL,
                market='US_CARDS',
                message=alert_configs['vamp_breach_risk']['message'],
                action=alert_configs['vamp_breach_risk']['action'],
                current_value=dispute_rate,
                threshold=alert_configs['vamp_breach_risk']['threshold'],
                details={
                    'metric': 'Monthly Dispute Rate',
                    'severity': 'critical',
                    'estimated_impact': 'Account hold risk within 7-14 days',
                    'immediate_actions': [
                        'Contact PSP compliance team immediately',
                        'Implement emergency dispute response procedures',
                        'Review all transactions from last 30 days',
                        'Prepare evidence pack for existing disputes'
                    ]
                }
            )
            alerts.append(alert)
        
        # Check chargeback rate
        cb_rate = float(feature_data.get('vamp.chargeback_rate', 0))
        if cb_rate >= thresholds['chargeback_rate']['amber']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='chargeback_rate_elevated',
                level=AlertLevel.WARNING if cb_rate < thresholds['chargeback_rate']['red'] else AlertLevel.CRITICAL,
                market='US_CARDS',
                message=f"Chargeback rate at {cb_rate:.3%} - VAMP program risk",
                action="Review chargeback prevention strategies",
                current_value=cb_rate,
                threshold=thresholds['chargeback_rate']['amber'],
                details={
                    'metric': 'Chargeback Rate',
                    'vamp_threshold': thresholds['chargeback_rate']['red'],
                    'recommended_actions': [
                        'Implement AVS/CVV verification',
                        'Enable fraud scoring',
                        'Review high-risk BIN patterns',
                        'Strengthen customer authentication'
                    ]
                }
            )
            alerts.append(alert)
        
        return alerts
    
    async def _check_pix_alerts(
        self, 
        user_id: int, 
        feature_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check PIX MED alerts for Brazil"""
        
        alerts = []
        market_config = self.markets_config['markets']['BR_PIX']
        thresholds = market_config['thresholds']
        alert_configs = market_config['alerts']
        
        # Check PIX dispute rate
        pix_dispute_rate = float(feature_data.get('pix.dispute_rate', 0))
        
        # PIX MED Watch
        if pix_dispute_rate >= alert_configs['pix_med_watch']['threshold']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='pix_med_watch',
                level=AlertLevel.WARNING,
                market='BR_PIX',
                message=alert_configs['pix_med_watch']['message'],
                action=alert_configs['pix_med_watch']['action'],
                current_value=pix_dispute_rate,
                threshold=alert_configs['pix_med_watch']['threshold'],
                details={
                    'metric': 'PIX Dispute Rate',
                    'program': 'PIX MED 2.0 (effective Feb 2026)',
                    'current_threshold': thresholds['dispute_rate']['red'],
                    'recommended_actions': [
                        'Review PIX dispute response SOP',
                        'Improve PIX transaction descriptions', 
                        'Strengthen customer support for PIX payments',
                        'Monitor dispute resolution times'
                    ]
                }
            )
            alerts.append(alert)
        
        # PIX MED Breach Risk
        if pix_dispute_rate >= alert_configs['pix_med_breach']['threshold']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='pix_med_breach',
                level=AlertLevel.CRITICAL,
                market='BR_PIX',
                message=alert_configs['pix_med_breach']['message'],
                action=alert_configs['pix_med_breach']['action'],
                current_value=pix_dispute_rate,
                threshold=alert_configs['pix_med_breach']['threshold'],
                details={
                    'metric': 'PIX Dispute Rate',
                    'severity': 'critical',
                    'estimated_impact': 'PIX MED program breach risk',
                    'immediate_actions': [
                        'Activate PIX dispute response team',
                        'Notify PSP of elevated dispute activity',
                        'Review all PIX transactions from last 14 days',
                        'Prepare comprehensive dispute evidence'
                    ]
                }
            )
            alerts.append(alert)
        
        return alerts
    
    async def _check_sca_alerts(
        self, 
        user_id: int, 
        feature_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check SCA alerts for EU Cards"""
        
        alerts = []
        market_config = self.markets_config['markets']['EU_CARDS_SCA']
        thresholds = market_config['thresholds']
        alert_configs = market_config['alerts']
        
        # Check authorization rate
        auth_rate = float(feature_data.get('eu.auth_rate_estimate', 1.0))
        
        # SCA Auth Decline Alert
        if auth_rate <= alert_configs['sca_auth_decline']['threshold']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='sca_auth_decline',
                level=AlertLevel.WARNING,
                market='EU_CARDS_SCA',
                message=alert_configs['sca_auth_decline']['message'],
                action=alert_configs['sca_auth_decline']['action'],
                current_value=auth_rate,
                threshold=alert_configs['sca_auth_decline']['threshold'],
                details={
                    'metric': 'Authorization Rate',
                    'program': 'SCA PSD2 Compliance',
                    'optimal_rate': thresholds['auth_rate']['green'],
                    'recommended_actions': [
                        'Review 3-DS authentication flow',
                        'Optimize exemption strategy (TRA, low-value)',
                        'Improve customer authentication experience',
                        'Analyze decline reason codes'
                    ]
                }
            )
            alerts.append(alert)
        
        # Check dispute rate (EU has stricter thresholds)
        dispute_rate = float(feature_data.get('vamp.monthly_dispute_rate', 0))  # Use general dispute rate
        if dispute_rate >= alert_configs['high_dispute_eu']['threshold']:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='high_dispute_eu',
                level=AlertLevel.WARNING,
                market='EU_CARDS_SCA',
                message=alert_configs['high_dispute_eu']['message'],
                action=alert_configs['high_dispute_eu']['action'],
                current_value=dispute_rate,
                threshold=alert_configs['high_dispute_eu']['threshold'],
                details={
                    'metric': 'EU Dispute Rate',
                    'program': 'EU Cards SCA Compliance',
                    'recommended_actions': [
                        'Review SCA implementation effectiveness',
                        'Improve authentication success rates',
                        'Optimize customer checkout experience',
                        'Analyze dispute reasons and patterns'
                    ]
                }
            )
            alerts.append(alert)
        
        return alerts
    
    async def _check_portfolio_alerts(
        self,
        user_id: int,
        feature_data: Dict[str, Any],
        confidence_data: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """Check portfolio-level alerts across all markets"""
        
        alerts = []
        
        # Low confidence alert
        confidence_score = guardscore_engine._calculate_overall_confidence(confidence_data or {})
        if confidence_score < 0.4:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='low_confidence_data',
                level=AlertLevel.INFO,
                market='ALL',
                message="Low confidence in risk assessment - consider data verification",
                action="Upload transaction data or complete additional verification",
                current_value=confidence_score,
                threshold=0.4,
                details={
                    'metric': 'Data Confidence Score',
                    'impact': 'Risk assessment may be less accurate',
                    'recommended_actions': [
                        'Upload Shopify/WooCommerce order history',
                        'Complete additional profile questions',
                        'Verify business documentation'
                    ]
                }
            )
            alerts.append(alert)
        
        # Multi-market complexity alert
        markets = feature_data.get('markets_served.selected', [])
        if len(markets) >= 3:
            alert = await self._create_alert(
                user_id=user_id,
                alert_id='multi_market_complexity',
                level=AlertLevel.INFO,
                market='ALL',
                message="Operating across multiple markets increases compliance complexity",
                action="Consider specialized compliance support",
                current_value=len(markets),
                threshold=3,
                details={
                    'metric': 'Market Complexity',
                    'markets': markets,
                    'recommended_actions': [
                        'Review market-specific compliance requirements',
                        'Consider Global Founder Kit for multi-market guidance',
                        'Implement market-specific monitoring',
                        'Plan for regulatory differences'
                    ]
                }
            )
            alerts.append(alert)
        
        return alerts
    
    async def _create_alert(
        self,
        user_id: int,
        alert_id: str,
        level: AlertLevel,
        market: str,
        message: str,
        action: str,
        current_value: float,
        threshold: float,
        details: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create standardized alert object"""
        
        alert = {
            'id': alert_id,
            'user_id': user_id,
            'level': level.value,
            'market': market,
            'message': message,
            'action': action,
            'current_value': current_value,
            'threshold': threshold,
            'details': details or {},
            'created_at': datetime.utcnow().isoformat(),
            'acknowledged': False,
            'resolved': False
        }
        
        # Track alert in analytics
        await analytics._emit_event(f'alert.triggered:{alert_id}', {
            'user_id': user_id,
            'level': level.value,
            'market': market,
            'current_value': current_value,
            'threshold': threshold
        })
        
        return alert
    
    def _estimate_days_to_breach(self, current_rate: float, breach_threshold: float) -> Optional[int]:
        """Estimate days until breach threshold (simplified)"""
        if current_rate >= breach_threshold:
            return 0
        
        # Simple linear projection (in reality, would use trend analysis)
        rate_margin = breach_threshold - current_rate
        estimated_daily_increase = 0.0001  # Assume 0.01% daily increase
        
        if estimated_daily_increase <= 0:
            return None
        
        days = int(rate_margin / estimated_daily_increase)
        return max(1, min(days, 365))  # Cap at 1 year
    
    async def send_alert_notifications(
        self, 
        user_id: int, 
        alerts: List[Dict[str, Any]]
    ) -> bool:
        """Send alert notifications via configured channels"""
        
        if not alerts:
            return True
        
        alerts_config = self.markets_config['alerts']
        
        try:
            # Sort alerts by severity
            critical_alerts = [a for a in alerts if a['level'] == 'critical']
            warning_alerts = [a for a in alerts if a['level'] == 'warning']
            info_alerts = [a for a in alerts if a['level'] == 'info']
            
            # Send critical alerts immediately
            if critical_alerts:
                await self._send_telegram_alerts(user_id, critical_alerts, 'critical')
                await self._send_email_alerts(user_id, critical_alerts, 'critical')
            
            # Send warning alerts with delay
            if warning_alerts:
                await asyncio.sleep(alerts_config['escalation']['level_2']['delay_hours'] * 3600)
                await self._send_telegram_alerts(user_id, warning_alerts, 'warning')
            
            # Send info alerts to dashboard only
            if info_alerts:
                await self._send_dashboard_alerts(user_id, info_alerts)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert notifications: {e}")
            return False
    
    async def _send_telegram_alerts(
        self, 
        user_id: int, 
        alerts: List[Dict[str, Any]], 
        level: str
    ):
        """Send alerts via Telegram bot"""
        try:
            from main import bot
            
            # Group alerts by market for cleaner message
            market_alerts = {}
            for alert in alerts:
                market = alert['market']
                if market not in market_alerts:
                    market_alerts[market] = []
                market_alerts[market].append(alert)
            
            for market, market_alert_list in market_alerts.items():
                emoji = "🚨" if level == 'critical' else "⚠️"
                
                message_lines = [f"{emoji} **{market} Compliance Alert**\n"]
                
                for alert in market_alert_list:
                    message_lines.append(f"• **{alert['message']}**")
                    message_lines.append(f"  Current: {alert['current_value']:.3%}")
                    message_lines.append(f"  Threshold: {alert['threshold']:.3%}")
                    message_lines.append(f"  Action: {alert['action']}\n")
                
                alert_message = "\n".join(message_lines)
                
                await bot.send_message(
                    chat_id=user_id,
                    text=alert_message,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Failed to send Telegram alerts: {e}")
    
    async def _send_email_alerts(self, user_id: int, alerts: List[Dict[str, Any]], level: str):
        """Send email alerts (placeholder - implement with your email service)"""
        logger.info(f"Email alert notification for user {user_id}: {len(alerts)} {level} alerts")
    
    async def _send_dashboard_alerts(self, user_id: int, alerts: List[Dict[str, Any]]):
        """Send alerts to dashboard (placeholder - implement with your dashboard system)"""
        logger.info(f"Dashboard alert notification for user {user_id}: {len(alerts)} alerts")

# Global instance
alert_engine = AlertEngine()