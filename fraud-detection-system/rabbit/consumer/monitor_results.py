#!/usr/bin/env python
"""
Monitor Fraud Detection Results
Displays messages from FRAUD_CDR and NORMAL_CDR queues
"""

import pika
import json
import os
import sys
from typing import Dict, Optional


class QueueMonitor:
    def __init__(
        self,
        host="rabbitmq",
        username="guest",
        password="guest",
        fraud_queue="FRAUD_CDR",
        normal_queue="NORMAL_CDR"
    ):
        self.host = host
        self.username = username
        self.password = password
        self.fraud_queue = fraud_queue
        self.normal_queue = normal_queue
        self._connection = None
        self._channel = None
        self.connect()
    
    def connect(self):
        """Connect to RabbitMQ"""
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
            self._channel.queue_declare(queue=self.fraud_queue, durable=True)
            self._channel.queue_declare(queue=self.normal_queue, durable=True)
            
            print(f"Connected to RabbitMQ at {self.host}")
        except Exception as e:
            print(f"Error connecting to RabbitMQ: {e}")
            raise
    
    def close(self):
        """Close connection"""
        if self._channel:
            self._channel.close()
        if self._connection:
            self._connection.close()
    
    def get_queue_stats(self) -> Dict:
        """Get message count for each queue"""
        try:
            fraud_method = self._channel.queue_declare(
                queue=self.fraud_queue,
                passive=True
            )
            normal_method = self._channel.queue_declare(
                queue=self.normal_queue,
                passive=True
            )
            
            return {
                'fraud': fraud_method.method.message_count,
                'normal': normal_method.method.message_count
            }
        except Exception as e:
            return {'fraud': 0, 'normal': 0}
    
    def display_queue_messages(self, queue_name: str, limit: int = 10):
        """Display messages from a queue without consuming them"""
        print(f"\n📦 Messages in {queue_name} queue (preview, up to {limit}):")
        print("-" * 100)
        
        count = 0
        while count < limit:
            try:
                method, properties, body = self._channel.basic_get(
                    queue=queue_name,
                    auto_ack=False  # Don't acknowledge, so messages stay in queue
                )
                
                if method is None:
                    break
                
                count += 1
                message = json.loads(body)
                
                # Display message
                self.print_message(count, queue_name, message)
                
                # Put message back (using basic_nack with requeue)
                self._channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True
                )
                
            except Exception as e:
                print(f"Error reading message: {e}")
                break
        
        if count == 0:
            print("  (No messages in queue)")
        print("-" * 100)
    
    def print_message(self, count: int, queue_name: str, message: Dict):
        """Format and print a message"""
        try:
            cdr = message.get('cdr', {})
            result = message.get('detection_result', {})
            
            emoji = "🚨" if result.get('is_fraud') else "✅"
            
            print(f"\n{emoji} Message {count}:")
            print(f"  Transaction ID: {cdr.get('transaction_id', 'N/A')}")
            print(f"  Customer: {cdr.get('full_name', 'N/A')} ({cdr.get('customer_id', 'N/A')})")
            print(f"  Mobile: {cdr.get('mobile_number', 'N/A')}")
            print(f"  Amount: €{cdr.get('amount_eur', 0):.2f}")
            print(f"  Fraud Status: {result.get('is_fraud', False)}")
            print(f"  Confidence: {result.get('confidence', 0):.2%}")
            print(f"  Method: {result.get('method', 'N/A')}")
            print(f"  Fraud Type: {result.get('fraud_type', 'N/A')}")
            print(f"  Explanation: {result.get('explanation', 'N/A')}")
            
            if result.get('suspicious_indicators'):
                print(f"  Suspicious Indicators: {', '.join(result['suspicious_indicators'])}")
            
            if result.get('recommended_action'):
                print(f"  Recommended Action: {result['recommended_action']}")
        
        except Exception as e:
            print(f"  Error parsing message: {e}")
            print(f"  Raw: {json.dumps(message, indent=2)[:200]}...")
    
    def display_dashboard(self):
        """Display interactive statistics dashboard"""
        print("\n" + "=" * 100)
        print("🎯 FRAUD DETECTION MONITORING DASHBOARD")
        print("=" * 100)
        
        stats = self.get_queue_stats()
        
        print(f"Queue Statistics:")
        print(f"  🚨 Fraudulent Transactions (FRAUD_CDR):  {stats['fraud']} messages")
        print(f"  ✅ Normal Transactions (NORMAL_CDR):    {stats['normal']} messages")
        print(f"  📈 Total Processed:                     {stats['fraud'] + stats['normal']} messages")
        
        if stats['fraud'] > 0:
            fraud_rate = (stats['fraud'] / (stats['fraud'] + stats['normal'])) * 100
            print(f"  Fraud Rate:                          {fraud_rate:.1f}%")
        
        print("\n" + "-" * 100)
        
        # Display fraud messages
        if stats['fraud'] > 0:
            self.display_queue_messages(self.fraud_queue, limit=5)
        else:
            print(f"\n✅ No fraudulent transactions detected!")
        
        # Display normal messages
        if stats['normal'] > 0:
            self.display_queue_messages(self.normal_queue, limit=5)
        else:
            print(f"\n📦 No normal transactions processed yet.")
    
    def monitor_continuous(self, interval: int = 5):
        """Continuously monitor queues"""
        import time
        
        print(f"\n🔄 Monitoring fraud detection queues (updating every {interval}s)")
        print("Press CTRL+C to stop...\n")
        
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                self.display_dashboard()
                print(f"\n⏰ Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("Press CTRL+C to stop monitoring...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Monitor fraud detection results in RabbitMQ queues"
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
        "--fraud-queue",
        default=os.getenv("FRAUD_QUEUE", "FRAUD_CDR"),
        help="Fraud queue name (default: FRAUD_CDR)"
    )
    parser.add_argument(
        "--normal-queue",
        default=os.getenv("NORMAL_QUEUE", "NORMAL_CDR"),
        help="Normal queue name (default: NORMAL_CDR)"
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Continuously monitor queues (auto-refresh)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Monitoring interval in seconds (default: 5)"
    )
    
    args = parser.parse_args()
    
    try:
        monitor = QueueMonitor(
            host=args.host,
            username=args.username,
            password=args.password,
            fraud_queue=args.fraud_queue,
            normal_queue=args.normal_queue
        )
        
        if args.monitor:
            monitor.monitor_continuous(interval=args.interval)
        else:
            monitor.display_dashboard()
        
        monitor.close()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
