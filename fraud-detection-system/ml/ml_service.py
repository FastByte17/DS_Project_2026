import requests
import json
import pika
import threading
import time
import numpy as np
from collections import deque
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from fastapi.responses import Response
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import os

# prometheus metrics
fraud_detected = Counter('fraud_detected_total', 'Frauds detected', ['method', 'fraud_type'])
llm_latency = Histogram('llm_analysis_duration_seconds', 'LLM analysis time')
cdr_processed = Counter('cdr_processed_total', 'Total CDRs processed', ['status'])

# FastAPI app
app = FastAPI(title="ML Fraud Detection Service")

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
        label = 1 if cdr.get('fraud_flag', False) or cdr.get('risk_score', 0) > 0.5 else 0
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
                'explanation': 'Failed to parse LLM response'
            }

# initialize detector
detector = FraudDetectionEngine()

# rabbitMQ Consumer
class RabbitMQConsumer:
    def __init__(
            self, 
            host='rabbitmq', 
            queue='CDR', 
            username=os.getenv("RABBITMQ_DEFAULT_USER", "NOT_SET"),
            password=os.getenv("RABBITMQ_DEFAULT_PASS", "NOT_SET")
            ):
        self.host = host
        self.queue = queue
        self.connection = None
        self.channel = None
        self.username=username
        self.password=password
        
    def connect(self):
        """connect to rabbitMQ with retry logic"""
        max_retries = 10
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                _credentials = pika.PlainCredentials(self.username, self.password)
                print(f"Connecting to rabbitMQ at {self.host}... (attempt {attempt + 1}/{max_retries})")
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self.host,
                        heartbeat=600,
                        blocked_connection_timeout=300,
                        credentials=_credentials
                    )
                )
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue, durable=True)
                print(f"connected to rabbitMQ queue: {self.queue}")
                return True
            except Exception as e:
                print(f"rabbitMQ connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("failed to connect to rabbitMQ after all retries")
                    return False
    
    def callback(self, ch, method, properties, body):
        """process incoming CDR from rabbitMQ"""
        try:
            # parse CDR
            cdr = json.loads(body)
            print(f"\nreceived CDR: {cdr.get('transaction_id', 'Unknown')}")
            
            # detect fraud
            result = detector.detect_fraud(cdr)
            
            # log result
            if result['is_fraud']:
                print(f" FRAUD DETECTED!")
                print(f"   Type: {result.get('fraud_type')}")
                print(f"   Confidence: {result.get('confidence'):.2%}")
                print(f"   Method: {result.get('method')}")
                print(f"   Explanation: {result.get('explanation')}")
                
                # send alert
                send_alert_to_prometheus(cdr, result)
                cdr_processed.labels(status='fraud').inc()
            else:
                print(f"clean transaction")
                cdr_processed.labels(status='clean').inc()
            
            # acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"error processing CDR: {e}")
            cdr_processed.labels(status='error').inc()
            # reject and don't requeue if processing fails
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def start_consuming(self):
        """start consuming messages from rabbitMQ"""
        try:
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=self.queue,
                on_message_callback=self.callback
            )
            
            print(f"\nlistening for CDRs on queue: {self.queue}")
            print("press CTRL+C to stop\n")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            print("\nstopping consumer...")
            self.stop()
        except Exception as e:
            print(f"consumer error: {e}")
            self.stop()
    
    def stop(self):
        """stop consuming and close connection"""
        if self.channel:
            self.channel.stop_consuming()
        if self.connection:
            self.connection.close()
        print("disconnected from rabbitMQ")

# global consumer instance
consumer = None

def send_alert_to_prometheus(cdr: Dict, detection_result: Dict):
    """Send alert to Prometheus Alertmanager"""
    try:
        alert = {
            "labels": {
                "alertname": "FraudDetected",
                "severity": "critical" if detection_result['confidence'] > 0.9 else "warning",
                "method": detection_result['method'],
                "customer_id": str(cdr.get('customer_id', 'Unknown')),
                "mobile_number": str(cdr.get('mobile_number', 'Unknown')),
                "transaction_id": str(cdr.get('transaction_id', 'Unknown'))
            },
            "annotations": {
                "summary": f"Fraud detected: {detection_result['fraud_type']}",
                "description": detection_result['explanation'],
                "confidence": str(detection_result['confidence']),
                "1fraud_type": detection_result['fraud_type'],
                "customer_name": str(cdr.get('full_name', 'Unknown')),
                "city": str(cdr.get('city', 'Unknown')),
                "amount_eur": str(cdr.get('amount_eur', 0))
            }
        }
        
        # send to Alertmanager
        response = requests.post(
            "http://alertmanager:9093/api/v2/alerts",
            json=[alert],
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"alert sent to grafana")
        else:
            print(f"alert failed: {response.status_code}")
            
    except Exception as e:
        print(f"failed to send alert: {e}")

# FastAPI Endpoints
@app.on_event("startup")
async def startup_event():
    """start rabbitMQ consumer on startup"""
    global consumer
    
    def start_consumer():
        consumer = RabbitMQConsumer(host='rabbitmq', queue='CDR')
        if consumer.connect():
            consumer.start_consuming()
    
    # start consumer in background thread
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()
    print("ml service started, rabbitMQ consumer running in background")

@app.post("/detect")
async def detect_fraud_endpoint(cdr: Dict):
    """manual fraud detection endpoint (for testing)"""
    try:
        result = detector.detect_fraud(cdr)
        
        if result['is_fraud'] and result['confidence'] > 0.7:
            send_alert_to_prometheus(cdr, result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """health check endpoint"""
    return {"status": "healthy", "service": "ml-fraud-detection"}

@app.get("/metrics")
async def metrics():
    """prometheus metrics endpoint"""
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain"
    )

@app.get("/model/status")
async def model_status():
    """returns the current state of the Random Forest model"""
    return {
        "rf_trained": detector.rf_trained,
        "buffer_size": len(detector.training_buffer),
        "batch_size": detector.BATCH_SIZE,
        "samples_until_next_train": max(0, detector.BATCH_SIZE - len(detector.training_buffer)),
        "rf_estimators": detector.rf_model.n_estimators if detector.rf_trained else None,
    }

@app.get("/")
async def root():
    """root endpoint"""
    return {
        "service": "ML Fraud Detection Service",
        "version": "2.0.0",
        "status": "running",
        "rabbitmq": "consuming from cdr_queue",
        "endpoints": {
            "detect": "POST /detect (manual testing)",
            "health": "GET /health",
            "metrics": "GET /metrics"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)