# Docker Quick Start

## Prerequisites

Generate certificates before running the container:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m tsa.cert_utils --dir certs
```

## Using Docker Compose (Recommended)

```bash
# Start the server
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the server
docker-compose down
```

## Using Docker CLI

### Build

```bash
docker build -t tsa-server .
```

### Run

```bash
docker run -d \
  --name tsa-server \
  -p 5000:5000 \
  -v $(pwd)/certs:/app/certs:ro \
  tsa-server
```

### Test

```bash
# Health check
curl http://localhost:5000/health

# Request timestamp (DER format)
curl -X POST http://localhost:5000/tsa \
  --data-binary "hello world" \
  --output timestamp.tsr

# Request timestamp (JSON format)
curl -X POST "http://localhost:5000/tsa?format=json" \
  --data-binary "hello world"
```

### Verify

```bash
# Install dependencies locally to run verify script
pip install -r requirements.txt

# Verify the timestamp reply
python tools/verify_tsr.py timestamp.tsr certs/tsa_cert.pem
```

## Production Deployment

For production use, consider:

1. **TLS/HTTPS**: Use a reverse proxy (nginx, traefik) with proper TLS certificates
2. **Certificate Management**: Mount certificates from a secure volume or secrets manager
3. **Resource Limits**: Set appropriate CPU and memory limits
4. **Monitoring**: Add logging and metrics collection
5. **Backup**: Regular backup of signing keys (in HSM/KMS ideally)

Example with resource limits:

```bash
docker run -d \
  --name tsa-server \
  -p 5000:5000 \
  -v /secure/path/certs:/app/certs:ro \
  --memory="512m" \
  --cpus="1.0" \
  --restart=unless-stopped \
  tsa-server
```

## Environment Variables

- `TSA_HOST` - Server host (default: 0.0.0.0)
- `TSA_PORT` - Server port (default: 5000)
- `TSA_CERT_DIR` - Certificate directory (default: /app/certs)
- `TSA_POLICY_OID` - Policy OID (default: 1.3.6.1.4.1.0)

## Troubleshooting

### Container won't start

Check logs:
```bash
docker logs tsa-server
```

### Certificate errors

Ensure certificates are properly mounted:
```bash
docker exec tsa-server ls -la /app/certs
```

### Health check fails

Test manually:
```bash
docker exec tsa-server curl http://localhost:5000/health
```
