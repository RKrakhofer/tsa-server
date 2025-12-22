# tsa-server

Minimal RFC3161-like Time-Stamping Authority (TSA) server implemented in Python for testing and demonstration purposes.

IMPORTANT: This project is a demonstration — it is NOT production-ready. It implements a simplified timestamp token flow and does not generate full CMS/TSTInfo structures.

## Features

- Minimal TSA HTTP endpoint (`POST /tsa`) that accepts raw data and returns a signed timestamp token (JSON with `digest`, `time`, `signature`).
- Test certificate generator (`tsa.cert_utils`) that creates a test CA and TSA certificate for local testing.
- Small client script for basic requests.

## Quickstart

### Using Docker (Recommended)

```bash
# Generate certificates first
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m tsa.cert_utils --dir certs

# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t tsa-server .
docker run -d -p 5000:5000 -v $(pwd)/certs:/app/certs:ro tsa-server
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

- This is a demonstration implementation. For production use, consider additional features like HSM integration, audit logging, and rate limiting.
- Private keys are stored on disk unencrypted in `certs/` for convenience — do not do this in production.
- The Flask development server is used; use a production WSGI server and TLS for real deployments.

## Verification

The server generates RFC 3161-compliant CMS SignedData structures. Verify a timestamp reply:

```bash
python tools/verify_tsr.py timestamp.tsr certs/tsa_cert.pem
# Output: Signature OK
```

The verifier checks:
- The signature over the SignedAttributes (content-type, message-digest, signing-time)
- That the signature was created with the private key corresponding to the TSA certificate

## Next Steps (optional)

- Add TLS support for HTTPS endpoints.
- Implement authentication and authorization (API keys, OAuth2).
- Add HSM/KMS integration for signing keys.
- Add comprehensive audit logging and rate limiting.
- Support for additional hash algorithms (SHA-384, SHA-512).

## Files of interest

- `tsa/cert_utils.py` — helper to generate test CA and TSA certs
- `tsa/server.py` — RFC 3161-compliant TSA HTTP endpoint with CMS SignedData generation
- `client/request_ts.py` — simple client for testing
- `tools/verify_tsr.py` — signature verification tool for timestamp replies

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

### Pull from GitHub Container Registry

```bash
docker pull ghcr.io/<username>/tsa-server:latest
docker run -d -p 5000:5000 -v $(pwd)/certs:/app/certs:ro ghcr.io/<username>/tsa-server:latest
```

### Environment Variables

- `TSA_HOST` - Server host (default: 0.0.0.0)
- `TSA_PORT` - Server port (default: 5000)
- `TSA_CERT_DIR` - Certificate directory (default: /app/certs)

### Health Check

```bash
curl http://localhost:5000/health
# {"status":"ok","service":"tsa-server","version":"1.0.0"}
```
