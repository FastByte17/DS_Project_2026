# Fraud Detection System - Prometheus Integration Guide

## Overview

The fraud detection system is now fully integrated with Prometheus for real-time monitoring and alerting. All fraud detection metrics are exposed via an HTTP endpoint that Prometheus scrapes every 10 seconds.

## Architecture

```
Fraud Detection Consumer
        ↓
[Prometheus Metrics]
  - fraud_detected_total
  - llm_analysis_duration_seconds
        ↓
    :8000/metrics
        ↓
    Prometheus (port 9090)
        ↓
    Alertmanager (port 9093)
        ↓
  Grafana Dashboards (port 3000)
```

## Setup Steps

### 1. Start Fraud Detection Consumer with Metrics

```powershell
cd "d:\Period 3\Distributed Systems\DS_Project_2026\fraud-detection-system\rabbit\consumer"

# Start consumer with metrics on port 8000
python fraud_detector_consumer.py --host 127.0.0.1 --username myuser --password mypassword --metrics-port 8000
```

Expected output:
Prometheus metrics server started on port 8000
  http://localhost:8000/metrics
Fraud Detection Engine initialized with Ollama at http://ollama:11434
Connected to RabbitMQ at 127.0.0.1
Input queue: CDR
Fraud queue: FRAUD_CDR
Normal queue: NORMAL_CDR

Starting Fraud Detection Consumer

Waiting for CDR messages...

### 2. Verify Metrics Endpoint

```powershell
curl http://localhost:8000/metrics
```

You should see output like:
```
# HELP fraud_detected_total Frauds detected
# TYPE fraud_detected_total counter
fraud_detected_total{fraud_type="high_risk_score",method="rules"} 2.0
fraud_detected_total{fraud_type="ml_detected",method="ml"} 1.0

# HELP llm_analysis_duration_seconds LLM analysis time
# TYPE llm_analysis_duration_seconds histogram
llm_analysis_duration_seconds_bucket{le="0.005",le_INF"} 0.0
llm_analysis_duration_seconds_bucket{le="0.01"} 0.0
...
```

### 3. Check Prometheus Targets

1. Go to **http://localhost:9090**
2. Click **Status** → **Targets**
3. You should see:
   - `prometheus` (UP)
   - `node-exporter` (UP)
   - `fraud-detection-consumer` (UP)

If fraud-detection-consumer shows DOWN, make sure:
- Consumer is running
- Metrics endpoint is accessible: curl http://localhost:8000/metrics
- Port 8000 is not blocked
- Prometheus can reach localhost:8000

## Available Metrics

### 1. Fraud Detection Counter

**Metric:** `fraud_detected_total`

**Labels:**
- `method` - Detection method: `rules`, `ml`, `llm`
- `fraud_type` - Type of fraud detected

**Query Examples:**

```promql
# Total frauds detected
fraud_detected_total

# Frauds detected per method
sum by (method) (fraud_detected_total)

# Frauds detected per type
sum by (fraud_type) (fraud_detected_total)

# Rate of fraud detection (frauds per second)
rate(fraud_detected_total[5m])

# Only critical fraud types
fraud_detected_total{fraud_type=~"sim_box|account_takeover|identity"}
```

### 2. LLM Analysis Latency

**Metric:** `llm_analysis_duration_seconds`

**Type:** Histogram (tracks quantiles)

**Query Examples:**

```promql
# Average LLM analysis time
rate(llm_analysis_duration_seconds_sum[5m]) / rate(llm_analysis_duration_seconds_count[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(llm_analysis_duration_seconds_bucket[5m]))

# 99th percentile latency
histogram_quantile(0.99, rate(llm_analysis_duration_seconds_bucket[5m]))

# Max latency (approximate)
llm_analysis_duration_seconds_bucket{le="+Inf"}
```

## Create Grafana Dashboards

### Dashboard 1: Fraud Detection Overview

1. Go to **http://localhost:3000** (admin/admin)
2. Click **+ Create** → **Dashboard**
3. Click **+ Add new panel**

**Panel 1: Total Frauds (Gauge)**
- **Metric:** `fraud_detected_total`
- **Panel Type:** Gauge
- **Thresholds:** 
  - 0-10 (Green), 10-50 (Yellow), 50+ (Red)

**Panel 2: Fraud Detection Rate (Graph)**
- **Metric:** `rate(fraud_detected_total[5m])`
- **Panel Type:** Time series
- **Title:** "Frauds per Second (Last 5 min)"

**Panel 3: Detection Method Distribution (Pie Chart)**
- **Metric:** `sum by (method) (fraud_detected_total)`
- **Panel Type:** Pie chart
- **Title:** "Fraud Detection Method Distribution"

**Panel 4: Fraud Types (Bar Chart)**
- **Metric:** `sum by (fraud_type) (fraud_detected_total)`
- **Panel Type:** Bar gauge
- **Title:** "Frauds by Type"

### Dashboard 2: Performance Monitoring

**Panel 1: LLM Latency P95 (Gauge)**
- **Metric:** `histogram_quantile(0.95, rate(llm_analysis_duration_seconds_bucket[5m]))`
- **Panel Type:** Gauge
- **Units:** seconds
- **Thresholds:** 0-0.5s (Green), 0.5-1s (Yellow), 1s+ (Red)

