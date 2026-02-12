import 'package:dio/dio.dart';
import '../models/models.dart';
import 'auth_service.dart';

class ApiService {
  // Default to localhost for development; update for production
  static const String baseUrl = 'http://10.0.2.2:8001'; // Android emulator
  // static const String baseUrl = 'http://localhost:8001'; // iOS simulator

  final AuthService _auth;
  late final Dio _dio;

  ApiService(this._auth) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_auth.token != null) {
          options.headers['Authorization'] = 'Bearer ${_auth.token}';
        }
        handler.next(options);
      },
    ));
  }

  // --- Auth ---
  Future<Map<String, dynamic>> login(String username, String password) async {
    final res = await _dio.post('/auth/login', data: {
      'username': username,
      'password': password,
    });
    return res.data;
  }

  Future<Map<String, dynamic>> register(
      String username, String email, String password,
      {String? displayName}) async {
    final res = await _dio.post('/auth/register', data: {
      'username': username,
      'email': email,
      'password': password,
      if (displayName != null) 'display_name': displayName,
    });
    return res.data;
  }

  // --- Races ---
  Future<List<Race>> getRaces({String? status}) async {
    final res = await _dio.get('/races',
        queryParameters: status != null ? {'status': status} : null);
    return (res.data as List).map((r) => Race.fromJson(r)).toList();
  }

  Future<Race> getRace(int id) async {
    final res = await _dio.get('/races/$id');
    return Race.fromJson(res.data);
  }

  Future<List<RaceEntry>> getRaceEntries(int raceId) async {
    final res = await _dio.get('/races/$raceId/entries');
    return (res.data as List).map((e) => RaceEntry.fromJson(e)).toList();
  }

  Future<List<SkierOdds>> getRaceOdds(int raceId) async {
    final res = await _dio.get('/races/$raceId/odds');
    return (res.data as List).map((o) => SkierOdds.fromJson(o)).toList();
  }

  Future<RaceDashboard> getRaceDashboard(int raceId) async {
    final res = await _dio.get('/races/$raceId/dashboard');
    return RaceDashboard.fromJson(res.data);
  }

  // --- Teams ---
  Future<FantasyTeam> createTeam({
    required int raceId,
    required String name,
    required List<int> skierIds,
    required int captainId,
  }) async {
    final res = await _dio.post('/teams', data: {
      'race_id': raceId,
      'name': name,
      'skier_ids': skierIds,
      'captain_id': captainId,
    });
    return FantasyTeam.fromJson(res.data);
  }

  Future<List<FantasyTeam>> getMyTeams() async {
    final res = await _dio.get('/teams');
    return (res.data as List).map((t) => FantasyTeam.fromJson(t)).toList();
  }

  // --- Bets ---
  Future<Bet> placeBet({
    required int raceId,
    required String betType,
    required int skierId,
    required double amount,
  }) async {
    final res = await _dio.post('/bets', data: {
      'race_id': raceId,
      'bet_type': betType,
      'skier_id': skierId,
      'amount': amount,
    });
    return Bet.fromJson(res.data);
  }

  Future<List<Bet>> getMyBets() async {
    final res = await _dio.get('/bets');
    return (res.data as List).map((b) => Bet.fromJson(b)).toList();
  }

  // --- Leaderboard ---
  Future<List<LeaderboardEntry>> getLeaderboard() async {
    final res = await _dio.get('/leaderboard');
    return (res.data as List)
        .map((e) => LeaderboardEntry.fromJson(e))
        .toList();
  }

  // --- Admin / Simulation ---
  Future<void> simulateCheckpoint(int raceId) async {
    await _dio.post('/admin/simulate/$raceId');
  }

  // --- Skiers ---
  Future<List<Skier>> getSkiers() async {
    final res = await _dio.get('/skiers');
    return (res.data as List).map((s) => Skier.fromJson(s)).toList();
  }
}
