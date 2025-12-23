# TSA Server - Deployment Guide

## Production Deployment

### Prerequisites

- Docker and Docker Compose
- Generated TSA certificates (see below)
- GitHub Container Registry access (for pre-built images)

### 1. Certificate Generation

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate test certificates
python -m tsa.cert_utils --dir certs

# For production: Use proper CA-signed certificates
# Place them in certs/:
#   - tsa_key.pem (TSA private key)
#   - tsa_cert.pem (TSA certificate)
#   - ca_cert.pem (CA certificate)
```

### 2. Configuration

```bash
# Create .env file from template
cp .env.example .env

# Edit .env and configure:
nano .env
```

Required settings:
```bash
GITHUB_REPOSITORY=your-username/tsa-server
IMAGE_TAG=latest  # or specific version like v1.0.0
```

### 3. Deploy with Docker Compose

#### Option A: Using Pre-built Images (Recommended)

```bash
# Pull latest images from GitHub Container Registry
docker compose -f docker-compose.audit.yml pull

# Start services
docker compose -f docker-compose.audit.yml up -d

# Check status
docker compose -f docker-compose.audit.yml ps
docker compose -f docker-compose.audit.yml logs -f
```

#### Option B: Build Images Locally

```bash
# Build and start
docker compose -f docker-compose.local.yml up -d --build
```

### 4. Verify Deployment

```bash
# Health check
curl http://localhost:5000/health

# Create test timestamp
echo "test data" | curl -X POST http://localhost:5000/tsa --data-binary @- -o test.tsr

# Verify timestamp
python tools/verify_tsr.py test.tsr certs/tsa_cert.pem

# Check audit chain
docker compose -f docker-compose.audit.yml exec audit-scheduler \
  python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
             ac = AuditChain(Path('/data/audit_chain.db')); \
             print(ac.get_statistics())"
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Docker Compose Network          │
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │              │    │              │  │
│  │  TSA Server  │◄───│   Audit      │  │
│  │  :5000       │    │  Scheduler   │  │
│  │              │    │              │  │
│  │  - Gunicorn  │    │ - Hourly     │  │
│  │  - 4 workers │    │   audits     │  │
│  │  - Health    │    │ - FreeTSA    │  │
│  │    checks    │    │   verify     │  │
│  │              │    │              │  │
│  └──────┬───────┘    └──────┬───────┘  │
│         │                   │          │
│    Port 5000            Volume:        │
│                        audit_chain.db  │
│                                         │
└─────────────────────────────────────────┘
```

## Production Hardening

### 1. Add TLS/HTTPS

Use a reverse proxy (nginx, Traefik, Caddy):

```nginx
# nginx.conf
upstream tsa {
    server localhost:5000;
}

