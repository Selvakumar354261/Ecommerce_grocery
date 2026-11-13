import 'dart:convert';

import 'package:chinnu_delivery/api.dart';
import 'package:chinnu_delivery/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> orderData({
  String status = 'dispatched',
  String payment = 'unpaid',
}) => {
  'id': 9,
  'number': 'ORD-000009',
  'customer_name': 'CUSTOMER',
  'phone': '9876543210',
  'address': 'Delivery address',
  'status': status,
  'payment_status': payment,
  'total': '750.00',
  'latitude': '11.341',
  'longitude': '77.7172',
  'items': [],
};

class FakeApi extends Api {
  FakeApi({String status = 'dispatched'})
    : current = Job.fromJson(orderData(status: status));
  Job current;
  int cashCalls = 0, completeCalls = 0, failureCalls = 0;
  bool rejectCompletion = false;
  Map<String, dynamic>? recordedPayload;
  @override
  Future<Job> order(int id) async => current;
  @override
  Future<void> start(int id) async {
    current = Job.fromJson(orderData());
  }

  @override
  Future<Map<String, dynamic>> previewPayment(
    int id,
    Map<String, dynamic> data,
  ) async => {
    'payment_method': data['payment_method'],
    'total': '750.00',
    'payments':
        data['payments'] ??
        [
          {'method': data['payment_method'], 'amount': '750.00'},
        ],
    'amount_tendered': data['payment_method'] == 'split' ? '500.00' : data['amount_tendered'],
    'change_due': data['payment_method'] == 'split'
        ? '0.00'
        : data['payment_method'] == 'cash'
        ? '250.00'
        : '0.00',
  };

  @override
  Future<Map<String, dynamic>> recordPayment(
    int id,
    Map<String, dynamic> data,
  ) async {
    cashCalls++;
    recordedPayload = data;
    final collection = await previewPayment(id, data);
    current = Job.fromJson({
      ...orderData(payment: 'paid'),
      'payment_collection': collection,
    });
    return collection;
  }

  @override
  Future<void> complete(int id, String otp) async {
    completeCalls++;
    if (rejectCompletion) {
      throw const ApiException('Enter the correct customer delivery OTP.');
    }
    current = Job.fromJson(orderData(status: 'completed', payment: 'paid'));
  }

  @override
  Future<void> fail(int id, String reason) async {
    failureCalls++;
    throw const ApiException('Branch could not be reached. Try again.');
  }
}

Future<void> showDetail(WidgetTester tester, FakeApi api) async {
  tester.view.physicalSize = const Size(800, 1400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(home: Detail(api.current, api: api)));
  await tester.pumpAndSettle();
}

