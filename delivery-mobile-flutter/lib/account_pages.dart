import 'package:flutter/material.dart';
import 'api.dart';
import 'delivery_widgets.dart';

class DriverProfile extends StatefulWidget {
  const DriverProfile({super.key, required this.api});
  final Api api;
  @override
  State<DriverProfile> createState() => _DriverProfileState();
}
class _DriverProfileState extends State<DriverProfile> {
  late Future<Map<String,dynamic>> data;
  @override
  void initState() {super.initState();data=widget.api.profile();}
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('My profile')),
    body: FutureBuilder<Map<String,dynamic>>(future:data,builder:(context,snapshot){
      if(snapshot.hasError) return Center(child: Column(mainAxisSize:MainAxisSize.min,children:[Text(snapshot.error.toString()),TextButton(onPressed:()=>setState(()=>data=widget.api.profile()),child:const Text('Retry'))]));
      if(!snapshot.hasData) return const Center(child:CircularProgressIndicator());
      final p=snapshot.data!;
      return ListView(padding:const EdgeInsets.all(20),children:[
        const CircleAvatar(radius:36,child:Icon(Icons.person_outline,size:40)),
        const SizedBox(height:16),
        Text(p['name'].toString(),textAlign:TextAlign.center,style:Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height:16),
        Card(child:Column(children:[
          ListTile(leading:const Icon(Icons.email_outlined),title:const Text('Email'),subtitle:Text(p['email'] ?? 'Not provided')),
          ListTile(leading:const Icon(Icons.phone_outlined),title:const Text('Mobile'),subtitle:Text(p['phone'] ?? 'Not provided')),
          ListTile(leading:const Icon(Icons.storefront_outlined),title:const Text('Branch'),subtitle:Text(p['branch_name'] ?? 'Not assigned')),
        ])),
        Card(child:Column(children:[
          ListTile(title:const Text('Active deliveries'),trailing:Text('${p['active']}')),
          ListTile(title:const Text('Completed deliveries'),trailing:Text('${p['completed']}')),
          ListTile(title:const Text('Unsuccessful delivery attempts'),trailing:Text('${p['failed_attempts']}')),
        ])),
        const Padding(padding:EdgeInsets.all(12),child:Text('Contact your branch manager to update your account details.')),
      ]);
    }),
  );
}

class DriverHistory extends StatefulWidget {
  const DriverHistory({super.key,required this.api,required this.onOpen});
  final Api api;
  final Future<void> Function(Job) onOpen;
  @override
  State<DriverHistory> createState()=>_DriverHistoryState();
}
class _DriverHistoryState extends State<DriverHistory> {
  String status='all',error=''; int page=1,total=0;
  List<Job> jobs=[]; bool busy=true;
  @override
  void initState(){super.initState();load();}
  Future<void> load() async {
    setState(()=>busy=true);
    try {
      final result=await widget.api.history(status,page);
      if(!mounted)return;
      setState((){jobs=(result['items'] as List).map((x)=>Job.fromJson(x)).toList();total=result['total'] as int;error='';});
    }catch(e){if(mounted)setState(()=>error=e.toString());}
    finally{if(mounted)setState(()=>busy=false);}
  }
  @override
  Widget build(BuildContext context)=>Scaffold(
    appBar:AppBar(title:const Text('Delivery history')),
    body:RefreshIndicator(onRefresh:load,child:ListView(physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.all(20),children:[
      const Text('Completed, cancelled and rejected orders currently assigned to your account.'),
      const SizedBox(height:16),
      Wrap(spacing:8,runSpacing:8,children:[
        for(final s in ['all','completed','cancelled','rejected'])
          ChoiceChip(
            label:Text(s[0].toUpperCase()+s.substring(1)),
            selected:status==s,
            selectedColor:Theme.of(context).colorScheme.primaryContainer,
            onSelected:busy?null:(selected){if(selected && status!=s){status=s;page=1;load();}},
          ),
      ]),
      const SizedBox(height:16),
      if(busy)const LinearProgressIndicator(),
      if(error.isNotEmpty)Text(error,style:TextStyle(color:Theme.of(context).colorScheme.error)),
      if(!busy && error.isEmpty && jobs.isEmpty)const DeliveryEmptyState(title:'No deliveries found',subtitle:'Completed deliveries will appear here. Try another status filter.'),
      if(error.isEmpty)for(final j in jobs)DeliveryJobCard(job:j,onTap:()=>widget.onOpen(j)),
      if(error.isEmpty)Wrap(alignment:WrapAlignment.center,spacing:12,crossAxisAlignment:WrapCrossAlignment.center,children:[
        TextButton(onPressed:busy||page==1?null:(){page--;load();},child:const Text('Previous')),
        Text('Page $page · $total ${total==1 ? 'order' : 'orders'}'),
        TextButton(onPressed:busy||page*20>=total?null:(){page++;load();},child:const Text('Next')),
      ]),
    ])),
  );
}
