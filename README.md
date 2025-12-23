# tsa-server

Minimal RFC3161-like Time-Stamping Authority (TSA) server implemented in Python for testing and demonstration purposes.

IMPORTANT: This project is a demonstration — it is NOT production-ready. It implements a simplified timestamp token flow and does not generate full CMS/TSTInfo structures.

## Features

- **RFC 3161-compliant TSA server** with CMS SignedData timestamp tokens
- **Production-ready** with Gunicorn WSGI server
- **Audit Chain** - Automatic trustworthiness verification through external TSAs (e.g., freetsa.org)
- **Docker support** - Pre-built images on GitHub Container Registry
- **Comprehensive test suite** - Unit tests, integration tests, coverage reporting
- **CI/CD pipeline** - Automated testing, building, and security scanning
- Test certificate generator for local development
- Health check endpoint for monitoring

## Quickstart

### Using Docker with Pre-built Images (Recommended)

```bash
# 1. Generate certificates
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m tsa.cert_utils --dir certs

# 2. Configure registry (create .env from template)
cp .env.example .env
# Edit .env and set GITHUB_REPOSITORY=your-username/tsa-server

# 3. Pull and run TSA Server + Audit Scheduler
docker compose -f docker-compose.audit.yml pull
docker compose -f docker-compose.audit.yml up -d

# 4. Check status
docker compose -f docker-compose.audit.yml ps
docker compose -f docker-compose.audit.yml logs -f
```

### Local Development (Build Images Locally)

```bash
# Generate certificates
python -m tsa.cert_utils --dir certs

# Build and run with local images
docker compose -f docker-compose.local.yml up -d
```

### Using Python directly

Clone the repo and create a virtual environment:

```bash
git clone <repo-url>
cd tsa-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Generate test certificates and start the server:

```bash
python -m tsa.cert_utils --dir certs
python -m tsa.server --host 127.0.0.1 --port 5000
```

Send a test timestamp request:

```bash
python client/request_ts.py --url http://127.0.0.1:5000/tsa --data "hello world"
# or
curl -X POST http://127.0.0.1:5000/tsa --data-binary "hello world"
```

The server responds with JSON similar to:

```json
{
  "algorithm": "sha256",
  "digest": "<sha256-hex>",
  "time": 1766398856,
  "signature": "<signature-hex>"
}
```

## Limitations & Security Notes

- **Test certificates**: Private keys are stored unencrypted in `certs/` — use HSM/KMS for production
- **No TLS**: Add reverse proxy (nginx, traefik) with TLS certificates for production
- **No authentication**: Consider adding API keys or OAuth2 for production deployments
- **Rate limiting**: Add rate limiting for production use
- **Monitoring**: Configure logging, metrics, and alerting for production

**Production Checklist:**
- ✅ Gunicorn WSGI server
- ✅ Docker multi-stage builds
- ✅ Health checks
- ✅ Audit chain for trustworthiness
- ✅ Automated testing and security scanning
- ⚠️ Add TLS/HTTPS
- ⚠️ Use HSM for key storage
- ⚠️ Add authentication
- ⚠️ Configure monitoring

## Testing

### Run Tests Locally

```bash
# Full test suite (like GitHub Actions)
make test-local

# Only unit tests
make test-unit

# With coverage report
make test-coverage
open htmlcov/index.html

# Linting only
make test-lint

# Auto-format code
make format
```

### Test Coverage

The project includes comprehensive tests:
- TSA server functionality tests
- Audit chain tests
- Certificate generation tests
- Integration tests with live server

## Verification

The server generates RFC 3161-compliant CMS SignedData structures. Verify a timestamp reply:

```bash
python tools/verify_tsr.py timestamp.tsr certs/tsa_cert.pem
# Output: Signature OK
```

Verify the audit chain:

```bash
python tools/verify_audit_chain.py audit_chain.db --verbose
```

The verifier checks:
- The signature over the SignedAttributes (content-type, message-digest, signing-time)
- That the signature was created with the private key corresponding to the TSA certificate

## Audit Chain for Trustworthiness

The TSA server includes an automatic audit chain system that proves trustworthiness through regular verification by external TSAs:

```bash
# Start audit scheduler (runs automatically with docker-compose.audit.yml)
python -m tsa.audit_scheduler

