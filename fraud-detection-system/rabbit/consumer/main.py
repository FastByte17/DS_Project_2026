from rabbitmq import RabbitMQConsumer

# def process_message(message: dict):
#     print(f"Processing message: {message}")

consumer = RabbitMQConsumer(
    host="rabbitmq",  # Docker service name
    queue_name="CDR",
)

if __name__ == "__main__":
    print("Starting consumer")
    consumer.start()