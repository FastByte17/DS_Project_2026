import requests
import json
import threading
import time
import numpy as np
from collections import deque
from typing import Dict, List
import pandas as pd
from prometheus_client import Counter, Histogram, generate_latest
from sklearn.calibration import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from fastapi import FastAPI, HTTPException
import pickle
import os

# FastAPI app
app = FastAPI(title="ML Fraud Detection Service")

# prometheus metrics
fraud_detected = Counter('fraud_detected_total', 'Frauds detected', ['method', 'fraud_type'])
llm_latency = Histogram('llm_analysis_duration_seconds', 'LLM analysis time')
cdr_processed = Counter('cdr_processed_total', 'Total CDRs processed', ['status'])

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
        self.blacklist = {'+1234567890', '+9876543210'}

        # random forest model (trained in batches)
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.sim_status_encoder = LabelEncoder()
        self.sim_status_encoder.fit(['active', 'suspended', 'blocked', 'compromised', 'unknown'])
        self.rf_trained = False

        # batch training buffer. trains once 50 CDRs have been collected
        self.BATCH_SIZE = 50
        self.training_buffer: deque = deque(maxlen=1000)
        self.training_lock = threading.Lock()

        print(" random forest model initialized,  will train after first batch of CDRs")
        
    def detect_fraud(self, cdr: Dict) -> Dict:
        """Main fraud detection pipeline"""
        
        # stage 1: rule-based detection
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
        
        # stage 2: random forest model prediction
        fraud_score = self.rf_predict(cdr)

        # adding CDR to training buffer and trigger batch training if ready
        self._buffer_and_train(cdr)
        
        if fraud_score > 0.8:
            fraud_detected.labels(method='random_forest', fraud_type='high_risk').inc()
            return {
                'is_fraud': True,
                'confidence': fraud_score,
                'method': 'random_forest',
                'fraud_type': 'high_risk_pattern',
                'explanation': f'High fraud score: {fraud_score:.2f}'
            }
        
        if fraud_score < 0.3:
            return {'is_fraud': False, 'confidence': 1 - fraud_score}
        
        # stage 3: LLM validation for uncertain cases
        llm_result = self.llm_validate(cdr, fraud_score)
        return llm_result
    
    def apply_rules(self, cdr: Dict) -> Dict:
        """Fast rule-based detection"""
        
        # rule 1: check if already flagged as fraud
        if cdr.get('fraud_flag', False):
            return {
                'is_fraud': True,
                'type': cdr.get('fraud_type', 'flagged'),
                'reason': f"Record marked as fraudulent: {cdr.get('fraud_type', 'Unknown type')}"
            }
        
        # rule 2: high risk score
        if cdr.get('risk_score', 0) > 0.8:
            return {
                'is_fraud': True,
                'type': 'high_risk_score',
                'reason': f"Risk score {cdr.get('risk_score', 0):.2f} exceeds threshold"
            }
        
        # rule 3: blacklisted number
        if cdr.get('mobile_number') in self.blacklist:
            return {
                'is_fraud': True,
                'type': 'blacklisted_number',
                'reason': f"Mobile number {cdr.get('mobile_number')} is blacklisted"
            }
        
        # rule 4: suspicious SIM status
        if cdr.get('sim_status', '').lower() in ['suspended', 'blocked', 'compromised']:
            return {
                'is_fraud': True,
                'type': 'suspicious_sim_status',
                'reason': f"SIM status: {cdr.get('sim_status')}"
            }
        
        # rule 5: high value transaction
        if cdr.get('amount_eur', 0) > 10000:
            return {
                'is_fraud': True,
                'type': 'high_value_transaction',
                'reason': f"Transaction amount €{cdr.get('amount_eur', 0):.2f} exceeds limit"
            }
        
        return {'is_fraud': False}
    
    def _extract_features(self, cdr: Dict) -> np.ndarray:
        """extract numerical feature vector from a CDR for the random forest model"""
        sim_status = cdr.get('sim_status', 'unknown').lower()
        if sim_status not in self.sim_status_encoder.classes_:
            sim_status = 'unknown'
        sim_status_encoded = self.sim_status_encoder.transform([sim_status])[0]

        features = [
            float(cdr.get('risk_score', 0.0)),
            float(cdr.get('amount_eur', 0.0)),
            float(sim_status_encoded),
            float(1 if cdr.get('fraud_flag', False) else 0),
            float(1 if cdr.get('mobile_number') in self.blacklist else 0),
        ]
        return np.array(features)

    def rf_predict(self, cdr: Dict) -> float:
        """predict fraud probability using the random forest model.
        falls back to heuristic scoring if the model has not been trained yet."""
        if not self.rf_trained:
            return self._heuristic_score(cdr)

        features = self._extract_features(cdr).reshape(1, -1)
        prob = self.rf_model.predict_proba(features)[0]
        # predict_proba returns [P(legit), P(fraud)] — return fraud probability
        fraud_class_index = list(self.rf_model.classes_).index(1) if 1 in self.rf_model.classes_ else 1
        return float(prob[fraud_class_index])

    def _heuristic_score(self, cdr: Dict) -> float:
        """simple heuristic fallback used before the RF model has been trained"""
        score = 0.0
        score += cdr.get('risk_score', 0) * 0.4
        amount = cdr.get('amount_eur', 0)
        if amount > 5000:
            score += 0.3
        elif amount > 1000:
            score += 0.15
        if cdr.get('sim_status', '').lower() != 'active':
            score += 0.2
        if cdr.get('fraud_flag', False):
            score += 0.3
        return min(score, 1.0)

    def _buffer_and_train(self, cdr: Dict):
        """add CDR to the training buffer and trigger batch training when full"""
        label = 1 if cdr.get('fraud_flag', False) or cdr.get('risk_score', 0) > 0.8 else 0
        with self.training_lock:
            self.training_buffer.append((cdr, label))
            if len(self.training_buffer) >= self.BATCH_SIZE:
                self._train_batch()

    def _train_batch(self):
        """train (or re-train) the random forest on the current buffer.
        must be called inside training_lock."""
        print(f"training random fforest on batch of {len(self.training_buffer)} CDRs...")
        X = np.array([self._extract_features(cdr) for cdr, _ in self.training_buffer])
        y = np.array([label for _, label in self.training_buffer])

        # only train if both classes are present in the batch
        if len(set(y)) < 2:
            print("  skipping RF training, batch contains only one class")
            return

        self.rf_model.fit(X, y)
        self.rf_trained = True
        print(f"random Forest trained! {sum(y)} fraud samples, {len(y) - sum(y)} clean samples")
    
    @llm_latency.time()
    def llm_validate(self, cdr: Dict, ml_score: float) -> Dict:
        """use LLM for uncertain cases"""
        
        prompt = self.create_llm_prompt(cdr, ml_score)
        
        try:
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
                },
                timeout=30
            )
            
            llm_response = response.json()['response']
            parsed_result = self.parse_llm_response(llm_response)
            
            fraud_detected.labels(
                method='llm',
                fraud_type=parsed_result.get('fraud_type', 'unknown')
            ).inc()
            
            return parsed_result
            
        except Exception as e:
            print(f"LLM validation error: {e}")
            # fallback to scoring if LLM fails
            return {
                'is_fraud': ml_score > 0.5,
                'confidence': ml_score,
                'method': 'scoring_fallback',
                'explanation': f'LLM unavailable, using score: {ml_score:.2f}'
            }
    
    def create_llm_prompt(self, cdr: Dict, ml_score: float) -> str:
        """Create structured prompt for LLM"""
        
        return f"""You are a telecom fraud detection expert. Analyze this customer transaction record and determine if it's fraudulent.

Customer & Transaction Details:
- Customer ID: {cdr.get('customer_id', 'Unknown')}
- Full Name: {cdr.get('full_name', 'Unknown')}
- Mobile Number: {cdr.get('mobile_number', 'Unknown')}
- City: {cdr.get('city', 'Unknown')}
- SIM Serial: {cdr.get('sim_serial_number', 'Unknown')}
- SIM Status: {cdr.get('sim_status', 'Unknown')}
- Transaction ID: {cdr.get('transaction_id', 'Unknown')}
- Timestamp: {cdr.get('time_stamp', 'Unknown')}
- Amount: €{cdr.get('amount_eur', 0):.2f}

Context:
- ML Fraud Score: {ml_score:.2f} (uncertain)
- Risk Score: {cdr.get('risk_score', 0):.2f}
- Pre-flagged: {cdr.get('fraud_flag', False)}

Respond ONLY in JSON format:
{{
    "is_fraud": true/false,
    "confidence": 0.0-1.0,
    "fraud_type": "sim_box|identity|high_value|account_takeover|none",
    "explanation": "Brief explanation",
    "suspicious_indicators": ["list", "of", "flags"],
    "recommended_action": "block|monitor|allow"
}}

Analysis:"""

    def parse_llm_response(self, response: str) -> Dict:
        """parse LLM JSON response"""
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
    try:
        alert = {
            "labels": {
                "alertname": "FraudDetected",
                "severity": "critical" if detection_result['confidence'] > 0.9 else "warning",
                "fraud_type": detection_result.get('fraud_type', 'unknown'),
                "customer_id": cdr.get('customer_id'),
                "mobile_number": cdr.get('mobile_number'),
                "transaction_id": cdr.get('transaction_id')
            },
            "annotations": {
                "summary": f"Fraud detected: {detection_result.get('fraud_type', 'unknown')}",
                "description": detection_result.get('explanation', ''),
                "confidence": str(detection_result.get('confidence', 0)),
                "method": detection_result.get('method', 'unknown'),
                "customer_name": cdr.get('full_name'),
                "city": cdr.get('city'),
                "amount_eur": str(cdr.get('amount_eur', 0))
            }
        }
        
        # Send to Alertmanager
        requests.post(
            "http://alertmanager:9093/api/v1/alerts",
            json=[alert],
            timeout=5
        )
    except Exception as e:
        print(f"Error sending alert: {e}")


# FastAPI endpoints
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ml-fraud-detection"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ML Fraud Detection Service",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "detect": "POST /detect",
            "health": "GET /health",
            "metrics": "GET /metrics"
        }
    }

@app.post("/detect")
async def detect_fraud_endpoint(cdr: Dict):
    """Detect fraud in CDR"""
    try:
        detector = FraudDetectionEngine()
        result = detector.detect_fraud(cdr)
        
        # Send to Prometheus/Alertmanager if fraud detected
        if result['is_fraud'] and result['confidence'] > 0.7:
            send_alert_to_prometheus(cdr, result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with: uvicorn ml_service:app --host 0.0.0.0 --port 8001
if __name__ == "__main__":
    import uvicorn
    detector = FraudDetectionEngine()
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
