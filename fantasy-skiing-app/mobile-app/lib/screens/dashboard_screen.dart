import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../widgets/country_flag.dart';
import '../widgets/position_badge.dart';
import '../widgets/status_badge.dart';

class DashboardScreen extends StatefulWidget {
  final int raceId;
  const DashboardScreen({super.key, required this.raceId});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  RaceDashboard? _dashboard;
  bool _loading = true;
  bool _autoRefresh = true;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _startAutoRefresh();
  }

  void _startAutoRefresh() {
    _timer?.cancel();
    if (_autoRefresh) {
      _timer = Timer.periodic(const Duration(seconds: 5), (_) => _load());
    }
  }

  Future<void> _load() async {
    try {
      final api = context.read<ApiService>();
      final dashboard = await api.getRaceDashboard(widget.raceId);
      if (mounted) {
        setState(() {
          _dashboard = dashboard;
          _loading = false;
        });
        // Stop auto-refresh when race finishes
        if (dashboard.race.isFinished) {
          _timer?.cancel();
        }
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _formatTime(double seconds) {
    if (seconds <= 0) return '--';
    final mins = seconds ~/ 60;
    final secs = (seconds % 60).toStringAsFixed(1);
    return '$mins:${secs.padLeft(4, '0')}';
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Live Dashboard')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final d = _dashboard;
    if (d == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Live Dashboard')),
        body: const Center(child: Text('Dashboard unavailable')),
      );
    }

    final maxCp = d.standings.isNotEmpty ? d.standings.first.currentCheckpoint : 0;
    final progressPct = d.race.numCheckpoints > 0
        ? maxCp / d.race.numCheckpoints
        : 0.0;

    return Scaffold(
      appBar: AppBar(
        title: Text(d.race.name),
        actions: [
          IconButton(
            icon: Icon(_autoRefresh ? Icons.pause_circle : Icons.play_circle),
            tooltip: _autoRefresh ? 'Pause auto-refresh' : 'Resume auto-refresh',
            onPressed: () {
              setState(() => _autoRefresh = !_autoRefresh);
              _startAutoRefresh();
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Race status card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        StatusBadge(status: d.race.status),
                        const Spacer(),
                        Text(
                          'CP $maxCp / ${d.race.numCheckpoints}',
                          style: TextStyle(
                            fontWeight: FontWeight.w600,
                            color: Colors.grey[700],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: LinearProgressIndicator(
                        value: progressPct,
                        minHeight: 10,
                        backgroundColor: Colors.grey[200],
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${(progressPct * 100).toStringAsFixed(0)}% complete',
                      style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                    ),
                  ],
                ),
              ),
            ),

            // Team summary
            if (d.team != null) ...[
              const SizedBox(height: 12),
              Card(
                color: theme.colorScheme.primaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              d.team!.name,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onPrimaryContainer,
                              ),
                            ),
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                '${d.teamTotalPoints.toStringAsFixed(0)}',
                                style: theme.textTheme.headlineSmall?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: theme.colorScheme.onPrimaryContainer,
                                ),
                              ),
                              Text('team pts',
                                  style: TextStyle(
                                      fontSize: 12,
                                      color: theme.colorScheme.onPrimaryContainer
                                          .withAlpha(180))),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: d.team!.members.map((m) {
                          return Chip(
                            avatar: CountryFlag(
                                country: m.skier.country, fontSize: 14),
                            label: Text(
                              '${m.skier.name}${m.isCaptain ? ' (C)' : ''} ${m.pointsEarned.toStringAsFixed(0)}pts',
                              style: const TextStyle(fontSize: 12),
                            ),
                            backgroundColor: m.isCaptain
                                ? const Color(0xFFFEF08A)
                                : null,
                            visualDensity: VisualDensity.compact,
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),
              ),
            ],

            const SizedBox(height: 16),

            // Standings
            Text(
              d.race.isFinished ? 'Final Standings' : 'Live Standings',
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),

            ...d.standings.map((s) {
              final isTeamMember = s.isOnTeam;
              return Card(
                color: s.isCaptain
                    ? const Color(0xFFFEFCE8)
                    : isTeamMember
                        ? theme.colorScheme.primaryContainer.withAlpha(100)
                        : null,
                margin: const EdgeInsets.only(bottom: 4),
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  child: Row(
                    children: [
                      PositionBadge(position: s.currentPosition, size: 28),
                      const SizedBox(width: 12),
                      CountryFlag(country: s.country, fontSize: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    s.skierName,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        fontSize: 14),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (s.isCaptain)
                                  Container(
                                    margin: const EdgeInsets.only(left: 4),
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 5, vertical: 1),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFFACC15),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: const Text('C',
                                        style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold)),
                                  ),
                                if (isTeamMember && !s.isCaptain)
                                  Container(
                                    margin: const EdgeInsets.only(left: 4),
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 5, vertical: 1),
                                    decoration: BoxDecoration(
                                      color: theme.colorScheme.primaryContainer,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text('Team',
                                        style: TextStyle(
                                            fontSize: 10,
                                            color: theme.colorScheme.primary)),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 2),
                            Text(
                              s.gapToLeader > 0
                                  ? '+${s.gapToLeader.toStringAsFixed(1)}s'
                                  : 'Leader',
                              style: TextStyle(
                                fontSize: 12,
                                color: s.gapToLeader > 0
                                    ? Colors.red[600]
                                    : Colors.green[700],
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            _formatTime(s.lastTimeSeconds),
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 13,
                              color: Colors.grey[700],
                            ),
                          ),
                          if (s.fantasyPoints > 0)
                            Text(
                              '${s.fantasyPoints.toStringAsFixed(0)} pts',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.green[700],
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            }),
          ],
        ),
      ),
      floatingActionButton: !d.race.isFinished
          ? FloatingActionButton.small(
              onPressed: () async {
                final api = context.read<ApiService>();
                await api.simulateCheckpoint(widget.raceId);
                _load();
              },
              tooltip: 'Advance race',
              child: const Icon(Icons.skip_next),
            )
          : null,
    );
  }
}
