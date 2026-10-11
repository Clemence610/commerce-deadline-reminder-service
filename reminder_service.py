"""Typed order updates and deterministic deadline decisions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Lock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from infrai_client import InfraiClient, InfraiError


class OrderStage(str, Enum):
    CHECKOUT_OPEN = "checkout_open"
    PAID = "paid"
    FULFILLED = "fulfilled"
    RECEIPT_READY = "receipt_ready"
    CUSTOMER_UPDATED = "customer_updated"


class OrderUpdate(BaseModel):
    order_ref: str = Field(min_length=1, max_length=80)
    stage: OrderStage
    occurred_at: datetime
    deadline_at: datetime | None = None


class ReminderDecision(BaseModel):
    order_ref: str
    event: str
    remind_at: datetime


def choose_reminder(update: OrderUpdate) -> ReminderDecision | None:
    """Return the next useful reminder, or None after customer notification."""
    occurred = update.occurred_at.astimezone(timezone.utc)
    if update.stage is OrderStage.CUSTOMER_UPDATED:
        return None
    if update.stage is OrderStage.CHECKOUT_OPEN:
        deadline = update.deadline_at or occurred + timedelta(hours=1)
        remind_at = deadline.astimezone(timezone.utc) - timedelta(minutes=15)
        event = "checkout_deadline"
    elif update.stage is OrderStage.PAID:
        remind_at = occurred + timedelta(hours=24)
        event = "fulfillment_due"
    elif update.stage is OrderStage.FULFILLED:
        remind_at = occurred + timedelta(minutes=5)
        event = "receipt_due"
    else:
        remind_at = occurred
        event = "customer_update_due"
    return ReminderDecision(order_ref=update.order_ref, event=event, remind_at=remind_at)


class ReminderBook:
    def __init__(self) -> None:
        self._items: dict[str, ReminderDecision] = {}
        self._lock = Lock()

    def replace(self, decision: ReminderDecision | None, order_ref: str) -> None:
        with self._lock:
            if decision is None:
                self._items.pop(order_ref, None)
            else:
                self._items[order_ref] = decision

    def take_due(self, now: datetime) -> list[ReminderDecision]:
        with self._lock:
            due = [item for item in self._items.values() if item.remind_at <= now]
            for item in due:
                del self._items[item.order_ref]
            return due


book = ReminderBook()
app = FastAPI(title="E-commerce deadline reminders")


@app.post("/orders/update", response_model=ReminderDecision | None)
def record_update(update: OrderUpdate) -> ReminderDecision | None:
    decision = choose_reminder(update)
    book.replace(decision, update.order_ref)
    return decision


@app.post("/reminders/due")
def publish_due(now: datetime | None = None) -> dict[str, int]:
    scan_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    due = book.take_due(scan_time)
    infrai = InfraiClient()
    try:
        for item in due:
            payload = {
                "order_ref": item.order_ref,
                "event": item.event,
                "remind_at": item.remind_at.isoformat(),
            }
            infrai.queue.publish(queue="customer-updates", payload=payload)
    except InfraiError as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from error
    return {"published": len(due)}


def install_scan(worker_url: str) -> str:
    infrai = InfraiClient()
    result = infrai.cron.create(cron_expr="*/5 * * * *", task=f"{worker_url}/reminders/due")
    return str(result["job_id"])
