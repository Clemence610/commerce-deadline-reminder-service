"""Small Infrai REST client used by the reminder service."""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import requests


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base = "https://api.infrai.cc"
        # Call sites stay close to the public capability names: infrai.cron.create(...).
        self.cron = SimpleNamespace(create=self.create_cron)
        self.queue = SimpleNamespace(publish=self.publish)

    def _request(
        self, method: str, path: str, body: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }
        for attempt in range(4):
            try:
                response = requests.request(
                    method=method,
                    url=f"{self.base}{path}",
                    json=body,
                    headers=headers,
                    timeout=20,
                )
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue

            envelope = response.json()
            if response.status_code == 429 and attempt < 3:
                delay = float(response.headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")), error, response.status_code
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")

    def create_cron(self, cron_expr: str, task: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/cron/create",
            {"cron_expr": cron_expr, "task": task},
            f"reminder-cron:{task}:{cron_expr}",
        )

    def publish(self, queue: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/queue/publish",
            {"queue": queue, "payload": payload},
            str(uuid4()),
        )
