import requests
import json
from typing import Dict, List
import pandas as pd
from prometheus_client import Counter, Histogram

# Metrics
fraud_detected = Counter('fraud_detected_total', 'Frauds detected', ['method', 'fraud_type'])
llm_latency = Histogram('llm_analysis_duration_seconds', 'LLM analysis time')

class FraudDetectionEngine:
    def __init__(self, ollama_host: str = "http://ollama:11434"):
        self.ollama_host = ollama_host
        self.ml_model = load_ml_model()  # load the trained model
        
    def detect_fraud(self, cdr: Dict) -> Dict:
        """main fraud detection pipeline"""
        
        rule_result = self.apply_rules(cdr)
        if rule_result['is_fraud']:
            fraud_detected.labels(method='rules', fraud_type=rule_result['type']).inc()
            return {
                'is_fraud': True,
                'confidence': 1.0,
                'method': 'rules',
                'fraud_type': rule_result['type'],
                'explanation': rule_result['reason']
            }
        
        fraud_score = self.ml_model_predict(cdr)
        
        if fraud_score > 0.8:
            fraud_detected.labels(method='ml', fraud_type='ml_detected').inc()
            return {
                'is_fraud': True,
                'confidence': fraud_score,
                'method': 'ml',
                'explanation': self.generate_ml_explanation(cdr, fraud_score)
            }
        
        if fraud_score < 0.3:
            return {'is_fraud': False, 'confidence': 1 - fraud_score}
        
        llm_result = self.llm_validate(cdr, fraud_score)
        
        return llm_result
    
    def apply_rules(self, cdr: Dict) -> Dict:
        """fast rule-based detection"""
        
        if cdr['duration'] > 86400:  # > 24 hours
            return {
                'is_fraud': True,
                'type': 'impossible_duration',
                'reason': f"Call duration {cdr['duration']}s exceeds 24 hours"
            }
        
        if cdr.get('calls_last_minute', 0) > 10:
            return {
                'is_fraud': True,
                'type': 'sim_box_fraud',
                'reason': f"{cdr['calls_last_minute']} calls in last minute"
            }
        
        if cdr['source_number'] in self.get_blacklist():
            return {
                'is_fraud': True,
                'type': 'blacklisted_number',
                'reason': f"Source number {cdr['source_number']} is blacklisted"
            }
        
        if cdr['destination_prefix'] in ['1-900', '+882', '+883']:
            if cdr['duration'] > 300:  # > 5 minutes
                return {
                    'is_fraud': True,
                    'type': 'premium_rate_abuse',
                    'reason': f"Long call to premium rate number"
                }
        
        return {'is_fraud': False}
    
    def ml_model_predict(self, cdr: Dict) -> float:
        """ml-based fraud scoring"""
        features = self.extract_features(cdr)
        fraud_probability = self.ml_model.predict_proba([features])[0][1]
        return fraud_probability
    
    @llm_latency.time()
    def llm_validate(self, cdr: Dict, ml_score: float) -> Dict:
        """use llm for uncertain cases"""
        
        prompt = self.create_llm_prompt(cdr, ml_score)
        
        response = requests.post(
            f"{self.ollama_host}/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }
        )
        
        llm_response = response.json()['response']
        parsed_result = self.parse_llm_response(llm_response)
        
        fraud_detected.labels(
            method='llm',
            fraud_type=parsed_result.get('fraud_type', 'unknown')
        ).inc()
        
        return parsed_result
    
    def create_llm_prompt(self, cdr: Dict, ml_score: float) -> str:
        """create structured prompt for llm"""
        
        return f"""You are a telecom fraud detection expert. Analyze this Call Detail Record (CDR) and determine if it's fraudulent.

CDR Details:
- Call ID: {cdr.get('call_id')}
- Source Number: {cdr.get('source_number')}
- Destination Number: {cdr.get('destination_number')}
- Duration: {cdr.get('duration')} seconds ({cdr.get('duration')//60} minutes)
- Timestamp: {cdr.get('timestamp')}
- Call Type: {cdr.get('call_type')}
- Location: {cdr.get('location', 'Unknown')}
- Cost: ${cdr.get('cost', 0):.2f}

Context:
- ML Model Fraud Score: {ml_score:.2f} (uncertain range)
- Recent calls from this number: {cdr.get('recent_call_count', 0)}
- Average call duration for this user: {cdr.get('avg_duration', 0)} seconds
- Time of day: {cdr.get('hour_of_day')} (0-23)

Known Fraud Patterns:
1. SIM Box Fraud: Multiple short calls to different numbers in rapid succession
2. Call Spoofing: Caller ID manipulation to appear as legitimate entity
3. Premium Rate Fraud: Long calls to expensive international numbers
4. Wangiri Fraud: Very short calls designed to prompt callback
5. International Revenue Share Fraud (IRSF): Calls routed to premium numbers

Respond ONLY in this JSON format:
{{
    "is_fraud": true/false,
    "confidence": 0.0-1.0,
    "fraud_type": "sim_box|call_spoofing|premium_rate|wangiri|irsf|none",
    "explanation": "Brief explanation of your reasoning",
    "suspicious_indicators": ["list", "of", "red", "flags"],
    "recommended_action": "block|monitor|allow"
}}

Analysis:"""

    def parse_llm_response(self, response: str) -> Dict:
        """Parse LLM JSON response"""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
            
            result = json.loads(json_str)
            
            return {
                'is_fraud': result.get('is_fraud', False),
                'confidence': result.get('confidence', 0.5),
                'method': 'llm',
                'fraud_type': result.get('fraud_type', 'unknown'),
                'explanation': result.get('explanation', ''),
                'suspicious_indicators': result.get('suspicious_indicators', []),
                'recommended_action': result.get('recommended_action', 'monitor')
            }
        except json.JSONDecodeError:
            return {
                'is_fraud': False,
                'confidence': 0.5,
                'method': 'llm_error',
                'explanation': 'Failed to parse LLM response',
                'error': response
            }
    
    def extract_features(self, cdr: Dict) -> List:
        """Extract features for ML model"""
        return [
            cdr.get('duration', 0),
            cdr.get('hour_of_day', 0),
            cdr.get('day_of_week', 0),
            cdr.get('recent_call_count', 0),
            cdr.get('avg_duration', 0),
            1 if cdr.get('is_international', False) else 0,
            cdr.get('cost', 0),
        ]
    
    def get_blacklist(self) -> set:
        """Get blacklisted numbers (from DB/cache)"""
        # TODO: Load from database/Redis
        return {'+1234567890', '+9876543210'}
    
    # FastAPI endpoint
from fastapi import FastAPI, HTTPException

app = FastAPI()
detector = FraudDetectionEngine()

@app.post("/detect")
async def detect_fraud_endpoint(cdr: Dict):
    try:
        result = detector.detect_fraud(cdr)
        
        # Send to Prometheus/Alertmanager if fraud detected
        if result['is_fraud'] and result['confidence'] > 0.7:
            send_alert_to_prometheus(cdr, result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def send_alert_to_prometheus(cdr: Dict, detection_result: Dict):
    """Send alert to Prometheus Alertmanager"""
    alert = {
        "labels": {
            "alertname": "FraudDetected",
            "severity": "critical" if detection_result['confidence'] > 0.9 else "warning",
            "fraud_type": detection_result['fraud_type'],
            "call_id": cdr['call_id'],
            "source_number": cdr['source_number']
        },
        "annotations": {
            "summary": f"Fraud detected: {detection_result['fraud_type']}",
            "description": detection_result['explanation'],
            "confidence": str(detection_result['confidence']),
            "method": detection_result['method']
        }
    }
    
    # Send to Alertmanager
    requests.post(
        "http://alertmanager:9093/api/v1/alerts",
        json=[alert]
    )
