"""Tests for the in-process ScanQueue: dedupe, backpressure, one-at-a-time."""

from __future__ import annotations

import threading
import time

from app.workflows.scan_queue import ScanQueue


class _Job:
    def __init__(self, sha):
        self.after = sha


def _key(job):
    return job.after


def test_runs_job_and_dedupes_same_key_in_flight():
    started = threading.Event()
    release = threading.Event()
    ran: list[str] = []

    def worker(job):
        ran.append(job.after)
        started.set()
        release.wait(timeout=5)  # hold the worker so the key stays "active"

    q = ScanQueue(worker, _key, workers=1, maxsize=10)
    assert q.submit(_Job("abc")) == "accepted"
    assert started.wait(timeout=5)
    # Same SHA while the first is still running → deduped.
    assert q.submit(_Job("abc")) == "duplicate"
    release.set()


def test_backpressure_returns_full():
    release = threading.Event()

    def worker(job):
        release.wait(timeout=5)  # block the single worker

    # maxsize=1: one job occupies the worker, one sits in the queue, next is full.
    q = ScanQueue(worker, _key, workers=1, maxsize=1)
    assert q.submit(_Job("s1")) == "accepted"  # goes to worker
    time.sleep(0.1)
    assert q.submit(_Job("s2")) == "accepted"  # sits in the queue (size 1)
    assert q.submit(_Job("s3")) == "full"      # queue full → backpressure
    release.set()


def test_one_at_a_time_with_single_worker():
    concurrent = []
    current = {"n": 0}
    lock = threading.Lock()

    def worker(job):
        with lock:
            current["n"] += 1
            concurrent.append(current["n"])
        time.sleep(0.05)
        with lock:
            current["n"] -= 1

    q = ScanQueue(worker, _key, workers=1, maxsize=10)
    for i in range(5):
        q.submit(_Job(f"sha{i}"))
    q._q.join()  # wait for all jobs to finish
    # With a single worker, no two jobs ever overlap → max observed concurrency 1.
    assert max(concurrent) == 1


def test_key_released_after_completion_allows_rescan():
    ran: list[str] = []

    def worker(job):
        ran.append(job.after)

    q = ScanQueue(worker, _key, workers=1, maxsize=10)
    assert q.submit(_Job("x")) == "accepted"
    q._q.join()
    # After completion the key is freed, so the same SHA can be scanned again.
    assert q.submit(_Job("x")) == "accepted"
    q._q.join()
    assert ran == ["x", "x"]
