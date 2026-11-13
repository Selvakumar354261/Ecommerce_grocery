import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chinnu_customer/api.dart';
import 'package:chinnu_customer/main.dart';

void main() {
  test('backend cookie and csrf are sent; validation is displayed', () async {
    final api =
        Api(
            client: MockClient((r) async {
              expect(r.headers['Cookie'], 'grocery_session=test');
              expect(r.headers['X-CSRF-Token'], 'csrf');
              expect(jsonDecode(r.body)['phone'], '9876543210');
              return http.Response('{"detail":"Invalid contact number"}', 422);
            }),
          )
          ..cookie = 'grocery_session=test'
          ..csrf = 'csrf';
    await expectLater(
      api.call('/orders', method: 'POST', body: {'phone': '9876543210'}),
      throwsA(
        isA<ApiError>().having(
          (e) => e.message,
          'message',
          'Invalid contact number',
        ),
      ),
    );
  });
  testWidgets('product card is readable on a narrow screen and adds variant', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    int? added;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ProductCard(
              product: {
                'id': 1,
                'name': 'Heritage rice',
                'category': 'Rice',
                'description': 'Everyday essentials',
                'variants': [
                  {
                    'id': 2,
                    'label': '1 kg sealed pack',
                    'price': '78.00',
                    'unit': 'pack',
                    'min_qty': '1',
                  },
                ],
              },
              onAdd: (v, q) => added = v['id'],
            ),
          ),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Add'));
    expect(added, 2);
  });
}
