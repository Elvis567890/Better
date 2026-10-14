import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  runApp(const ProductivityTimerApp());
}

class ProductivityTimerApp extends StatelessWidget {
  const ProductivityTimerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'App',
      theme: ThemeData(useMaterial3: true),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;
  final List<int> _sessions = [];

  void _addSession(int seconds) {
    setState(() {
      _sessions.add(seconds);
    });
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = [
      TimerPage(onSessionComplete: _addSession),
      StatsPage(sessions: _sessions),
      ExportPage(sessions: _sessions),
    ];
    return Scaffold(
      body: SessionData(
        sessions: _sessions,
        addSession: _addSession,
        child: pages[_selectedIndex],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) => setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.timer), label: 'Timer'),
          NavigationDestination(icon: Icon(Icons.bar_chart), label: 'Stats'),
          NavigationDestination(icon: Icon(Icons.share), label: 'Export'),
        ],
      ),
    );
  }
}

// Inherited widget to expose session data to any child
class SessionData extends InheritedWidget {
  final List<int> sessions;
  final void Function(int) addSession;

  const SessionData({
    required this.sessions,
    required this.addSession,
    required super.child,
  });

  static SessionData of(BuildContext context) {
    final SessionData? result = context.dependOnInheritedWidgetOfExactType<SessionData>();
    assert(result != null, 'No SessionData found in context');
    return result!;
  }

  @override
  bool updateShouldNotify(SessionData old) => sessions != old.sessions;
}

class TimerPage extends StatefulWidget {
  final void Function(int) onSessionComplete;
  const TimerPage({required this.onSessionComplete, super.key});

  @override
  State<TimerPage> createState() => _TimerPageState();
}

class _TimerPageState extends State<TimerPage> {
  bool _running = false;
  int _seconds = 0;
  Timer? _timer;

  void _start() {
    setState(() {
      _running = true;
      _seconds = 0;
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _seconds++);
    });
  }

  void _stop() {
    _timer?.cancel();
    setState(() => _running = false);
    widget.onSessionComplete(_seconds);
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final minutes = _seconds ~/ 60;
    final secs = _seconds % 60;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}',
            style: const TextStyle(fontSize: 48),
          ),
          const SizedBox(height: 24),
          _running
              ? ElevatedButton.icon(
                  onPressed: _stop,
                  icon: const Icon(Icons.stop),
                  label: const Text('Stop'),
                )
              : ElevatedButton.icon(
                  onPressed: _start,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Start'),
                ),
        ],
      ),
    );
  }
}

class StatsPage extends StatelessWidget {
  final List<int> sessions;
  const StatsPage({required this.sessions, super.key});

  @override
  Widget build(BuildContext context) {
    final totalSeconds = sessions.fold<int>(0, (a, b) => a + b);
    final totalMinutes = totalSeconds ~/ 60;
    final remainingSeconds = totalSeconds % 60;
    return Scaffold(
      appBar: AppBar(title: const Text('Stats')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              'Total time: ${totalMinutes}m ${remainingSeconds}s',
              style: const TextStyle(fontSize: 24),
            ),
          ),
          const Divider(),
          Expanded(
            child: ListView.builder(
              itemCount: sessions.length,
              itemBuilder: (context, index) {
                final sec = sessions[index];
                final min = sec ~/ 60;
                final s = sec % 60;
                return ListTile(
                  title: Text('Session ${index + 1}: ${min}m ${s}s'),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class ExportPage extends StatelessWidget {
  final List<int> sessions;
  const ExportPage({required this.sessions, super.key});

  String _generateCsv() {
    final buffer = StringBuffer('Session,Minutes,Seconds\n');
    for (var i = 0; i < sessions.length; i++) {
      final sec = sessions[i];
      final min = sec ~/ 60;
      final s = sec % 60;
      buffer.writeln('${i + 1},$min,$s');
    }
    return buffer.toString();
  }

  @override
  Widget build(BuildContext context) {
    final csv = _generateCsv();
    return Scaffold(
      appBar: AppBar(title: const Text('Export')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            const Text('CSV Export', style: TextStyle(fontSize: 20)),
            const SizedBox(height: 12),
            Expanded(
              child: SingleChildScrollView(
                child: SelectableText(csv),
              ),
            ),
            ElevatedButton.icon(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: csv));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('CSV copied to clipboard')),
                );
              },
              icon: const Icon(Icons.copy),
              label: const Text('Copy to Clipboard'),
            ),
          ],
        ),
      ),
    );
  }
}
