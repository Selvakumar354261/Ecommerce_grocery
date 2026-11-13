# Delivery operations

Admins and managers can use **Delivery management** to assign ready delivery orders and inspect delivery-person performance. This page focuses on operational records rather than live GPS tracking.

- Admins can report across all branches or select a branch. Managers are restricted by the backend to their assigned branch.
- Branch and order-date filters apply to the team performance table. Dates are interpreted as whole days in India. These are cohorts of orders **placed** during the selected dates, not counts of completion events during those dates.
- Delivery-person, search and status filters apply to the delivery-jobs list. Status badges retain the counts for the current branch/date/person/search selection, independent of the selected status. Jobs are paginated; counts include the entire filtered set.
- Current workload includes all ready and dispatched assignments, even jobs placed outside the selected dates. Failed deliveries remain active until resolved.
- A failed attempt is a recorded `delivery_failed` event. Multiple attempts on one order are counted separately. An order completed after a failed attempt contributes to completed orders and historical failed attempts, but not to the current needs-attention count.
- Customer cancellations, store rejections and automatic reservation expirations are reported separately. Legacy cancellations performed by a manager or admin are classified as store rejections.
- Average trip time uses recorded dispatch and completion timestamps. Older completed orders without both timestamps do not contribute to the average.
- Assignment and reassignment are limited to ready orders and active delivery people in the order's branch. Once dispatch starts, reassignment is blocked. Repeating the same assignment does not duplicate its history event.
- Order detail includes items, totals, payment state, customer address/map pin, assignment and trip timestamps, unsuccessful-attempt reasons, cancellation/rejection reasons, and an actor-labelled event history including cash collection. Customer verification codes remain private to the customer.

The backend endpoints are `GET /api/v1/delivery/operations` and `GET /api/v1/delivery/operations/{id}`. Assignment uses `POST /api/v1/orders/{id}/assign-delivery`.

## Payment collection

Delivery staff select cash, UPI, card or split, then review the server-calculated settlement before confirming. Cash requires the actual notes received. Split requires at least two distinct positive allocations totalling the full order amount. Cash received must cover the cash allocation, and change equals cash received minus that allocation. For example, a INR 750 bill split into INR 500 cash and INR 250 UPI, with INR 1,000 cash tendered, returns INR 500 change.

`POST /api/v1/orders/{id}/payment/preview` validates and calculates without recording collection. `POST /api/v1/orders/{id}/payment` records the same inputs and accepts `expected_total` to detect a changed order total. The backend stores the collector, timestamp, methods, allocations, cash tender and change atomically with the paid status and history event. Exact retries are safe; conflicting rewrites are rejected. Drivers can collect only assigned, dispatched deliveries; admins and branch managers can also record collection at handover. Completion still requires payment and the customer's OTP.

Migration `0020` adds `order_collections`. Old paid orders deliberately retain unknown settlement details, since actual cash tender and change cannot be reconstructed. New breakdowns appear in the Flutter app, management details, customer orders and online sales receipts. Card and UPI entries are manual collection records, not payment-gateway transactions.
