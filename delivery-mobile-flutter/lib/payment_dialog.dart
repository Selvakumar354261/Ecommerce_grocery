import 'package:flutter/material.dart';

import 'api.dart';

class PaymentSummary extends StatelessWidget {
  const PaymentSummary(this.collection, {super.key});
  final Map<String, dynamic> collection;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Payment: ${collection['payment_method'].toString().toUpperCase()}',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          for (final part in collection['payments'] as List? ?? [])
            Text(
              '${part['method'].toString().toUpperCase()}: ₹${part['amount']}',
            ),
          if (collection['amount_tendered'] != null) ...[
            const Divider(),
            Text('Actual cash received: ₹${collection['amount_tendered']}'),
            Text(
              'Change to return: ₹${collection['change_due']}',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
            ),
          ],
        ],
      ),
    ),
  );
}

class PaymentDialog extends StatefulWidget {
  const PaymentDialog({super.key, required this.api, required this.job});
  final Api api;
  final Job job;
  @override
  State<PaymentDialog> createState() => _PaymentDialogState();
}

class _PaymentDialogState extends State<PaymentDialog> {
  String method = 'cash', error = '';
  final cashReceived = TextEditingController();
  final parts = {
    for (final name in ['cash', 'upi', 'card']) name: TextEditingController(),
  };
  bool busy = false;
  Map<String, dynamic>? quote, reviewedPayload;
  // UI estimate only; the backend still validates and calculates the settlement.
  int? cents(String text) {
    final value = text.trim();
    if (value.isEmpty) return 0;
    if (!RegExp(r'^\d+(\.\d{0,2})?$').hasMatch(value)) return null;
    final pieces = value.split('.');
    return int.parse(pieces[0]) * 100 +
        int.parse((pieces.length == 1 ? '' : pieces[1]).padRight(2, '0'));
  }

  Widget splitBalance() {
    final total = cents(widget.job.total.toString());
    final values = parts.values.map((p) => cents(p.text)).toList();
    if (total == null || values.any((v) => v == null)) {
      return const Text('Enter valid amounts with up to two decimal places.');
    }
    final allocated = values.fold<int>(0, (sum, v) => sum + v!);
    final remaining = total - allocated;
    return Container(
      key: const Key('split-balance'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: remaining < 0
            ? Theme.of(context).colorScheme.errorContainer
            : Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Entered portions: \u20b9${(allocated / 100).toStringAsFixed(2)}'),
          Text(
            remaining < 0
                ? 'Over allocated: \u20b9${(-remaining / 100).toStringAsFixed(2)}'
                : 'Remaining to allocate: \u20b9${(remaining / 100).toStringAsFixed(2)}',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          const Text('The cash portion is the exact cash collected. No change is calculated for split payments. Final amounts are verified on review.'),
        ],
      ),
    );
  }
  @override
  void dispose() {
    cashReceived.dispose();
    for (final controller in parts.values) {
      controller.dispose();
    }
    super.dispose();
  }

  void invalidate() => setState(() {
    quote = null;
    reviewedPayload = null;
    error = '';
  });
  Map<String, dynamic> payload() => {
    'payment_method': method,
    if (method == 'split')
      'payments': [
        for (final entry in parts.entries)
          if (entry.value.text.trim().isNotEmpty)
            {'method': entry.key, 'amount': entry.value.text.trim()},
      ],
    if (method == 'cash' &&
        cashReceived.text.trim().isNotEmpty)
      'amount_tendered': cashReceived.text.trim(),
  };
  Future<void> review() async {
    setState(() {
      busy = true;
      error = '';
    });
    try {
      final data = payload();
      final result = await widget.api.previewPayment(widget.job.id, data);
      if (mounted) {
        setState(() {
          quote = result;
          reviewedPayload = data;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> confirm() async {
    if (reviewedPayload == null || quote == null || busy) return;
    setState(() {
      busy = true;
      error = '';
    });
    try {
      await widget.api.recordPayment(widget.job.id, {
        ...reviewedPayload!,
        'expected_total': quote!['total'],
      });
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget amountInput(String label, TextEditingController controller) =>
      TextField(
        controller: controller,
        enabled: !busy,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: InputDecoration(labelText: label, prefixText: '₹ '),
        onChanged: (_) => invalidate(),
      );
  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: const Text('Collect payment'),
      content: SizedBox(
        width: 480,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Order total: ₹${widget.job.total}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: method,
                decoration: const InputDecoration(labelText: 'Payment method'),
                items: [
                  for (final name in ['cash', 'upi', 'card', 'split'])
                    DropdownMenuItem(
                      value: name,
                      child: Text(name.toUpperCase()),
                    ),
                ],
                onChanged: busy
                    ? null
                    : (value) {
                        method = value!;
                        invalidate();
                      },
              ),
              const SizedBox(height: 16),
              if (method == 'split') ...[
                const Text(
                  'Enter each payment portion. Leave unused methods empty.',
                ),
                const SizedBox(height: 12),
                splitBalance(),
                for (final entry in parts.entries) ...[
                  const SizedBox(height: 12),
                  amountInput(
                    '${entry.key.toUpperCase()} portion',
                    entry.value,
                  ),
                ],
              ],
              if (method == 'cash') ...[
                const SizedBox(height: 12),
                amountInput('Actual cash received', cashReceived),
                const SizedBox(height: 8),
                Text(
                  method == 'split'
                      ? 'Required only when a cash portion is included. Enter the notes received, before returning change.'
                      : 'Enter the notes received, before returning change.',
                ),
              ],
              if (error.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    error,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (busy) const LinearProgressIndicator(),
              if (quote != null) ...[
                const SizedBox(height: 16),
                PaymentSummary(quote!),
                const Text(
                  'Confirm only after receiving all listed payments and returning any change.',
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context, false),
          child: const Text('Back'),
        ),
        FilledButton(
          onPressed: busy
              ? null
              : quote == null
              ? review
              : confirm,
          child: Text(quote == null ? 'Review payment' : 'Confirm collection'),
        ),
      ],
    ),
  );
}
