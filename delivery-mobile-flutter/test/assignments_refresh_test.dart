import 'package:chinnu_delivery/api.dart';
import 'package:chinnu_delivery/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class AssignmentsApi extends Api {
  int calls = 0;
  bool failFetch = false;
  @override
  Future<List<Job>> jobs() async {
    calls++;
    if (failFetch) throw const ApiException('Connection unavailable');
    return calls == 1 ? [] : [Job.fromJson({
      'id': 1, 'number': 'ORD-NEW', 'customer_name': 'CUSTOMER',
      'address': 'Address', 'phone': '9876543210', 'status': 'ready',
      'payment_status': 'unpaid', 'total': '100', 'items': [],
    })];
  }
}

void main() {
  testWidgets('new assignments appear automatically and polling stops on dispose', (tester) async {
    final api = AssignmentsApi();
    await tester.pumpWidget(MaterialApp(home: Jobs(onLogout: () {}, api: api)));
    await tester.pump();
    expect(find.text('No active deliveries'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    await tester.pump();
    expect(find.text('ORD-NEW'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    final calls = api.calls;
    await tester.pump(const Duration(seconds: 10));
    expect(api.calls, calls);
  });

  testWidgets('failed fetch does not claim there are no deliveries', (tester) async {
    final api = AssignmentsApi()..failFetch = true;
    await tester.pumpWidget(MaterialApp(home: Jobs(onLogout: () {}, api: api)));
    await tester.pump();
    expect(find.text('Connection unavailable'), findsOneWidget);
    expect(find.text('No active deliveries'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
}
