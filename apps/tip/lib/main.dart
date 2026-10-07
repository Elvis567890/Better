import 'package:flutter/material.dart';

void main() {
  runApp(const TipApp());
}

class TipApp extends StatelessWidget {
  const TipApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Tip',
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.teal,
      ),
      home: const TipCalculatorPage(),
    );
  }
}

class TipCalculatorPage extends StatefulWidget {
  const TipCalculatorPage({super.key});

  @override
  State<TipCalculatorPage> createState() => _TipCalculatorPageState();
}

class _TipCalculatorPageState extends State<TipCalculatorPage> {
  final TextEditingController _billController = TextEditingController();
  final TextEditingController _peopleController = TextEditingController(text: '1');
  double _tipPercent = 15;

  @override
  void dispose() {
    _billController.dispose();
    _peopleController.dispose();
    super.dispose();
  }

  double get _bill {
    final text = _billController.text;
    return double.tryParse(text) ?? 0.0;
  }

  int get _people {
    final text = _peopleController.text;
    final value = int.tryParse(text);
    return (value != null && value > 0) ? value : 1;
  }

  double get _tipAmount => _bill * _tipPercent / 100;
  double get _total => _bill + _tipAmount;
  double get _perPerson => _total / _people;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tip Calculator'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _billController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Bill amount',
                prefixIcon: Icon(Icons.attach_money),
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('Tip %'),
                Expanded(
                  child: Slider(
                    min: 0,
                    max: 100,
                    divisions: 100,
                    value: _tipPercent,
                    label: '${_tipPercent.round()}%',
                    onChanged: (value) {
                      setState(() {
                        _tipPercent = value;
                      });
                    },
                  ),
                ),
                Text('${_tipPercent.round()}%'),
              ],
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _peopleController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Number of people',
                prefixIcon: Icon(Icons.person),
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 24),
            Card(
              elevation: 4,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    _ResultRow(label: 'Bill', value: _bill),
                    _ResultRow(label: 'Tip', value: _tipAmount),
                    const Divider(),
                    _ResultRow(label: 'Total', value: _total),
                    const Divider(),
                    _ResultRow(label: 'Per Person', value: _perPerson),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultRow extends StatelessWidget {
  final String label;
  final double value;

  const _ResultRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 16)),
        Text('\$${value.toStringAsFixed(2)}',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      ],
    );
  }
}
