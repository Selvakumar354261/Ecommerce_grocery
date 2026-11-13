import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:chinnu_customer/api.dart';
import 'package:chinnu_customer/main.dart';

class ShopApi extends Api {
  @override
  Future<void> restore() async {}
  @override
  Future<dynamic> call(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    String? key,
  }) async => path == '/catalogue' ? [] : {'user': null};
}

void main() {
  testWidgets('shop fits narrow screen with bottom navigation', (tester) async {
    tester.view.physicalSize = const Size(320, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: Store(api: ShopApi())));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Basket'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Basket'));
    await tester.pumpAndSettle();
    expect(find.text('1. Basket'), findsOneWidget);
    expect(find.text('2. Delivery'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
