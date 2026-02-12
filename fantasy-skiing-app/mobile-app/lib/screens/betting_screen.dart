import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../widgets/country_flag.dart';

class BettingScreen extends StatefulWidget {
  final int raceId;
  const BettingScreen({super.key, required this.raceId});

  @override
  State<BettingScreen> createState() => _BettingScreenState();
}

class _BettingScreenState extends State<BettingScreen> {
  List<SkierOdds> _odds = [];
  bool _loading = true;
  String _betType = 'winner';
  int? _selectedSkierId;
  double _amount = 100;
  final _amountCtrl = TextEditingController(text: '100');
  String? _error;
  String? _success;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    try {
      _odds = await api.getRaceOdds(widget.raceId);
    } catch (e) {
      _error = 'Failed to load odds';
    }
    if (mounted) setState(() => _loading = false);
  }

  SkierOdds? get _selectedOdds =>
      _selectedSkierId != null
          ? _odds.cast<SkierOdds?>().firstWhere(
              (o) => o?.skier.id == _selectedSkierId,
              orElse: () => null)
          : null;

  double get _currentOdds {
    final o = _selectedOdds;
    if (o == null) return 0;
    return _betType == 'winner' ? o.winOdds : o.podiumOdds;
  }

  Future<void> _placeBet() async {
    setState(() {
      _error = null;
      _success = null;
    });

    if (_selectedSkierId == null) {
      setState(() => _error = 'Select a skier');
      return;
    }

    final auth = context.read<AuthService>();
    if (_amount > auth.balance) {
      setState(() => _error = 'Insufficient balance');
      return;
    }

    try {
      final api = context.read<ApiService>();
      final bet = await api.placeBet(
        raceId: widget.raceId,
        betType: _betType,
        skierId: _selectedSkierId!,
        amount: _amount,
      );
      auth.updateBalance(auth.balance - _amount);
      setState(() {
        _success =
            'Bet placed on ${bet.skierName} at ${bet.odds.toStringAsFixed(2)}x!';
        _selectedSkierId = null;
      });
    } catch (e) {
      setState(() => _error = 'Failed to place bet');
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final auth = context.watch<AuthService>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Place Bets'),
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Text(
                '${auth.balance.toStringAsFixed(0)} coins',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Bet config
                Container(
                  color: theme.colorScheme.surfaceContainerHighest,
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Bet type toggle
                      Row(
                        children: [
                          Expanded(
                            child: SegmentedButton<String>(
                              segments: const [
                                ButtonSegment(
                                    value: 'winner', label: Text('Win')),
                                ButtonSegment(
                                    value: 'podium', label: Text('Podium')),
                              ],
                              selected: {_betType},
                              onSelectionChanged: (s) =>
                                  setState(() => _betType = s.first),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // Amount
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _amountCtrl,
                              keyboardType: TextInputType.number,
                              decoration: const InputDecoration(
                                labelText: 'Amount',
                                border: OutlineInputBorder(),
                                isDense: true,
                                suffixText: 'coins',
                              ),
                              onChanged: (v) {
                                _amount = double.tryParse(v) ?? 0;
                              },
                            ),
                          ),
                          const SizedBox(width: 8),
                          for (final preset in [50, 100, 500])
                            Padding(
                              padding: const EdgeInsets.only(left: 4),
                              child: ActionChip(
                                label: Text('$preset'),
                                onPressed: () {
                                  _amount = preset.toDouble();
                                  _amountCtrl.text = '$preset';
                                  setState(() {});
                                },
                                visualDensity: VisualDensity.compact,
                              ),
                            ),
                        ],
                      ),

                      // Summary & place bet button
                      if (_selectedOdds != null) ...[
                        const SizedBox(height: 12),
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                          _selectedOdds!.skier.name,
                                          style: const TextStyle(
                                              fontWeight: FontWeight.w600)),
                                      Text(
                                          '${_betType.toUpperCase()} @ ${_currentOdds.toStringAsFixed(2)}x',
                                          style: TextStyle(
                                              fontSize: 12,
                                              color: Colors.grey[600])),
                                      Text(
                                        'Payout: ${(_amount * _currentOdds).toStringAsFixed(0)} coins',
                                        style: TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.green[700],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                FilledButton(
                                  onPressed: _placeBet,
                                  child: const Text('Place Bet'),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],

                      if (_error != null) ...[
                        const SizedBox(height: 8),
                        Text(_error!,
                            style: TextStyle(
                                color: Colors.red[700], fontSize: 13)),
                      ],
                      if (_success != null) ...[
                        const SizedBox(height: 8),
                        Text(_success!,
                            style: TextStyle(
                                color: Colors.green[700], fontSize: 13)),
                      ],
                    ],
                  ),
                ),

                // Odds list
                Expanded(
                  child: ListView.builder(
                    itemCount: _odds.length,
                    itemBuilder: (context, index) {
                      final o = _odds[index];
                      final isSelected = _selectedSkierId == o.skier.id;
                      return ListTile(
                        onTap: () =>
                            setState(() => _selectedSkierId = o.skier.id),
                        selected: isSelected,
                        selectedTileColor:
                            theme.colorScheme.primaryContainer.withAlpha(80),
                        leading: CountryFlag(
                            country: o.skier.country, fontSize: 24),
                        title: Text(o.skier.name,
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text(
                          '${o.skier.specialty} | Rating: ${o.skier.skillRating}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  '${o.winOdds.toStringAsFixed(2)}x',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: _betType == 'winner'
                                        ? theme.colorScheme.primary
                                        : Colors.grey[400],
                                  ),
                                ),
                                Text('Win',
                                    style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.grey[500])),
                              ],
                            ),
                            const SizedBox(width: 16),
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  '${o.podiumOdds.toStringAsFixed(2)}x',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: _betType == 'podium'
                                        ? theme.colorScheme.primary
                                        : Colors.grey[400],
                                  ),
                                ),
                                Text('Podium',
                                    style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.grey[500])),
                              ],
                            ),
                          ],
                        ),
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
    _amountCtrl.dispose();
    super.dispose();
  }
}
