import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const server = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://10.0.2.2:8080/api/v1',
);

class Api {
  final http.Client client;
  Api({http.Client? client}) : client = client ?? http.Client();
  static const storage = FlutterSecureStorage();
  String? cookie, csrf;
  Future<void> restore() async {
    cookie = await storage.read(key: 'session');
    csrf = await storage.read(key: 'csrf');
  }

  Future<dynamic> call(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    String? key,
  }) async {
    final request = http.Request(method, Uri.parse('$server$path'));
    request.headers.addAll({
      'Content-Type': 'application/json',
      'Cookie': ?cookie,
      'X-CSRF-Token': ?csrf,
      'Idempotency-Key': ?key,
    });
    if (body != null) request.body = jsonEncode(body);
    late http.Response response;
    try {
      response = await (() async => http.Response.fromStream(
        await client.send(request),
      ))().timeout(const Duration(seconds: 25));
    } catch (_) {
      throw const ApiError(
        'Cannot reach the store. Check your connection and try again.',
      );
    }
    dynamic data;
    try {
      data = jsonDecode(response.body);
    } catch (_) {
      throw const ApiError(
        'The store is temporarily unavailable. Please try again.',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiError(
        data is Map && data['detail'] is String
            ? data['detail']
            : 'Please check your entries and try again.',
      );
    }
    if (path == '/auth/otp/verify' && data['user'] != null) {
      final match = RegExp(r'grocery_session=([^;]+)')
          .firstMatch(response.headers['set-cookie'] ?? '');
      if (match == null) {
        throw const ApiError('Sign-in could not be saved. Please retry.');
      }
      cookie = 'grocery_session=${match.group(1)}';
      csrf = data['csrf'];
      await storage.write(key: 'session', value: cookie);
      await storage.write(key: 'csrf', value: csrf);
    }
    return data;
  }

  Future<void> logout() async {
    await call('/auth/logout', method: 'POST');
    cookie = null;
    csrf = null;
    await storage.delete(key: 'session');
    await storage.delete(key: 'csrf');
  }
}

class ApiError implements Exception {
  final String message;
  const ApiError(this.message);
  @override
  String toString() => message;
}
