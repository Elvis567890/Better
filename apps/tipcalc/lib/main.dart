import 'package:flutter/material.dart';

void main() {
  runApp(const TipCalcApp());
}

class TipCalcApp extends StatelessWidget {
  const TipCalcApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TipCalc',
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.teal,
      ),
      home: const TipCalculatorScreen(),
    );
  }
}

class TipCalculatorScreen extends StatefulWidget {
  const TipCalculatorScreen({super.key});

  @override
  State<TipCalculatorScreen> createState() => _TipCalculatorScreenState();
}

class _TipCalculatorScreenState extends State<TipCalculatorScreen> {
  final TextEditingController _billController = TextEditingController();
  final TextEditingController _tipController = TextEditingController();

  double _bill = 0.0;
  double _tipPercent = 0.0;

  @override
  void initState() {
    super.initState();
    _billController.addListener(_updateValues);
    _tipController.addListener(_updateValues);
  }

  @override
  void dispose() {
    _billController.removeListener(_updateValues);
    _tipController.removeListener(_updateValues);
    _billController.dispose();
    _tipController.dispose();
    super.dispose();
  }

  void _updateValues() {
    setState(() {
      _bill = double.tryParse(_billController.text) ?? 0.0;
      _tipPercent = double.tryParse(_tipController.text) ?? 0.0;
    });
  }

  double get _total => _bill + (_bill * _tipPercent / 100);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('TipCalc'),
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
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _tipController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Tip %',
                suffixText: '%',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Total: \$${_total.toStringAsFixed(2)}',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
          ],
        ),
      ),
    );
  }
}
