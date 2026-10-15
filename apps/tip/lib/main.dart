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
      theme: ThemeData(useMaterial3: true),
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
  double _tipPercent = 15.0;

  @override
  void dispose() {
    _billController.dispose();
    _peopleController.dispose();
    super.dispose();
  }

  double get _bill => double.tryParse(_billController.text) ?? 0.0;
  int get _people => int.tryParse(_peopleController.text) ?? 1;

  double get _tipAmount => _bill * _tipPercent / 100.0;
  double get _total => _bill + _tipAmount;
  double get _perPerson => _people > 0 ? _total / _people : 0.0;

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
                labelText: 'Bill Amount',
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
                labelText: 'Number of People',
                prefixIcon: Icon(Icons.person),
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    _buildResultRow('Bill', _bill),
                    _buildResultRow('Tip (${_tipPercent.round()}%)', _tipAmount),
                    const Divider(),
                    _buildResultRow('Total', _total),
                    const Divider(),
                    _buildResultRow('Per Person', _perPerson),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultRow(String label, double value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label),
        Text('\$${value.toStringAsFixed(2)}'),
      ],
    );
  }
}
