from __future__ import annotations

import threading
from typing import Dict, Optional

from domain.models import JobState
from usecases.ports import JobStorePort


class InMemoryJobStore(JobStorePort):
    """シンプルなスレッドセーフなメモリ上の JobStore。"""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create(self, job: JobState) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Optional[JobState]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job: JobState) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

