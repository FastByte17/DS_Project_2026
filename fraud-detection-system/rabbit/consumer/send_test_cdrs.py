#!/usr/bin/env python
"""
Test script for Fraud Detection Consumer
Sends sample CDR messages to RabbitMQ for processing
"""

import pika
import json
import os
import time
from typing import Dict, List

def send_test_cdr(
    host="rabbitmq",
    username="guest",
    password="guest",
    queue_name="CDR"
):
    """Send test CDR messages to RabbitMQ"""
    
    # Sample CDR records with varying fraud indicators
    test_cdrs = [
        {
            "description": "Normal transaction",
            "cdr": {
                "customer_id": "CUST001",
                "full_name": "Alice Johnson",
                "mobile_number": "+1234567890",
                "city": "New York",
                "sim_serial_number": "SIM001",
                "sim_status": "active",
                "imei": "123456789012345",
                "transaction_id": "TXN20260227001",
                "time_stamp": "2026-02-27T20:30:00Z",
                "type": "local_call",
                "amount_eur": 50.00,
                "risk_score": 0.2,
                "fraud_flag": False,
                "fraud_type": None
            }
        },
        {
            "description": "High-risk score",
            "cdr": {
                "customer_id": "CUST002",
                "full_name": "Bob Smith",
                "mobile_number": "+2345678901",
                "city": "London",
                "sim_serial_number": "SIM002",
                "sim_status": "active",
                "imei": "234567890123456",
                "transaction_id": "TXN20260227002",
                "time_stamp": "2026-02-27T20:31:00Z",
                "type": "international_call",
                "amount_eur": 500.00,
                "risk_score": 0.85,  # High risk
                "fraud_flag": False,
                "fraud_type": None
            }
        },
        {
            "description": "High-value transaction",
            "cdr": {
                "customer_id": "CUST003",
                "full_name": "Charlie Brown",
                "mobile_number": "+3456789012",
                "city": "Paris",
                "sim_serial_number": "SIM003",
                "sim_status": "active",
                "imei": "345678901234567",
                "transaction_id": "TXN20260227003",
                "time_stamp": "2026-02-27T20:32:00Z",
                "type": "premium_service",
                "amount_eur": 15000.00,  # Over €10,000 limit
                "risk_score": 0.5,
                "fraud_flag": False,
                "fraud_type": None
            }
        },
        {
            "description": "Suspicious SIM status",
            "cdr": {
                "customer_id": "CUST004",
                "full_name": "Diana Prince",
                "mobile_number": "+4567890123",
                "city": "Berlin",
                "sim_serial_number": "SIM004",
                "sim_status": "suspended",  # Suspicious status
                "imei": "456789012345678",
                "transaction_id": "TXN20260227004",
                "time_stamp": "2026-02-27T20:33:00Z",
                "type": "international_call",
                "amount_eur": 200.00,
                "risk_score": 0.3,
                "fraud_flag": False,
                "fraud_type": None
            }
        },
        {
            "description": "Pre-flagged as fraud",
            "cdr": {
                "customer_id": "CUST005",
                "full_name": "Eve Wilson",
                "mobile_number": "+5678901234",
                "city": "Madrid",
                "sim_serial_number": "SIM005",
                "sim_status": "active",
                "imei": "567890123456789",
                "transaction_id": "TXN20260227005",
                "time_stamp": "2026-02-27T20:34:00Z",
                "type": "international_call",
                "amount_eur": 300.00,
                "risk_score": 0.4,
                "fraud_flag": True,  # Pre-flagged
                "fraud_type": "sim_box"
            }
        },
        {
            "description": "Moderate risk - needs ML/LLM",
            "cdr": {
                "customer_id": "CUST006",
                "full_name": "Frank Miller",
                "mobile_number": "+6789012345",
                "city": "Amsterdam",
                "sim_serial_number": "SIM006",
                "sim_status": "active",
                "imei": "678901234567890",
                "transaction_id": "TXN20260227006",
                "time_stamp": "2026-02-27T20:35:00Z",
                "type": "international_call",
                "amount_eur": 750.00,
                "risk_score": 0.55,  # Moderate risk (0.3 < score < 0.8)
                "fraud_flag": False,
                "fraud_type": None
            }
        }
    ]
    
    try:
        # Connect to RabbitMQ
        cred = pika.PlainCredentials(username, password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host,
                credentials=cred,
                heartbeat=30,
                blocked_connection_timeout=300
            )
        )
        channel = connection.channel()
        
        # Declare queue
        channel.queue_declare(queue=queue_name, durable=True)
        
        print(f"Connected to RabbitMQ at {host}")
        print(f"Sending {len(test_cdrs)} test CDR messages to queue: {queue_name}")
        print("-" * 80)
        
        # Send test messages
        for i, test_case in enumerate(test_cdrs, 1):
            cdr = test_case["cdr"]
            description = test_case["description"]
            
            # Send message
            channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(cdr),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            print(f"{i}. {description}")
            print(f"   Transaction ID: {cdr['transaction_id']}")
            print(f"   Customer: {cdr['full_name']} ({cdr['customer_id']})")
            print(f"   Amount: €{cdr['amount_eur']:.2f}")
            print(f"   Risk Score: {cdr['risk_score']:.2f}")
            print(f"   Status: Sent")
            print()
            
            # Small delay between messages
            time.sleep(0.2)
        
        connection.close()
        print("-" * 80)
        print(f"Successfully sent {len(test_cdrs)} test messages!")
        print("\nYou should see these messages processed in the fraud detection consumer.")
        print("Check the FRAUD_CDR and NORMAL_CDR queues in RabbitMQ Management UI:")
        print("http://localhost:15672 (username: guest, password: guest)")
        
    except pika.exceptions.AMQPConnectionError:
        print(f"Error: Could not connect to RabbitMQ at {host}:{5672}")
        print(f"  Make sure RabbitMQ is running and accessible")
    except Exception as e:
        print(f"Error sending test messages: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Send test CDR messages to fraud detection consumer"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        help="RabbitMQ host (default: rabbitmq)"
    )
    parser.add_argument(
        "--username",
        default=os.getenv("RABBITMQ_USER", "guest"),
        help="RabbitMQ username (default: guest)"
    )
    parser.add_argument(
        "--password",
        default=os.getenv("RABBITMQ_PASSWORD", "guest"),
        help="RabbitMQ password (default: guest)"
    )
    parser.add_argument(
        "--queue",
        default=os.getenv("CDR_INPUT_QUEUE", "CDR"),
        help="CDR input queue name (default: CDR)"
    )
    
    args = parser.parse_args()
    
    send_test_cdr(
        host=args.host,
        username=args.username,
        password=args.password,
        queue_name=args.queue
    )
