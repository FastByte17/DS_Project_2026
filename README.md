# Telecom Fraud Detection & Prevention System - Setup Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Configuration Files](#configuration-files)
- [Starting the Monitoring Stack](#starting-the-monitoring-stack)
- [Accessing Services](#accessing-services)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)
- [Common Commands](#common-commands)

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Git** ([Download](https://git-scm.com/downloads))
- **Docker Desktop** ([Download](https://www.docker.com/products/docker-desktop))
  - Make sure Docker Desktop is running before executing any commands
- **Text Editor**
  - Windows: Notepad, VS Code, or Notepad++
  - Linux/Mac: nano, vim, VS Code

---

## Initial Setup

### 1. Clone the Repository

#### Windows (PowerShell or Command Prompt):
```powershell
git clone https://github.com/FastByte17/DS_Project_2026
cd fraud-detection-system
```

#### Linux/Mac (Terminal):
```bash
git clone https://github.com/FastByte17/DS_Project_2026
cd fraud-detection-system
```

---

### 2. Set Up Environment Variables

#### Windows (PowerShell):
```powershell
# Copy the example file
Copy-Item .env.example .env

# Edit with Notepad
notepad .env

# Or edit with VS Code
code .env
```

#### Linux/Mac (Terminal):
```bash
# Copy the example file
cp .env.example .env

# Edit with nano
nano .env

# Or edit with your favorite editor
vim .env
# or
code .env
```

#### Edit the `.env` file with your credentials:
```env
# Grafana Credentials
GRAFANA_ADMIN_USER=XXXXXXXXX
GRAFANA_ADMIN_PASSWORD=XXXXXXXXXX

```
---

## Configuration Files

Before starting the services, you need to create the required configuration files.

### 3. Create Directory Structure and Configuration Files

#### Windows (PowerShell):

Open `setup-config.ps1` and run it:

```powershell
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
```

Run the script:
```powershell
.\setup-config.ps1
```

#### Linux/Mac (Bash):

Save this as `setup-config.sh` and run it:

```bash
#!/bin/bash

# Create directories
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/alertmanager

# Create prometheus.yml
cat > monitoring/prometheus/prometheus.yml <<'EOF'
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
EOF

# Create alerts.yml
cat > monitoring/prometheus/alerts.yml <<'EOF'
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
          description: "CPU usage is {{ $value }}% on {{ $labels.instance }}"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"
EOF

# Create alertmanager.yml
cat > monitoring/alertmanager/alertmanager.yml <<'EOF'
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
EOF

# Create Grafana datasource configuration
cat > monitoring/grafana/provisioning/datasources/prometheus.yml <<'EOF'
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
EOF

# Create Grafana dashboard provisioning
cat > monitoring/grafana/provisioning/dashboards/dashboard.yml <<'EOF'
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
EOF

echo "✅ All configuration files created successfully!"
```

Make it executable and run:
```bash
chmod +x setup-config.sh
./setup-config.sh
```

---

## Starting the Monitoring Stack

### 4. Validate Configuration

Before starting, validate your docker-compose file:

```bash
docker-compose -f docker-compose.monitoring.yml config
```

If there are no errors, you'll see the parsed configuration.

### 5. Start All Services

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

**Expected output:**
```
[+] Running 8/8
 ✔ Network fraud-detection_monitoring           Created
 ✔ Volume fraud-detection_prometheus-data       Created
 ✔ Volume fraud-detection_grafana-data          Created
 ✔ Volume fraud-detection_alertmanager-data     Created
 ✔ Container fraud-detection-prometheus         Started
 ✔ Container fraud-detection-alertmanager       Started
 ✔ Container fraud-detection-node-exporter      Started
 ✔ Container fraud-detection-grafana            Started
```

### 6. Verify Services Are Running

```bash
docker-compose -f docker-compose.monitoring.yml ps
```

**Expected output:**
```
NAME                              STATUS
fraud-detection-prometheus        Up
fraud-detection-grafana           Up
fraud-detection-node-exporter     Up
fraud-detection-alertmanager      Up
```

---

## Accessing Services

Open your web browser and navigate to:

### Grafana
- **URL**: http://localhost:3000
- **Username**: Value from your `.env` file (default: `admin`)
- **Password**: Value from your `.env` file

**First login steps:**
1. Navigate to http://localhost:3000
2. Enter your credentials
3. You'll see the Grafana home page
4. Prometheus datasource is already configured

### Prometheus
- **URL**: http://localhost:9090
- **Check targets**: http://localhost:9090/targets
- Should show `prometheus` and `node-exporter` as UP

### Alertmanager
- **URL**: http://localhost:9093
- View active alerts and silence rules

### Node Exporter Metrics
- **URL**: http://localhost:9100/metrics
- Raw metrics exported by Node Exporter

---

## Security Best Practices

### ⚠️ Critical Security Rules

1. **NEVER commit the `.env` file to Git**
   - It contains sensitive credentials
   - Always keep it in `.gitignore`

2. **Use different credentials for each environment**
   - Development vs Production should have different passwords

---

## Troubleshooting

### Issue: "docker-compose: command not found"

**Solution:**
- Ensure Docker Desktop is running
- Try `docker compose` (without hyphen) for newer Docker versions
- Check Docker is in your PATH

**Linux only:**
```bash
# Install docker-compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

---

### Issue: "Port already in use"

**Check what's using the port:**

**Windows (PowerShell):**
```powershell
# Check port 3000 (Grafana)
Get-NetTCPConnection -LocalPort 3000 -State Listen

# Stop the process
Stop-Process -Id <PID>
```

**Linux/Mac:**
```bash
# Check port 3000
lsof -i :3000

# Kill the process
kill -9 <PID>
```

**Alternative:** Change the port in `docker-compose.monitoring.yml`:
```yaml
ports:
  - "3001:3000"  # Use 3001 instead of 3000
```

---

### Issue: "Cannot connect to Docker daemon"

**Windows:**
1. Open Docker Desktop
2. Wait for it to fully start (whale icon should be steady)
3. Try the command again

**Linux:**
```bash
# Start Docker service
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker

# Add your user to docker group (to avoid sudo)
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

---

### Issue: Configuration file not found

**Verify files exist:**

**Windows (PowerShell):**
```powershell
Test-Path monitoring\prometheus\prometheus.yml
Test-Path monitoring\prometheus\alerts.yml
Test-Path monitoring\alertmanager\alertmanager.yml
```

**Linux/Mac:**
```bash
ls -la monitoring/prometheus/prometheus.yml
ls -la monitoring/prometheus/alerts.yml
ls -la monitoring/alertmanager/alertmanager.yml
```

If files don't exist, run the setup script again (Step 3).

---

### Issue: Services keep restarting

**View logs to diagnose:**
```bash
# View all logs
docker-compose -f docker-compose.monitoring.yml logs

# View specific service logs
docker-compose -f docker-compose.monitoring.yml logs grafana
docker-compose -f docker-compose.monitoring.yml logs prometheus

# Follow logs in real-time
docker-compose -f docker-compose.monitoring.yml logs -f
```

**Common causes:**
- Configuration file syntax errors
- Port conflicts
- Insufficient system resources

---

### Issue: Grafana shows "Bad Gateway"

**Solution:**
1. Wait 30 seconds for Grafana to fully start
2. Check if Prometheus is running:
   ```bash
   docker-compose -f docker-compose.monitoring.yml ps prometheus
   ```
3. Restart Grafana:
   ```bash
   docker-compose -f docker-compose.monitoring.yml restart grafana
   ```

---

## Common Commands

### Service Management

| Action | Command |
|--------|---------|
| Start all services | `docker-compose -f docker-compose.monitoring.yml up -d` |
| Stop all services | `docker-compose -f docker-compose.monitoring.yml down` |
| Restart all services | `docker-compose -f docker-compose.monitoring.yml restart` |
| Stop and remove volumes (⚠️ deletes data!) | `docker-compose -f docker-compose.monitoring.yml down -v` |

### Monitoring

| Action | Command |
|--------|---------|
| View status | `docker-compose -f docker-compose.monitoring.yml ps` |
| View all logs | `docker-compose -f docker-compose.monitoring.yml logs` |
| Follow logs | `docker-compose -f docker-compose.monitoring.yml logs -f` |
| View specific service logs | `docker-compose -f docker-compose.monitoring.yml logs grafana` |

### Individual Service Control

| Action | Command |
|--------|---------|
| Restart Grafana | `docker-compose -f docker-compose.monitoring.yml restart grafana` |
| Restart Prometheus | `docker-compose -f docker-compose.monitoring.yml restart prometheus` |
| Stop Grafana | `docker-compose -f docker-compose.monitoring.yml stop grafana` |
| Start Grafana | `docker-compose -f docker-compose.monitoring.yml start grafana` |

### Maintenance

| Action | Command |
|--------|---------|
| Rebuild containers | `docker-compose -f docker-compose.monitoring.yml up -d --force-recreate` |
| Pull latest images | `docker-compose -f docker-compose.monitoring.yml pull` |
| Remove unused volumes | `docker volume prune` |
| Remove unused images | `docker image prune` |

---

## Port Reference

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Grafana | 3000 | http://localhost:3000 | Visualization dashboards |
| Prometheus | 9090 | http://localhost:9090 | Metrics collection & queries |
| Node Exporter | 9100 | http://localhost:9100/metrics | System metrics |
| Alertmanager | 9093 | http://localhost:9093 | Alert management |

---

## Next Steps

After successfully setting up the monitoring stack:

1. ✅ **Log in to Grafana** at http://localhost:3000
2. ✅ **Import pre-built dashboards**
   - Go to Dashboards → Import
   - Import Node Exporter Full dashboard (ID: 1860)
3. ✅ **Configure alerts** in Alertmanager for your team
4. ✅ **Add your fraud detection services** to Prometheus scrape configs
5. ✅ **Create custom dashboards** for CDR ingestion, fraud detection metrics
6. ✅ **Set up email/Slack notifications** in Alertmanager

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check logs**: `docker-compose -f docker-compose.monitoring.yml logs`
2. **Verify services**: `docker-compose -f docker-compose.monitoring.yml ps`
3. **Check Docker Desktop** is running (Windows/Mac)
4. **Verify ports** are not in use by other applications
5. **Review configuration files** for syntax errors
6. **Consult Docker documentation**: https://docs.docker.com/
7. **Create an issue** in the project repository

---

## Project Structure

```
fraud-detection-system/
├── docker-compose.monitoring.yml
├── .env                          # ⚠️ DO NOT COMMIT
├── .env.example                  # ✅ Commit this
├── .gitignore                    # Must include .env
├── README.md                     # This file
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alerts.yml
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/
│   │   │   │   └── prometheus.yml
│   │   │   └── dashboards/
│   │   │       └── dashboard.yml
│   │   └── dashboards/
│   └── alertmanager/
│       └── alertmanager.yml
└── services/
    ├── cdr-ingestion/
    ├── fraud-detection/
    └── ...
```

---

## License

TBD

## Contributors

[Nabeel Hussain, Muhammad Abdur Rehman, Christoph Gasche, Marko Tiitto, Talha Pasha
]

---

**Last Updated**: February 2026