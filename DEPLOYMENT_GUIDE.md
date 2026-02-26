# GXNT Traefik Manager — Deployment Guide

**Version:** 1.0  
**Audience:** DevOps Engineers, System Administrators, Operators

---

## Table of Contents

1. [Quick Start (Docker Compose)](#quick-start-docker-compose)
2. [Production Deployment (Kubernetes)](#production-deployment-kubernetes)
3. [Configuration Reference](#configuration-reference)
4. [Database Setup](#database-setup)
5. [Security Hardening](#security-hardening)
6. [Monitoring & Health Checks](#monitoring--health-checks)
7. [Troubleshooting](#troubleshooting)
8. [Backup & Recovery](#backup--recovery)
9. [Scaling & Performance Tuning](#scaling--performance-tuning)

---

## Quick Start (Docker Compose)

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- etcd v3.4+ running (reachable at network level)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/genxnext/traefik-manager.git
cd traefik-manager

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env (required fields)
cat .env
# FLASK_SECRET_KEY=your-secret-key-here-change-this
# ETCD_URL=http://etcd:2379  # Point to your etcd instance
# DEBUG=False

# 4. Build and start
docker compose up --build -d

# 5. Verify
docker compose logs -f traefik-manager  # Check logs
curl http://localhost:8090               # Access UI

# 6. Login
# Username: admin
# Password: admin
# (You will be forced to change password)
```

### First-Time Setup Checklist

- [ ] Access UI at http://localhost:8090
- [ ] Log in with default credentials
- [ ] Change admin password immediately
- [ ] Configure etcd connection in UI (Settings → etcd Connections)
- [ ] Test by creating a test HTTP router
- [ ] Export a backup (Config → Export Full Backup)

---

## Production Deployment (Kubernetes)

### Architecture Overview

```
┌─────────────────────────────────────────┐
│  Traefik Manager Pod(s)                │
│  ├─ Flask App (port 8090)              │
│  └─ SQLite Data (PVC mount)            │
└──────────────┬──────────────────────────┘
               │
        (Ingress / LoadBalancer)
               │
        ┌──────┴──────────┐
        ▼                 ▼
   etcd Cluster      SQLite DB (PVC)
```

### Kubernetes Manifest (Example)

```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: traefik-manager

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: traefik-manager-config
  namespace: traefik-manager
data:
  ETCD_URL: "http://etcd:2379"
  DEBUG: "False"
  # Add other env vars as needed

---
apiVersion: v1
kind: Secret
metadata:
  name: traefik-manager-secrets
  namespace: traefik-manager
type: Opaque
stringData:
  FLASK_SECRET_KEY: "your-secure-random-key-here"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: traefik-manager
  namespace: traefik-manager
  labels:
    app: traefik-manager
spec:
  replicas: 2 # High availability
  selector:
    matchLabels:
      app: traefik-manager
  template:
    metadata:
      labels:
        app: traefik-manager
    spec:
      containers:
        - name: traefik-manager
          image: gcr.io/your-project/traefik-manager:1.0.0 # Your image registry
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8090
              name: http
          envFrom:
            - configMapRef:
                name: traefik-manager-config
            - secretRef:
                name: traefik-manager-secrets
          volumeMounts:
            - name: data
              mountPath: /app/data
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /api/health
              port: 8090
            initialDelaySeconds: 10
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /api/health
              port: 8090
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 2
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: traefik-manager-data

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: traefik-manager-data
  namespace: traefik-manager
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 5Gi

---
apiVersion: v1
kind: Service
metadata:
  name: traefik-manager
  namespace: traefik-manager
  labels:
    app: traefik-manager
spec:
  type: ClusterIP # Use Ingress for external access
  ports:
    - port: 80
      targetPort: 8090
      protocol: TCP
      name: http
  selector:
    app: traefik-manager

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: traefik-manager-ingress
  namespace: traefik-manager
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod # Requires cert-manager
spec:
  ingressClassName: nginx # Or your ingress controller class
  tls:
    - hosts:
        - traefik-manager.example.com
      secretName: traefik-manager-tls
  rules:
    - host: traefik-manager.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: traefik-manager
                port:
                  number: 80
```

### Deploy to Kubernetes

```bash
# Build and push image to registry
docker build -t your-registry/traefik-manager:1.0.0 .
docker push your-registry/traefik-manager:1.0.0

# Apply manifests
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl -n traefik-manager get pods
kubectl -n traefik-manager logs -f deployment/traefik-manager

# Port-forward for testing
kubectl -n traefik-manager port-forward svc/traefik-manager 8090:80
```

---

## Configuration Reference

### Environment Variables

| Variable           | Default                 | Required | Description                                                                                              |
| ------------------ | ----------------------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `FLASK_SECRET_KEY` | _(none)_                | ✅       | Secret key for session encryption (generate: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `ETCD_URL`         | `http://localhost:2379` | ✅       | etcd v3 API endpoint                                                                                     |
| `DEBUG`            | `False`                 | ❌       | Enable Flask debug mode (NEVER in production)                                                            |
| `LOG_LEVEL`        | `INFO`                  | ❌       | Logging level (DEBUG, INFO, WARNING, ERROR)                                                              |
| `PORT`             | `8090`                  | ❌       | Flask app port                                                                                           |
| `HOST`             | `0.0.0.0`               | ❌       | Flask bind address                                                                                       |
| `WORKERS`          | `4`                     | ❌       | Gunicorn worker count (for production)                                                                   |

### .env Example

```env
# Core
FLASK_SECRET_KEY=your-very-secure-random-key-min-32-chars
ETCD_URL=http://etcd.example.com:2379

# Optional
DEBUG=False
LOG_LEVEL=INFO
PORT=8090
HOST=0.0.0.0
```

### Docker Compose `docker-compose.yml`

```yaml
version: "3.8"

services:
  traefik-manager:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: traefik-manager
    ports:
      - "8090:8090"
    environment:
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
      - ETCD_URL=${ETCD_URL}
      - DEBUG=False
    volumes:
      - ./data:/app/data # Persist SQLite
    depends_on:
      - etcd
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8090/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  etcd:
    image: quay.io/coreos/etcd:v3.5.9
    container_name: etcd
    environment:
      - ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379
      - ETCD_ADVERTISE_CLIENT_URLS=http://etcd:2379
      - ETCD_INITIAL_ADVERTISE_PEER_URLS=http://etcd:2380
      - ETCD_LISTEN_PEER_URLS=http://0.0.0.0:2380
      - ETCD_INITIAL_CLUSTER=default=http://etcd:2380
      - ETCD_NAME=default
    ports:
      - "2379:2379"
    volumes:
      - ./etcd-data:/etcd-data
    restart: unless-stopped
```

---

## Database Setup

### SQLite (Default)

```bash
# Location
./data/traefik_manager.db

# Initialization
# Automatic on first run (Flask creates schema)

# Backup
cp ./data/traefik_manager.db ./data/traefik_manager.db.backup

# Restore
cp ./data/traefik_manager.db.backup ./data/traefik_manager.db
```

### Schema

```sql
-- Users (credentials)
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- etcd Connections (profiles)
CREATE TABLE etcd_connections (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  url TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### PostgreSQL (v1.1+)

For production deployments with multiple instances, PostgreSQL is recommended:

```bash
# Requirements
uv add psycopg2-binary

# Connection string
DATABASE_URL=postgresql://user:password@db:5432/traefik_manager
```

---

## Security Hardening

### 1. Change Default Credentials

```bash
# On first access, password change is forced
# But manually change via:
# In app: Settings → Change Password
# Or restart with FLASK_SECRET_KEY rotated
```

### 2. Enable HTTPS/TLS

```bash
# Behind Nginx with Let's Encrypt
# Configure Nginx as reverse proxy with SSL
# Traefik Manager remains HTTP internally

# Example Nginx config
upstream traefik_manager {
    server 127.0.0.1:8090;
}

server {
    listen 443 ssl http2;
    server_name traefik-manager.example.com;

    ssl_certificate /etc/letsencrypt/live/traefik-manager.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/traefik-manager.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://traefik_manager;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Restrict Network Access

```bash
# Only allow trusted IPs to access UI
# Example: firewall rule or Kubernetes NetworkPolicy

apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: traefik-manager-ingress
spec:
  podSelector:
    matchLabels:
      app: traefik-manager
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: traefik  # Only Traefik can access
    - podSelector:
        matchLabels:
          role: admin    # Only admin pods
```

### 4. etcd Access Control

```bash
# Enable etcd authentication
etcdctl user add admin
etcdctl user grant-role admin root

# Set RBAC
etcdctl role add traefik-manager
etcdctl role grant-permission traefik-manager readwrite /traefik/
```

### 5. Secrets Management

```bash
# Use secrets manager (e.g., HashiCorp Vault)
# Never commit .env with real secrets to git

# .gitignore
.env
data/
*.db
```

---

## Monitoring & Health Checks

### Health Check Endpoint

```
GET /api/health

Response (200 OK):
{}
```

### Metrics (v1.1+)

Future: Prometheus metrics at `/metrics`

### Application Logs

```bash
# Docker
docker compose logs -f traefik-manager

# Kubernetes
kubectl -n traefik-manager logs -f deployment/traefik-manager
kubectl -n traefik-manager logs -f --tail=100 deployment/traefik-manager

# Check etcd connectivity
curl http://your-etcd:2379/version
```

### Example Health Check Script

```bash
#!/bin/bash
# health_check.sh

set -e

# Check Flask app
echo "Checking app health..."
curl -f http://localhost:8090/api/health || exit 1

# Check etcd connectivity
echo "Checking etcd connectivity..."
curl -f http://etcd:2379/version || exit 1

# Check SQLite
echo "Checking database..."
[ -f ./data/traefik_manager.db ] || exit 1

echo "✅ All health checks passed"
```

---

## Troubleshooting

### Issue: "Cannot connect to etcd"

**Symptoms**: Error in UI when loading routers, or connection test fails.

**Solution**:

1. Verify etcd is running: `curl http://etcd:2379/version`
2. Check `ETCD_URL` env var: `docker compose config | grep ETCD_URL`
3. Check network connectivity: `docker compose exec traefik-manager curl http://etcd:2379/version`
4. For k8s: `kubectl exec -it <pod> -- curl http://etcd:2379/version`

### Issue: "Login fails or session expires"

**Symptoms**: Redirected to login, or logged out unexpectedly.

**Solution**:

1. Check `FLASK_SECRET_KEY` is set and consistent
2. Restart app: `docker compose restart traefik-manager`
3. Clear browser cookies (Settings → Clear browsing data)
4. For k8s: Check secret: `kubectl -n traefik-manager get secret traefik-manager-secrets`

### Issue: "Invalid Configuration" errors when creating routers

**Symptoms**: Form submission fails with validation error.

**Solution**:

1. Check rule syntax: Traefik docs on [routing rules](https://doc.traefik.io/traefik/v2.10/routing/routers/#rule)
2. Verify referenced service exists: Go to HTTP → Services first
3. Check middleware name is correct
4. Examine app logs: `docker compose logs traefik-manager | grep ERROR`

### Issue: "Backup import fails"

**Symptoms**: "Invalid backup file" or "etcd write failed".

**Solution**:

1. Verify JSON format: `python -m json.tool backup.json`
2. Check etcd has space available
3. Restore to test environment first
4. Try partial restore (one entity at a time)

### Issue: "High memory usage"

**Symptoms**: App crashes or becomes slow.

**Solution**:

1. Restart app: `docker compose restart traefik-manager`
2. Check for large configs: Export backup and count keys
3. Enable log compression: `docker compose logs --follow --tail=10 traefik-manager`
4. Scale to multiple pods (Kubernetes)

---

## Backup & Recovery

### Automatic Backups (Recommended)

```bash
#!/bin/bash
# backup.sh - Daily backup script

BACKUP_DIR="/backups/traefik-manager"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/traefik-backup-$TIMESTAMP.json"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Download backup via API (future v1.1)
# For now, manual export via UI

# Cleanup old backups (keep last 30 days)
find "$BACKUP_DIR" -name "traefik-backup-*.json" -mtime +30 -delete

# Backup SQLite
cp ./data/traefik_manager.db "$BACKUP_DIR/sqlite-$TIMESTAMP.db"

# Upload to S3/GCS (optional)
# aws s3 cp "$BACKUP_FILE" s3://backups/traefik-manager/

echo "✅ Backup completed: $BACKUP_FILE"
```

### Cron Job

```bash
# crontab -e
# Daily backup at 2 AM
0 2 * * * /path/to/backup.sh
```

### Recovery Procedure

```bash
# 1. Stop app
docker compose stop traefik-manager

# 2. Restore SQLite
cp ./data/traefik_manager.db.backup ./data/traefik_manager.db

# 3. Restore etcd (via UI or manual etcdctl)
# Option A: Use UI import (Config → Import Full Backup)
# Option B: Manual restore
#   etcdctl del /traefik/ --prefix
#   etcdctl put /traefik/http/routers/example/rule "Host(\`example.com\`)"
#   ...

# 4. Restart
docker compose up -d traefik-manager

# 5. Verify
docker compose exec traefik-manager curl http://localhost:8090/api/health
```

---

## Scaling & Performance Tuning

### Horizontal Scaling (Multiple Instances)

```yaml
# docker-compose.yml
services:
  traefik-manager-1:
    build: .
    environment:
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
      - ETCD_URL=http://etcd:2379
    ports:
      - "8090:8090"
    volumes:
      - shared-data:/app/data # Shared storage

  traefik-manager-2:
    build: .
    environment:
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
      - ETCD_URL=http://etcd:2379
    ports:
      - "8091:8090"
    volumes:
      - shared-data:/app/data

  traefik-manager-3:
    build: .
    environment:
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
      - ETCD_URL=http://etcd:2379
    ports:
      - "8092:8090"
    volumes:
      - shared-data:/app/data

volumes:
  shared-data:
    driver: local
```

### Performance Tuning

| Setting         | Recommendation | Impact                 |
| --------------- | -------------- | ---------------------- |
| etcd distance   | <50ms latency  | Lower = faster UI      |
| SQLite location | Local SSD      | Single-digit ms writes |
| Flask workers   | CPU cores × 2  | Parallelism            |
| etcd cluster    | 3+ nodes       | Fault tolerance        |
| Cache TTL       | 60s            | Refresh frequency      |

### Load Testing

```bash
# Using Apache Bench
ab -n 1000 -c 10 http://localhost:8090/

# Using wrk
wrk -t4 -c100 -d30s http://localhost:8090/
```

---

## Support & Documentation

- **Issues**: GitHub Issues
- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Development**: See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

---

**Last Updated**: February 2026  
**Maintainer**: GXNT TECH PVT LTD
