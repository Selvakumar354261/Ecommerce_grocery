import 'package:flutter/material.dart';
import 'api.dart';

class DeliveryJobCard extends StatelessWidget {
  const DeliveryJobCard({super.key,required this.job,required this.onTap});
  final Job job;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final color=job.status=='completed' ? const Color(0xff205a3c)
      : ['cancelled','rejected'].contains(job.status) ? const Color(0xff9b3636)
      : const Color(0xff1d6546);
    return Card(clipBehavior:Clip.antiAlias,child:InkWell(onTap:onTap,child:Padding(
      padding:const EdgeInsets.all(18),
      child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
        Wrap(spacing:12,runSpacing:8,crossAxisAlignment:WrapCrossAlignment.center,children:[
          Text(job.number,style:const TextStyle(fontWeight:FontWeight.w800,fontSize:17)),
          Chip(backgroundColor:color.withValues(alpha:.09),label:Text(job.status.replaceAll('_',' '),style:TextStyle(color:color))),
        ]),
        const SizedBox(height:10),
        Text(job.customer,style:const TextStyle(fontWeight:FontWeight.w600,fontSize:16)),
        const SizedBox(height:6),
        Row(crossAxisAlignment:CrossAxisAlignment.start,children:[
          const Icon(Icons.place_outlined,size:18,color:Color(0xff64735c)),
          const SizedBox(width:6),
          Expanded(child:Text(job.address,style:const TextStyle(color:Color(0xff64735c),height:1.5))),
        ]),
        const Divider(height:28),
        Wrap(spacing:16,runSpacing:8,crossAxisAlignment:WrapCrossAlignment.center,children:[
          Text('Order total: \u20b9${job.total}',style:const TextStyle(fontWeight:FontWeight.w700)),
          const Text('View delivery',style:TextStyle(color:Color(0xff1d5a43),fontWeight:FontWeight.w600)),
        ]),
      ]),
    )));
  }
}

class DeliveryEmptyState extends StatelessWidget {
  const DeliveryEmptyState({super.key,required this.title,required this.subtitle});
  final String title,subtitle;
  @override
  Widget build(BuildContext context)=>Padding(padding:const EdgeInsets.symmetric(vertical:40,horizontal:16),child:Column(children:[
    const CircleAvatar(radius:34,backgroundColor:Color(0xffe7eddf),child:Icon(Icons.local_shipping_outlined,size:32,color:Color(0xff1d5a43))),
    const SizedBox(height:18),
    Text(title,textAlign:TextAlign.center,style:Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight:FontWeight.w700)),
    const SizedBox(height:8),
    Text(subtitle,textAlign:TextAlign.center,style:const TextStyle(color:Color(0xff64735c),height:1.5)),
  ]));
}
