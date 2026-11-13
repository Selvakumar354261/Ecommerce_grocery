# Client demonstration

## Start the installed Android delivery app

Connect an unlocked phone by USB with USB debugging authorized, then run from the repository root:

```powershell
.\start.ps1 -Mobile
```

This starts Docker and launches the delivery app. The first run builds and installs an APK configured for USB forwarding; subsequent runs reuse it unless mobile source/configuration changes. Updates use `adb install -r` to preserve app data. Backend-only changes do not trigger an APK rebuild.

If Docker is already running, use `.\start-mobile.ps1`. Force a mobile rebuild with `.\start-mobile.ps1 -Rebuild`. Multiple connected phones require `-DeviceId SERIAL` on that script. This helper currently assumes the server uses port 8080 and Flutter is installed at `C:\Develop\flutter`.

Keep USB connected for backend access in this testing mode. Docker cannot automatically open apps on disconnected phones, and running `docker compose up` directly does not invoke this helper. Installed apps used over Wi-Fi can instead be opened manually, provided their configured server address is reachable.

Use a fresh local demo database. Keep the customer session in one browser profile and staff in another. This walkthrough demonstrates connected business behaviour, not external gateway or delivery-provider integrations.

1. **Catalogue flexibility** — show the same rice product with 1 kg/5 kg sealed options and loose kg. Add an allowed fractional quantity of almonds. Explain that sealed and loose inventories are independent and that central prices are the same in every branch.
2. **Checkout after shopping** — select delivery or pickup, use the Erode demo coordinates, and find branches for the whole basket. Show a nearest recommendation and a branch that is missing a requested item. Choosing a different eligible branch does not change product prices; delivery fees are separate.
3. **Order ownership** — place an order, show its customer history, and open the branch queue in the manager session. Confirm and prepare it. Show the reservation in branch inventory before dispatch/handover.
4. **Fulfilment** — pickup requires the customer's code and cash collection. Delivery deducts stock at dispatch and completes after cash collection. Show that the final completion does not deduct stock again.
5. **Shop billing** — open a cashier shift, scan/type RICE-1KG, add a loose quantity, hold/resume the bill, and complete cash billing. Print or reprint the saved receipt from sales history.
6. **Control of stock** — receive goods, inspect the ledger, dispatch a transfer, and receive part at the destination. Explain the remaining in-transit balance.
7. **Approval and traceability** — submit a physical count as inventory staff, approve as manager, and inspect audit history as owner. A cashier cannot manage another branch or change central prices.
8. **Management view** — show realised sales, pending orders, low stock, the 7-day trend, and CSV export. Close the cashier shift with a counted amount and inspect the variance.

Before a client promises a real launch, review VALIDATION.md and run the PostgreSQL integration tests on a working Docker installation. Replace the illustrative data, confirm tax/invoice needs, and configure HTTPS, backups, and staff cash/refund procedures.
