import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../widgets/country_flag.dart';
import '../widgets/status_badge.dart';
import '../widgets/position_badge.dart';
import 'team_builder_screen.dart';
import 'betting_screen.dart';
import 'dashboard_screen.dart';

class RaceDetailScreen extends StatefulWidget {
  final int raceId;
  const RaceDetailScreen({super.key, required this.raceId});

  @override
  State<RaceDetailScreen> createState() => _RaceDetailScreenState();
}

class _RaceDetailScreenState extends State<RaceDetailScreen> {
  Race? _race;
  List<RaceEntry> _entries = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    try {
      final race = await api.getRace(widget.raceId);
      final entries = await api.getRaceEntries(widget.raceId);
      if (mounted) {
        setState(() {
          _race = race;
          _entries = entries;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _formatTime(double? seconds) {
    if (seconds == null) return '--';
    final mins = seconds ~/ 60;
    final secs = (seconds % 60).toStringAsFixed(1);
    return '$mins:${secs.padLeft(4, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Race Details')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_race == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Race Details')),
        body: const Center(child: Text('Race not found')),
      );
    }

    final race = _race!;
    final sorted = List<RaceEntry>.from(_entries)
      ..sort((a, b) {
        if (a.finalPosition != null && b.finalPosition != null) {
          return a.finalPosition!.compareTo(b.finalPosition!);
        }
        return a.bibNumber.compareTo(b.bibNumber);
      });

    return Scaffold(
      appBar: AppBar(title: Text(race.name)),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Race info card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        StatusBadge(status: race.status),
                        const Spacer(),
                        Text(race.technique.toUpperCase(),
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[500],
                              fontWeight: FontWeight.w600,
                            )),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(race.location,
                        style: TextStyle(color: Colors.grey[600])),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        _InfoChip(
                            icon: Icons.straighten, label: '${race.distanceKm}km'),
                        const SizedBox(width: 8),
                        _InfoChip(
                            icon: Icons.flag_outlined,
                            label: '${race.numCheckpoints} CPs'),
                        const SizedBox(width: 8),
                        _InfoChip(
                            icon: Icons.people_outline,
                            label: '${race.entryCount} skiers'),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 12),

            // Action buttons
            Row(
              children: [
                if (!race.isFinished) ...[
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              TeamBuilderScreen(raceId: race.id),
                        ),
                      ),
                      icon: const Icon(Icons.groups, size: 18),
                      label: const Text('Build Team'),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF15803D),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => BettingScreen(raceId: race.id),
                        ),
                      ),
                      icon: const Icon(Icons.casino, size: 18),
                      label: const Text('Place Bets'),
                    ),
                  ),
                ],
                if (race.isLive || race.isFinished) ...[
                  if (!race.isFinished) const SizedBox(width: 8),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => DashboardScreen(raceId: race.id),
                        ),
                      ),
                      icon: const Icon(Icons.dashboard, size: 18),
                      label: const Text('Dashboard'),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFFDC2626),
                      ),
                    ),
                  ),
                ],
              ],
            ),

            const SizedBox(height: 16),

            // Entries list
            Text(
              race.isFinished ? 'Final Results' : 'Start List',
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),

            ...sorted.map((entry) => Card(
                  margin: const EdgeInsets.only(bottom: 4),
                  child: ListTile(
                    leading: entry.finalPosition != null
                        ? PositionBadge(position: entry.finalPosition!)
                        : CircleAvatar(
                            backgroundColor: Colors.grey[200],
                            child: Text('${entry.bibNumber}',
                                style: const TextStyle(fontSize: 14)),
                          ),
                    title: Row(
                      children: [
                        CountryFlag(country: entry.skier.country, fontSize: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(entry.skier.name,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w600)),
                        ),
                      ],
                    ),
                    subtitle: Text(
                        '${entry.skier.specialty} | Rating: ${entry.skier.skillRating}'),
                    trailing: race.isFinished
                        ? Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                entry.dnf
                                    ? 'DNF'
                                    : _formatTime(entry.finalTimeSeconds),
                                style: TextStyle(
                                  fontFamily: 'monospace',
                                  color:
                                      entry.dnf ? Colors.red : Colors.grey[700],
                                ),
                              ),
                              Text('${entry.pointsEarned.toStringAsFixed(0)} pts',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.green[700],
                                    fontWeight: FontWeight.w600,
                                  )),
                            ],
                          )
                        : null,
                  ),
                )),
          ],
        ),
      ),
      // Simulate button for testing
      floatingActionButton: !race.isFinished
          ? FloatingActionButton.small(
              onPressed: () async {
                final api = context.read<ApiService>();
                await api.simulateCheckpoint(race.id);
                _load();
              },
              tooltip: 'Simulate checkpoint',
              child: const Icon(Icons.skip_next),
            )
          : null,
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _InfoChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey[600]),
          const SizedBox(width: 4),
          Text(label,
              style: TextStyle(fontSize: 13, color: Colors.grey[700])),
        ],
      ),
    );
  }
}
