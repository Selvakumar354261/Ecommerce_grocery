import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';

class CustomerLogin extends StatefulWidget {
  const CustomerLogin({super.key, required this.api});
  final Api api;
  @override
  State<CustomerLogin> createState() => _CustomerLoginState();
}

class _CustomerLoginState extends State<CustomerLogin> {
  final phone = TextEditingController(),
      otp = TextEditingController(),
      name = TextEditingController(),
      email = TextEditingController();
  bool sent = false, profile = false, busy = false;
  String error = '', dev = '';
  @override
  void dispose() {
    for (final c in [phone, otp, name, email]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    setState(() {
      busy = true;
      error = '';
    });
    try {
      if (!sent) {
        final r = await widget.api.call(
          '/auth/otp/request',
          method: 'POST',
          body: {'phone': phone.text},
        );
        if (mounted) {
          setState(() {
            sent = true;
            dev = r['development_otp'] ?? '';
          });
        }
        return;
      }
      final r = await widget.api.call(
        '/auth/otp/verify',
        method: 'POST',
        body: {
          'phone': phone.text,
          'otp': otp.text,
          if (profile) 'name': name.text.trim(),
          if (profile && email.text.trim().isNotEmpty)
            'email': email.text.trim(),
        },
      );
      if (!mounted) return;
      if (r['profile_required'] == true) {
        setState(() => profile = true);
      } else {
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Welcome to CHINNU')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Image.asset('assets/chinnu-logo.png', height: 88),
        const SizedBox(height: 24),
        Text(
          profile
              ? 'A little about you'
              : sent
              ? 'Verify your number'
              : 'Shopping made simple',
          style: Theme.of(context).textTheme.headlineMedium
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 10),
        Text(
          profile
              ? 'Your number is verified. Add your name to finish.'
              : 'Sign in securely with a mobile OTP. No password needed.',
        ),
        const SizedBox(height: 26),
        if (!profile) ...[
          TextField(
            controller: phone,
            enabled: !sent && !busy,
            keyboardType: TextInputType.phone,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(10),
            ],
            decoration: const InputDecoration(
              labelText: 'Mobile number',
              prefixText: '+91 ',
            ),
          ),
          if (sent) ...[
            const SizedBox(height: 16),
            TextField(
              controller: otp,
              keyboardType: TextInputType.number,
              inputFormatters: [
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(6),
              ],
              decoration: const InputDecoration(labelText: 'Six-digit OTP'),
            ),
          ],
          if (dev.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text('Development OTP: $dev'),
            ),
        ] else ...[
          TextField(
            controller: name,
            decoration: const InputDecoration(labelText: 'Full name *'),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email (optional)'),
          ),
        ],
        if (error.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(error, style: const TextStyle(color: Colors.red)),
          ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: busy ? null : submit,
          child: Text(
            busy
                ? 'Please wait…'
                : profile
                ? 'Create account'
                : sent
                ? 'Verify and continue'
                : 'Send OTP',
          ),
        ),
      ],
    ),
  );
}

class CustomerOrders extends StatefulWidget {
  const CustomerOrders({super.key, required this.api, this.embedded = false});
  final bool embedded;
  final Api api;
  @override
  State<CustomerOrders> createState() => _CustomerOrdersState();
}

class _CustomerOrdersState extends State<CustomerOrders> {
  List orders = [];
  String error = '';
  bool busy = true;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await widget.api.call('/orders');
      if (mounted) {
        setState(() {
          orders = data;
          error = '';
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: widget.embedded
        ? null
        : AppBar(
            title: const Text('My orders'),
            actions: [
              IconButton(
                onPressed: load,
                icon: const Icon(Icons.refresh),
                tooltip: 'Refresh orders',
              ),
            ],
          ),
    body: RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (busy) const LinearProgressIndicator(),
          if (error.isNotEmpty) Text(error),
          if (!busy && error.isEmpty && orders.isEmpty)
            const Padding(
              padding: EdgeInsets.all(32),
              child: Text(
                'Your first order starts here. Explore the shop and fill your basket.',
              ),
            ),
          for (final o in orders)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 12,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          o['number'],
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 20,
                          ),
                        ),
                        Chip(
                          label: Text(
                            (o['display_status'] ?? o['status'])
                                .toString()
                                .replaceAll('_', ' '),
                          ),
                        ),
                      ],
                    ),
                    Text(o['branch_name']),
                    const Divider(height: 28),
                    for (final item in o['items'])
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text('${item['name']} × ${item['quantity']}'),
                      ),
                    const SizedBox(height: 12),
                    Text(
                      'Total including delivery: ₹${o['total']}',
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    if (o['coverage_approval_required'] == true &&
                        o['status'] == 'approval_pending')
                      const Text(
                        'Your order has been placed. The branch will review delivery within 24 hours.',
                      ),
                    if (o['pickup_code'] != null &&
                        ['ready', 'dispatched'].contains(o['status']))
                      Container(
                        margin: const EdgeInsets.only(top: 16),
                        padding: const EdgeInsets.all(16),
                        color: const Color(0xffe7f2df),
                        child: Text(
                          'Delivery / pickup OTP: ${o['pickup_code']}',
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 21,
                          ),
                        ),
                      ),
                    const SizedBox(height: 16),
                    for (final event in o['events'])
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              (event['display_status'] ?? event['status'])
                                  .toString()
                                  .replaceAll('_', ' '),
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            if ((event['note'] ?? '').toString().isNotEmpty)
                              Text(event['note']),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
        ],
      ),
    ),
  );
}

class CustomerProfile extends StatelessWidget {
  const CustomerProfile({
    super.key,
    required this.user,
    required this.api,
    this.embedded = false,
    this.onSignedOut,
  });
  final bool embedded;
  final VoidCallback? onSignedOut;
  final Map user;
  final Api api;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: embedded ? null : AppBar(title: const Text('My account')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: const Color(0xff175c3c),
            borderRadius: BorderRadius.circular(22),
          ),
          child: Column(
            children: [
              const CircleAvatar(
                radius: 32,
                backgroundColor: Color(0xffdeeddc),
                child: Icon(
                  Icons.person_outline,
                  size: 34,
                  color: Color(0xff175c3c),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                user['name'],
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Your CHINNU account',
                style: TextStyle(color: Color(0xffc8e1bf)),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        Card(
          child: Column(
            children: [
              ListTile(
                leading: const Icon(Icons.phone_outlined),
                title: const Text('Mobile'),
                subtitle: Text(user['phone'] ?? 'Not provided'),
              ),
              ListTile(
                leading: const Icon(Icons.mail_outline),
                title: const Text('Email'),
                subtitle: Text(user['email'] ?? 'Not provided'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        OutlinedButton(
          onPressed: () async {
            try {
              await api.logout();
              if (context.mounted) {
                if (onSignedOut != null) {
                  onSignedOut!();
                } else {
                  Navigator.pop(context);
                }
              }
            } catch (e) {
              if (context.mounted) {
                ScaffoldMessenger.of(context)
                    .showSnackBar(SnackBar(content: Text(e.toString())));
              }
            }
          },
          child: const Text('Sign out'),
        ),
      ],
    ),
  );
}
