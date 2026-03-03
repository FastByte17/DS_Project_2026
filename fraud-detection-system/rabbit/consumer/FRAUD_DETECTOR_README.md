# Fraud Detection Consumer

This service consumes CDR (Call Detail Records) messages from RabbitMQ and processes them through a machine learning-based fraud detection engine. It automatically routes messages to appropriate queues based on fraud detection results.

## Architecture

```
CDR Queue (Input)
       ↓
[Fraud Detection Engine]
       ├→ Rule-based detection (fast)
       ├→ ML model prediction
       └→ LLM validation (for uncertain cases)
       ↓
   [Router]
       ├→ FRAUD_CDR queue (if fraud detected)
       └→ NORMAL_CDR queue (if normal)
```

## Features

✅ **Multi-stage Fraud Detection:**
- Fast rule-based checks (blacklist, risk score, SIM status)
- ML model scoring for probabilistic detection
- LLM-powered validation for uncertain cases (0.3 < score < 0.8)

✅ **Intelligent Routing:**
- Automatic routing to FRAUD_CDR or NORMAL_CDR queues
- Persistent message storage for auditing

✅ **Alerting:**
- Sends high-confidence fraud alerts (>70% confidence) to Prometheus Alertmanager
- Integrates with monitoring systems

✅ **Metrics:**
- Prometheus metrics for fraud detection (method, fraud type)
- LLM analysis latency tracking

## Prerequisites

- RabbitMQ running and accessible
- Ollama with llama3.2 model (for LLM validation)
- PostgreSQL (for data storage)
- Prometheus & Alertmanager (optional, for alerts)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
export RABBITMQ_HOST=rabbitmq
export RABBITMQ_USER=guest
export RABBITMQ_PASSWORD=guest
export CDR_INPUT_QUEUE=CDR
export FRAUD_QUEUE=FRAUD_CDR
export NORMAL_QUEUE=NORMAL_CDR
export OLLAMA_HOST=http://ollama:11434
```

### 3. Run Standalone

```bash
python fraud_detector_consumer.py
```

### 4. Run with Docker

Build and run the fraud detection consumer:

```bash
cd ../
docker-compose -f rabbit/docker-compose.yml up fraud_detector_consumer
```

## Usage

Once running, the consumer will:

1. **Listen for CDR messages** on the `CDR` queue (configurable via `CDR_INPUT_QUEUE`)
2. **Process each message** through the fraud detection pipeline
3. **Route to appropriate queue:**
   - 🚨 **Fraudulent** → `FRAUD_CDR` queue
   - ✅ **Normal** → `NORMAL_CDR` queue
4. **Send alerts** for high-confidence fraud (>70%)

## Message Format

### Input (CDR Message)

```json
{
  "customer_id": "CUST001",
  "full_name": "John Doe",
  "mobile_number": "+1234567890",
  "city": "New York",
  "sim_serial_number": "SIM123456",
  "sim_status": "active",
  "imei": "123456789012345",
  "transaction_id": "TXN20260227001",
  "time_stamp": "2026-02-27T20:30:00Z",
  "type": "international_call",
  "amount_eur": 150.00,
  "risk_score": 0.65,
  "fraud_flag": false,
  "fraud_type": null
}
```

### Output (Routed Message with Detection Result)

```json
{
  "cdr": { ... original CDR data ... },
  "detection_result": {
    "is_fraud": true,
    "confidence": 0.85,
    "method": "llm",
    "fraud_type": "sim_box",
    "explanation": "Unusual SIM activity detected with high transaction amount",
    "suspicious_indicators": [
      "High transaction value",
      "Suspicious SIM status"
    ],
    "recommended_action": "block"
  },
  "timestamp": 1709072400.123
}
```

## Detection Methods

### 1. Rule-Based Detection (Fast)
Checks for immediate red flags:
- Fraud flag already set
- Risk score > 0.8
- Number in blacklist
- Suspicious SIM status (suspended, blocked, compromised)
- High transaction amount (> 10,000 EUR)

### 2. ML Model Prediction
Uses trained RandomForest model on features:
- Risk score
- Transaction amount
- Fraud flag
- SIM serial hash
- IMEI hash
- SIM status
- Name length

**Scoring:**
- Score > 0.8 → **Fraud** (high confidence)
- Score < 0.3 → **Normal** (high confidence)
- 0.3 ≤ Score ≤ 0.8 → **LLM Validation** (uncertain)

### 3. LLM Validation (Ollama)
For uncertain cases, uses Llama 3.2 to analyze context:
- Customer history
- Transaction patterns
- Known fraud indicators
- SIM/IMEI anomalies

## Fraud Types

- `sim_box` - Compromised SIM card used for fraud
- `identity` - Fraudulent transaction with stolen credentials
- `high_value` - Unusual high-amount transaction
- `sim_bypass` - IMEI/SIM mismatch indicating spoofing
- `account_takeover` - Transaction inconsistent with customer behavior
- `blacklisted_number` - Number in fraud blacklist
- `suspicious_sim_status` - SIM status indicates compromise
- `high_risk_score` - Pre-flagged as high-risk

## Monitoring

### Prometheus Metrics

```bash
# Get fraud detection metrics
curl http://localhost:9090/api/v1/query?query=fraud_detected_total
curl http://localhost:9090/api/v1/query?query=llm_analysis_duration_seconds
```

### RabbitMQ Management UI

```
http://localhost:15672
Username: guest
Password: guest
```

Monitor queues:
- `CDR` - Incoming messages
- `FRAUD_CDR` - Detected frauds
- `NORMAL_CDR` - Normal transactions

## Troubleshooting

### Container keeps restarting

Check logs:
```bash
docker logs fraud_detector_consumer_1
```

Common issues:
- RabbitMQ not running → Ensure rabbitmq:5672 is accessible
- Ollama not available → Check `http://ollama:11434/api/tags`
- Missing environment variables → Verify all env vars are set

