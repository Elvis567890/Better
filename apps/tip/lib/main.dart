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
  double _tipPercent = 15;
  int _people = 1;

  double get _bill => double.tryParse(_billController.text) ?? 0.0;
  double get _tipAmount => _bill * _tipPercent / 100;
  double get _total => _bill + _tipAmount;
  double get _perPerson => _people > 0 ? _total / _people : 0.0;

  @override
  void dispose() {
    _billController.dispose();
    super.dispose();
  }

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
                SizedBox(width: 48, child: Text('${_tipPercent.round()}%')),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('People'),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.remove),
                  onPressed: _people > 1 ? () => setState(() => _people--) : null,
                ),
                Text('$_people'),
                IconButton(
                  icon: const Icon(Icons.add),
                  onPressed: () => setState(() => _people++),
                ),
              ],
            ),
            const Divider(height: 32),
            _buildResultRow('Tip Amount', _tipAmount),
            _buildResultRow('Total', _total),
            _buildResultRow('Per Person', _perPerson),
          ],
        ),
      ),
    );
  }

  Widget _buildResultRow(String label, double value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        children: [
          Text(label),
          const Spacer(),
          Text('\$${value.toStringAsFixed(2)}'),
        ],
      ),
    );
  }
}
