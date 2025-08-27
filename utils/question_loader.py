# utils/question_loader.py
from __future__ import annotations

import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class QuestionLoader:
    """Loads and manages Golden Question Bank v4.0"""
    
    def __init__(self):
        self.config_path = Path("config/questions_v4.yaml")
        self.events_path = Path("config/events_taxonomy.json")
        self._questions_config = None
        self._events_config = None
        self._questions_by_id = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load YAML and JSON configs"""
        try:
            # Load questions config
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._questions_config = yaml.safe_load(f)
            
            # Load events taxonomy
            with open(self.events_path, 'r', encoding='utf-8') as f:
                self._events_config = json.load(f)
            
            # Build question ID index
            self._build_question_index()
            
            logger.info(f"Loaded Golden Question Bank v{self._questions_config['version']}")
            
        except Exception as e:
            logger.error(f"Failed to load question configs: {e}")
            raise
    
    def _build_question_index(self):
        """Build index of all questions by ID"""
        self._questions_by_id = {}
        
        for group in self._questions_config.get('groups', []):
            for item in group.get('items', []):
                question_id = item['id']
                self._questions_by_id[question_id] = {
                    **item,
                    'group_code': group['code'],
                    'required_for_markets': group.get('required_for_markets', [])
                }
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get question configuration by ID"""
        return self._questions_by_id.get(question_id)
    
    def get_market_questions(self) -> List[str]:
        """Get market selection question IDs"""
        return ['MKT_1', 'MKT_2']
    
    def get_business_profile_questions(self) -> List[str]:
        """Get business profile question IDs"""
        return [f'BP_{i}' for i in range(1, 8)]
    
    def get_vamp_questions(self) -> List[str]:
        """Get VAMP question IDs (crown jewels)"""
        return ['VAMP_1', 'VAMP_2', 'VAMP_3', 'VAMP_4']
    
    def get_pix_questions(self) -> List[str]:
        """Get PIX question IDs"""
        return ['PIX_1', 'PIX_3']
    
    def get_eu_questions(self) -> List[str]:
        """Get EU SCA question IDs"""
        return ['EU_1', 'EU_2']
    
    def get_questions_for_markets(self, selected_markets: List[str]) -> List[str]:
        """Get question IDs required for selected markets"""
        required_questions = []
        
        # Always ask market and business profile questions
        required_questions.extend(self.get_market_questions())
        required_questions.extend(self.get_business_profile_questions())
        
        # Add market-specific questions
        if 'US_CARDS' in selected_markets:
            required_questions.extend(self.get_vamp_questions())
        
        if 'BR_PIX' in selected_markets:
            required_questions.extend(self.get_pix_questions())
        
        if 'EU_CARDS_SCA' in selected_markets:
            required_questions.extend(self.get_eu_questions())
        
        return required_questions
    
    def get_prompt(self, question_id: str, locale: str = 'en') -> str:
        """Get localized prompt for question"""
        question = self.get_question_by_id(question_id)
        if not question:
            return f"Question {question_id} not found"
        
        prompts = question.get('prompt', {})
        return prompts.get(locale, prompts.get('en', f"No prompt for {question_id}"))
    
    def get_options(self, question_id: str, locale: str = 'en') -> List[Dict[str, Any]]:
        """Get localized options for select/multiselect questions"""
        question = self.get_question_by_id(question_id)
        if not question or 'options' not in question:
            return []
        
        localized_options = []
        for option in question['options']:
            label = option['label']
            localized_label = label.get(locale, label.get('en', option['value']))
            
            localized_options.append({
                'value': option['value'],
                'label': localized_label
            })
        
        return localized_options
    
    def get_scoring_config(self) -> Dict[str, Any]:
        """Get scoring configuration"""
        return self._questions_config.get('scoring_map', {})
    
    def get_confidence_weights(self) -> Dict[str, float]:
        """Get confidence weight mappings"""
        scoring = self.get_scoring_config()
        return scoring.get('confidence_weights', {})
    
    def get_market_thresholds(self, market: str) -> Dict[str, float]:
        """Get thresholds for specific market"""
        scoring = self.get_scoring_config()
        thresholds = scoring.get('thresholds', {})
        
        market_key = market.lower().replace('_', '_')
        return thresholds.get(market_key, {})
    
    def should_offer_powerup(self, user_data: Dict[str, Any]) -> bool:
        """Check if Data-Verified powerup should be offered"""
        platform = user_data.get('platform', {}).get('primary')
        return platform in ['Shopify', 'WooCommerce']
    
    def get_analytics_key(self, question_id: str) -> str:
        """Get analytics key for question"""
        question = self.get_question_by_id(question_id)
        if not question:
            return f"unknown.{question_id}"
        
        return question.get('analytics_key', f"question.{question_id}")
    
    def map_answer_to_feature(self, question_id: str, answer: Any) -> Dict[str, Any]:
        """Map answer to feature store path"""
        question = self.get_question_by_id(question_id)
        if not question:
            return {}
        
        map_to = question.get('map_to', f'unknown.{question_id}')
        return {map_to: answer}

# Global instance
question_loader = QuestionLoader()