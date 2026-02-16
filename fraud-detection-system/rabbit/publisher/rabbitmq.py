import pika
import json
import os

class RabbitMQPublisher:

    def __init__(
        self,
        host="rabbitmq",
        username=os.getenv("RABBITMQ_DEFAULT_USER", "NOT_SET"),
        password=os.getenv("RABBITMQ_DEFAULT_PASS", "NOT_SET"),
        queue_name="default_queue",
    ):
        self.host = host
        self.username = username
        self.password = password
        self.queue_name = queue_name
        self._connection = None
        self._channel = None
        self.initConnection()

    def initConnection(self):        
        cred = pika.PlainCredentials(self.username, self.password)
        self._connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host, credentials=cred))
        self._channel = self._connection.channel()

        self._channel.queue_declare(queue=self.queue_name)
    
    def publish(self, msg: dict):
        message = json.dumps(msg)
        self._channel.basic_publish(exchange='', routing_key=self.queue_name, body=message)
        print(f"Published: {message}")

    def closeConnection(self):
        self._channel.close()
        self._connection.close()

