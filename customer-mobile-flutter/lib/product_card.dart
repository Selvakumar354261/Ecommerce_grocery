import 'package:flutter/material.dart';

class ProductCard extends StatefulWidget {
  const ProductCard({super.key, required this.product, required this.onAdd});
  final Map product;
  final void Function(Map, num) onAdd;
  @override
  State<ProductCard> createState() => _ProductCardState();
}

class _ProductCardState extends State<ProductCard> {
  int index = 0;
  @override
  Widget build(BuildContext context) {
    final variants = widget.product['variants'] as List;
    if (variants.isEmpty) return const SizedBox();
    if (index >= variants.length) index = 0;
    final v = variants[index];
    final art = Container(
      width: 88,
      height: 110,
      decoration: BoxDecoration(
        color: const Color(0xffe8efdf),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Center(
        child: Transform.rotate(
          angle: -.06,
          child: Container(
            width: 56,
            height: 82,
            decoration: BoxDecoration(
              color: const Color(0xfffafcf6),
              border: Border.all(color: const Color(0xffb9cba7)),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Image.asset('assets/chinnu-logo.png', width: 48, height: 40),
                const SizedBox(height: 4),
                Text(
                  widget.product['category'].toString().toUpperCase(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 6,
                    letterSpacing: 1,
                    color: Color(0xff175c3c),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                art,
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.product['category'].toString().toUpperCase(),
                        style: const TextStyle(
                          fontSize: 10,
                          color: Color(0xff5a7954),
                          letterSpacing: 1,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(
                        widget.product['name'],
                        style: const TextStyle(
                          fontSize: 17,
                          height: 1.3,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        widget.product['description'] ?? '',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12,
                          height: 1.5,
                          color: Color(0xff72806a),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int>(
              key: ValueKey('${widget.product['id']}-$index'),
              initialValue: index,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Pack / quantity option',
                contentPadding: EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
              ),
              items: [
                for (int i = 0; i < variants.length; i++)
                  DropdownMenuItem(
                    value: i,
                    child: Text(
                      variants[i]['label'],
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
              ],
              onChanged: (i) => setState(() => index = i!),
            ),
            const SizedBox(height: 14),
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 10,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '₹${v['price']}',
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        color: Color(0xff175c3c),
                      ),
                    ),
                    Text(
                      'per ${v['unit']}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: Color(0xff72806a),
                      ),
                    ),
                  ],
                ),
                FilledButton.icon(
                  onPressed: () =>
                      widget.onAdd(v, num.parse('${v['min_qty']}')),
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
