#!/usr/bin/env python3
"""
Bulk CDR Data Sender
Loads 100+ customer records from JSON file and sends them to RabbitMQ for fraud detection
"""

import pika
import json
import sys
import time
import argparse
import os
from pathlib import Path

class BulkCDRSender:
    def __init__(self, host="rabbitmq", username="guest", password="guest", queue_name="CDR"):
        self.host = host
        self.username = username
        self.password = password
        self.queue_name = queue_name
        self._connection = None
        self._channel = None
        self.sent_count = 0
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
            
            # Declare queue
            self._channel.queue_declare(queue=self.queue_name, durable=True)
            
            print(f"Connected to RabbitMQ at {self.host}")
            print(f"Queue: {self.queue_name}")
        except Exception as e:
            print(f"Connection error: {e}")
            raise
    
    def closeConnection(self):
        """Close RabbitMQ connection"""
        if self._channel:
            self._channel.close()
        if self._connection:
            self._connection.close()
    
    def send_cdr(self, cdr_record):
        """Send a single CDR record to RabbitMQ"""
        try:
            message_json = json.dumps(cdr_record)
            
            self._channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=message_json,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            self.sent_count += 1
            
            # Progress indicator every 10 messages
            if self.sent_count % 10 == 0:
                print(f"  Sent {self.sent_count} CDR records...")
                
        except Exception as e:
            print(f"Error sending CDR: {e}")
            raise
    
    def send_from_file(self, file_path):
        """Load CDRs from JSON file and send them to RabbitMQ"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                print("JSON file must contain an array of CDR records")
                return 0
            
            print(f"Loading {len(data)} CDR records from {Path(file_path).name}")
            
            for i, cdr in enumerate(data):
                self.send_cdr(cdr)
            
            print(f"Successfully sent {self.sent_count} CDR records!")
            print(f"  Fraud flagged: {sum(1 for r in data if r.get('fraud_flag'))}")
            print(f"  Normal transactions: {sum(1 for r in data if not r.get('fraud_flag'))}")
            
            return self.sent_count
            
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            return 0
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bulk CDR Data Sender - Load customer records from JSON file"
    )
    parser.add_argument(
        "file",
        help="Path to JSON file with CDR records"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("RABBITMQ_HOST", "127.0.0.1"),
        help="RabbitMQ host (default: 127.0.0.1 or env var RABBITMQ_HOST)"
    )
    parser.add_argument(
        "--username",
        default=os.getenv("RABBITMQ_USER", "myuser"),
        help="RabbitMQ username (default: myuser or env var RABBITMQ_USER)"
    )
    parser.add_argument(
        "--password",
        default=os.getenv("RABBITMQ_PASSWORD", "mypassword"),
        help="RabbitMQ password (default: mypassword or env var RABBITMQ_PASSWORD)"
    )
    parser.add_argument(
        "--queue",
        default=os.getenv("CDR_QUEUE", "CDR"),
        help="CDR queue name (default: CDR or env var CDR_QUEUE)"
    )
    
    args = parser.parse_args()
    
    try:
        sender = BulkCDRSender(
            host=args.host,
            username=args.username,
            password=args.password,
            queue_name=args.queue
        )
        
        sender.send_from_file(args.file)
        sender.closeConnection()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
