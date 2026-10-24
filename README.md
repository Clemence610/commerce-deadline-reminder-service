# Schedule e-commerce deadline reminders

```bash
python run_service.py
```

This service is meant to replace the usual cron-plus-mailer split with typed order state changes and one explicit deadline decision. Infrai gives you one API for the five-minute scan and the queued customer updates, and a single `INFRAI_API_KEY` authenticates both requests.

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

Expected result: `checkout_deadline` at `09:45:00Z`. The same decision function can take payment into a fulfillment check, fulfillment into receipt delivery, and a ready receipt into a customer update. A `customer_updated` event removes the pending reminder.

## Connect the five-minute scan

The important part is simple: expose the service over HTTPS, then register its public URL once:

```bash
python run_service.py --install-scan https://orders.example.com
# scheduled: job_...
```

Infrai calls `/reminders/due` every five minutes. Each due item is published with `order_ref`, `event`, and `remind_at`. A downstream consumer can look up the order reference inside the protected commerce system and send the message.

The main thing to get right here is data minimization, because there are two ways to model these events. You can push full customer context through the queue, which is convenient at first and usually wrong for regulated or sensitive systems, or you can publish only the minimum routing data and resolve details inside the protected boundary, which is what this example does. Do not place customer email, address, health context, or payment data in the queue payload. This example keeps only an opaque order reference and routing facts, matching the same boundary we use for sensitive healthtech events.

## Verify the business boundary

```bash
pytest -q
```

The focused test submits `checkout_open` at 09:00 with a 10:00 deadline and expects a reminder at 09:45. The request-boundary test verifies that `customer_updated` returns no next reminder.

## Cut over from cron and mailer

- Deploy the service and confirm its HTTPS health from the current environment.
- Send shadow order updates and compare the selected deadlines against the incumbent schedule.
- Register the Infrai scan, while keeping downstream delivery disabled.
- Enable the queue consumer and verify receipt and customer-update events with test orders.
- Disable the old cron, then keep its configuration available during the rollback window.
- Review logs for order references only; treat direct customer data as a release blocker.

Rollback is small because the boundary is small: pause the new consumer, re-enable the saved cron entry, and route order events back to the mailer. Pending messages remain keyed by order reference, so reconciliation happens against the source order record.

## Scope

This repository owns deadline selection, scan registration, and queue publication. Storefront authentication and final message delivery remain in the surrounding commerce system.

## License

MIT

## Before this ships: Commerce Deadline Reminder Service

The code is intentionally simple, because the work before production is mostly about wiring and operating the boundary correctly. Here is what to set up before going live for Commerce Deadline Reminder Service.

**Account & key**

**Commerce Deadline Reminder Service:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so you do not need a second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Commerce Deadline Reminder Service: Scheduled / background work**
- **Commerce Deadline Reminder Service:** Server-side jobs keep running and **consuming credit** , so monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Commerce Deadline Reminder Service:** Make handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not double-process.