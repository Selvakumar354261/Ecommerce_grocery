import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

const apiUrl = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://10.0.2.2:8080/api/v1',
);

class Api {
  Api({this.client, this.tokenReader});

  final http.Client? client;
  final Future<String?> Function()? tokenReader;
  static const storage = FlutterSecureStorage();
  Future<dynamic> call(
    String p, {
    String method = 'GET',
    Map<String, dynamic>? body,
    Map<String, String>? headers,
  }) async {
    final t = await (tokenReader?.call() ?? storage.read(key: 'token'));
    final q = http.Request(method, Uri.parse('$apiUrl$p'))
      ..headers.addAll({
        'Content-Type': 'application/json',
        if (t != null) 'Authorization': 'Bearer $t',
        ...?headers,
      });
    if (body != null) q.body = jsonEncode(body);
    late http.Response r;
    try {
      r = await (() async => http.Response.fromStream(
        await (client?.send(q) ?? q.send()),
      ))().timeout(const Duration(seconds: 25));
    } on TimeoutException {
      throw const ApiException(
        'The server took too long to respond. Refresh the order before trying again.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Cannot reach the server. Check your connection and try again.',
      );
    }
    dynamic d;
    try {
      d = r.body.isEmpty ? <String, dynamic>{} : jsonDecode(r.body);
    } on FormatException {
      throw const ApiException(
        'The server returned an unexpected response. Please try again.',
      );
    }
    if (r.statusCode < 200 || r.statusCode > 299) {
      final detail = d is Map ? d['detail'] : null;
      final fields = d is Map ? d['fields'] : null;
      throw ApiException(
        fields is List && fields.isNotEmpty
            ? fields.join('\n')
            : detail is String
            ? detail
            : 'Request failed. Please try again.',
      );
    }
    return d;
  }

  Future<void> login(String e, String p) async {
    final r = await call(
      '/delivery/auth/login',
      method: 'POST',
      body: {'email': e, 'password': p},
    );
    await storage.write(key: 'token', value: r['token']);
  }

  Future<bool> hasSession() async => (await storage.read(key: 'token')) != null;
  Future<Map<String, dynamic>> profile() async => Map<String, dynamic>.from(await call('/delivery/profile'));
  Future<Map<String, dynamic>> history(String status, int page) async => Map<String, dynamic>.from(await call('/delivery/history?status=$status&page=$page'));
  Future<void> logout() => storage.delete(key: 'token');
  Future<List<Job>> jobs() async => (await call('/delivery/orders') as List)
      .map((x) => Job.fromJson(x))
      .toList();
  Future<Job> order(int id) async => Job.fromJson(await call('/orders/$id'));
  Future<void> start(int id) => call(
    '/delivery/orders/$id/start',
    method: 'POST',
    headers: {'Idempotency-Key': 'start-$id'},
  );
  Future<Map<String, dynamic>> previewPayment(
    int id,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await call('/orders/$id/payment/preview', method: 'POST', body: data),
  );
  Future<Map<String, dynamic>> recordPayment(
    int id,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await call('/orders/$id/payment', method: 'POST', body: data),
  );
  Future<void> complete(int id, String otp) => call(
    '/delivery/orders/$id/complete',
    method: 'POST',
    headers: {'Idempotency-Key': 'complete-$id'},
    body: {'otp': otp},
  );
  Future<void> fail(int id, String reason) => call(
    '/delivery/orders/$id/failed',
    method: 'POST',
    body: {'reason': reason},
  );
  Future<void> location(int id, double a, double b) => call(
    '/delivery/orders/$id/location',
    method: 'POST',
    body: {'latitude': a, 'longitude': b},
  );
}

class ApiException implements Exception {
  const ApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

class Job {
  final int id;
  final String number, customer, phone, address, status, payment, total;
  final double? lat, lng;
  final List items;
  final Map<String, dynamic>? collection;
  Job(
    this.id,
    this.number,
    this.customer,
    this.phone,
    this.address,
    this.status,
    this.payment,
    this.total,
    this.lat,
    this.lng,
    this.items, {
    this.collection,
  });
  factory Job.fromJson(Map j) => Job(
    j['id'],
    j['number'],
    j['customer_name'],
    j['phone'],
    j['address'],
    j['status'],
    j['payment_status'],
    j['total'].toString(),
    double.tryParse('${j['latitude'] ?? ''}'),
    double.tryParse('${j['longitude'] ?? ''}'),
    j['items'] ?? [],
    collection: j['payment_collection'] is Map
        ? Map<String, dynamic>.from(j['payment_collection'])
        : null,
  );
}
