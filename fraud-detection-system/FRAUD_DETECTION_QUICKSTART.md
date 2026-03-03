# Fraud Detection System - Quick Start Guide

## Overview

This guide will help you get the fraud detection system up and running. The system processes CDR (Call Detail Records) from RabbitMQ and classifies them as fraudulent or normal using machine learning and LLM validation.

## System Components

CDR Data Source
     |
     v
RabbitMQ (CDR Queue)
     |
     v
[Fraud Detector Consumer]
|- Rule-based checks (fast)
|- ML model prediction
|- LLM validation (uncertain cases)
     |
     v
RabbitMQ (Split Results)
|- FRAUD_CDR Queue
|- NORMAL_CDR Queue
     |
     v
Prometheus Alertmanager (High-confidence fraud alerts)

## Quick Start (5 minutes)

### Step 1: Start the Infrastructure

cd d:\Period\ 3\Distributed\ Systems\DS_Project_2026\fraud-detection-system\cdr-ingestion

Start CDR ingestion, RabbitMQ, and PostgreSQL
docker-compose up -d

Verify services are running
docker-compose ps

Expected output:
cdr_ingestion_1    (port 8080)
rabbitmq_1         (port 5672)
postgres_1         (port 5432)

### Step 2: Start Fraud Detection Consumer

In a new terminal:

cd d:\Period\ 3\Distributed\ Systems\DS_Project_2026\fraud-detection-system\rabbit

Option A: Run with Docker
docker-compose -f rabbit/docker-compose.yml up fraud_detector_consumer

Option B: Run standalone (Python)
cd consumer
python fraud_detector_consumer.py

You should see:
Connected to RabbitMQ at rabbitmq
Input queue: CDR
Fraud queue: FRAUD_CDR
Normal queue: NORMAL_CDR
Starting Fraud Detection Consumer

Waiting for CDR messages... (Press CTRL+C to exit)

### Step 3: Send Test Data

In another terminal:

cd d:\Period\ 3\Distributed\ Systems\DS_Project_2026\fraud-detection-system\rabbit\consumer

Send 6 test CDR messages
python send_test_cdrs.py

Or with custom RabbitMQ settings
python send_test_cdrs.py --host rabbitmq --username guest --password guest

You should see:
Connected to RabbitMQ at rabbitmq
Sending 6 test CDR messages to queue: CDR

1. Normal transaction
   Transaction ID: TXN20260227001
   Customer: Alice Johnson (CUST001)
   Amount: 50.00 EUR
   Risk Score: 0.20
   Status: Sent

Successfully sent 6 test messages!
```

### Step 4: Monitor Results

In another terminal:

```bash
cd d:\Period\ 3\Distributed\ Systems\DS_Project_2026\fraud-detection-system\rabbit\consumer

# View current queue statistics
python monitor_results.py

# Or continuously monitor with auto-refresh (every 5 seconds)
python monitor_results.py --monitor

# Or with custom interval (refresh every 10 seconds)
python monitor_results.py --monitor --interval 10

You should see output like:
FRAUD DETECTION MONITORING DASHBOARD

Queue Statistics:
  Fraudulent Transactions (FRAUD_CDR):  3 messages
  Normal Transactions (NORMAL_CDR):     3 messages
  Total Processed:                      6 messages
  Fraud Rate:                           50.0%

Messages in FRAUD_CDR queue:
Transaction ID: TXN20260227004
Customer: Diana Prince (CUST004)
Amount: 200.00 EUR
Fraud Status: True
Confidence: 95.00%
Method: rules
Fraud Type: suspicious_sim_status
Explanation: SIM status: suspended
Suspicious Indicators: []
Recommended Action: block

## How It Works

### Detection Pipeline

1. Rule-Based Detection (Fast path)
   - Checks blacklist, risk score, SIM status, amount
   - If any rule matches: Fraud detected
   - Takes ~1ms

2. ML Model Scoring
   - Uses trained RandomForest classifier
   - Returns fraud probability (0-1)
   - If score > 0.8: Fraud, if < 0.3: Normal
   - Takes ~10ms

3. LLM Validation (Uncertain cases)
   - For medium-confidence cases (0.3 score 0.8)
   - Sends to Ollama (Llama 3.2)
   - Gets detailed analysis
   - Takes ~500-2000ms

### Fraud Types

- sim_box - Compromised SIM used for fraud
- identity - Stolen identity fraud
- high_value - Unusual high amount
- sim_bypass - Device spoofing (IMEI/SIM mismatch)
- account_takeover - Unauthorized account access
- blacklisted_number - Number marked as fraudulent
- suspicious_sim_status - SIM compromised (suspended/blocked)
- high_risk_score - Pre-flagged as risky

