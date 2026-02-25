## RabbitMQ Pub/Sub sample

### Start up containers rabbit, consumer, publisher
`docker compose up`

OR in detached mode

`docker compose up -d` 

Should start total of three containers (check docker-compose.yml).

### Test flow

- After running compose
- Go to http://0.0.0.0:8081/docs 
    - Should open a swagger UI with two endpoints /root and /publish
- Post to /publish endpoint
    - sends dummy content to rabbitmq CDR queue
- View consumer container logs to see the published message
    - `docker container logs python_consumer_1 -f`

### Utilizing consumer/publisher elsewhere

Directory *./rabbit/consumer* contains the sample code for the consumer. <br>
 The rabbitmq.py has the needed basic functionality to connect and ingest messages from a queue. 

Directory *./rabbit/publisher* contains the sample code for the publisher. <br> 
The rabbitmq.py has the needed basic functionality to connect to a queue and publish messages to that queue. <br>
NOTE the main.py in publisher is more complex because it starts up a FastApi service so that publishing can be triggered via HTTP requests. 


### RabbitMQ dashboard

- Add prometheus as data source
- Use rabbitmq dashboard template id: 10991