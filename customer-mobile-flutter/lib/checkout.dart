import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import 'api.dart';
import 'customer_pages.dart';

class CustomerCheckout extends StatefulWidget {
  const CustomerCheckout({
    super.key,
    required this.api,
    required this.cart,
    required this.products,
    required this.signedIn,
    required this.signIn,
    required this.onPlaced,
  });
  final Api api;
  final Map<int, num> cart;
  final List products;
  final bool Function() signedIn;
  final Future<bool> Function() signIn;
  final VoidCallback onPlaced;
  @override
  State<CustomerCheckout> createState() => _CustomerCheckoutState();
}

class _CustomerCheckoutState extends State<CustomerCheckout> {
  final address = TextEditingController(),
      phone = TextEditingController(),
      lat = TextEditingController(),
      lon = TextEditingController(),
      label = TextEditingController();
  List branches = [], saved = [];
  int? selected;
  String method = 'delivery', error = '';
  bool busy = false;
  int stage = 0;
  String? orderKey;
  @override
  void initState() {
    super.initState();
    defaults();
    for (final c in [lat, lon]) {
      c.addListener(invalidate);
    }
    for (final c in [address, phone]) {
      c.addListener(() => orderKey = null);
    }
  }

  @override
  void dispose() {
    for (final c in [address, phone, lat, lon, label]) {
      c.dispose();
    }
    super.dispose();
  }

  void invalidate() {
    if (mounted) {
      setState(() {
        branches = [];
        selected = null;
        orderKey = null;
      });
    }
  }

