import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../widgets/status_badge.dart';
import 'race_detail_screen.dart';

class RacesScreen extends StatefulWidget {
  const RacesScreen({super.key});

  @override
  State<RacesScreen> createState() => _RacesScreenState();
}

class _RacesScreenState extends State<RacesScreen> {
  List<Race> _races = [];
  bool _loading = true;
  String? _filter;

  @override
  void initState() {
    super.initState();
    _loadRaces();
  }

  Future<void> _loadRaces() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();
      _races = await api.getRaces(status: _filter);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load races: $e')),
        );
      }
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Filter chips
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              _FilterChip(
                label: 'All',
                selected: _filter == null,
                onTap: () {
                  _filter = null;
                  _loadRaces();
                },
              ),
              _FilterChip(
                label: 'Live',
                selected: _filter == 'live',
                onTap: () {
                  _filter = 'live';
                  _loadRaces();
                },
              ),
              _FilterChip(
                label: 'Upcoming',
                selected: _filter == 'upcoming',
                onTap: () {
                  _filter = 'upcoming';
                  _loadRaces();
                },
              ),
              _FilterChip(
                label: 'Finished',
                selected: _filter == 'finished',
                onTap: () {
                  _filter = 'finished';
                  _loadRaces();
                },
              ),
            ],
          ),
        ),

        // Race list
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _races.isEmpty
                  ? const Center(child: Text('No races found'))
                  : RefreshIndicator(
                      onRefresh: _loadRaces,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _races.length,
                        itemBuilder: (context, index) {
                          final race = _races[index];
                          return _RaceCard(
                            race: race,
                            onTap: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => RaceDetailScreen(raceId: race.id),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
        ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onTap(),
        selectedColor: theme.colorScheme.primaryContainer,
      ),
    );
  }
}

class _RaceCard extends StatelessWidget {
  final Race race;
  final VoidCallback onTap;

  const _RaceCard({required this.race, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  StatusBadge(status: race.status),
                  Text(
                    race.technique.toUpperCase(),
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey[500],
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                race.name,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                race.location,
                style: TextStyle(color: Colors.grey[600], fontSize: 14),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Text(
                    '${race.distanceKm}km',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    race.raceType,
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                  const Spacer(),
                  Text(
                    '${race.entryCount} skiers',
                    style: TextStyle(color: Colors.grey[500], fontSize: 13),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
