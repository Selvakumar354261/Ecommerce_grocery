import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:chinnu_delivery/api.dart';
import 'package:chinnu_delivery/delivery_widgets.dart';

void main(){
  testWidgets('delivery card fits narrow screen and large text',(tester)async{
    tester.view.physicalSize=const Size(320,900);
    tester.view.devicePixelRatio=1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final job=Job.fromJson({'id':1,'number':'ORD-000001','customer_name':'A CUSTOMER WITH A LONG NAME','phone':'9876543210','address':'A long rural delivery address with landmarks and village details','status':'completed','payment_status':'paid','total':'1000.00','items':[]});
    bool opened=false;
    await tester.pumpWidget(MaterialApp(home:MediaQuery(data:const MediaQueryData(textScaler:TextScaler.linear(1.5)),child:Scaffold(body:SingleChildScrollView(child:DeliveryJobCard(job:job,onTap:()=>opened=true))))));
    expect(tester.takeException(),isNull);
    await tester.tap(find.text('View delivery'));
    expect(opened,isTrue);
  });
}
