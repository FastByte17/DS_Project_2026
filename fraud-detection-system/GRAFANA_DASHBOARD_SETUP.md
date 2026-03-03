# Grafana Fraud Detection Dashboard Setup Guide

## Quick Setup

1. **Open Grafana**: http://localhost:3000
   - Username: `admin`
   - Password: `admin`

2. **Verify Prometheus Data Source**:
   - Go to Settings → Data Sources
   - Look for "Prometheus"
   - If not present, click "Add data source":
     - Type: Prometheus
     - URL: `http://prometheus:9090`
     - Click "Save & Test"

3. **Create New Dashboard**:
   - Click "+" → Dashboard
   - Add panels following the guide below

---

## Dashboard Panels

### Panel 1: Total Frauds Detected (Stat)

**Visualization**: Stat

**Query**:
```
sum(fraud_detected_total)
```

**Settings**:
- Title: "Total Frauds Detected"
- Unit: "short"
- Threshold: 
  - Green: 0-25
  - Yellow: 26-50
  - Red: 50+

---

### Panel 2: Frauds by Type (Pie Chart)

**Visualization**: Pie chart

**Query**:
```
sum by (fraud_type) (fraud_detected_total)
```

**Settings**:
- Title: "Fraud Distribution by Type"
- Legend: Show all
- Tooltip: Multi-series

**Expected breakdown**:
- blacklisted_number
- high_risk_score
- high_value_transaction
- suspicious_sim_status
- sim_box
- account_takeover
- etc.

---

### Panel 3: Detection Method Breakdown (Bar Chart)

**Visualization**: Bar chart

**Query**:
```
sum by (method) (fraud_detected_total)
```

**Settings**:
- Title: "Detection Method Distribution"
- Orientation: Horizontal
- Legend: Show all

**Expected methods**:
- rules (fastest, rule-based checks)
- ml (RandomForest model)
- llm (Ollama LLM validation)

---

### Panel 4: Fraud Detection Rate Over Time (Time Series)

**Visualization**: Time series

**Query**:
```
rate(fraud_detected_total[5m])
```

**Settings**:
- Title: "Fraud Detection Rate (per 5 min)"
- Legend: Show all
- Tooltip: Multi-series

---

### Panel 5: High-Risk Frauds (Table)

**Visualization**: Table

**Query**:
```
topk(10, sum by (fraud_type) (fraud_detected_total))
```

**Settings**:
- Title: "Top 10 Fraud Types"
- Columns: fraud_type, value

---

### Panel 6: Fraud vs Normal Transactions (Stat)

**Visualization**: Two stat panels side-by-side

**Query 1 - Fraud Count**:
```
sum(fraud_detected_total)
```

**Query 2 - Expected Normal Count** (approximate from CDR ingestion):
```
sum(fraud_detected_total) * 1  # Placeholder - adjust based on your data
```

---

### Panel 7: LLM Analysis Latency (Gauge)

**Visualization**: Gauge

**Query**:
```
histogram_quantile(0.95, rate(llm_analysis_duration_seconds_bucket[5m]))
```

**Settings**:
- Title: "LLM Analysis P95 Latency"
- Unit: "seconds"
- Thresholds:
  - Green: 0-1s
  - Yellow: 1-2s
  - Red: 2s+

---

## Step-by-Step Instructions

### Create the Dashboard

1. Click **"+" menu** → **"Dashboard"** → **"Create new dashboard"**

2. Add first panel:
   - Click **"Add panel"**
   - Under "Queries" tab:
     - Select Data source: **Prometheus**
     - Enter query: `sum(fraud_detected_total)`
   - Under "Visualization" tab:
     - Select: **Stat**
   - Under "General" tab:
     - Title: "Total Frauds Detected"
   - Click **"Apply"**

3. Repeat for each panel above with corresponding queries and visualizations

4. **Save Dashboard**:
   - Click **"Save"** (top-right)
   - Name: "Fraud Detection Dashboard"
   - Click **"Save"**

---

## Useful PromQL Queries

**Total fraud count by hour**:
```
sum(rate(fraud_detected_total[1h])) * 3600
```

**Fraud trend (24h)**:
```
sum(increase(fraud_detected_total[24h]))
```

**Detection method distribution**:
```
sum by (method) (fraud_detected_total)
```

**Fraud type distribution**:
```
sum by (fraud_type) (fraud_detected_total)
```

**High-confidence frauds (>0.7 confidence)**:
```
sum(fraud_detected_total{fraud_type!="normal"})
```

**LLM analysis average duration**:
```
avg(rate(llm_analysis_duration_seconds_sum[5m]) / rate(llm_analysis_duration_seconds_count[5m]))
```

**LLM analysis p50 latency**:
```
histogram_quantile(0.5, rate(llm_analysis_duration_seconds_bucket[5m]))
```

**LLM analysis p95 latency**:
```
histogram_quantile(0.95, rate(llm_analysis_duration_seconds_bucket[5m]))
```

**LLM analysis p99 latency**:
```
histogram_quantile(0.99, rate(llm_analysis_duration_seconds_bucket[5m]))
```

---

## Alerts Configured (in Prometheus)

Your system has 3 active alert rules:

1. **HighFraudDetectionRate**: Triggers when fraud rate > 0.1/sec for 5 min
2. **LLMAnalysisLatencyHigh**: Triggers when p95 latency > 2s for 5 min  
3. **CriticalFraudDetected**: Triggers on sim_box or account_takeover

View alerts in Grafana: **Alerting** → **Alert rules**

---

## Dashboard Layout Suggestion

```
┌─────────────────────────────────────────────────┐
│  Total Frauds (Stat)  │  Detection Rate (Gauge) │
├─────────────────────────────────────────────────┤
│     Fraud by Type (Pie)     │  By Method (Bar)  │
├─────────────────────────────────────────────────┤
│         Fraud Rate Over Time (Time Series)      │
├─────────────────────────────────────────────────┤
│           Top Fraud Types (Table)               │
└─────────────────────────────────────────────────┘
```

---

## Troubleshooting

**No data showing?**
- Verify Prometheus target is up: http://localhost:9090/targets
- Check if fraud detection consumer is running
- Send test data: `python send_bulk_cdrs.py <file>`

**Can't connect to Prometheus?**
- Ensure Prometheus is running: `docker ps | find "prometheus"`
- Verify URL is: `http://prometheus:9090` (not localhost)

**Metrics not updating?**
- Check Prometheus scrape interval: should be 10s
- Wait 30-60 seconds for first scrape after data arrives