**Panel 2: LLM Latency Trend (Graph)**
- **Metric:** 
  ```promql
  histogram_quantile(0.50, rate(llm_analysis_duration_seconds_bucket[5m])) as "p50"
  histogram_quantile(0.95, rate(llm_analysis_duration_seconds_bucket[5m])) as "p95"
  histogram_quantile(0.99, rate(llm_analysis_duration_seconds_bucket[5m])) as "p99"
  ```
- **Panel Type:** Time series
- **Title:** "LLM Analysis Latency"

**Panel 3: Detection Method Latency Breakdown**
- **Metric:** `rate(llm_analysis_duration_seconds_sum[5m]) / rate(llm_analysis_duration_seconds_count[5m])`
- **Panel Type:** Time series
- **Title:** "Average Analysis Time"

## Prometheus Alert Rules

The following alert rules have been configured in `alerts.yml`:

### Alert 1: High Fraud Detection Rate

```yaml
HighFraudDetectionRate:
  Condition: fraud detection rate > 0.1 frauds/sec for 5 minutes
  Severity: WARNING
  Trigger: When there's a spike in fraud detection (more than normal)
```

### Alert 2: High LLM Analysis Latency

```yaml
LLMAnalysisLatencyHigh:
  Condition: 95th percentile latency > 2 seconds for 5 minutes
  Severity: WARNING
  Trigger: When LLM is responding slowly
```

### Alert 3: Critical Fraud Types Detected

```yaml
CriticalFraudDetected:
  Condition: Any sim_box or account_takeover fraud detected
  Severity: CRITICAL
  Trigger: When high-risk fraud types detected
```

## Test the Setup

### Send Test Data

```powershell
cd "d:\Period 3\Distributed Systems\DS_Project_2026\fraud-detection-system\rabbit\consumer"
python send_test_cdrs.py
```

### View Metrics in Real-Time

**In Prometheus (http://localhost:9090):**

1. Click **Graph**
2. Enter query: `fraud_detected_total`
3. Click **Execute**
4. See metrics update as test data is processed

### View Alerts

**In Prometheus (http://localhost:9090):**

1. Click **Alerts**
2. See list of alert rules
3. Firing alerts show in red
4. Pending alerts show in yellow

## PromQL Query Examples

### Business Metrics

```promql
# Total fraud detected today
increase(fraud_detected_total[24h])

# Fraud detection rate (per minute)
rate(fraud_detected_total[1m]) * 60

# Most common fraud type (today)
topk(1, sum by (fraud_type) (increase(fraud_detected_total[24h])))

# Detection accuracy by method
sum by (method) (fraud_detected_total) / on (method) group_left 
sum by (method) (count(fraud_detected_total) by (method))
```

### Performance Metrics

```promql
# LLM performance (how much time spent on analysis)
sum(rate(llm_analysis_duration_seconds_sum[5m]))

# Average fraud detection latency
avg(rate(llm_analysis_duration_seconds_sum[5m]) / rate(llm_analysis_duration_seconds_count[5m]))

# LLM usage (how often used)
rate(llm_analysis_duration_seconds_count[5m])
```

### Operational Metrics

```promql
# Rules-based detection (fastest)
rate(fraud_detected_total{method="rules"}[5m])

# ML detection
rate(fraud_detected_total{method="ml"}[5m])

# LLM detection (only for uncertain cases)
rate(fraud_detected_total{method="llm"}[5m])

# Ratio of LLM usage
rate(fraud_detected_total{method="llm"}[5m]) / 
rate(fraud_detected_total[5m])
```

## Troubleshooting

### Metrics Not Appearing in Prometheus

1. **Consumer not running?**
   ```powershell
   curl http://localhost:8000/metrics
   ```
   Should return metrics data

2. **Prometheus can't reach consumer?**
   - Check firewall
   - Verify port 8000
   - Check `/metrics` endpoint
   - Try: `curl http://127.0.0.1:8000/metrics`

3. **Metrics scrape failing?**
   - Go to Prometheus → Status → Targets
   - Click fraud-detection-consumer
   - Check error message
   - Check Prometheus logs

### Alert Rules Not Firing

1. **Go to Alerts page in Prometheus**
2. **Verify alert rule is present**
3. **Check condition:** Enter query in Graph and verify it returns data
4. **Check threshold:** May need to adjust for your environment

## Production Setup

For production with Docker:

```yaml
fraud-detector:
  environment:
    METRICS_PORT: 8000
  ports:
    - "8000:8000"
  networks:
    - monitoring

prometheus:
  scrape_configs:
    - job_name: 'fraud-detection-consumer'
      static_configs:
        - targets: ['fraud-detector:8000']
```

## Reference

- **Prometheus Docs:** https://prometheus.io/docs/
- **PromQL Examples:** https://prometheus.io/docs/prometheus/latest/querying/examples/
- **Alert Rules:** https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- **Grafana Panels:** https://grafana.com/docs/grafana/latest/panels/visualizations/

---

Summary:
Real-time fraud detection metrics in Prometheus
Automated alerting on suspicious patterns
Beautiful dashboards in Grafana
Production-ready monitoring

You now have a complete observability system for your fraud detection!