server {
    listen 443 ssl http2;
    server_name tsa.example.com;
    
    ssl_certificate /etc/ssl/certs/tsa.crt;
    ssl_certificate_key /etc/ssl/private/tsa.key;
    
    location / {
        proxy_pass http://tsa;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. Add Authentication

Option A: API Key (simple):
```bash
# Add to docker-compose environment
environment:
  - API_KEY=your-secret-key
```

Option B: OAuth2 Proxy:
```yaml
services:
  oauth2-proxy:
    image: quay.io/oauth2-proxy/oauth2-proxy:latest
    ports:
      - "4180:4180"
    environment:
      - OAUTH2_PROXY_PROVIDER=github
      - OAUTH2_PROXY_CLIENT_ID=...
      - OAUTH2_PROXY_CLIENT_SECRET=...
```

### 3. Monitoring & Logging

#### Prometheus Metrics

Add metrics exporter:
```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

#### Log Aggregation

```yaml
services:
  tsa-server:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 4. Backup Strategy

```bash
#!/bin/bash
# backup-audit-chain.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups

# Backup audit database
docker compose -f docker-compose.audit.yml exec -T audit-scheduler \
  cat /data/audit_chain.db > $BACKUP_DIR/audit_chain_$DATE.db

# Backup certificates
tar -czf $BACKUP_DIR/certs_$DATE.tar.gz certs/

# Keep only last 30 days
find $BACKUP_DIR -name "audit_chain_*.db" -mtime +30 -delete
```

Add to crontab:
```bash
0 2 * * * /path/to/backup-audit-chain.sh
```

## Scaling

### Horizontal Scaling (Multiple Replicas)

```yaml
services:
  tsa-server:
    image: ghcr.io/${GITHUB_REPOSITORY}:${IMAGE_TAG}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### Load Balancer

```yaml
services:
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "443:443"
    depends_on:
      - tsa-server
```

## Maintenance

### Update to New Version

```bash
# Pull new images
docker compose -f docker-compose.audit.yml pull

# Restart services (zero-downtime with health checks)
docker compose -f docker-compose.audit.yml up -d

# Verify
docker compose -f docker-compose.audit.yml ps
curl http://localhost:5000/health
```

### View Logs

```bash
# All services
docker compose -f docker-compose.audit.yml logs -f

# Specific service
docker compose -f docker-compose.audit.yml logs -f tsa-server
docker compose -f docker-compose.audit.yml logs -f audit-scheduler

# Last 100 lines
docker compose -f docker-compose.audit.yml logs --tail=100
```

### Access Audit Database

```bash
# Export audit proof
docker compose -f docker-compose.audit.yml exec audit-scheduler \
  python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
             AuditChain(Path('/data/audit_chain.db')).export_audit_proof(Path('/data/proof.json'))"

# Copy to host
docker compose -f docker-compose.audit.yml cp audit-scheduler:/data/proof.json ./

# View statistics
docker compose -f docker-compose.audit.yml exec audit-scheduler \
  python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
             import json; print(json.dumps(AuditChain(Path('/data/audit_chain.db')).get_statistics(), indent=2))"
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose -f docker-compose.audit.yml logs

# Check health
docker compose -f docker-compose.audit.yml ps

# Restart specific service
docker compose -f docker-compose.audit.yml restart tsa-server
```

### Certificates Not Found

```bash
# Verify certificate mount
docker compose -f docker-compose.audit.yml exec tsa-server ls -la /app/certs/

# Regenerate if needed
python -m tsa.cert_utils --dir certs
docker compose -f docker-compose.audit.yml restart
```

### Audit Chain Not Working

```bash
# Check audit-scheduler logs
docker compose -f docker-compose.audit.yml logs audit-scheduler

# Manual audit test
docker compose -f docker-compose.audit.yml exec audit-scheduler \
  python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
             ac = AuditChain(Path('/data/audit_chain.db')); \
             result = ac.create_audit_timestamp('http://tsa-server:5000/tsa'); \
             print(f'Status: {result.status}')"
```

### Network Issues

```bash
# Check network connectivity
docker compose -f docker-compose.audit.yml exec audit-scheduler ping tsa-server

# Test external TSA
docker compose -f docker-compose.audit.yml exec audit-scheduler \
  curl -I https://freetsa.org/tsr
```

## Security Checklist

- [ ] Use proper CA-signed certificates (not self-signed)
- [ ] Enable TLS/HTTPS (reverse proxy)
- [ ] Add authentication (API keys or OAuth2)
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerts
- [ ] Regular backups of audit database
- [ ] Rotate credentials regularly
- [ ] Keep images updated
- [ ] Review security scan results
- [ ] Implement rate limiting
- [ ] Use secrets management (Docker secrets, Vault)

## CI/CD Integration

Images are automatically built and pushed to GitHub Container Registry when you push to main/master:

1. **Push code** → GitHub Actions triggers
2. **Run tests** → Pytest, linting, type checking
3. **Build images** → Multi-platform (amd64, arm64)
4. **Security scan** → Trivy vulnerability scanning
5. **Push to registry** → ghcr.io/username/tsa-server:latest
6. **Deploy** → Pull and restart on your server

### Automatic Deployment

Create a webhook or use GitHub Actions for automatic deployment:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  workflow_run:
    workflows: ["CI/CD Pipeline"]
    types:
      - completed

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            cd /opt/tsa-server
            docker compose -f docker-compose.audit.yml pull
            docker compose -f docker-compose.audit.yml up -d
```
