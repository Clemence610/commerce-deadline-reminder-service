from datetime import datetime, timezone

from fastapi.testclient import TestClient

from reminder_service import OrderStage, OrderUpdate, app, choose_reminder


def test_checkout_reminder_is_fifteen_minutes_before_deadline() -> None:
    update = OrderUpdate(
        order_ref="ord_2048",
        stage=OrderStage.CHECKOUT_OPEN,
        occurred_at=datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc),
        deadline_at=datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
    )

    decision = choose_reminder(update)

    assert decision is not None
    assert decision.event == "checkout_deadline"
    assert decision.remind_at == datetime(2026, 9, 4, 9, 45, tzinfo=timezone.utc)


def test_customer_update_closes_the_reminder() -> None:
    client = TestClient(app)
    response = client.post(
        "/orders/update",
        json={
            "order_ref": "ord_2048",
            "stage": "customer_updated",
            "occurred_at": "2026-09-04T10:02:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json() is None
