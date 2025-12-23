"""Tests for TSA server functionality"""

import hashlib
import time
from multiprocessing import Process
from pathlib import Path

import pytest
import requests

from tsa.server import app


@pytest.fixture(scope="module")
def test_certs(tmp_path_factory):
    """Generate test certificates"""
    from tsa.cert_utils import generate

    cert_dir = tmp_path_factory.mktemp("certs")
    generate(cert_dir)


@pytest.fixture(scope="module")
def server_url(test_certs):
    """Start test server and return URL"""
    import os

    # Set cert paths
    os.environ["TSA_CERT_DIR"] = str(test_certs)

    def run_server():
        app.run(host="127.0.0.1", port=5555, debug=False, use_reloader=False)

    # Start server in subprocess
    proc = Process(target=run_server, daemon=True)
    proc.start()

    # Wait for server to start
    time.sleep(2)

    url = "http://127.0.0.1:5555"

    # Verify server is running
    for _ in range(10):
        try:
            requests.get(f"{url}/health", timeout=1)
            break
        except requests.exceptions.RequestException:
            time.sleep(0.5)

    yield url

    # Cleanup
    proc.terminate()
    proc.join(timeout=5)


def test_health_endpoint(server_url):
    """Test health check endpoint"""
    response = requests.get(f"{server_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "tsa-server"


def test_timestamp_creation(server_url):
    """Test timestamp token creation"""
    test_data = b"test data for timestamp"

    response = requests.post(f"{server_url}/tsa", data=test_data)
    assert response.status_code == 200

    # Response should be binary (timestamp token)
    assert len(response.content) > 0


def test_timestamp_different_data(server_url):
    """Test that different data produces different tokens"""
    data1 = b"first data"
    data2 = b"second data"

    token1 = requests.post(f"{server_url}/tsa", data=data1).content
    token2 = requests.post(f"{server_url}/tsa", data=data2).content

    # Tokens should be different
    assert token1 != token2


def test_empty_data(server_url):
    """Test timestamp with empty data"""
    # Empty data should return 400 Bad Request or work, depending on server implementation
    response = requests.post(f"{server_url}/tsa", data=b"")

    # Accept either 200 (works) or 400 (rejected)
    assert response.status_code in [200, 400]


def test_large_data(server_url):
    """Test timestamp with large data"""
    large_data = b"x" * 1024 * 100  # 100 KB

    response = requests.post(f"{server_url}/tsa", data=large_data)
    assert response.status_code == 200
