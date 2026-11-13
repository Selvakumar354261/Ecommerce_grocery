import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'payment_dialog.dart';
import 'account_pages.dart';
import 'delivery_widgets.dart';

const green = Color(0xff1d6546), bg = Color(0xfff3f8f3);
void main() => runApp(const DeliveryApp());

class DeliveryLogo extends StatelessWidget {
  const DeliveryLogo({super.key, this.height = 80});
  final double height;
  @override
  Widget build(BuildContext context) => Image.asset(
    'assets/chinnu-logo.png',
    height: height,
    fit: BoxFit.contain,
    semanticLabel: 'CHINNU delivery',
  );
}

class DeliveryApp extends StatelessWidget {
  const DeliveryApp({super.key});
  @override
  Widget build(BuildContext c) => MaterialApp(
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: green).copyWith(
        primary: green, secondary: const Color(0xff397c51),
        surface: const Color(0xfffafffa),
      ),
      scaffoldBackgroundColor: bg,
      useMaterial3: true,
      appBarTheme: const AppBarTheme(
        backgroundColor: bg, foregroundColor: Color(0xff173d2c),
        surfaceTintColor: Colors.transparent, centerTitle: false,
        titleTextStyle: TextStyle(fontSize: 23, fontWeight: FontWeight.w700, color: Color(0xff173d2c)),
      ),
      cardTheme: CardThemeData(
        elevation: 0, color: const Color(0xfffafffa),
        margin: const EdgeInsets.symmetric(vertical: 7),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: const BorderSide(color: Color(0xffdce5d5))),
      ),
      filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(
        minimumSize: const Size(0, 52), padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      )),
      outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 48), side: const BorderSide(color: Color(0xff9caf94)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      )),
      chipTheme: ChipThemeData(
        backgroundColor: const Color(0xffeaf0e2), side: BorderSide.none,
        labelStyle: const TextStyle(color: green, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true, fillColor: Color(0xfffafffa),
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14)), borderSide: BorderSide(color: Color(0xffb7c6af))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14)), borderSide: BorderSide(color: green, width: 2)),
      ),
    ),
    home: const Gate(),
  );
}

class Gate extends StatefulWidget {
  const Gate({super.key});
  @override
  State<Gate> createState() => _GateState();
}

class _GateState extends State<Gate> {
  bool? signed;
  @override
  void initState() {
    super.initState();
    Api().hasSession().then((v) => setState(() => signed = v));
  }

