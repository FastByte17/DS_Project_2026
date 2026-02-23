from fastapi import FastAPI
from contextlib import asynccontextmanager
from rabbitmq import RabbitMQPublisher


@asynccontextmanager
async def lifespan(app: FastAPI):
    #Startup
    publisher = RabbitMQPublisher(queue_name="CDR")
    publisher.initConnection()

    app.state.rabbitmq = publisher

    yield

    #Shutdown
    publisher.closeConnection()


app = FastAPI(lifespan=lifespan)

def getPublisher() -> RabbitMQPublisher:
    return app.state.rabbitmq

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/publish")
async def httpPublish():
    
    try:
        publisher = getPublisher()

        publisher.publish({
            "record_id": "CDR-20260223-0001",
            "call_type": "outbound",
            "call_status": "completed",
            "caller": {
                "phone_number": "+1-202-555-0147",
                "extension": "101",
                "device_id": "DEV-78945",
                "ip_address": "192.168.1.25"
            },
            "callee": {
                "phone_number": "+1-303-555-0198",
                "country": "US",
                "network": "Verizon"
            },
            "timestamps": {
                "start_time_utc": "2026-02-23T14:32:18Z",
                "answer_time_utc": "2026-02-23T14:32:25Z",
                "end_time_utc": "2026-02-23T14:45:42Z",
                "duration_seconds": 797,
                "billable_seconds": 780
            },
            "routing": {
                "source_trunk": "SIP-Trunk-01",
                "destination_trunk": "PSTN-Gateway-03",
                "codec": "G.711",
                "qos": {
                "packet_loss_percent": 0.3,
                "jitter_ms": 5,
                "latency_ms": 42
                }
            },
            "billing": {
                "currency": "USD",
                "rate_per_minute": 0.05,
                "total_cost": 0.65,
                "billing_account_id": "ACC-556677"
            },
            "location": {
                "caller_country": "US",
                "caller_city": "Washington",
                "callee_country": "US",
                "callee_city": "Denver"
            }
        })
        return {"status": 100, "message": f"Published to queue {publisher.queue_name}"}
    except Exception as e:
        print(f"Error: {e}")
        return {"status": 404, "message": e}

