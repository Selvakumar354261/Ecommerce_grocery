import 'package:flutter/material.dart';

import 'api.dart';
import 'checkout.dart';
import 'customer_pages.dart';
export 'product_card.dart';
import 'product_card.dart';

const green = Color(0xff175c3c);
void main() => runApp(const CustomerApp());

class CustomerApp extends StatelessWidget {
  const CustomerApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'CHINNU',
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xfff6f8f4),
      colorScheme: ColorScheme.fromSeed(seedColor: green)
          .copyWith(primary: green, surface: Colors.white),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xfff6f8f4),
        foregroundColor: green,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          fontSize: 21,
          fontWeight: FontWeight.w700,
          color: green,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.all(16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xffdce7d8)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xffdce7d8)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 50),
          textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: const EdgeInsets.symmetric(vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Color(0xffe0e8dc)),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: const Color(0xffdeeddc),
        height: 72,
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
        ),
      ),
    ),
    home: const Store(),
  );
}

class Store extends StatefulWidget {
  const Store({super.key, this.api});
  final Api? api;
  @override
  State<Store> createState() => _StoreState();
}

class _StoreState extends State<Store> {
  late final Api api;
  final Map<int, num> cart = {};
  List products = [];
  Map<String, dynamic>? user;
  String search = '', category = 'All', error = '';
  bool loading = true;
  int tab = 0;
  @override
  void initState() {
    super.initState();
    api = widget.api ?? Api();
    load();
  }

  Future<void> load() async {
    try {
      await api.restore();
      final data = await api.call('/catalogue');
      final session = await api.call('/auth/session');
      if (mounted) {
        setState(() {
          products = data;
          user = session['user'];
          error = '';
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<bool> signIn() async {
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => CustomerLogin(api: api)),
    );
    if (result == true) {
      final session = await api.call('/auth/session');
      if (mounted) setState(() => user = session['user']);
      return true;
    }
    return false;
  }

  Future<void> checkout() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CustomerCheckout(
          api: api,
          cart: cart,
          products: products,
          signedIn: () => user != null,
          signIn: signIn,
          onPlaced: () => setState(() => cart.clear()),
        ),
      ),
    );
    if (mounted) setState(() {});
  }

  Future<void> selectTab(int value) async {
    if (value == 1) {
      await checkout();
      return;
    }
    try {
      if (value > 1 && user == null && !await signIn()) return;
      if (mounted) setState(() => tab = value);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      toolbarHeight: 70,
      title: Row(
        children: [
          Image.asset('assets/chinnu-logo.png', width: 66, height: 50),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  tab == 0
                      ? 'Your everyday store'
                      : tab == 2
                      ? 'Your orders'
                      : 'Your account',
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const Text(
                  'CHINNU · Quality, close to home',
                  style: TextStyle(fontSize: 11, color: Color(0xff6c7b67)),
                ),
              ],
            ),
          ),
        ],
      ),
      actions: [
        if (tab == 0)
          IconButton(
            tooltip: 'Refresh shop',
            onPressed: load,
            icon: const Icon(Icons.refresh),
          ),
      ],
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: tab,
      onDestinationSelected: selectTab,
      destinations: [
        const NavigationDestination(
          icon: Icon(Icons.storefront_outlined),
          selectedIcon: Icon(Icons.storefront),
          label: 'Shop',
        ),
        NavigationDestination(
          icon: Badge(
            isLabelVisible: cart.isNotEmpty,
            label: Text('${cart.length}'),
            child: const Icon(Icons.shopping_bag_outlined),
          ),
          label: 'Basket',
        ),
        const NavigationDestination(
          icon: Icon(Icons.receipt_long_outlined),
          label: 'Orders',
        ),
        const NavigationDestination(
          icon: Icon(Icons.person_outline),
          label: 'Account',
        ),
      ],
    ),
    body: tab == 2
        ? CustomerOrders(api: api, embedded: true)
        : tab == 3 && user != null
        ? CustomerProfile(
            user: user!,
            api: api,
            embedded: true,
            onSignedOut: () {
              setState(() {
                user = null;
                tab = 0;
              });
            },
          )
        : shop(),
  );
  Widget shop() {
    final categories = [
      'All',
      ...{for (final p in products) p['category'].toString()},
    ];
    final filtered = products
        .where(
          (p) =>
              (category == 'All' || p['category'] == category) &&
              '${p['name']} ${p['category']}'.toLowerCase().contains(
                search.toLowerCase(),
              ),
        )
        .toList();
    return RefreshIndicator(
      onRefresh: load,
      child: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'What are you shopping for?',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (v) => setState(() => search = v),
                ),
                const SizedBox(height: 20),
                Container(
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    color: green,
                    borderRadius: BorderRadius.circular(22),
                  ),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'FROM OUR MILL TO YOUR HOME',
                              style: TextStyle(
                                fontSize: 9,
                                letterSpacing: 1.5,
                                color: Color(0xffbadbb7),
                              ),
                            ),
                            SizedBox(height: 10),
                            Text(
                              'Simple ingredients.\nEveryday goodness.',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 25,
                                height: 1.2,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            SizedBox(height: 12),
                            Text(
                              'Shop your essentials, your way.',
                              style: TextStyle(
                                color: Color(0xffd7e8cf),
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Icon(
                        Icons.spa_outlined,
                        size: 48,
                        color: Color(0xffa8ce9a),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
                const Wrap(
                  spacing: 18,
                  runSpacing: 8,
                  children: [
                    _Service(
                      icon: Icons.local_shipping_outlined,
                      label: 'Home delivery',
                    ),
                    _Service(
                      icon: Icons.storefront_outlined,
                      label: 'Shop pickup',
                    ),
                  ],
                ),
                const SizedBox(height: 26),
                const Text(
                  'Browse categories',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 12),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      for (final c in categories)
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ChoiceChip(
                            showCheckmark: false,
                            selectedColor: const Color(0xffdeeddc),
                            label: Text(c),
                            selected: category == c,
                            onSelected: (_) => setState(() => category = c),
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 22),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        category == 'All' ? 'Made for your pantry' : category,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    Text(
                      '${filtered.length} products',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xff6c7b67),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (loading) const LinearProgressIndicator(),
                if (error.isNotEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        children: [
                          Text(error),
                          TextButton(
                            onPressed: load,
                            child: const Text('Try again'),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (!loading && error.isEmpty && filtered.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(32),
                    child: Text(
                      'No matching products. Try a different search.',
                    ),
                  ),
              ]),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            sliver: SliverList.builder(
              itemCount: filtered.length,
              itemBuilder: (context, index) => ProductCard(
                key: ValueKey(filtered[index]['id']),
                product: filtered[index],
                onAdd: (v, q) {
                  setState(() => cart[v['id']] = (cart[v['id']] ?? 0) + q);
                  ScaffoldMessenger.of(context).hideCurrentSnackBar();
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Added to basket'),
                      action: SnackBarAction(
                        label: 'View',
                        onPressed: checkout,
                      ),
                      duration: const Duration(seconds: 2),
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Service extends StatelessWidget {
  const _Service({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 18, color: green),
      const SizedBox(width: 7),
      Text(
        label,
        style: const TextStyle(fontSize: 12, color: Color(0xff536b50)),
      ),
    ],
  );
}