  @override
  Widget build(BuildContext c) {
    if (signed == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return signed!
        ? Jobs(onLogout: () => setState(() => signed = false))
        : Login(onDone: () => setState(() => signed = true));
  }
}

class Login extends StatefulWidget {
  final VoidCallback onDone;
  const Login({super.key, required this.onDone});
  @override
  State<Login> createState() => _LoginState();
}

class _LoginState extends State<Login> {
  final email = TextEditingController(), password = TextEditingController();
  String error = '';
  bool busy = false;
  Future<void> submit() async {
    setState(() => busy = true);
    try {
      await Api().login(email.text.trim(), password.text);
      widget.onDone();
    } catch (e) {
      setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext c) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: SizedBox(
            width: 520,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const DeliveryLogo(height: 130),
                const SizedBox(height: 16),
                const Text(
                  'CHINNU',
                  style: TextStyle(
                    color: green,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 3,
                  ),
                ),
                const SizedBox(height: 36),
                Text(
                  'Delivery partner',
                  style: Theme.of(c).textTheme.displaySmall,
                ),
                const Text(
                  'Sign in with the delivery account created by your administrator.',
                ),
                const SizedBox(height: 25),
                TextField(
                  controller: email,
                  decoration: const InputDecoration(labelText: 'Staff email'),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: password,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'Password'),
                ),
                if (error.isNotEmpty)
                  Text(error, style: const TextStyle(color: Colors.red)),
                const SizedBox(height: 14),
                FilledButton(
                  onPressed: busy ? null : submit,
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Text(busy ? 'Signing in…' : 'Sign in'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class Jobs extends StatefulWidget {
  final VoidCallback onLogout;
  final Api? api;
  const Jobs({super.key, required this.onLogout, this.api});
  @override
  State<Jobs> createState() => _JobsState();
}

class _JobsState extends State<Jobs> with WidgetsBindingObserver {
  Timer? refreshTimer;
  late final Api api;
  bool fetching = false;
  List<Job> jobs = [];
  bool loading = true;
  String error = '';
  Future<void> load() async {
    if (fetching || !mounted) return;
    fetching = true;
    try {
      final latest = await api.jobs();
      if (!mounted) return;
      jobs = latest;
      error = '';
    } catch (e) {
      if (!mounted) return;
      error = e.toString();
    } finally {
      fetching = false;
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  void initState() {
    super.initState();
    api = widget.api ?? Api();
    WidgetsBinding.instance.addObserver(this);
    load();
    startRefresh();
  }

  void startRefresh() {
    refreshTimer?.cancel();
    refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) => load());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    refreshTimer?.cancel();
    if (state == AppLifecycleState.resumed) {
      load();
      startRefresh();
    }
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext c) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My assignments', maxLines: 2, style: TextStyle(fontSize: 21)),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: () async {
              await api.logout();
              widget.onLogout();
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            const Center(child: DeliveryLogo(height: 100)),
            const SizedBox(height: 12),
            const Text(
              'CHINNU DELIVERY',
              style: TextStyle(
                color: green,
                fontWeight: FontWeight.bold,
                letterSpacing: 2,
              ),
            ),
            const SizedBox(height: 8),
            const Text('Assignments update automatically while this screen is open.', style: TextStyle(color: Color(0xff63715c))),
            const SizedBox(height: 16),
            Wrap(spacing: 10, runSpacing: 8, children: [
              OutlinedButton.icon(icon: const Icon(Icons.person_outline), label: const Text('My profile'), onPressed: () => Navigator.push(c, MaterialPageRoute(builder: (_) => DriverProfile(api: api)))),
              OutlinedButton.icon(icon: const Icon(Icons.history), label: const Text('Delivery history'), onPressed: () => Navigator.push(c, MaterialPageRoute(builder: (_) => DriverHistory(api: api, onOpen: (job) async { await Navigator.push(c, MaterialPageRoute(builder: (_) => Detail(job))); })))),
            ]),
            const SizedBox(height: 16),
            if (error.isNotEmpty) Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(error, style: TextStyle(color: Theme.of(c).colorScheme.error)))),
            if (loading) const Center(child: CircularProgressIndicator()),
            if (!loading && error.isEmpty && jobs.isEmpty)
              const DeliveryEmptyState(title: 'No active deliveries', subtitle: 'New assignments will appear here automatically. You are all caught up.'),
            for (final j in jobs)
              DeliveryJobCard(job: j,
                  onTap: () async {
                    await Navigator.push(
                      c,
                      MaterialPageRoute(builder: (_) => Detail(j)),
                    );
                    load();
                  },
              ),
          ],
        ),
      ),
    );
  }
}

class Detail extends StatefulWidget {
  final Job job;
  final Api? api;
  const Detail(this.job, {super.key, this.api});
  @override
  State<Detail> createState() => _DetailState();
}

class _DetailState extends State<Detail> {
  StreamSubscription<Position>? gps;
  final otp = TextEditingController();
  String message = '';
  String locationMessage = '';
  bool hasError = false;
  bool busy = false;
  late Job j;
  late final Api api;
  @override
  void initState() {
    super.initState();
    j = widget.job;
    api = widget.api ?? Api();
    if (j.status == 'dispatched') startTracking();
  }

  @override
  void dispose() {
    gps?.cancel();
    otp.dispose();
    super.dispose();
  }

