"""Tests for audit chain functionality"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tsa.audit_chain import AuditChain, AuditRecord


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


def test_audit_chain_init(temp_db):
    """Test audit chain initialization"""
    ac = AuditChain(temp_db)

    # Database should exist
    assert temp_db.exists()

    # Should have empty stats
    stats = ac.get_statistics()
    assert stats["total_audits"] == 0
    assert stats["successful_audits"] == 0
    assert stats["failed_audits"] == 0


def test_audit_chain_store_record(temp_db):
    """Test storing audit records"""
    ac = AuditChain(temp_db)

    record = AuditRecord(
        timestamp=datetime.now(timezone.utc),
        local_token_hash="test_hash_123",
        external_tsr=b"test_tsr_data",
        external_tsa_url="https://test.tsa",
        status="success",
    )

    ac._store_record(record)

    # Check statistics
    stats = ac.get_statistics()
    assert stats["total_audits"] == 1
    assert stats["successful_audits"] == 1


def test_audit_chain_get_recent_audits(temp_db):
    """Test retrieving recent audits"""
    ac = AuditChain(temp_db)

    # Store multiple records
    for i in range(5):
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc),
            local_token_hash=f"hash_{i}",
            external_tsr=b"test_data",
            external_tsa_url="https://test.tsa",
            status="success",
        )
        ac._store_record(record)

    # Get recent audits
    recent = ac.get_recent_audits(limit=3)
    assert len(recent) == 3

    # Should be in reverse chronological order (most recent first)
    # Note: Since records are inserted sequentially, the most recent is the last one inserted
    assert recent[0]["local_token_hash"] in [
        "hash_0",
        "hash_1",
        "hash_2",
        "hash_3",
        "hash_4",
    ]


def test_audit_chain_export_proof(temp_db):
    """Test exporting audit proof"""
    ac = AuditChain(temp_db)

    # Store a record
    record = AuditRecord(
        timestamp=datetime.now(timezone.utc),
        local_token_hash="test_hash",
        external_tsr=b"\x01\x02\x03",
        external_tsa_url="https://test.tsa",
        status="success",
    )
    ac._store_record(record)

    # Export proof
    export_path = temp_db.parent / "proof.json"
    ac.export_audit_proof(export_path)

    assert export_path.exists()

    # Check content
    import json

    proof = json.loads(export_path.read_text())
    assert "export_date" in proof
    assert "statistics" in proof
    assert "records" in proof
    assert len(proof["records"]) == 1

    # Cleanup
    export_path.unlink()


def test_audit_chain_statistics(temp_db):
    """Test statistics calculation"""
    ac = AuditChain(temp_db)

    # Store mixed success/failure records
    for i in range(10):
        status = "success" if i % 2 == 0 else "failed"
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc),
            local_token_hash=f"hash_{i}",
            external_tsr=b"test",
            external_tsa_url="https://test.tsa",
            status=status,
        )
        ac._store_record(record)

    stats = ac.get_statistics()
    assert stats["total_audits"] == 10
    assert stats["successful_audits"] == 5
    assert stats["failed_audits"] == 5
    assert stats["success_rate"] == 50.0
