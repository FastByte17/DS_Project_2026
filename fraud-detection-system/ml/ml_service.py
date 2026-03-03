import requests
import json
from typing import Dict, List
import pandas as pd
from prometheus_client import Counter, Histogram
from sklearn.ensemble import RandomForestClassifier
import pickle
import os

# Metrics
fraud_detected = Counter('fraud_detected_total', 'Frauds detected', ['method', 'fraud_type'])
llm_latency = Histogram('llm_analysis_duration_seconds', 'LLM analysis time')

def load_ml_model():
    """Load pre-trained ML model or create a mock model"""
    model_path = os.path.join(os.path.dirname(__file__), 'fraud_detection_model.pkl')
    
    # Try to load existing model
    if os.path.exists(model_path):
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
                print(f"✓ Loaded trained model from {model_path}")
                return model
        except Exception as e:
            print(f"⚠ Error loading model from {model_path}: {e}")
    
    # Create mock model if no trained model exists
    print("⚠ No trained model found. Creating mock model for testing...")
    
    # Create a simple RandomForest model for demonstration
    # In production, this would be trained on historical fraud data
    mock_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    
    # Create dummy training data
    X_dummy = [
        [0.5, 1000, 0, 50, 60, 1, 10],  # Example features: risk_score, amount, fraud_flag, sim_hash, imei_hash, sim_status, name_len
        [0.2, 500, 0, 30, 40, 1, 8],
        [0.8, 15000, 1, 70, 80, 0, 12],
        [0.1, 100, 0, 20, 25, 1, 5],
    ]
    y_dummy = [0, 0, 1, 0]  # Labels: 0=normal, 1=fraud
    
    mock_model.fit(X_dummy, y_dummy)
    print("✓ Mock ML model created for fraud detection")
    
    return mock_model

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
        
        # Check if fraud_flag is already set
        if cdr.get('fraud_flag', False):
            return {
                'is_fraud': True,
                'type': cdr.get('fraud_type', 'flagged'),
                'reason': f"Record marked as fraudulent: {cdr.get('fraud_type', 'Unknown type')}"
            }
        
        # Check risk_score threshold
        if cdr.get('risk_score', 0) > 0.8:
            return {
                'is_fraud': True,
                'type': 'high_risk_score',
                'reason': f"Risk score {cdr.get('risk_score', 0):.2f} exceeds threshold"
            }
        
        # Check if mobile number is in blacklist
        if cdr.get('mobile_number') in self.get_blacklist():
            return {
                'is_fraud': True,
                'type': 'blacklisted_number',
                'reason': f"Mobile number {cdr.get('mobile_number')} is blacklisted"
            }
        
        # Check if SIM status is suspicious
        if cdr.get('sim_status', '').lower() in ['suspended', 'blocked', 'compromised']:
            return {
                'is_fraud': True,
                'type': 'suspicious_sim_status',
                'reason': f"SIM status: {cdr.get('sim_status')}"
            }
        
        # Check if transaction amount is unusually high
        if cdr.get('amount_eur', 0) > 10000:
            return {
                'is_fraud': True,
                'type': 'high_value_transaction',
                'reason': f"Transaction amount €{cdr.get('amount_eur', 0):.2f} exceeds limit"
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
        
        return f"""You are a telecom fraud detection expert. Analyze this customer transaction record and determine if it's fraudulent.

Customer & Transaction Details:
- Customer ID: {cdr.get('customer_id')}
- Full Name: {cdr.get('full_name')}
- Mobile Number: {cdr.get('mobile_number')}
- City: {cdr.get('city', 'Unknown')}
- SIM Serial Number: {cdr.get('sim_serial_number')}
- SIM Status: {cdr.get('sim_status', 'Unknown')}
- IMEI: {cdr.get('imei')}
- Transaction ID: {cdr.get('transaction_id')}
- Timestamp: {cdr.get('time_stamp')}
- Transaction Type: {cdr.get('type')}
- Amount: €{cdr.get('amount_eur', 0):.2f}

Context:
- ML Model Fraud Score: {ml_score:.2f} (uncertain range)
- Risk Score: {cdr.get('risk_score', 0):.2f}
- Pre-flagged as Fraud: {cdr.get('fraud_flag', False)}
- Reported Fraud Type: {cdr.get('fraud_type', 'None')}

Known Fraud Patterns:
1. SIM Box Fraud: Compromised SIM cards used for fraudulent transactions
2. Identity Fraud: Transactions initiated with stolen customer credentials
3. High-Value Fraud: Unusual high-amount transactions from customer
4. SIM Bypass Fraud: IMEI/SIM serial mismatch indicating device spoofing
5. Account Takeover: Unusual transaction patterns inconsistent with customer behavior

Respond ONLY in this JSON format:
{{
    "is_fraud": true/false,
    "confidence": 0.0-1.0,
    "fraud_type": "sim_box|identity|high_value|sim_bypass|account_takeover|none",
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
            cdr.get('risk_score', 0.0),
            cdr.get('amount_eur', 0),
            1 if cdr.get('fraud_flag', False) else 0,
            hash(cdr.get('sim_serial_number', '')) % 100,  # SIM serial hash
            hash(cdr.get('imei', '')) % 100,  # IMEI hash
            1 if cdr.get('sim_status', '').lower() == 'active' else 0,
            len(cdr.get('full_name', '')),  # Name length as proxy for data quality
        ]
    
    def get_blacklist(self) -> set:
        """Get blacklisted numbers (from DB/cache)"""
        # TODO: Load from database/Redis
        return {'+1234567890', '+9876543210'}


def send_alert_to_prometheus(cdr: Dict, detection_result: Dict):
    """Send alert to Prometheus Alertmanager"""
    alert = {
        "labels": {
            "alertname": "FraudDetected",
            "severity": "critical" if detection_result['confidence'] > 0.9 else "warning",
            "fraud_type": detection_result['fraud_type'],
            "customer_id": cdr.get('customer_id'),
            "mobile_number": cdr.get('mobile_number'),
            "transaction_id": cdr.get('transaction_id')
        },
        "annotations": {
            "summary": f"Fraud detected: {detection_result['fraud_type']}",
            "description": detection_result['explanation'],
            "confidence": str(detection_result['confidence']),
            "method": detection_result['method'],
            "customer_name": cdr.get('full_name'),
            "city": cdr.get('city'),
            "amount_eur": str(cdr.get('amount_eur', 0))
        }
    }
    
    # Send to Alertmanager
    requests.post(
        "http://alertmanager:9093/api/v1/alerts",
        json=[alert]
    )


# FastAPI endpoint - only import and run if executed directly
if __name__ == "__main__":
    from fastapi import FastAPI, HTTPException
    
    app = FastAPI(title="ML Fraud Detection Service")
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