void main() {
  test(
    'requests match the delivery backend and include validation details',
    () async {
      final requests = <http.Request>[];
      final api = Api(
        tokenReader: () async => 'test-token',
        client: MockClient((request) async {
          requests.add(request);
          if (request.url.path.endsWith('/complete')) {
            return http.Response(
              jsonEncode({
                'detail': 'Please check your entries.',
                'fields': ['otp: Enter six digits.'],
              }),
              422,
            );
          }
          return http.Response(jsonEncode(orderData()), 200);
        }),
      );
      await api.recordPayment(9, {
        'payment_method': 'cash',
        'amount_tendered': '1000.00',
      });
      expect(requests.single.method, 'POST');
      expect(requests.single.url.path, '/api/v1/orders/9/payment');
      expect(jsonDecode(requests.single.body), {
        'payment_method': 'cash',
        'amount_tendered': '1000.00',
      });
      expect(requests.single.headers['Authorization'], 'Bearer test-token');
      expect((await api.order(9)).id, 9);
      await expectLater(
        api.complete(9, '123'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            'otp: Enter six digits.',
          ),
        ),
      );
      expect(jsonDecode(requests.last.body), {'otp': '123'});
      expect(requests.last.headers['Idempotency-Key'], isNotEmpty);
    },
  );

  testWidgets(
    'cash refreshes payment, OTP gates completion, completed actions disappear',
    (tester) async {
      final api = FakeApi();
      await showDetail(tester, api);
      FilledButton completeButton() => tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Complete delivery'),
      );
      expect(completeButton().onPressed, isNull);
      await tester.tap(find.text('Collect payment'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Actual cash received'),
        '1000.00',
      );
      await tester.tap(find.text('Review payment'));
      await tester.pumpAndSettle();
      expect(find.text('Change to return: ₹250.00'), findsOneWidget);
      expect(api.cashCalls, 0);
      await tester.tap(find.text('Confirm collection'));
      await tester.pumpAndSettle();
      expect(api.cashCalls, 1);
      expect(find.text('Collect payment'), findsNothing);
      expect(find.text('Payment received: ₹750.00'), findsOneWidget);
      expect(completeButton().onPressed, isNull);
      await tester.enterText(find.byType(TextField), '12345');
      await tester.pump();
      expect(completeButton().onPressed, isNull);
      await tester.enterText(find.byType(TextField), '123456');
      await tester.pump();
      expect(completeButton().onPressed, isNotNull);
      await tester.tap(find.text('Complete delivery'));
      await tester.pumpAndSettle();
      expect(api.completeCalls, 1);
      expect(find.text('Delivery completed successfully.'), findsOneWidget);
      expect(find.text('Complete delivery'), findsNothing);
      expect(find.text('Could not deliver'), findsNothing);
    },
  );

  testWidgets('split payment reviews server change and records each portion', (
    tester,
  ) async {
    final api = FakeApi();
    await showDetail(tester, api);
    await tester.tap(find.text('Collect payment'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('SPLIT').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'CASH portion'),
      '500.00',
    );
    await tester.pump();
    expect(find.text('Remaining to allocate: \u20b9250.00'), findsOneWidget);
    await tester.enterText(
      find.widgetWithText(TextField, 'UPI portion'),
      '250.00',
    );
    await tester.pump();
    expect(find.text('Remaining to allocate: \u20b90.00'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Actual cash received'), findsNothing);
    await tester.tap(find.text('Review payment'));
    await tester.pumpAndSettle();
    expect(find.text('Change to return: ₹0.00'), findsOneWidget);
    await tester.enterText(
      find.widgetWithText(TextField, 'UPI portion'),
      '251.00',
    );
    await tester.pump();
    expect(find.text('Over allocated: \u20b91.00'), findsOneWidget);
    expect(find.text('Confirm collection'), findsNothing);
    await tester.enterText(
      find.widgetWithText(TextField, 'UPI portion'),
      '250.00',
    );
    await tester.tap(find.text('Review payment'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm collection'));
    await tester.pumpAndSettle();
    expect(api.recordedPayload, {
      'payment_method': 'split',
      'payments': [
        {'method': 'cash', 'amount': '500.00'},
        {'method': 'upi', 'amount': '250.00'},
      ],
      'expected_total': '750.00',
    });
    expect(find.text('CASH: ₹500.00'), findsOneWidget);
    expect(find.text('UPI: ₹250.00'), findsOneWidget);
    expect(find.text('Change to return: ₹0.00'), findsOneWidget);
  });

  testWidgets('starting a delivery immediately renders dispatched actions', (
    tester,
  ) async {
    final api = FakeApi(status: 'ready');
    await showDetail(tester, api);
    await tester.tap(find.text('Start delivery'));
    await tester.pumpAndSettle();
    expect(find.text('Start delivery'), findsNothing);
    expect(find.text('Status: dispatched'), findsOneWidget);
    expect(find.text('Collect payment'), findsOneWidget);
  });

  testWidgets(
    'backend OTP rejection stays visible and permits a corrected retry',
    (tester) async {
      final api = FakeApi()..rejectCompletion = true;
      api.current = Job.fromJson(orderData(payment: 'paid'));
      await showDetail(tester, api);
      await tester.enterText(find.byType(TextField), '123456');
      await tester.pump();
      await tester.tap(find.text('Complete delivery'));
      await tester.pumpAndSettle();
      expect(
        find.text('Enter the correct customer delivery OTP.'),
        findsOneWidget,
      );
      expect(find.text('Status: dispatched'), findsOneWidget);
      api.rejectCompletion = false;
      await tester.enterText(find.byType(TextField), '654321');
      await tester.pump();
      await tester.tap(find.text('Complete delivery'));
      await tester.pumpAndSettle();
      expect(api.completeCalls, 2);
      expect(find.text('Delivery completed successfully.'), findsOneWidget);
    },
  );

  testWidgets(
    'failed-delivery dialog validates reason and preserves backend errors',
    (tester) async {
      final api = FakeApi();
      await showDetail(tester, api);
      await tester.tap(find.text('Could not deliver'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();
      expect(api.failureCalls, 0);
      expect(
        find.text('Enter a reason with at least three characters.'),
        findsOneWidget,
      );
      await tester.enterText(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.byType(TextField),
        ),
        'Customer unavailable',
      );
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();
      expect(api.failureCalls, 1);
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(
        find.text('Branch could not be reached. Try again.'),
        findsOneWidget,
      );
      await tester.tap(find.text('Back'));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 350));
    },
  );
}
