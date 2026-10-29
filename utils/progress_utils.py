"""
Thread-safe job progress tracking for real-time UI updates.
"""

import threading
from datetime import datetime

_lock = threading.Lock()
_jobs = {}


def init_job(job_id):
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "percent": 0,
            "message": "Uploading document...",
            "status": "processing",
            "updated_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }


def set_progress(job_id, percent, message, status="processing"):
    with _lock:
        if job_id not in _jobs:
            init_job(job_id)
        _jobs[job_id].update({
            "percent": max(0, min(100, int(percent))),
            "message": message,
            "status": status,
            "updated_at": datetime.now().isoformat(),
        })


def complete_job(job_id, result):
    with _lock:
        if job_id not in _jobs:
            init_job(job_id)
        _jobs[job_id].update({
            "percent": 100,
            "message": "Completed",
            "status": "completed",
            "result": result,
            "updated_at": datetime.now().isoformat(),
        })


def fail_job(job_id, error_message):
    with _lock:
        if job_id not in _jobs:
            init_job(job_id)
        _jobs[job_id].update({
            "percent": 0,
            "message": error_message,
            "status": "failed",
            "error": error_message,
            "updated_at": datetime.now().isoformat(),
        })


def get_progress(job_id):
    with _lock:
        return dict(_jobs.get(job_id, {
            "job_id": job_id,
            "percent": 0,
            "message": "Unknown job",
            "status": "unknown",
        }))


def cleanup_job(job_id):
    with _lock:
        _jobs.pop(job_id, None)
