"""
Automatic scheduler for TSA audit chain creation.

Runs in background and creates regular audit timestamps.
"""

import logging
import signal
import sys
import time
from pathlib import Path
from threading import Event, Thread

from .audit_chain import AuditChain

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AuditScheduler:
    """
    Background scheduler for automatic audit timestamp creation.
    """

    def __init__(
        self,
        audit_chain: AuditChain,
        local_tsa_url: str,
        interval_seconds: int = 3600,  # Default: hourly
    ):
        """
        Initialize audit scheduler.

        Args:
            audit_chain: AuditChain instance
            local_tsa_url: URL of local TSA server
            interval_seconds: Interval between audits (default: 3600 = 1 hour)
        """
        self.audit_chain = audit_chain
        self.local_tsa_url = local_tsa_url
        self.interval_seconds = interval_seconds
        self.stop_event = Event()
        self.thread: Thread = None

    def start(self):
        """Start the scheduler in a background thread"""
        if self.thread and self.thread.is_alive():
            logger.warning("Scheduler already running")
            return

        logger.info(f"Starting audit scheduler (interval: {self.interval_seconds}s)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping audit scheduler")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def _run_loop(self):
        """Main scheduler loop"""
        # Create initial audit immediately
        self._create_audit()

        while not self.stop_event.is_set():
            # Wait for interval or stop signal
            if self.stop_event.wait(timeout=self.interval_seconds):
                break  # Stop signal received

            # Create audit
            self._create_audit()

    def _create_audit(self):
        """Create a single audit timestamp"""
        try:
            logger.info("Creating audit timestamp...")
            record = self.audit_chain.create_audit_timestamp(self.local_tsa_url)

            if record.status == "success":
                logger.info(f"✓ Audit successful: {record.local_token_hash[:16]}...")
            else:
                logger.error(f"✗ Audit failed: {record.error_message}")

            # Log statistics
            stats = self.audit_chain.get_statistics()
            logger.info(
                f"Stats: {stats['total_audits']} total, "
                f"{stats['success_rate']:.1f}% success rate"
            )

        except Exception as e:
            logger.error(f"Failed to create audit: {e}", exc_info=True)


def main():
    """CLI entry point for running audit scheduler"""
    import argparse

    parser = argparse.ArgumentParser(
        description="TSA Audit Scheduler - Automatic trustworthiness verification"
    )
    parser.add_argument(
        "--db",
        default="audit_chain.db",
        help="Path to audit database (default: audit_chain.db)",
    )
    parser.add_argument(
        "--local-tsa",
        default="http://127.0.0.1:5000/tsa",
        help="URL of local TSA server (default: http://127.0.0.1:5000/tsa)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Audit interval in seconds (default: 3600 = 1 hour)",
    )
    parser.add_argument(
        "--external-tsa",
        action="append",
        help="External TSA URL (can be specified multiple times)",
    )

    args = parser.parse_args()

    # Setup audit chain
    db_path = Path(args.db)
    external_tsas = args.external_tsa or ["https://freetsa.org/tsr"]

    audit_chain = AuditChain(db_path, external_tsas)
    scheduler = AuditScheduler(audit_chain, args.local_tsa, args.interval)

    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start scheduler
    scheduler.start()

    logger.info("Audit scheduler running. Press Ctrl+C to stop.")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    main()