## Web Interfaces

### RabbitMQ Management

http://localhost:15672
Username: guest
Password: guest

Monitor:
- CDR queue (input messages)
- FRAUD_CDR queue (detected fraud)
- NORMAL_CDR queue (normal transactions)
- Consumer activity

### Prometheus

http://localhost:9090

Useful queries:
Total frauds detected
fraud_detected_total

Which fraud types detected
fraud_detected_total{method="llm"}

LLM analysis latency
llm_analysis_duration_seconds
```

### Grafana

```
http://localhost:3000
Default: admin/admin
```

Connect Prometheus as data source and create dashboards.

## Testing Different Fraud Scenarios

The test data includes:

1. Normal Transaction - Should pass all checks
2. High Risk Score - Should trigger rule (score > 0.8)
3. High-Value TX - Should trigger rule (amount > 10000 EUR)
4. Suspicious SIM - Should trigger rule (SIM suspended)
5. Pre-flagged - Should trigger rule (fraud_flag=true)
6. Moderate Risk - Should use ML/LLM validation

Expected distribution:
- ~50% normal
- ~50% fraud

## Configuration

### Environment Variables

RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

Queues
CDR_INPUT_QUEUE=CDR
FRAUD_QUEUE=FRAUD_CDR
NORMAL_QUEUE=NORMAL_CDR

LLM
OLLAMA_HOST=http://ollama:11434

### Fraud Thresholds

Edit in ml_service.py:

ML score thresholds
if fraud_score > 0.8:  # High confidence fraud
    # Mark as fraud

if fraud_score < 0.3:  # High confidence normal
    # Mark as normal

Rule thresholds
if cdr.get('amount_eur', 0) > 10000:  # Adjust high-value threshold
    # Mark as fraud

if cdr.get('risk_score', 0) > 0.8:  # Adjust risk score threshold
    # Mark as fraud

## Troubleshooting

### Consumer not starting

Check logs
docker logs fraud_detector_consumer_1

Common issues:
- RabbitMQ not running: docker-compose -f rabbit/docker-compose.yml up rabbitmq
- Ollama not available: ollama serve
- Port conflicts: netstat -an | findstr :5672

### No messages in queues

Check if CDR ingestion is sending data
curl http://localhost:8080/health

Check RabbitMQ queues
Go to http://localhost:15672 and check CDR queue

Send test data manually
python send_test_cdrs.py

### High latency/memory usage

- LLM validation is memory-intensive
Options:
- Adjust ML thresholds to reduce LLM calls
- Use smaller model
- Increase server memory
- Process messages more slowly

### Ollama connection errors

Check Ollama is running
curl http://localhost:11434/api/tags

Pull the model if missing
ollama pull llama3.2

Start Ollama
ollama serve

## 📈 Performance Metrics

Expected performance:

| Operation | Latency | Notes |
|-----------|---------|-------|
| Rule-based detection | ~1ms | Very fast |
| ML model scoring | ~10-20ms | Moderate |
| LLM validation | ~500-2000ms | Can be slow |
| Message routing | ~5ms | Sending to RabbitMQ |

### Throughput

- Without LLM: 200+ CDRs/second
- With LLM: 1-5 CDRs/second (depends on model)

## Production Deployment

### Docker Compose Setup

cd fraud-detection-system

Use the full docker-compose from cdr-ingestion
docker-compose -f cdr-ingestion/docker-compose.yml up -d

Also start fraud detector
docker-compose -f rabbit/docker-compose.yml up -d fraud_detector_consumer

### Scale to Multiple Consumers

In docker-compose.yml, add more replicas:

fraud_detector_consumer_1:
  ... config ...

fraud_detector_consumer_2:
  ... same config but different container_name ...

fraud_detector_consumer_3:
  ... same config but different container_name ...

## Documentation

- Fraud Detector README - Detailed documentation
- Test Script - Send test data
- Monitor Script - View results

## Checklist

- RabbitMQ running on port 5672
- PostgreSQL running on port 5432
- CDR ingestion running on port 8080
- Fraud detector consumer running
- Ollama running on port 11434
- Test data sent successfully
- Fraud/Normal queues receiving messages
- Monitoring dashboard showing results

## Next Steps

1. Train ML Model - Replace mock model with real trained model
2. Add Custom Rules - Add domain-specific fraud rules
3. Setup Alerts - Configure Alertmanager for real fraud alerts
4. Dashboard - Create Grafana dashboards for monitoring
5. Integration - Integrate with your business systems

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review logs: docker logs <container_name>
3. Check RabbitMQ Management UI: http://localhost:15672
4. Verify all services running: docker ps

---

Happy fraud detecting! 🛡️
