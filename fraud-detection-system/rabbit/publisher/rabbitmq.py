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
        self._connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host, credentials=cred, heartbeat=30, blocked_connection_timeout=300))
        self._channel = self._connection.channel()

        self._channel.queue_declare(queue=self.queue_name, durable=True, auto_delete=False)
    
    def publish(self, msg: dict):
        message = json.dumps(msg)

        i = 0
        for i in range(4): #reconnection retry just in case
            if(self._connection.is_open):
                self._channel.basic_publish(exchange='', routing_key=self.queue_name, body=message)
                break
            else:
                print(f"Reconneting to {self.host}")
                self.initConnection()
            i += 1

        print(f"Published: {message}")


    def closeConnection(self):
        self._channel.close()
        self._connection.close()

