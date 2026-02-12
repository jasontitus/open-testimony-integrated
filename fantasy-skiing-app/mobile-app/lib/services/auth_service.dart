import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService extends ChangeNotifier {
  final _storage = const FlutterSecureStorage();
  String? _token;
  String? _username;
  double _balance = 0;
  int? _userId;
  bool _isLoading = true;

  String? get token => _token;
  String? get username => _username;
  double get balance => _balance;
  int? get userId => _userId;
  bool get isAuthenticated => _token != null;
  bool get isLoading => _isLoading;

  AuthService() {
    _loadToken();
  }

  Future<void> _loadToken() async {
    _token = await _storage.read(key: 'token');
    _username = await _storage.read(key: 'username');
    final balStr = await _storage.read(key: 'balance');
    _balance = double.tryParse(balStr ?? '') ?? 0;
    final idStr = await _storage.read(key: 'userId');
    _userId = int.tryParse(idStr ?? '');
    _isLoading = false;
    notifyListeners();
  }

  Future<void> setAuth({
    required String token,
    required String username,
    required double balance,
    required int userId,
  }) async {
    _token = token;
    _username = username;
    _balance = balance;
    _userId = userId;
    await _storage.write(key: 'token', value: token);
    await _storage.write(key: 'username', value: username);
    await _storage.write(key: 'balance', value: balance.toString());
    await _storage.write(key: 'userId', value: userId.toString());
    notifyListeners();
  }

  void updateBalance(double newBalance) {
    _balance = newBalance;
    _storage.write(key: 'balance', value: newBalance.toString());
    notifyListeners();
  }

  Future<void> logout() async {
    _token = null;
    _username = null;
    _balance = 0;
    _userId = null;
    await _storage.deleteAll();
    notifyListeners();
  }
}
