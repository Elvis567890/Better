import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

void main() {
  runApp(const TipCalcApp());
}

class TipCalcApp extends StatelessWidget {
  const TipCalcApp({Key? key}) : super(key: key);

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
  const TipCalculatorScreen({Key? key}) : super(key: key);

  @override
  State<TipCalculatorScreen> createState() => _TipCalculatorScreenState();
}

class _TipCalculatorScreenState extends State<TipCalculatorScreen> {
  final TextEditingController _billController = TextEditingController();
  final TextEditingController _tipController = TextEditingController();

  double _total = 0.0;

  void _calculate() {
    final bill = double.tryParse(_billController.text) ?? 0.0;
    final tipPercent = double.tryParse(_tipController.text) ?? 0.0;
    final tipAmount = bill * tipPercent / 100;
    setState(() {
      _total = bill + tipAmount;
    });
  }

  @override
  void initState() {
    super.initState();
    _billController.addListener(_calculate);
    _tipController.addListener(_calculate);
  }

  @override
  void dispose() {
    _billController.dispose();
    _tipController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final formatter = NumberFormat.currency(symbol: '\\$', decimalDigits: 2);
    return Scaffold(
      appBar: AppBar(
        title: const Text('TipCalc'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _billController,
              keyboardType: TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Bill Amount',
                prefixIcon: Icon(Icons.attach_money),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _tipController,
              keyboardType: TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Tip %',
                suffixText: '%',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Total: ${formatter.format(_total)}',
              style: Theme.of(context).textTheme.headlineMedium,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
