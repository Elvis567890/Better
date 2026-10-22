import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'App',
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.blue,
      ),
      home: const TimerPage(),
    );
  }
}

class TimerPage extends StatefulWidget {
  const TimerPage({super.key});
  @override
  State<TimerPage> createState() => _TimerPageState();
}

class _TimerPageState extends State<TimerPage> {
  final Stopwatch _stopwatch = Stopwatch();
  Timer? _timer;

  void _start() {
    if (!_stopwatch.isRunning) {
      _stopwatch.start();
      _timer = Timer.periodic(const Duration(milliseconds: 100), (_) {
        setState(() {});
      });
    }
  }

  void _stop() {
    if (_stopwatch.isRunning) {
      _stopwatch.stop();
      _timer?.cancel();
    }
  }

  void _reset() {
    _stop();
    _stopwatch.reset();
    setState(() {});
  }

  Future<void> _exportCsv() async {
    final timestamp = DateTime.now().toIso8601String();
    final elapsed = _stopwatch.elapsed.inSeconds;
    final csv = 'Timestamp,ElapsedSeconds\\n$timestamp,$elapsed\\n';
    final file = File('${Directory.systemTemp.path}/timer_export_${DateTime.now().millisecondsSinceEpoch}.csv');
    await file.writeAsString(csv);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('CSV exported to ${file.path}')),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  String get _formattedTime {
    final elapsed = _stopwatch.elapsed;
    final hours = elapsed.inHours.toString().padLeft(2, '0');
    final minutes = (elapsed.inMinutes % 60).toString().padLeft(2, '0');
    final seconds = (elapsed.inSeconds % 60).toString().padLeft(2, '0');
    final milliseconds = (elapsed.inMilliseconds % 1000).toString().padLeft(3, '0');
    return '$hours:$minutes:$seconds.$milliseconds';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Timer Utility'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Text(
              _formattedTime,
              style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 12,
              children: [
                ElevatedButton(
                  onPressed: _start,
                  child: const Text('Start'),
                ),
                ElevatedButton(
                  onPressed: _stop,
                  child: const Text('Stop'),
                ),
                ElevatedButton(
                  onPressed: _reset,
                  child: const Text('Reset'),
                ),
                ElevatedButton(
                  onPressed: _exportCsv,
                  child: const Text('Export CSV'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
