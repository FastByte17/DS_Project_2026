# Create directories
New-Item -ItemType Directory -Force -Path "monitoring\prometheus"
New-Item -ItemType Directory -Force -Path "monitoring\grafana\provisioning\datasources"
New-Item -ItemType Directory -Force -Path "monitoring\grafana\provisioning\dashboards"
New-Item -ItemType Directory -Force -Path "monitoring\grafana\dashboards"
New-Item -ItemType Directory -Force -Path "monitoring\alertmanager"

# Create prometheus.yml
@"
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'fraud-detection-system'
    environment: 'development'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
"@ | Out-File -FilePath "monitoring\prometheus\prometheus.yml" -Encoding utf8

# Create alerts.yml
@"
groups:
  - name: fraud_detection_alerts
    interval: 30s
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is {{ `$value }}% on {{ `$labels.instance }}"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ `$value }}%"
"@ | Out-File -FilePath "monitoring\prometheus\alerts.yml" -Encoding utf8

# Create alertmanager.yml
@"
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default-receiver'

receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://localhost:8003/webhook/alerts'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'cluster', 'service']
"@ | Out-File -FilePath "monitoring\alertmanager\alertmanager.yml" -Encoding utf8

# Create Grafana datasource configuration
@"
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
"@ | Out-File -FilePath "monitoring\grafana\provisioning\datasources\prometheus.yml" -Encoding utf8

# Create Grafana dashboard provisioning
@"
apiVersion: 1

providers:
  - name: 'Fraud Detection Dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
"@ | Out-File -FilePath "monitoring\grafana\provisioning\dashboards\dashboard.yml" -Encoding utf8

Write-Host "✅ All configuration files created successfully!"