# View audit statistics
python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
           ac = AuditChain(Path('audit_chain.db')); \
           print(ac.get_statistics())"

# Export audit proof for customers
python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
           AuditChain(Path('audit_chain.db')).export_audit_proof(Path('proof.json'))"
```

**See [AUDIT_CHAIN.md](AUDIT_CHAIN.md) for complete documentation.**

## Next Steps (optional)

- Add TLS support for HTTPS endpoints
- Implement authentication and authorization (API keys, OAuth2)
- Add HSM/KMS integration for signing keys
- Configure monitoring and alerting
- Support for additional hash algorithms (SHA-384, SHA-512)

## Project Structure

- `tsa/server.py` — RFC 3161-compliant TSA HTTP endpoint with Gunicorn
- `tsa/cert_utils.py` — Test CA and TSA certificate generator
- `tsa/audit_chain.py` — Audit chain for trustworthiness verification
- `tsa/audit_scheduler.py` — Automatic audit timestamp scheduler
- `client/request_ts.py` — Simple client for testing
- `tools/verify_tsr.py` — Timestamp signature verification
- `tools/verify_audit_chain.py` — Audit chain verification
- `tests/` — Comprehensive test suite
- `docker-compose.audit.yml` — Production deployment with registry images
- `docker-compose.local.yml` — Local development with local builds
- `AUDIT_CHAIN.md` — Complete audit chain documentation

## License

This repository is provided as-is for demonstration and educational purposes.

## Endpoints

The server exposes a single TSA endpoint at `POST /tsa`. It supports two output modes:

- DER (default): returns a DER-encoded RFC3161-like timestamp reply (`Content-Type: application/timestamp-reply`) and sets `Content-Disposition: attachment; filename="timestamp.tsr"` so clients can save the reply.

  Example (save DER reply):

  ```bash
  curl -X POST http://127.0.0.1:5000/tsa --data-binary "hello world" --output timestamp.tsr
  # Content-Type: application/timestamp-reply
  # Content-Disposition: attachment; filename="timestamp.tsr"
  ```

- JSON (readable): request `?format=json` or send `Accept: application/json`. The server returns a readable JSON object with TSTInfo fields (`policy`, `message_imprint`, `gen_time`, `serial_number`, `accuracy`, `ordering`, `nonce`, `extensions`, `signature`).

  Example (query parameter):

  ```bash
  curl -X POST "http://127.0.0.1:5000/tsa?format=json" --data-binary "hello world" -H "Accept: application/json"
  ```

  Example (Accept header):

  ```bash
  curl -X POST http://127.0.0.1:5000/tsa --data-binary "hello world" -H "Accept: application/json"
  ```

Use the DER reply for binary interoperable timestamp replies; use the JSON form for quick inspection during development and debugging.


## Docker Deployment

### Using Pre-built Images

Images are automatically built and published to GitHub Container Registry via GitHub Actions:

- **TSA Server**: `ghcr.io/<username>/tsa-server:latest`
- **Audit Scheduler**: `ghcr.io/<username>/tsa-server:latest` (same image, different command)

```bash
# Pull latest images
docker pull ghcr.io/<username>/tsa-server:latest

# Run with docker-compose (recommended)
cp .env.example .env
# Edit .env: GITHUB_REPOSITORY=your-username/tsa-server
docker compose -f docker-compose.audit.yml up -d

# Or run manually
docker run -d -p 5000:5000 \
  -v $(pwd)/certs:/app/certs:ro \
  ghcr.io/<username>/tsa-server:latest
```

### Environment Variables

- `GITHUB_REPOSITORY` - Repository name (e.g., username/tsa-server)
- `IMAGE_TAG` - Image tag (default: latest)
- `TSA_CERT_DIR` - Certificate directory (default: /app/certs)
- `PYTHONUNBUFFERED` - Python output buffering (set to 1)

### Health Check

```bash
curl http://localhost:5000/health
# {"status":"ok","service":"tsa-server","version":"1.0.0"}
```

### Production Notes

- Uses **Gunicorn** WSGI server (4 workers)
- Multi-platform support: `linux/amd64`, `linux/arm64`
- Automatic health checks and restarts
- Security scanning with Trivy
- Supply chain attestation
