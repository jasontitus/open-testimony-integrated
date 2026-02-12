import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../widgets/country_flag.dart';
import '../widgets/status_badge.dart';
import 'dashboard_screen.dart';

class MyTeamsScreen extends StatefulWidget {
  const MyTeamsScreen({super.key});

  @override
  State<MyTeamsScreen> createState() => _MyTeamsScreenState();
}

class _MyTeamsScreenState extends State<MyTeamsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  List<FantasyTeam> _teams = [];
  List<Bet> _bets = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    try {
      _teams = await api.getMyTeams();
      _bets = await api.getMyBets();
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      children: [
        TabBar(
          controller: _tabCtrl,
          tabs: [
            Tab(text: 'Teams (${_teams.length})'),
            Tab(text: 'Bets (${_bets.length})'),
          ],
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : TabBarView(
                  controller: _tabCtrl,
                  children: [
                    // Teams tab
                    _teams.isEmpty
                        ? const Center(
                            child: Text('No teams yet.\nBrowse races to build your first team!',
                                textAlign: TextAlign.center))
                        : RefreshIndicator(
                            onRefresh: _load,
                            child: ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: _teams.length,
                              itemBuilder: (context, index) {
                                final team = _teams[index];
                                return Card(
                                  margin: const EdgeInsets.only(bottom: 12),
                                  child: InkWell(
                                    borderRadius: BorderRadius.circular(16),
                                    onTap: () => Navigator.push(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) => DashboardScreen(
                                            raceId: team.raceId),
                                      ),
                                    ),
                                    child: Padding(
                                      padding: const EdgeInsets.all(16),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Expanded(
                                                child: Text(
                                                  team.name,
                                                  style: theme
                                                      .textTheme.titleMedium
                                                      ?.copyWith(
                                                          fontWeight:
                                                              FontWeight.bold),
                                                ),
                                              ),
                                              Text(
                                                '${team.totalPoints.toStringAsFixed(0)} pts',
                                                style: TextStyle(
                                                  fontSize: 18,
                                                  fontWeight: FontWeight.bold,
                                                  color: Colors.green[700],
                                                ),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            'Race #${team.raceId}',
                                            style: TextStyle(
                                                fontSize: 12,
                                                color: Colors.grey[500]),
                                          ),
                                          const SizedBox(height: 8),
                                          Wrap(
                                            spacing: 6,
                                            runSpacing: 4,
                                            children:
                                                team.members.map((m) {
                                              return Chip(
                                                avatar: CountryFlag(
                                                    country: m.skier.country,
                                                    fontSize: 12),
                                                label: Text(
                                                  '${m.skier.name}${m.isCaptain ? ' (C)' : ''} ${m.pointsEarned.toStringAsFixed(0)}pts',
                                                  style: const TextStyle(
                                                      fontSize: 11),
                                                ),
                                                backgroundColor: m.isCaptain
                                                    ? const Color(0xFFFEF08A)
                                                    : null,
                                                visualDensity:
                                                    VisualDensity.compact,
                                              );
                                            }).toList(),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),

                    // Bets tab
                    _bets.isEmpty
                        ? const Center(
                            child: Text('No bets placed yet.\nBrowse races to start betting!',
                                textAlign: TextAlign.center))
                        : RefreshIndicator(
                            onRefresh: _load,
                            child: ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: _bets.length,
                              itemBuilder: (context, index) {
                                final bet = _bets[index];
                                return Card(
                                  margin: const EdgeInsets.only(bottom: 8),
                                  child: ListTile(
                                    title: Text(
                                      bet.skierName,
                                      style: const TextStyle(
                                          fontWeight: FontWeight.w600),
                                    ),
                                    subtitle: Text(
                                      '${bet.betType.toUpperCase()} | ${bet.amount.toStringAsFixed(0)} coins @ ${bet.odds.toStringAsFixed(2)}x',
                                      style: const TextStyle(fontSize: 12),
                                    ),
                                    trailing: Column(
                                      mainAxisAlignment:
                                          MainAxisAlignment.center,
                                      crossAxisAlignment:
                                          CrossAxisAlignment.end,
                                      children: [
                                        StatusBadge(status: bet.status),
                                        const SizedBox(height: 4),
                                        if (bet.status == 'won')
                                          Text(
                                            '+${bet.payout.toStringAsFixed(0)}',
                                            style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              color: Colors.green[700],
                                            ),
                                          ),
                                        if (bet.status == 'lost')
                                          Text(
                                            '-${bet.amount.toStringAsFixed(0)}',
                                            style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              color: Colors.red[600],
                                            ),
                                          ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                  ],
                ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }
}
