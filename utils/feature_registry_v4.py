# utils/feature_registry_v4.py
"""
GuardScore™ Feature Registry v4.0
The authoritative mapping from Golden Question Bank to ML features
"""
import pandas as pd
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

class FeatureRegistryV4:
    """
    v4 Feature Registry - Maps Golden Question Bank to ML Pipeline
    
    Key Features:
    - Immutable question_id → feature_name mapping
    - Confidence range tracking (0.30-0.95)
    - Market-specific scoping (US_CARDS, BR_PIX, EU_CARDS_SCA)
    - Type safety with dtype validation
    - Behavioral signal capture
    """
    
    def __init__(self, csv_path: str = "config/guardscore_feature_mapping_v4.csv"):
        self.csv_path = csv_path
        self.mapping = None
        self.question_to_feature = {}
        self.feature_to_model = {}
        self.market_features = {}
        self._load_mapping()
    
    def _load_mapping(self):
        """Load the v4 CSV mapping"""
        try:
            csv_file = Path(self.csv_path)
            if not csv_file.exists():
                logger.error(f"v4 mapping file not found: {self.csv_path}")
                raise FileNotFoundError(f"v4 mapping file not found: {self.csv_path}")
            
            self.mapping = pd.read_csv(csv_file)
            self._build_lookup_tables()
            logger.info(f"✅ Loaded {len(self.mapping)} features from v4 mapping")
            
        except Exception as e:
            logger.error(f"Failed to load v4 mapping: {e}")
            raise
    
    def _build_lookup_tables(self):
        """Build fast lookup dictionaries from v4 mapping"""
        for _, row in self.mapping.iterrows():
            question_id = row['question_id']
            
            # Question ID → Feature mapping
            self.question_to_feature[question_id] = {
                'feature_name': row['feature_name'],
                'dtype': row['dtype'],
                'allowed_values': row.get('allowed_values', ''),
                'confidence_range': row['confidence_range'],
                'market_scope': row['market_scope'],
                'model_usage': row['model_usage'],
                'example_value': row.get('example_value', ''),
                'notes': row.get('notes', '')
            }
            
            # Feature → Model mapping
            feature_name = row['feature_name']
            self.feature_to_model[feature_name] = {
                'question_id': question_id,
                'model_usage': row['model_usage'],
                'market_scope': row['market_scope'],
                'dtype': row['dtype']
            }
            
            # Market-specific features
            market = row['market_scope']
            if market not in self.market_features:
                self.market_features[market] = []
            self.market_features[market].append(feature_name)
    
    def map_answer_to_feature(self, question_id: str, answer: Any, 
                             has_csv: bool = False, session_data: Dict = None) -> Optional[Dict]:
        """
        Convert bot answer to ML feature using v4 mapping
        
        Args:
            question_id: The Golden Question Bank ID (e.g., 'VAMP_1')
            answer: Raw answer from bot
            has_csv: Whether user uploaded CSV (boosts confidence)
            session_data: Behavioral data (latency, depth, etc.)
            
        Returns:
            Feature dict with value, confidence, market scope
        """
        if question_id not in self.question_to_feature:
            logger.warning(f"Unknown question_id: {question_id}")
            return None
        
        mapping = self.question_to_feature[question_id]
        feature_name = mapping['feature_name']
        dtype = mapping['dtype']
        
        try:
            # Type conversion based on v4 spec
            value = self._convert_value(answer, dtype, mapping.get('allowed_values', ''))
            
            # Calculate confidence using v4 ranges
            confidence = self._calculate_confidence_v4(question_id, answer, has_csv, session_data)
            
            return {
                'question_id': question_id,
                'feature': feature_name,
                'value': value,
                'confidence': confidence,
                'market': mapping['market_scope'],
                'model_usage': mapping['model_usage'],
                'dtype': dtype
            }
            
        except Exception as e:
            logger.error(f"Failed to map {question_id}={answer}: {e}")
            return None
    
    def _convert_value(self, answer: Any, dtype: str, allowed_values: str) -> Any:
        """Convert answer to proper type based on v4 dtype spec"""
        
        if answer is None or answer == 'unknown' or answer == '':
            return None
        
        if dtype == 'float':
            # Handle percentage strings
            if isinstance(answer, str):
                answer = answer.replace('%', '').replace(',', '.')
                if float(answer) > 1.0:  # Convert percentage to decimal
                    answer = float(answer) / 100
            return float(answer)
        
        elif dtype == 'int':
            return int(answer)
        
        elif dtype == 'bool':
            if isinstance(answer, str):
                return answer.lower() in ['true', 'yes', '1', 'on']
            return bool(answer)
        
        elif dtype.startswith('enum'):
            # Validate against allowed values
            allowed = [v.strip() for v in allowed_values.split(',')]
            return answer if answer in allowed else None
        
        elif dtype == 'array[str]':
            if isinstance(answer, str):
                # Parse array from string
                try:
                    return json.loads(answer) if answer.startswith('[') else [answer]
                except:
                    return [answer]
            return answer if isinstance(answer, list) else [str(answer)]
        
        elif dtype.startswith('map'):
            if isinstance(answer, str):
                try:
                    return json.loads(answer)
                except:
                    return {}
            return answer if isinstance(answer, dict) else {}
        
        else:
            return str(answer)
    
    def _calculate_confidence_v4(self, question_id: str, answer: Any, 
                                has_csv: bool = False, session_data: Dict = None) -> float:
        """Calculate confidence using v4 ranges and boosters"""
        
        mapping = self.question_to_feature[question_id]
        conf_range = mapping['confidence_range']
        
        # Parse range (e.g., "0.30–0.95")
        try:
            range_parts = conf_range.replace('–', '-').split('-')
            min_conf = float(range_parts[0])
            max_conf = float(range_parts[1])
        except:
            logger.warning(f"Invalid confidence range for {question_id}: {conf_range}")
            min_conf, max_conf = 0.30, 0.95
        
        # Start at minimum confidence
        confidence = min_conf
        
        # Boost for non-empty answers
        if answer and answer != 'unknown':
            confidence = min_conf + 0.15
        
        # CSV upload boost (per v4 spec)
        if has_csv and question_id in ['VAMP_1', 'VAMP_2', 'PIX_1', 'EU_2']:
            confidence = max_conf  # Verified data
        
        # System-generated features get max confidence
        if question_id.startswith('POWERUP_') or question_id.startswith('BEH_'):
            confidence = max_conf
        
        # Session behavioral boost
        if session_data:
            if session_data.get('session_depth', 0) > 10:
                confidence += 0.05  # Deep engagement
            if session_data.get('answer_latency_ms', 0) < 3000:
                confidence += 0.03  # Quick, confident answers
        
        return min(confidence, max_conf)
    
    def get_market_features(self, market: str) -> List[str]:
        """Get all features for a specific market"""
        market_features = self.market_features.get(market, [])
        global_features = self.market_features.get('GLOBAL', [])
        return market_features + global_features
    
    def get_vamp_features(self) -> List[str]:
        """Get VAMP-specific features"""
        vamp_questions = ['VAMP_1', 'VAMP_2', 'VAMP_3', 'VAMP_4']
        return [self.question_to_feature[qid]['feature_name'] for qid in vamp_questions]
    
    def get_prescriptive_features(self) -> List[str]:
        """Get features used for prescriptive recommendations"""
        prescriptive = []
        for qid, mapping in self.question_to_feature.items():
            if 'prescriptive' in mapping['model_usage']:
                prescriptive.append(mapping['feature_name'])
        return prescriptive
    
    def validate_feature_values(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Validate feature values against v4 constraints"""
        validated = {}
        
        for feature_name, value in features.items():
            # Find the mapping
            mapping_found = None
            for qid, mapping in self.question_to_feature.items():
                if mapping['feature_name'] == feature_name:
                    mapping_found = mapping
                    break
            
            if not mapping_found:
                logger.warning(f"Unknown feature: {feature_name}")
                continue
            
            # Validate based on dtype
            try:
                validated_value = self._convert_value(
                    value, 
                    mapping_found['dtype'], 
                    mapping_found['allowed_values']
                )
                validated[feature_name] = validated_value
            except Exception as e:
                logger.warning(f"Failed to validate {feature_name}={value}: {e}")
                validated[feature_name] = None
        
        return validated
    
    def get_feature_stats(self) -> Dict[str, Any]:
        """Get statistics about the v4 feature mapping"""
        stats = {
            'total_features': len(self.mapping),
            'markets': list(set(self.mapping['market_scope'].tolist())),
            'dtypes': list(set(self.mapping['dtype'].tolist())),
            'confidence_sources': list(set(self.mapping['confidence_source'].tolist())),
            'vamp_features': len([q for q in self.question_to_feature.keys() if q.startswith('VAMP_')]),
            'pix_features': len([q for q in self.question_to_feature.keys() if q.startswith('PIX_')]),
            'eu_features': len([q for q in self.question_to_feature.keys() if q.startswith('EU_')]),
            'behavioral_features': len([q for q in self.question_to_feature.keys() if q.startswith('BEH_')])
        }
        return stats

# Global instance
feature_registry_v4 = FeatureRegistryV4()

def map_golden_answers_to_features(answers: Dict[str, Any], 
                                  has_csv: bool = False, 
                                  session_data: Dict = None) -> Dict[str, Any]:
    """
    Convenience function to map all answers to features
    
    Usage:
        answers = {'VAMP_1': 0.008, 'VAMP_2': 0.012, 'MKT_1': ['US_CARDS']}
        features = map_golden_answers_to_features(answers, has_csv=True)
    """
    features = {}
    confidence_scores = {}
    
    for question_id, answer in answers.items():
        result = feature_registry_v4.map_answer_to_feature(
            question_id, answer, has_csv, session_data
        )
        
        if result:
            features[result['feature']] = result['value']
            confidence_scores[result['feature']] = result['confidence']
    
    return {
        'features': features,
        'confidence': confidence_scores,
        'total_features': len(features),
        'avg_confidence': sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0
    }