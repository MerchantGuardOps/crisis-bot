# utils/aha_moments_engine.py
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AhaMomentsEngine:
    """Real-time contextual insights engine for VAMP assessments"""
    
    def __init__(self):
        self.config_path = Path("config/vamp_aha_moments.yaml")
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load aha moments configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Loaded Aha Moments Engine v{self._config['version']}")
        except Exception as e:
            logger.error(f"Failed to load aha moments config: {e}")
            self._config = {"aha_moments": {}, "combined_insights": {}}
    
    def get_instant_insight(self, question_id: str, answer: Any, user_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Get immediate contextual insight for a question answer"""
        if not self._config or question_id not in self._config.get('aha_moments', {}):
            return None
            
        question_config = self._config['aha_moments'][question_id]
        
        # Check triggers for this question
        for trigger in question_config.get('triggers', []):
            if self._evaluate_condition(trigger['condition'], answer, user_data):
                insight = trigger['insight'].copy()
                
                # Format dynamic values in the insight
                insight = self._format_insight(insight, answer, user_data)
                insight['severity'] = trigger['severity']
                insight['question_id'] = question_id
                
                return insight
        
        return None
    
    def get_combined_insights(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get insights based on multiple question answers"""
        insights = []
        
        if not self._config:
            return insights
            
        combined_config = self._config.get('combined_insights', {})
        
        for insight_key, config in combined_config.items():
            conditions = config.get('conditions', [])
            
            # Check if all conditions are met
            if self._check_all_conditions(conditions, user_data):
                insight = config['insight'].copy()
                insight['severity'] = config['severity']
                insight['type'] = 'combined'
                insight['insight_key'] = insight_key
                insights.append(insight)
        
        return insights
    
    def get_contextual_recommendation(self, user_data: Dict[str, Any]) -> Optional[str]:
        """Get contextual recommendation based on business profile"""
        if not self._config:
            return None
            
        recommendations = self._config.get('contextual_recommendations', {})
        
        for rec_key, config in recommendations.items():
            if self._evaluate_condition(config['condition'], None, user_data):
                return config['message']
        
        return None
    
    def get_educational_content(self, topic: str) -> Optional[Dict[str, str]]:
        """Get educational content for a specific topic"""
        if not self._config:
            return None
            
        educational = self._config.get('educational_content', {})
        return educational.get(topic)
    
    def _evaluate_condition(self, condition: str, answer: Any, user_data: Dict[str, Any] = None) -> bool:
        """Evaluate a condition string against answer and user data"""
        try:
            # Replace 'value' with actual answer value
            if answer is not None:
                if isinstance(answer, str):
                    condition = condition.replace('value', f"'{answer}'")
                else:
                    condition = condition.replace('value', str(answer))
            
            # Handle user_data path lookups (e.g., BP_2 == 'EARLY')
            if user_data:
                for key, value in user_data.items():
                    if isinstance(value, str):
                        condition = condition.replace(key, f"'{value}'")
                    elif isinstance(value, bool):
                        condition = condition.replace(key, str(value))
                    else:
                        condition = condition.replace(key, str(value))
            
            # Special handling for 'in' operations
            if ' in [' in condition:
                # Convert string like "'Basic' in ['Basic', 'None']" 
                parts = condition.split(' in ')
                if len(parts) == 2:
                    value_part = parts[0].strip()
                    list_part = parts[1].strip()
                    # Evaluate safely
                    return eval(f"{value_part} in {list_part}")
            
            # Safe evaluation for comparison operators
            return eval(condition)
            
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False
    
    def _check_all_conditions(self, conditions: List[str], user_data: Dict[str, Any]) -> bool:
        """Check if all conditions in a list are met"""
        for condition in conditions:
            if not self._evaluate_condition(condition, None, user_data):
                return False
        return True
    
    def _format_insight(self, insight: Dict[str, str], answer: Any, user_data: Dict[str, Any] = None) -> Dict[str, str]:
        """Format insight text with dynamic values"""
        formatted = {}
        
        for key, text in insight.items():
            if isinstance(text, str):
                # Format percentage values
                if '{value:' in text and answer is not None:
                    try:
                        text = text.format(value=float(answer))
                    except (ValueError, TypeError):
                        text = text.replace('{value}', str(answer))
                
                # Calculate buffer for warning conditions
                if 'buffer_calculation' in insight and key == 'impact':
                    try:
                        # Simple buffer calculation example
                        if user_data and 'monthly_volume' in user_data:
                            monthly_volume = user_data['monthly_volume']
                            buffer = monthly_volume * (0.0075 - float(answer))
                            text = text.format(buffer=buffer)
                    except Exception:
                        pass  # Skip buffer calculation if data unavailable
                
                formatted[key] = text
            else:
                formatted[key] = text
        
        return formatted

# Global instance
aha_engine = AhaMomentsEngine()