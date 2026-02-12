import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../widgets/position_badge.dart';

class LeaderboardScreen extends StatefulWidget {
  const LeaderboardScreen({super.key});

  @override
  State<LeaderboardScreen> createState() => _LeaderboardScreenState();
}

class _LeaderboardScreenState extends State<LeaderboardScreen> {
  List<LeaderboardEntry> _entries = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    try {
      _entries = await api.getLeaderboard();
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final auth = context.watch<AuthService>();

    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Podium for top 3
          if (_entries.length >= 3) ...[
            SizedBox(
              height: 200,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  // 2nd place
                  Expanded(child: _PodiumColumn(entry: _entries[1], height: 120)),
                  const SizedBox(width: 8),
                  // 1st place
                  Expanded(child: _PodiumColumn(entry: _entries[0], height: 160)),
                  const SizedBox(width: 8),
                  // 3rd place
                  Expanded(child: _PodiumColumn(entry: _entries[2], height: 100)),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Full list
          ...List.generate(_entries.length, (i) {
            final e = _entries[i];
            final isMe = e.userId == auth.userId;
            return Card(
              color: isMe ? theme.colorScheme.primaryContainer.withAlpha(120) : null,
              margin: const EdgeInsets.only(bottom: 4),
              child: ListTile(
                leading: PositionBadge(position: e.rank, size: 28),
                title: Row(
                  children: [
                    Expanded(
                      child: Text(
                        e.displayName ?? e.username,
                        style: TextStyle(
                          fontWeight: isMe ? FontWeight.bold : FontWeight.w600,
                        ),
                      ),
                    ),
                    if (isMe)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primary,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text('YOU',
                            style: TextStyle(
                              fontSize: 10,
                              color: theme.colorScheme.onPrimary,
                              fontWeight: FontWeight.bold,
                            )),
                      ),
                  ],
                ),
                subtitle:
                    Text('${e.teamCount} teams', style: const TextStyle(fontSize: 12)),
                trailing: Text(
                  '${e.totalPoints.toStringAsFixed(0)} pts',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: Colors.green[700],
                  ),
                ),
              ),
            );
          }),

          if (_entries.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(40),
                child: Text('No players yet.\nBe the first to join!',
                    textAlign: TextAlign.center),
              ),
            ),
        ],
      ),
    );
  }
}

class _PodiumColumn extends StatelessWidget {
  final LeaderboardEntry entry;
  final double height;

  const _PodiumColumn({required this.entry, required this.height});

  Color get _color {
    switch (entry.rank) {
      case 1:
        return const Color(0xFFFACC15);
      case 2:
        return const Color(0xFFD1D5DB);
      case 3:
        return const Color(0xFFD97706);
      default:
        return const Color(0xFFE5E7EB);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Text(
          entry.displayName ?? entry.username,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 2),
        Text(
          '${entry.totalPoints.toStringAsFixed(0)} pts',
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.green[700],
          ),
        ),
        const SizedBox(height: 8),
        Container(
          height: height,
          decoration: BoxDecoration(
            color: _color,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
          ),
          alignment: Alignment.center,
          child: Text(
            '${entry.rank}',
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}
