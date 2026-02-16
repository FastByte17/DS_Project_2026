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
            "endDateTime": "String (timestamp)",
            "id": "String (identifier)",
            "joinWebUrl": "String",
            "lastModifiedDateTime": "String (timestamp)",
            "modalities": ["string"],
            "organizer": {"@odata.type": "microsoft.graph.identitySet"},
            "participants": [{"@odata.type": "microsoft.graph.identitySet"}],
            "startDateTime": "String (timestamp)",
            "type": "String",
            "version": "Int64"
        })
        return {"status": 100, "message": f"Published to queue {publisher.queue_name}"}
    except Exception as e:
        print(e)
        return {"status": 404, "message": e}