  Future<void> startTracking() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        if (mounted) {
          setState(
            () => locationMessage =
                'Turn on location to share your position with the branch.',
          );
        }
        return;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        if (mounted) {
          setState(
            () => locationMessage = 'Location permission is needed to share your position with the branch.',
          );
        }
        return;
      }
      if (!mounted || j.status != 'dispatched') return;
      await gps?.cancel();
      gps =
          Geolocator.getPositionStream(
            locationSettings: const LocationSettings(
              accuracy: LocationAccuracy.high,
              distanceFilter: 20,
            ),
          ).listen(
            (p) async {
              try {
                await api.location(j.id, p.latitude, p.longitude);
              } catch (_) {
                if (mounted) {
                  setState(
                    () => locationMessage =
                        'Unable to share location. Check your connection.',
                  );
                }
              }
            },
            onError: (Object error) {
              if (mounted) {
                setState(
                  () => locationMessage =
                      'Location is unavailable. Check your location settings.',
                );
              }
            },
          );
      if (mounted) {
        setState(
          () => locationMessage =
              'Location sharing is enabled for this delivery.',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => locationMessage =
              'Location is unavailable. Check your location settings.',
        );
      }
    }
  }

  void showMessage(String text, {bool error = false}) {
    if (mounted) {
      setState(() {
        message = text;
        hasError = error;
      });
    }
  }

  Future<bool> act(Future<void> Function() action, String success) async {
    if (busy) return false;
    setState(() {
      busy = true;
      message = '';
    });
    var saved = false;
    try {
      await action();
      saved = true;
      final updated = await api.order(j.id);
      if (!mounted) return true;
      setState(() {
        j = updated;
        message = success;
        hasError = false;
      });
      if (j.status == 'dispatched' && gps == null) {
        unawaited(startTracking());
      } else if (j.status != 'dispatched') {
        await gps?.cancel();
        gps = null;
        if (mounted) setState(() => locationMessage = '');
      }
      return true;
    } catch (e) {
      showMessage(
        saved
            ? '$success Could not refresh the order. Tap Refresh to load the latest status.'
            : e.toString(),
        error: true,
      );
      return saved;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> refresh() async {
    if (busy) return;
    setState(() => busy = true);
    try {
      final updated = await api.order(j.id);
      if (!mounted) return;
      setState(() {
        j = updated;
        message = '';
      });
      if (j.status == 'dispatched' && gps == null) unawaited(startTracking());
      if (j.status != 'dispatched') {
        await gps?.cancel();
        gps = null;
        if (mounted) setState(() => locationMessage = '');
      }
    } catch (e) {
      showMessage(e.toString(), error: true);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openExternal(Uri uri) async {
    try {
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        showMessage('No app is available to open this action.', error: true);
      }
    } catch (_) {
      showMessage(
        'Could not open the app. Please check that a phone or maps app is installed.',
        error: true,
      );
    }
  }

  Future<void> navigate() async {
    if (j.lat == null || j.lng == null) {
      showMessage(
        'Customer map pin unavailable for this order. Contact the customer or branch.',
        error: true,
      );
      return;
    }
    await openExternal(
      Uri.parse(
        'https://www.google.com/maps/dir/?api=1&destination=${j.lat},${j.lng}&travelmode=driving',
      ),
    );
  }

  Future<void> collectPayment() async {
    final recorded = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => PaymentDialog(api: api, job: j),
    );
    if (recorded == true && mounted) {
      await refresh();
      if (mounted && j.payment == 'paid') {
        showMessage('Payment collection recorded.');
      }
    }
  }

  @override
  Widget build(BuildContext c) => Scaffold(
    appBar: AppBar(
      title: Text(j.number),
      actions: [
        IconButton(
          onPressed: busy ? null : refresh,
          tooltip: 'Refresh order',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Chip(label: Text('Status: ${j.status.replaceAll('_', ' ')}')),
            const SizedBox(height: 12),
            Text(j.customer, style: Theme.of(c).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(j.address, style: const TextStyle(fontSize: 16, height: 1.5)),
          ],
        ))),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () =>
                    openExternal(Uri(scheme: 'tel', path: j.phone)),
                icon: const Icon(Icons.call),
                label: const Text('Call'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: navigate,
                icon: const Icon(Icons.navigation),
                label: const Text('Navigate'),
              ),
            ),
          ],
        ),
        const Divider(),
        for (final x in j.items)
          ListTile(
            title: Text(x['name']),
            subtitle: Text('${x['quantity']} ${x['unit']}'),
            trailing: Text('₹${x['line_total']}'),
          ),
        Text(
          j.payment == 'paid'
              ? 'Payment received: ₹${j.total}'
              : 'Amount to collect: ₹${j.total}',
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        if (message.isNotEmpty)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              message,
              style: TextStyle(color: hasError ? Colors.red.shade800 : green),
            ),
          ),
        if (locationMessage.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(locationMessage),
          ),
        if (busy) const LinearProgressIndicator(),
        if (j.collection != null) PaymentSummary(j.collection!),
        if (j.status == 'ready')
          FilledButton(
            onPressed: busy
                ? null
                : () => act(() => api.start(j.id), 'Delivery started.'),
            child: const Text('Start delivery'),
          ),
        if (j.status == 'dispatched') ...[
          if (j.payment != 'paid')
            FilledButton(
              onPressed: busy ? null : collectPayment,
              child: const Text('Collect payment'),
            ),
          TextField(
            controller: otp,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            enabled: !busy,
            onChanged: (_) => setState(() {}),
            maxLength: 6,
            decoration: InputDecoration(
              labelText: 'Customer OTP',
              helperText: j.payment != 'paid'
                  ? 'Record the payment before completing delivery.'
                  : 'Ask the customer for the six-digit delivery OTP.',
              helperMaxLines: 2,
            ),
          ),
          FilledButton(
            onPressed:
                busy ||
                    j.payment != 'paid' ||
                    !RegExp(r'^[0-9]{6}$').hasMatch(otp.text)
                ? null
                : () => act(
                    () => api.complete(j.id, otp.text.trim()),
                    'Delivery completed.',
                  ),
            child: const Text('Complete delivery'),
          ),
          TextButton(
            onPressed: busy ? null : failureDialog,
            child: const Text('Could not deliver'),
          ),
        ],
        if (j.status == 'completed')
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Text(
              'Delivery completed successfully.',
              style: TextStyle(color: green, fontWeight: FontWeight.bold),
            ),
          ),
      ],
    ),
  );
  Future<void> failureDialog() async {
    final reason = TextEditingController();
    String? error;
    bool submitting = false;
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialog) => StatefulBuilder(
        builder: (dialog, update) => AlertDialog(
          title: const Text('Delivery unsuccessful'),
          content: TextField(
            controller: reason,
            maxLines: 3,
            maxLength: 500,
            enabled: !submitting,
            decoration: InputDecoration(
              labelText: 'Reason',
              errorText: error,
              errorMaxLines: 4,
            ),
          ),
          actions: [
            TextButton(
              onPressed: submitting ? null : () => Navigator.pop(dialog),
              child: const Text('Back'),
            ),
            FilledButton(
              onPressed: submitting
                  ? null
                  : () async {
                      if (reason.text.trim().length < 3) {
                        update(
                          () => error =
                              'Enter a reason with at least three characters.',
                        );
                        return;
                      }
                      update(() {
                        submitting = true;
                        error = null;
                      });
                      try {
                        await api.fail(j.id, reason.text.trim());
                        showMessage(
                          'Branch notified. Contact the branch for the next steps.',
                        );
                        if (dialog.mounted) Navigator.pop(dialog);
                      } catch (e) {
                        if (dialog.mounted) {
                          update(() {
                            submitting = false;
                            error = e.toString();
                          });
                        }
                      }
                    },
              child: Text(submitting ? 'Submitting...' : 'Submit'),
            ),
          ],
        ),
      ),
    );
    // The dialog's closing animation may still be using its controller.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    reason.dispose();
  }
}