### Ollama connection errors

```bash
# Test Ollama connection
curl http://ollama:11434/api/tags

# If using local Ollama, pull the model
ollama pull llama3.2
ollama serve
```

### High memory usage

The LLM validation can be memory-intensive. Options:
- Adjust ML score thresholds to reduce LLM calls
- Use a smaller model
- Run on a machine with more resources

## Performance Tuning

### Prefetch Count
Currently set to 1 (process one message at a time). Increase for higher throughput:

```python
self._channel.basic_qos(prefetch_count=5)  # Process 5 messages in parallel
```

### ML Score Thresholds
Adjust in `FraudDetectionEngine.detect_fraud()`:
- Lower threshold for more fraud detection (higher false positives)
- Higher threshold for fewer false alarms (might miss real fraud)

## Development

### Testing Fraud Detection Locally

```bash
# Install dev dependencies
pip install -r requirements.txt

# Test with sample data
python -c "
from fraud_detector_consumer import FraudDetectionConsumer
import json

consumer = FraudDetectionConsumer()
sample_cdr = {
    'customer_id': 'TEST001',
    'transaction_id': 'TXN001',
    'amount_eur': 15000,
    'risk_score': 0.85,
    'fraud_flag': False
}
result = consumer.detector.detect_fraud(sample_cdr)
print(json.dumps(result, indent=2))
"
```

### Adding Custom Rules

Edit `FraudDetectionEngine.apply_rules()` in `ml_service.py`:

```python
# Add new rule
if some_condition:
    return {
        'is_fraud': True,
        'type': 'custom_rule',
        'reason': 'Description of why it\'s flagged'
    }
```

## Future Enhancements

- [ ] Real model training pipeline with historical fraud data
- [ ] Dynamic blacklist/whitelist from database
- [ ] Customer behavior profiling for anomaly detection
- [ ] A/B testing framework for fraud thresholds
- [ ] Model version management and rollout
- [ ] Real-time model retraining
- [ ] Advanced analytics dashboard

## License

Internal Use Only - Distributed Systems Project 2026
