import pika
import json
import os
import time

class RabbitMQConsumer:

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

    def closeConnection(self):
        self._channel.close()
        self._connection.close()

    def process_message(self, message: dict):
        
        ### ADD MESSAGE PROCESSING HERE ### 
        
        print(f"Processing message: {message}")
        time.sleep(5)

    def on_message(self, ch, method, properties, body):
        try:
            message = json.loads(body)
            self.process_message(message)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as e:
            print(f"Dumping Invalid json: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"Error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start(self):
        self.initConnection()
        print(f"Start consuming queue: {self.queue_name}")

        self._channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.on_message,
        )

        self._channel.start_consuming()