  Future<void> defaults() async {
    if (!widget.signedIn()) return;
    try {
      final d = await widget.api.call('/checkout/defaults');
      final s = await widget.api.call('/customer/addresses');
      if (!mounted) return;
      setState(() {
        saved = s;
        if (phone.text.isEmpty) phone.text = d['phone'];
        if (address.text.isEmpty) address.text = d['address'];
      });
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  List<Map<String, dynamic>> get items => widget.cart.entries
      .map((e) => {'variant_id': e.key, 'quantity': e.value.toString()})
      .toList();
  Map<String, dynamic> payload() => {
    'items': items,
    'method': method,
    'latitude': lat.text,
    'longitude': lon.text,
  };
  Future<void> act(Future<void> Function() fn) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = '';
    });
    try {
      await fn();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> locate() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const ApiError('Turn on your phone location first.');
    }
    var p = await Geolocator.checkPermission();
    if (p == LocationPermission.denied) {
      p = await Geolocator.requestPermission();
    }
    if (p == LocationPermission.denied ||
        p == LocationPermission.deniedForever) {
      throw const ApiError(
        'Location permission is needed. You can also enter coordinates.',
      );
    }
    final position = await Geolocator.getCurrentPosition().timeout(
      const Duration(seconds: 20),
    );
    lat.text = position.latitude.toStringAsFixed(7);
    lon.text = position.longitude.toStringAsFixed(7);
  }

  Future<void> find() async {
    final result = await widget.api.call(
      '/checkout/branches',
      method: 'POST',
      body: payload(),
    );
    if (mounted) {
      setState(() {
        branches = result;
        stage = 2;
      });
    }
  }

  Future<void> place() async {
    if (!widget.signedIn()) {
      if (!await widget.signIn()) return;
      await defaults();
      await find();
      return;
    }
    if (selected == null) throw const ApiError('Select an available branch.');
    orderKey ??= 'customer-${DateTime.now().microsecondsSinceEpoch}';
    final quote = branches.firstWhere((b) => b['id'] == selected);
    await widget.api.call(
      '/orders',
      method: 'POST',
      key: orderKey,
      body: {
        ...payload(),
        'branch_id': selected,
        'address': address.text,
        'phone': phone.text,
        'expected_subtotal': quote['subtotal'],
      },
    );
    widget.onPlaced();
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => CustomerOrders(api: widget.api)),
    );
  }

  Map variant(int id) {
    for (final p in widget.products) {
      for (final v in p['variants']) {
        if (v['id'] == id) return {...v, 'name': p['name']};
      }
    }
    return {};
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        ['Your basket', 'Delivery details', 'Review your order'][stage],
      ),
    ),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (int i = 0; i < 3; i++)
              Chip(
                backgroundColor: i == stage
                    ? Theme.of(context).colorScheme.primaryContainer
                    : Colors.white,
                label: Text(
                  '${i + 1}. ${['Basket', 'Delivery', 'Review'][i]}',
                  style: TextStyle(
                    fontWeight: i == stage
                        ? FontWeight.w700
                        : FontWeight.normal,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 20),
        if (stage > 0)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: busy ? null : () => setState(() => stage--),
              icon: const Icon(Icons.arrow_back, size: 18),
              label: const Text('Previous step'),
            ),
          ),
        if (stage == 0) ...[
          if (widget.cart.isEmpty)
            const Padding(
              padding: EdgeInsets.all(32),
              child: Text(
                'Your basket is empty. Return to the shop to add your essentials.',
              ),
            ),
          for (final entry in widget.cart.entries.toList())
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${variant(entry.key)['name']} · ${variant(entry.key)['label']}',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      initialValue: entry.value.toString(),
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: InputDecoration(
                        labelText: 'Quantity (${variant(entry.key)['unit']})',
                      ),
                      onChanged: (value) {
                        final q = num.tryParse(value);
                        if (q != null) {
                          widget.cart[entry.key] = q;
                          invalidate();
                        }
                      },
                    ),
                    TextButton(
                      onPressed: busy
                          ? null
                          : () {
                              setState(() => widget.cart.remove(entry.key));
                              invalidate();
                            },
                      child: const Text('Remove'),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: widget.cart.isEmpty || busy
                ? null
                : () => setState(() => stage = 1),
            child: const Text('Continue to delivery'),
          ),
        ],
        if (stage == 1) ...[
          Text(
            'Delivery details',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: method,
            decoration: const InputDecoration(
              labelText: 'How would you like your order?',
            ),
            items: const [
              DropdownMenuItem(value: 'delivery', child: Text('Home delivery')),
              DropdownMenuItem(value: 'pickup', child: Text('Shop pickup')),
            ],
            onChanged: busy
                ? null
                : (v) {
                    method = v!;
                    invalidate();
                  },
          ),
          const SizedBox(height: 16),
          if (saved.isNotEmpty) ...[
            DropdownButtonFormField<int>(
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Saved delivery details',
              ),
              items: [
                for (final s in saved)
                  DropdownMenuItem(value: s['id'], child: Text(s['label'])),
              ],
              onChanged: busy
                  ? null
                  : (id) {
                      final s = saved.firstWhere((a) => a['id'] == id);
                      address.text = s['address'];
                      phone.text = s['phone'] ?? '';
                      lat.text = s['latitude'].toString();
                      lon.text = s['longitude'].toString();
                    },
            ),
            const SizedBox(height: 16),
          ],
          if (method == 'delivery') ...[
            _field('Complete delivery address', address, lines: 3),
            const SizedBox(height: 16),
          ],
          _field('Contact mobile number', phone),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: busy ? null : () => act(locate),
            icon: const Icon(Icons.my_location),
            label: const Text('Use my location'),
          ),
          const SizedBox(height: 16),
          _field('Latitude', lat),
          const SizedBox(height: 16),
          _field('Longitude', lon),
          const SizedBox(height: 12),
          const Text(
            'Delivery distance is a straight-line estimate. The branch confirms availability and delivery.',
          ),
          if (widget.signedIn() && method == 'delivery') ...[
            const SizedBox(height: 16),
            _field('Save location as (Home, Work, Farm)', label),
            TextButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await widget.api.call(
                        '/customer/addresses',
                        method: 'POST',
                        body: {
                          'label': label.text,
                          'address': address.text,
                          'phone': phone.text,
                          'latitude': lat.text,
                          'longitude': lon.text,
                        },
                      );
                      await defaults();
                    }),
              child: const Text('Save these delivery details'),
            ),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: busy || widget.cart.isEmpty ? null : () => act(find),
            child: const Text('Find available branches'),
          ),
        ],
        if (stage == 2) ...[
          const Text(
            'Choose your branch',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          const Text(
            'Availability and delivery charges are confirmed by the store.',
          ),
          RadioGroup<int>(
            groupValue: selected,
            onChanged: (v) {
              if (!busy) {
                setState(() {
                  selected = v;
                  orderKey = null;
                });
              }
            },
            child: Column(
              children: [
                for (final b in branches)
                  Card(
                    child: RadioListTile<int>(
                      value: b['id'],
                      enabled: !busy && b['eligible'] == true,
                      title: Text(b['name']),
                      subtitle: Text(
                        b['eligible'] != true
                            ? 'Items unavailable'
                            : '${b['distance_km']} km · ${b['requires_approval'] == true ? 'Manager approval required within 24 hours' : 'Delivery ₹${b['delivery_fee']}'}',
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
        if (error.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(error, style: const TextStyle(color: Colors.red)),
          ),
        if (stage == 2 && selected != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Order total: ₹${branches.firstWhere((b) => b['id'] == selected)['total']}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 22,
                    ),
                  ),
                  if (branches.firstWhere(
                        (b) => b['id'] == selected,
                      )['requires_approval'] ==
                      true)
                    const Text(
                      'Delivery fee will be added after manager review.',
                    ),
                ],
              ),
            ),
          ),
        if (busy) const LinearProgressIndicator(),
        const SizedBox(height: 20),
        if (stage == 2)
          FilledButton(
            onPressed: busy || selected == null || widget.cart.isEmpty
                ? null
                : () => act(place),
            child: Text(
              widget.signedIn() ? 'Place order' : 'Sign in to continue',
            ),
          ),
        const SizedBox(height: 24),
      ],
    ),
  );
  Widget _field(String text, TextEditingController c, {int lines = 1}) =>
      TextField(
        controller: c,
        maxLines: lines,
        decoration: InputDecoration(labelText: text),
      );
}
