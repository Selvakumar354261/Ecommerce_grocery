# Architecture and business rules

This project implements the agreed web scope using React, TypeScript, Vite, MUI, React Router, TanStack Query, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Docker Compose, and Nginx. No alternative database, hosted authentication service, UI framework, message broker, or payment gateway is introduced. The worker is the same Python/FastAPI application image with a different entry command. Tests use pytest and HTTPX as development tools.

## Application boundaries

- Customer website: browse all active products before selecting a branch, build a cart, select delivery/pickup, list available branches, recommend the nearest eligible branch, place cash/pay-at-shop orders, view progress and pickup code.
- Staff workspace: role-specific navigation for the owner, manager, cashier, and inventory staff. The owner can work across branches. Other staff have one assigned branch enforced on every backend resource.
- Backend: authoritative pricing, availability, permission checks, transitions, and transactional writes. The frontend never connects to the database.
- Database: persistent named Docker volume, private to the Compose network. Public ports are not opened for PostgreSQL or the API.
- Worker: sweeps expired unconfirmed reservations every 15 seconds using row locks and `SKIP LOCKED`.

## Stock model

Every variant is an independent stock item. A product can have sealed packs, loose kg/litres, or both. Sealed packs/pieces use integer quantities; loose goods use exact decimals with configured minimum, increment, and maximum. A 5 kg sealed bag is one pack, not five units of the loose variant. Pack conversion is not automated. Use linked, reasoned adjustments if manually opening sealed stock until an approved conversion workflow is added.

`available = on_hand - reserved - damaged`

On-hand includes damaged stock physically held. Damaged is an unsellable subset. PostgreSQL constraints prohibit negative balances and reservation/damage totals above on-hand. Every physical change writes a ledger entry within the same transaction. Opening stock is traceable in the seed ledger.

POS consumes available stock immediately. Online checkout reserves quantities; branch confirmation removes the reservation timeout. Delivery dispatch and pickup handover consume the reservation and decrement on-hand together. Delivery completion never deducts a second time. Cancelling before dispatch/handover releases stock; paid orders cannot be cancelled through the simple cancellation flow.

Sales and orders recheck price and quantity rules server-side. The web sends its expected subtotal so a concurrent central price change can be shown as a conflict before acceptance. Prices are identical across branches. The chosen branch may add a separate delivery charge. All listed prices are treated as final prices; jurisdiction-specific tax calculation and tax-invoice certification are not implemented.

## Concurrency and retry rules

Inventory rows are locked in variant ID order within each transaction. A whole cart succeeds or fails together. PostgreSQL advisory transaction locks serialize duplicate requests by actor, operation, and retry key. The request fingerprint and committed result are persisted together with the business transaction. Same key and payload returns the saved result; different payload returns 409. Never replace a retry key just because a response timed out.

Browser mutation requests include a CSRF header bound to the authenticated session. Sessions use random opaque identifiers; only SHA-256 hashes are stored. Passwords use salted PBKDF2-HMAC-SHA256 with 600,000 iterations. Cookies are HttpOnly and SameSite=Lax; set Secure when HTTPS is enabled. Unsafe browser origins are rejected. Login throttling persists in PostgreSQL. All permission decisions are made by the server.

The browser retains pending retry keys in tab session storage using a hashed path/payload fingerprint. Network failures and uncertain server errors retain the key for retry; a confirmed successful response clears it. This avoids a new key being generated when a user retries a partial receipt after losing the response. Passwords and request payloads are not stored in that cache.

## Order state machine

Delivery: `placed -> confirmed -> preparing -> ready -> dispatched -> completed`.

Pickup: `placed -> confirmed -> preparing -> ready -> completed` with code verification.

An order can be cancelled while placed/confirmed/preparing/ready if unpaid. Customer self-cancellation is allowed only while placed. Staff may cancel later before dispatch with a recorded event. Cash collection is allowed at ready/dispatched. Completion requires paid status. No integrated electronic payment exists in this release.

Unconfirmed orders expire after RESERVATION_MINUTES (default 30). Confirmed orders do not auto-expire; staff must monitor and explicitly resolve them. Staff status changes are polled every 15 seconds by active web screens. There are no SMS, email, push, driver, or mapping-provider integrations.

## Branch recommendation

Catalogue availability means at least one accepting branch has stock. It is not a promise that one branch can fulfil a combined cart. Checkout evaluates each requested variant and quantity as a whole. Delivery eligibility also requires the customer's supplied coordinates to fall inside the configured branch radius. Pickup does not require delivery coverage. Eligible branches sort by straight-line Haversine distance, and only the nearest eligible one is recommended. Customers can choose another eligible branch.

The app uses browser geolocation or manually entered coordinates. The typed address is delivery text, not a geocoding source. Seed coordinates and addresses are illustrative Erode demo data. No paid external maps dependency is included. Browser geolocation works on localhost and on HTTPS origins. Distances are not road routes, arrival predictions, or verified addresses. Operating hours are displayed; staff explicitly use accepting-orders to open/pause ordering.

## Operations

Transfers deduct source stock at dispatch and track in-transit quantity. Destination receipt supports partial quantities. Unreceived quantities remain visible; loss/damage resolution requires an audited operational decision and is not silently written off.

Purchase orders are one-variant records in this initial release. Creating a purchase does not alter stock. Each partial receipt updates accepted stock and the received quantity transactionally. Inventory also supports direct receiving, damage quarantine, and manager-authorised adjustments.

Physical stock count requests preserve the system snapshot at submission. A different authorised manager approves. Approval rejects a stale on-hand balance or a count that consumes reserved/damaged stock. Count in a controlled window and reject/recount after movement. General adjustment access is restricted to managers/admins and audited.

Each cashier opens a shift before POS sales. Closing locks the shift against concurrent completion and records expected cash, counted cash, and variance. Expected cash contains opening float plus linked POS sales minus linked POS returns at closing. Online cash collections and refunds issued after a shift closes are outside that drawer snapshot and need manager reconciliation.

POS returns currently return the full remaining quantity of a selected sale line, with condition and reason. Sellable returns restore available stock; damaged returns increase on-hand and damaged equally. The server calculates the cash refund from the historical sale price. Online refunds/returns after fulfilment require a later supervised workflow and are not represented as completed here.

## Reporting definitions

Net realised sales = POS totals minus POS refunds + completed online order totals. Online order totals include delivery charges. Orders are not copied into POS sales, preventing double counting. The dashboard shows all-time totals and a 7-day IST trend attributed to transaction creation date. This is an operational report, not a statutory accounting ledger. CSV includes original totals, refunds, net realised amount, and statuses.

## Design references

- Docker service readiness: https://docs.docker.com/compose/how-tos/startup-order/
- PostgreSQL row locking: https://www.postgresql.org/docs/current/explicit-locking.html
- SQLAlchemy refresh/locking: https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html
- FastAPI deployment: https://fastapi.tiangolo.com/deployment/

These references informed the implementation. They do not establish that this environment has executed a Docker image build; see VALIDATION.md for actual verification results.

