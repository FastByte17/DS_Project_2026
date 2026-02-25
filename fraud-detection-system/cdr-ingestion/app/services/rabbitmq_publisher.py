"""RabbitMQ Publisher Service for CDR ingestion"""
import pika
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.config import settings


logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RabbitMQPublisher:
    """Handles publishing of CDR records to RabbitMQ"""
    
    def __init__(self, queue_name: str = None, host: str = None):
        """Initialize RabbitMQ Publisher"""
        self.queue_name = queue_name or settings.rabbitmq_queue
        self.host = host or settings.rabbitmq_host
        self.port = settings.rabbitmq_port
        self.username = settings.rabbitmq_user
        self.password = settings.rabbitmq_password
        
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        
        logger.info(f"RabbitMQ Publisher initialized for queue: {self.queue_name}")
    
    def init_connection(self) -> bool:
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=3,
                retry_delay=2,
                heartbeat=600,
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                auto_delete=False
            )
            
            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            return False
    
    def publish(self, message: Dict[str, Any]) -> bool:
        """Publish a CDR record to RabbitMQ"""
        if not self.channel or self.connection.is_closed:
            logger.warning("Channel closed, reconnecting...")
            if not self.init_connection():
                return False
        
        try:
            message_body = json.dumps(message, cls=DateTimeEncoder)
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type='application/json'
                )
            )
            
            logger.info(f"Published CDR {message.get('call_id')} to {self.queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            return False
    
    def close_connection(self) -> None:
        """Close RabbitMQ connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {str(e)}")
    
    def health_check(self) -> bool:
        """Check if RabbitMQ connection is healthy"""
        try:
            return self.connection is not None and not self.connection.is_closed
        except Exception:
            return False