# CHINNU customer app

Separate Flutter Android/iOS customer application using the existing CHINNU backend. Green storefront, category search, selling-option selection, basket, OTP login/profile creation, checkout, saved delivery details, branch eligibility, orders with event history and delivery OTP, and a read-only account page.

## Android phone testing

Start Docker from the repository root and connect an authorized USB-debugging Android phone:

```powershell
docker compose up -d --build
docker compose restart proxy
.\start-customer.ps1
```

The helper uses port 8080 through USB forwarding, builds on source changes and reuses the installed app otherwise. It installs alongside the delivery app with application ID `in.chinnu.chinnu_customer`. It does not erase the delivery app. Flutter is expected at `C:\Develop\flutter`.

For an emulator: `flutter run --dart-define=API_URL=http://10.0.2.2:8080/api/v1`.
For Wi-Fi, use your reachable backend IP and expose the proxy only on a trusted network. Release builds require an HTTPS backend; Android HTTP access is enabled only in the debug manifest.

## Boundaries

Stock, quantity validation, branch eligibility, delivery fees, account verification and order creation are backend-owned. Checkout totals are returned by `/checkout/branches`; old backends should be rebuilt before testing. The cart and form remain in memory across the OTP screen, but are not yet durable across an OS process kill. Session cookies and CSRF tokens use secure storage. OTP delivery depends on the backend's configured SMS mode; a development OTP appears only when explicitly returned by the development backend.

This is the first functional version, not a production release: physical-device end-to-end checkout and design review are still required. Product art is illustrative (not product photography). Address selection and creation are included; full saved-address editing/removal, order cancellation, and push notifications are not yet included. No live customer tracking, external payment gateway or road-routing API is introduced.

iOS source is included, but building/signing requires macOS with Xcode and Apple provisioning. Configure HTTPS, permissions, app icons, signing, backups, provider credentials and real SMS before release. iOS has not been built on this Windows machine.

Tests: `flutter test`; analysis: `flutter analyze`.
