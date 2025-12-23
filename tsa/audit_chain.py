"""
TSA Audit Chain - Automatic trustworthiness verification through external TSA

This module creates audit trails by timestamping your own TSA operations
with external trusted TSAs (e.g., freetsa.org), creating a verifiable
chain of trust.
"""

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class AuditRecord:
    """Record of an audit timestamp operation"""

    timestamp: datetime
    local_token_hash: str  # Hash of our TSA token
    external_tsr: bytes  # TSR from external TSA
    external_tsa_url: str
    status: str  # 'success', 'failed', 'pending'
    error_message: Optional[str] = None


class AuditChain:
    """
    Manages the audit chain for TSA server trustworthiness.

    Regularly creates audit records by:
    1. Generating a local timestamp
    2. Sending it to an external TSA for verification
    3. Storing both timestamps in an audit database
    """

    def __init__(self, db_path: Path, external_tsas: Optional[list[str]] = None):
        """
        Initialize audit chain manager.

        Args:
            db_path: Path to SQLite database for audit records
            external_tsas: List of external TSA URLs (default: freetsa.org)
        """
        self.db_path = db_path
        self.external_tsas = external_tsas or [
            "https://freetsa.org/tsr",
            # Add backups in case primary is down
        ]
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for audit records"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                local_token_hash TEXT NOT NULL,
                external_tsr BLOB,
                external_tsa_url TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at INTEGER NOT NULL
            )
        """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_records(timestamp)
        """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_status ON audit_records(status)
        """
        )
        conn.commit()
        conn.close()

    def create_audit_timestamp(
        self, local_tsa_url: str, test_data: Optional[bytes] = None
    ) -> AuditRecord:
        """
        Create an audit record by timestamping with external TSA.

        Args:
            local_tsa_url: URL of your local TSA server
            test_data: Optional test data (default: current timestamp)

        Returns:
            AuditRecord with the results
        """
        if test_data is None:
            test_data = f"TSA-AUDIT-{datetime.now(timezone.utc).isoformat()}".encode()

        now = datetime.now(timezone.utc)

        try:
            # Step 1: Get timestamp from our local TSA
            logger.info(f"Requesting local timestamp from {local_tsa_url}")
            local_resp = requests.post(local_tsa_url, data=test_data, timeout=10)
            local_resp.raise_for_status()
            local_token = local_resp.content
            local_token_hash = hashlib.sha256(local_token).hexdigest()

            # Step 2: Send local token to external TSA for verification
            external_tsr = None
            external_url = None
            error_msg = None

            for tsa_url in self.external_tsas:
                try:
                    logger.info(f"Requesting external timestamp from {tsa_url}")
                    external_tsr = self._request_rfc3161_timestamp(tsa_url, local_token)
                    external_url = tsa_url
                    break  # Success, use this TSA
                except Exception as e:
                    logger.warning(f"Failed to get timestamp from {tsa_url}: {e}")
                    error_msg = str(e)
                    continue

            if external_tsr is None:
                # All external TSAs failed
                status = "failed"
                error_msg = f"All external TSAs failed. Last error: {error_msg}"
            else:
                status = "success"
                error_msg = None

            record = AuditRecord(
                timestamp=now,
                local_token_hash=local_token_hash,
                external_tsr=external_tsr or b"",
                external_tsa_url=external_url or "none",
                status=status,
                error_message=error_msg,
            )

            # Store in database
            self._store_record(record)

            return record

        except Exception as e:
            logger.error(f"Audit timestamp creation failed: {e}")
            record = AuditRecord(
                timestamp=now,
                local_token_hash="",
                external_tsr=b"",
                external_tsa_url="none",
                status="failed",
                error_message=str(e),
            )
            self._store_record(record)
            return record

    def _request_rfc3161_timestamp(self, tsa_url: str, data: bytes) -> bytes:
        """
        Request RFC 3161 timestamp from external TSA.

        Args:
            tsa_url: URL of the TSA server
            data: Data to timestamp

        Returns:
            TSR (TimeStampResp) bytes
        """
        from asn1crypto import core, tsp

        # Create RFC 3161 TimeStampReq
        digest = hashlib.sha256(data).digest()

        req = tsp.TimeStampReq(
            {
                "version": "v1",
                "message_imprint": {
                    "hash_algorithm": {"algorithm": "sha256"},
                    "hashed_message": digest,
                },
                "cert_req": True,  # Request certificate in response
            }
        )

        req_der = req.dump()

        # Send request
        response = requests.post(
            tsa_url,
            data=req_der,
            headers={"Content-Type": "application/timestamp-query"},
            timeout=30,
        )
        response.raise_for_status()

        # Parse response
        tsr = tsp.TimeStampResp.load(response.content)

        # Check status
        status = tsr["status"]
        if status["status"].native != "granted":
            failure = status.get("failure_info")
            raise ValueError(f"TSA request failed: {failure}")

        return bytes(response.content)

    def _store_record(self, record: AuditRecord):
        """Store audit record in database"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_records 
            (timestamp, local_token_hash, external_tsr, external_tsa_url, status, error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.timestamp.isoformat(),
                record.local_token_hash,
                record.external_tsr,
                record.external_tsa_url,
                record.status,
                record.error_message,
                int(time.time()),
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"Stored audit record: {record.status}")

    def get_recent_audits(self, limit: int = 100) -> list[dict]:
        """Get recent audit records"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT timestamp, local_token_hash, external_tsa_url, status, error_message, created_at
            FROM audit_records
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        records = []
        for row in cur.fetchall():
            records.append(
                {
                    "timestamp": row[0],
                    "local_token_hash": row[1],
                    "external_tsa_url": row[2],
                    "status": row[3],
                    "error_message": row[4],
                    "created_at": row[5],
                }
            )

        conn.close()
        return records

    def get_statistics(self) -> dict:
        """Get audit chain statistics"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Total records
        cur.execute("SELECT COUNT(*) FROM audit_records")
        total = cur.fetchone()[0]

        # Success rate
        cur.execute('SELECT COUNT(*) FROM audit_records WHERE status = "success"')
        success = cur.fetchone()[0]

        # Last audit
        cur.execute(
            "SELECT timestamp, status FROM audit_records ORDER BY created_at DESC LIMIT 1"
        )
        last = cur.fetchone()

        # Failure stats
        cur.execute('SELECT COUNT(*) FROM audit_records WHERE status = "failed"')
        failed = cur.fetchone()[0]

        conn.close()

        return {
            "total_audits": total,
            "successful_audits": success,
            "failed_audits": failed,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "last_audit_time": last[0] if last else None,
            "last_audit_status": last[1] if last else None,
        }

    def export_audit_proof(self, output_path: Path, limit: Optional[int] = None):
        """
        Export audit chain as proof of trustworthiness.

        Creates a JSON file with all audit records and external TSRs
        that can be independently verified.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        query = "SELECT * FROM audit_records ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)

        proof: dict = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "statistics": self.get_statistics(),
            "records": [],
        }

        for row in cur.fetchall():
            proof["records"].append(
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "local_token_hash": row[2],
                    "external_tsr_hex": row[3].hex() if row[3] else None,
                    "external_tsa_url": row[4],
                    "status": row[5],
                    "error_message": row[6],
                    "created_at": row[7],
                }
            )

        conn.close()

        output_path.write_text(json.dumps(proof, indent=2))
        logger.info(f"Exported audit proof to {output_path}")
