import pika
import json
import os
import sys
import time
import requests
from typing import Dict
from threading import Thread
from prometheus_client import start_http_server, generate_latest, CONTENT_TYPE_LATEST

# Add ml service to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ml'))

from ml_service import FraudDetectionEngine, fraud_detected, llm_latency

class FraudDetectionConsumer:
    
    def __init__(
        self,
        host="rabbitmq",
        username=os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
        password=os.getenv("RABBITMQ_DEFAULT_PASS", "guest"),
        input_queue_name="CDR",
        fraud_queue_name="FRAUD_CDR",
        normal_queue_name="NORMAL_CDR",
        ollama_host="http://ollama:11434",
        metrics_port=8000
    ):
        self.host = host
        self.username = username
        self.password = password
        self.input_queue_name = input_queue_name
        self.fraud_queue_name = fraud_queue_name
        self.normal_queue_name = normal_queue_name
        self.metrics_port = metrics_port
        
        self._connection = None
        self._channel = None
        
        # Initialize Prometheus metrics endpoint
        try:
            start_http_server(metrics_port)
            print(f"Prometheus metrics server started on port {metrics_port}")
            print(f"  http://localhost:{metrics_port}/metrics")
        except Exception as e:
            print(f"Warning: Could not start metrics server on port {metrics_port}: {e}")
        
        # Initialize fraud detection engine
        try:
            self.detector = FraudDetectionEngine(ollama_host=ollama_host)
            print(f"Fraud Detection Engine initialized with Ollama at {ollama_host}")
        except Exception as e:
            print(f"Error initializing Fraud Detection Engine: {e}")
            self.detector = None
        
        self.initConnection()
    
    def initConnection(self):
        """Initialize RabbitMQ connection"""
        try:
            cred = pika.PlainCredentials(self.username, self.password)
            self._connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host,
                    credentials=cred,
                    heartbeat=30,
                    blocked_connection_timeout=300
                )
            )
            self._channel = self._connection.channel()
            
            # Declare queues
            self._channel.queue_declare(queue=self.input_queue_name, durable=True)
            self._channel.queue_declare(queue=self.fraud_queue_name, durable=True)
            self._channel.queue_declare(queue=self.normal_queue_name, durable=True)
            
            print(f"Connected to RabbitMQ at {self.host}")
            print(f"Input queue: {self.input_queue_name}")
            print(f"Fraud queue: {self.fraud_queue_name}")
            print(f"Normal queue: {self.normal_queue_name}")
        except Exception as e:
            print(f"Connection error: {e}")
            raise
    
    def closeConnection(self):
        """Close RabbitMQ connection"""
        if self._channel:
            self._channel.close()
        if self._connection:
            self._connection.close()
        print("Connection closed")
    
    def route_message(self, detection_result: Dict, cdr: Dict):
        """Route message to appropriate queue based on fraud detection result"""
        try:
            message_json = json.dumps({
                'cdr': cdr,
                'detection_result': detection_result,
                'timestamp': time.time()
            })
            
            if detection_result['is_fraud']:
                # Route to fraud queue
                self._channel.basic_publish(
                    exchange='',
                    routing_key=self.fraud_queue_name,
                    body=message_json,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type='application/json'
                    )
                )
                print(f"[FRAUD] {cdr.get('transaction_id', 'N/A')}: "
                      f"{detection_result['fraud_type']} "
                      f"(confidence: {detection_result['confidence']:.2f})")
                
                # Send alert if high confidence fraud
                if detection_result['confidence'] > 0.7:
                    self.send_alert_to_prometheus(cdr, detection_result)
            else:
                # Route to normal queue
                self._channel.basic_publish(
                    exchange='',
                    routing_key=self.normal_queue_name,
                    body=message_json,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json'
                    )
                )
                print(f"[NORMAL] {cdr.get('transaction_id', 'N/A')}: "
                      f"Confidence: {1 - detection_result['confidence']:.2f}")
        except Exception as e:
            print(f"Error routing message: {e}")
            raise
    
    def process_message(self, cdr: Dict):
        """Process CDR message through fraud detection engine"""
        if not self.detector:
            print("Fraud Detection Engine not available")
            return

        try:
            transaction_id = cdr.get('transaction_id', 'N/A')
            customer_id = cdr.get('customer_id', 'N/A')
            
            print(f"Processing CDR: {transaction_id} (Customer: {customer_id})")
            
            # Run fraud detection
            detection_result = self.detector.detect_fraud(cdr)
            
            # Route the message
            self.route_message(detection_result, cdr)
            
        except Exception as e:
            print(f"Error processing message: {e}")
            raise
    
    def send_alert_to_prometheus(self, cdr: Dict, detection_result: Dict):
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
            response = requests.post(
                "http://alertmanager:9093/api/v1/alerts",
                json=[alert],
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"  Alert sent to Prometheus")
            else:
                print(f"  Alert response: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"  Could not reach Alertmanager at http://alertmanager:9093")
        except Exception as e:
            print(f"  Error sending alert: {e}")
    
    def on_message(self, ch, method, properties, body):
        """Callback when message is received from queue"""
        try:
            message = json.loads(body)
            self.process_message(message)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start(self):
        """Start consuming messages from RabbitMQ"""
        try:
            self.initConnection()
            print(f"Starting Fraud Detection Consumer")
            print(f"Consuming from queue: {self.input_queue_name}")
            
            self._channel.basic_qos(prefetch_count=1)  # Process one message at a time
            
            self._channel.basic_consume(
                queue=self.input_queue_name,
                on_message_callback=self.on_message,
            )
            
            print("Waiting for CDR messages... (Press CTRL+C to exit)")
            self._channel.start_consuming()
            
        except KeyboardInterrupt:
            print("Stopping consumer...")
            self.closeConnection()
        except Exception as e:
            print(f"Consumer error: {e}")
            self.closeConnection()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Fraud Detection Consumer for RabbitMQ CDR messages"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        help="RabbitMQ host (default: rabbitmq or env var RABBITMQ_HOST)"
    )
    parser.add_argument(
        "--username",
        default=os.getenv("RABBITMQ_USER", "guest"),
        help="RabbitMQ username (default: guest or env var RABBITMQ_USER)"
    )
    parser.add_argument(
        "--password",
        default=os.getenv("RABBITMQ_PASSWORD", "guest"),
        help="RabbitMQ password (default: guest or env var RABBITMQ_PASSWORD)"
    )
    parser.add_argument(
        "--input-queue",
        default=os.getenv("CDR_INPUT_QUEUE", "CDR"),
        help="CDR input queue name (default: CDR or env var CDR_INPUT_QUEUE)"
    )
    parser.add_argument(
        "--fraud-queue",
        default=os.getenv("FRAUD_QUEUE", "FRAUD_CDR"),
        help="Fraud queue name (default: FRAUD_CDR or env var FRAUD_QUEUE)"
    )
    parser.add_argument(
        "--normal-queue",
        default=os.getenv("NORMAL_QUEUE", "NORMAL_CDR"),
        help="Normal queue name (default: NORMAL_CDR or env var NORMAL_QUEUE)"
    )
    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", "http://ollama:11434"),
        help="Ollama host (default: http://ollama:11434 or env var OLLAMA_HOST)"
    )
    
    args = parser.parse_args()
    
    consumer = FraudDetectionConsumer(
        host=args.host,
        username=args.username,
        password=args.password,
        input_queue_name=args.input_queue,
        fraud_queue_name=args.fraud_queue,
        normal_queue_name=args.normal_queue,
        ollama_host=args.ollama_host
    )
    
    consumer.start()
