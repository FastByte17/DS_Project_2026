from rabbitmq import RabbitMQConsumer
from prometheus_client import start_http_server
import os

consumer = RabbitMQConsumer(
    host="rabbitmq",  # Docker service name
    queue_name="CDR",
)

if __name__ == "__main__":
    print("Starting consumer")
    start_http_server(int(os.getenv("PROMETHEUS_PORT", default=8123)))
    consumer.start()