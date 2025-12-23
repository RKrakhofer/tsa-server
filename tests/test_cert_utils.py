"""Tests for certificate utilities"""

import tempfile
from pathlib import Path

import pytest

from tsa.cert_utils import generate


@pytest.fixture
def temp_cert_dir():
    """Create temporary directory for certificates"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_generate_test_certs(temp_cert_dir):
    """Test certificate generation"""
    generate(temp_cert_dir)

    # Check that all required files were created
    assert (temp_cert_dir / "ca_key.pem").exists()
    assert (temp_cert_dir / "ca_cert.pem").exists()
    assert (temp_cert_dir / "tsa_key.pem").exists()
    assert (temp_cert_dir / "tsa_cert.pem").exists()


def test_cert_files_not_empty(temp_cert_dir):
    """Test that generated cert files have content"""
    generate(temp_cert_dir)

    for filename in ["ca_key.pem", "ca_cert.pem", "tsa_key.pem", "tsa_cert.pem"]:
        filepath = temp_cert_dir / filename
        assert filepath.stat().st_size > 0


def test_certs_are_valid_pem(temp_cert_dir):
    """Test that generated certs are valid PEM format"""
    generate(temp_cert_dir)

    # Check PEM headers
    ca_cert = (temp_cert_dir / "ca_cert.pem").read_text()
    assert "-----BEGIN CERTIFICATE-----" in ca_cert
    assert "-----END CERTIFICATE-----" in ca_cert

    tsa_cert = (temp_cert_dir / "tsa_cert.pem").read_text()
    assert "-----BEGIN CERTIFICATE-----" in tsa_cert
    assert "-----END CERTIFICATE-----" in tsa_cert
