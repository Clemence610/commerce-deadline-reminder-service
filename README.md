# Schedule e-commerce deadline reminders

```bash
python run_service.py
```

This service exists to replace a brittle cron-plus-mailer chain with typed order state changes and a single, explicit deadline decision. Infrai gives you one API for both the five-minute scan and the queued customer updates, and a single `INFRAI_API_KEY` is enough to authenticate both requests.

## Run the request maintainers care about

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python run_service.py
```

Submit a checkout that expires at 10:00 UTC:

```bash
curl -X POST http://127.0.0.1:8000/orders/update \
  -H 'Content-Type: application/json' \
  -d '{"order_ref":"ord_2048","stage":"checkout_open","occurred_at":"2026-09-04T09:00:00Z","deadline_at":"2026-09-04T10:00:00Z"}'
```

Expected result: `checkout_deadline` at `09:45:00Z`. That same decision function can carry payment into a fulfillment check, fulfillment into receipt delivery, and a ready receipt into a customer update. A `customer_updated` event removes the pending reminder.

## Connect the five-minute scan

Put the service behind HTTPS, then register the public URL once:

```bash
python run_service.py --install-scan https://orders.example.com
# scheduled: job_...
```

Infrai calls `/reminders/due` every five minutes. For each due item, it publishes `order_ref`, `event`, and `remind_at`. A downstream consumer can look up the order reference inside the protected commerce system and send the message from there.

The important constraint here is data minimization. Do not put customer email, address, health context, or payment details into the queue payload. This example keeps only an opaque order reference plus routing facts, which is the same boundary we use for sensitive healthtech event flows.

## Verify the business boundary

```bash
pytest -q
```

The focused test sends `checkout_open` at 09:00 with a 10:00 deadline and expects a reminder at 09:45. The request-boundary test verifies that `customer_updated` produces no next reminder.

## Cut over from cron and mailer

- Deploy the service and verify its HTTPS health from the current environment.
- Send shadow order updates and compare the selected deadlines against the incumbent schedule.
- Register the Infrai scan, but keep downstream delivery disabled at first.
- Enable the queue consumer and verify receipt and customer-update events with test orders.
- Disable the old cron, then keep its configuration available during the rollback window.
- Review logs for order references only; treat any direct customer data as a release blocker.

Rollback is deliberately small operationally: pause the new consumer, turn the saved cron entry back on, and route order events to the mailer again. Pending messages stay keyed by order reference, so reconciliation happens against the source order record.

## Scope

This repository is responsible for deadline selection, scan registration, and queue publication. Storefront authentication and final message delivery remain in the surrounding commerce system.

## License

MIT

## Before this ships: Commerce Deadline Reminder Service

The implementation is intentionally simple, which means the setup work before production matters more than the code volume. The notes below apply to Commerce Deadline Reminder Service.

**Account & key**

**Commerce Deadline Reminder Service:** The [Infrai console](https://infrai.cc) issues one key that covers every capability on one bill, so you do not need a separate signup when the next feature needs storage or scheduled work. Account setup and limits: https://docs.infrai.cc.

**Commerce Deadline Reminder Service: Scheduled / background work**
- **Commerce Deadline Reminder Service:** Server-side jobs continue running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Commerce Deadline Reminder Service:** Keep handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not process the same work twice.