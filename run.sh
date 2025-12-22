#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  python -m venv .venv
fi
. .venv/bin/activate
pip install -r requirements.txt

echo "Ready. Use: python -m tsa.cert_utils --dir certs && python -m tsa.server"
