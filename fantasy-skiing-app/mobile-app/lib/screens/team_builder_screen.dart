import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../widgets/country_flag.dart';
import 'dashboard_screen.dart';

class TeamBuilderScreen extends StatefulWidget {
  final int raceId;
  const TeamBuilderScreen({super.key, required this.raceId});

  @override
  State<TeamBuilderScreen> createState() => _TeamBuilderScreenState();
}

class _TeamBuilderScreenState extends State<TeamBuilderScreen> {
  static const maxTeamSize = 5;

  List<RaceEntry> _entries = [];
  final Set<int> _selected = {};
  int? _captainId;
  final _nameCtrl = TextEditingController();
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    try {
      _entries = await api.getRaceEntries(widget.raceId);
    } catch (e) {
      _error = 'Failed to load entries';
    }
    if (mounted) setState(() => _loading = false);
  }

  void _toggleSkier(int id) {
    setState(() {
      if (_selected.contains(id)) {
        _selected.remove(id);
        if (_captainId == id) {
          _captainId = _selected.isNotEmpty ? _selected.first : null;
        }
      } else if (_selected.length < maxTeamSize) {
        _selected.add(id);
        _captainId ??= id;
      }
    });
  }

  Future<void> _submit() async {
    if (_nameCtrl.text.trim().isEmpty) {
      setState(() => _error = 'Enter a team name');
      return;
    }
    if (_selected.isEmpty) {
      setState(() => _error = 'Select at least one skier');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final api = context.read<ApiService>();
      await api.createTeam(
        raceId: widget.raceId,
        name: _nameCtrl.text.trim(),
        skierIds: _selected.toList(),
        captainId: _captainId!,
      );
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => DashboardScreen(raceId: widget.raceId),
          ),
        );
      }
    } catch (e) {
      setState(() => _error = e.toString().contains('already')
          ? 'You already have a team for this race'
          : 'Failed to create team');
    }

    if (mounted) setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Build Your Team'),
        actions: [
          if (_selected.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilledButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Confirm'),
              ),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Team name & selected summary
                Container(
                  color: theme.colorScheme.surfaceContainerHighest,
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      TextField(
                        controller: _nameCtrl,
                        decoration: const InputDecoration(
                          labelText: 'Team Name',
                          hintText: 'e.g. Nordic Thunder',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Selected: ${_selected.length}/$maxTeamSize | Tap skier chip to make captain',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                      ),
                      if (_selected.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: _selected.map((id) {
                            final entry =
                                _entries.firstWhere((e) => e.skier.id == id);
                            return GestureDetector(
                              onTap: () =>
                                  setState(() => _captainId = id),
                              child: Chip(
                                avatar: CountryFlag(
                                    country: entry.skier.country, fontSize: 14),
                                label: Text(
                                  entry.skier.name,
                                  style: const TextStyle(fontSize: 12),
                                ),
                                deleteIcon:
                                    const Icon(Icons.close, size: 16),
                                onDeleted: () => _toggleSkier(id),
                                backgroundColor: _captainId == id
                                    ? const Color(0xFFFEF08A)
                                    : null,
                                side: _captainId == id
                                    ? const BorderSide(
                                        color: Color(0xFFFACC15), width: 2)
                                    : null,
                                visualDensity: VisualDensity.compact,
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                      if (_error != null) ...[
                        const SizedBox(height: 8),
                        Text(_error!,
                            style: TextStyle(
                                color: Colors.red[700], fontSize: 13)),
                      ],
                    ],
                  ),
                ),

                // Skier list
                Expanded(
                  child: ListView.builder(
                    itemCount: _entries.length,
                    itemBuilder: (context, index) {
                      final entry = _entries[index];
                      final isSelected = _selected.contains(entry.skier.id);
                      final isFull =
                          _selected.length >= maxTeamSize && !isSelected;

                      return ListTile(
                        onTap: isFull ? null : () => _toggleSkier(entry.skier.id),
                        leading: Checkbox(
                          value: isSelected,
                          onChanged: isFull && !isSelected
                              ? null
                              : (_) => _toggleSkier(entry.skier.id),
                        ),
                        title: Row(
                          children: [
                            CountryFlag(
                                country: entry.skier.country, fontSize: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                entry.skier.name,
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  color: isFull
                                      ? Colors.grey[400]
                                      : Colors.grey[900],
                                ),
                              ),
                            ),
                          ],
                        ),
                        subtitle: Text(
                          'Bib #${entry.bibNumber} | ${entry.skier.specialty} | ${entry.skier.skillRating}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        trailing: SizedBox(
                          width: 60,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Expanded(
                                child: ClipRRect(
                                  borderRadius: BorderRadius.circular(3),
                                  child: LinearProgressIndicator(
                                    value: entry.skier.skillRating / 100,
                                    minHeight: 6,
                                    backgroundColor: Colors.grey[200],
                                  ),
                                ),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                '${entry.skier.skillRating.toStringAsFixed(0)}',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey[600],
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ),
                        ),
                        tileColor:
                            isSelected ? theme.colorScheme.primaryContainer.withAlpha(60) : null,
                      );
                    },
                  ),
                ),
              ],
            ),
    );
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }
}
