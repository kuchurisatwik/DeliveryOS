"""Tiny in-process scan queue: webhook/UI submit jobs, worker threads run them.

Replaces Starlette ``BackgroundTasks`` for the security pipeline. Problems that
fixed nothing about: unbounded concurrency (two multi-minute CodeQL scans could
run at once and thrash a small box), no backpressure, and no dedupe (GitHub
redelivers a webhook and the same commit gets scanned twice — exactly the
duplicate PRs seen in testing).

This module is deliberately simple and dependency-free (stdlib ``queue`` +
``threading``):

* **Bounded concurrency** — ``workers`` long-lived threads pull one job at a time
  (default **1**, right for a small single-scan-at-a-time box like t3.medium).
* **Dedupe** — a job whose key (the commit SHA) is already queued or running is
  skipped, so redelivered/duplicate webhooks don't scan the same commit twice.
* **Backpressure** — a full queue rejects new jobs (caller returns HTTP 503).
* **Isolation** — one failing scan is logged and never kills the worker.

Tradeoff (accepted, documented): it's in-process, so a restart drops queued /
in-flight jobs — no worse than ``BackgroundTasks`` today. The :meth:`submit`
signature matches what a Redis/Celery-backed queue would expose, so swapping the
internals later needs no caller changes.
"""

from __future__ import annotations

import collections
import queue
import threading
import time
from typing import Any, Callable, Optional

from app.utils.logger import logger


class ScanQueue:
    """In-process job queue with bounded workers, dedupe, and backpressure."""

    def __init__(
        self,
        worker_fn: Callable[[Any], Any],
        key_fn: Callable[[Any], str],
        *,
        workers: int = 1,
        maxsize: int = 20,
    ) -> None:
        """Create the queue and start the worker threads.

        Args:
            worker_fn: Runs one job to completion (e.g. ``run_ai_sde_workflow``).
            key_fn: Extracts a job's dedupe key (e.g. the commit SHA).
            workers: Number of concurrent scans (keep small — CodeQL is heavy).
            maxsize: Max queued jobs before :meth:`submit` sheds with backpressure.
        """
        self._q: "queue.Queue[Any]" = queue.Queue(maxsize=maxsize)
        self._worker_fn = worker_fn
        self._key_fn = key_fn
        self._active: set[str] = set()  # keys queued or currently running
        self._recent: "collections.deque[dict]" = collections.deque(maxlen=50)
        self._lock = threading.Lock()
        self._workers = max(1, int(workers))
        for i in range(self._workers):
            threading.Thread(
                target=self._loop, name=f"scan-worker-{i}", daemon=True
            ).start()
        logger.info(
            "ScanQueue started: %d worker(s), maxsize=%d", self._workers, maxsize
        )

    # ------------------------------------------------------------------ #
    # Producer side
    # ------------------------------------------------------------------ #
    def submit(self, job: Any) -> str:
        """Enqueue a job. Returns 'accepted' | 'duplicate' | 'full'.

        * ``duplicate`` — the same key is already queued/running (skipped).
        * ``full`` — the queue is at capacity (caller should return HTTP 503).
        * ``accepted`` — enqueued for a worker.
        """
        try:
            key = str(self._key_fn(job))
        except Exception:  # noqa: BLE001 - a bad key must not crash the webhook
            key = ""

        with self._lock:
            if key and key in self._active:
                logger.info("ScanQueue: skipping duplicate job for key %s", key)
                return "duplicate"
            record = {
                "key": key,
                "kind": getattr(job, "kind", "push"),
                "repository": getattr(getattr(job, "repository", None), "full_name", ""),
                "status": "queued",
                "submitted_at": time.time(),
                "started_at": None,
                "finished_at": None,
            }
            try:
                self._q.put_nowait((job, record))
            except queue.Full:
                logger.warning("ScanQueue: full (maxsize reached); rejecting job")
                return "full"
            if key:
                self._active.add(key)
            self._recent.appendleft(record)
            return "accepted"

    def stats(self) -> dict[str, int]:
        """Lightweight snapshot for a status endpoint/UI."""
        with self._lock:
            return {"queued": self._q.qsize(), "active_keys": len(self._active)}

    def recent(self, limit: int = 20) -> list[dict]:
        """Return the most recent job records (newest first) for the UI."""
        with self._lock:
            return list(self._recent)[:limit]

    # ------------------------------------------------------------------ #
    # Consumer side
    # ------------------------------------------------------------------ #
    def _loop(self) -> None:
        while True:
            job, record = self._q.get()
            record["status"] = "running"
            record["started_at"] = time.time()
            try:
                self._worker_fn(job)
                record["status"] = "done"
            except Exception as exc:  # noqa: BLE001 - one bad scan never kills the worker
                logger.error("ScanQueue: job failed: %s", exc)
                record["status"] = "failed"
                record["error"] = str(exc)[:300]
            finally:
                record["finished_at"] = time.time()
                try:
                    key = str(self._key_fn(job))
                except Exception:  # noqa: BLE001
                    key = ""
                with self._lock:
                    self._active.discard(key)
                self._q.task_done()


#: Process-wide queue, created at app startup via :func:`init_scan_queue`.
scan_queue: Optional[ScanQueue] = None


def init_scan_queue(worker_fn: Callable[[Any], Any], key_fn: Callable[[Any], str]) -> ScanQueue:
    """Create (once) and return the process-wide scan queue from settings."""
    global scan_queue
    if scan_queue is not None:
        return scan_queue
    try:
        from app.config.settings import settings

        workers = int(getattr(settings, "SECURITY_SCAN_WORKERS", 1) or 1)
        maxsize = int(getattr(settings, "SECURITY_SCAN_QUEUE_MAX", 20) or 20)
    except Exception:  # noqa: BLE001 - never block startup on settings
        workers, maxsize = 1, 20
    scan_queue = ScanQueue(worker_fn, key_fn, workers=workers, maxsize=maxsize)
    return scan_queue
