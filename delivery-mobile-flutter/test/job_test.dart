import 'package:flutter_test/flutter_test.dart';
import 'package:chinnu_delivery/api.dart';

void main() {
  test('delivery job parses backend coordinates and values', () {
    final job = Job.fromJson({
      'id': 7,
      'number': 'ORD-000007',
      'customer_name': 'CUSTOMER',
      'phone': '9876543210',
      'address': 'Delivery address',
      'status': 'ready',
      'payment_status': 'unpaid',
      'total': '750.00',
      'latitude': '11.3410000',
      'longitude': '77.7172000',
      'items': [],
    });
    expect(job.number, 'ORD-000007');
    expect(job.lat, 11.341);
    expect(job.lng, 77.7172);
  });
}
