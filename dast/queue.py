"""The DAST service's own scan queue.

Reuses the SAST pipeline's :class:`~app.workflows.scan_queue.ScanQueue` (stdlib
threads, bounded workers, dedupe, backpressure) but as a **separate instance** with
its own settings. Sharing the queue itself was the thing we set out to avoid: a
45-minute web scan sitting in the SAST queue blocks every code scan behind it.

Two differences from the SAST wiring:

* **Dedupe key is the target, not the commit.** Two scans of the same URL at once
  would have both tools' traffic hitting one app and neither result would be
  trustworthy. Two scans of *different* targets are fine.
* **Workers default to 1** for the same reason.
"""

from __future__ import annotations

from typing import Optional

from app.utils.logger import logger
from app.workflows.scan_queue import ScanQueue
from dast.config import dast_settings

#: Process-wide DAST queue, created at service startup.
dast_queue: Optional[ScanQueue] = None


def job_key(job) -> str:
    """Dedupe key for a queued scan: one scan per target + profile at a time."""
    return f"{getattr(job, 'target_url', '')}|{getattr(job, 'profile', '')}"


def init_dast_queue(worker_fn) -> ScanQueue:
    """Create (once) and return the process-wide DAST scan queue."""
    global dast_queue
    if dast_queue is not None:
        return dast_queue
    dast_queue = ScanQueue(
        worker_fn,
        job_key,
        workers=max(1, int(dast_settings.DAST_SCAN_WORKERS or 1)),
        maxsize=max(1, int(dast_settings.DAST_SCAN_QUEUE_MAX or 20)),
    )
    logger.info("DAST scan queue ready")
    return dast_queue
