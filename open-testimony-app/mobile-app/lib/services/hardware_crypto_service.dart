import 'dart:convert';
import 'dart:math';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';

/// Hardware-backed cryptographic service using platform channels.
/// Uses Secure Enclave (iOS) / StrongBox (Android) for ECDSA P-256.
/// Falls back to software HMAC-SHA256 if hardware is unavailable.
class HardwareCryptoService {
  static const _channel = MethodChannel('com.opentestimony/crypto');
  static const _storage = FlutterSecureStorage();
  static const _deviceIdKey = 'device_id';
  static const _signingKeyKey = 'signing_key';
  static const _cryptoVersionKey = 'crypto_version';

  final uuid = const Uuid();

  bool _hardwareAvailable = false;
  String _cryptoVersion = 'hmac';

  bool get isHardwareBacked => _hardwareAvailable;
  String get cryptoVersion => _cryptoVersion;

  /// Initialize crypto: try hardware ECDSA, fall back to HMAC
  Future<void> initialize() async {
    try {
      String? deviceId = await _storage.read(key: _deviceIdKey);
      final storedVersion = await _storage.read(key: _cryptoVersionKey);

      // Check hardware availability
      _hardwareAvailable = await _checkHardwareAvailable();
      print('Hardware crypto available: $_hardwareAvailable');

      if (deviceId == null) {
        // First launch
        print('First launch - generating keys...');
        deviceId = uuid.v4();
        await _storage.write(key: _deviceIdKey, value: deviceId);

        if (_hardwareAvailable) {
          await _initHardwareKeys(deviceId);
          _cryptoVersion = 'ecdsa';
        } else {
          await _initSoftwareKeys(deviceId);
          _cryptoVersion = 'hmac';
        }
        await _storage.write(key: _cryptoVersionKey, value: _cryptoVersion);
        print('Keys generated ($_cryptoVersion) for device: $deviceId');
      } else {
        _cryptoVersion = storedVersion ?? 'hmac';
        print('Device initialized: $deviceId (crypto: $_cryptoVersion)');

        // Check if we can upgrade from HMAC to ECDSA
        if (_cryptoVersion == 'hmac' && _hardwareAvailable) {
          print('Hardware now available - upgrading to ECDSA...');
          await _initHardwareKeys(deviceId);
          _cryptoVersion = 'ecdsa';
          await _storage.write(key: _cryptoVersionKey, value: 'ecdsa');
          print('Upgraded to ECDSA');
        }

        // Verify keys exist
        if (_cryptoVersion == 'hmac') {
          final signingKey = await _storage.read(key: _signingKeyKey);
          if (signingKey == null) {
            print('HMAC keys missing, regenerating...');
            await _initSoftwareKeys(deviceId);
          }
        }
      }
    } catch (e) {
      print('Crypto initialization error: $e');
      rethrow;
    }
  }

  Future<bool> _checkHardwareAvailable() async {
    try {
      final result = await _channel.invokeMethod<bool>('isHardwareBacked');
      return result ?? false;
    } on MissingPluginException {
      return false;
    } catch (e) {
      print('Hardware check failed: $e');
      return false;
    }
  }

  Future<void> _initHardwareKeys(String deviceId) async {
    try {
      await _channel.invokeMethod('generateKey', {'deviceId': deviceId});
    } catch (e) {
      print('Hardware key generation failed, falling back to HMAC: $e');
      _hardwareAvailable = false;
      _cryptoVersion = 'hmac';
      await _initSoftwareKeys(deviceId);
    }
  }

  Future<void> _initSoftwareKeys(String deviceId) async {
    final random = Random.secure();
    final keyBytes = List<int>.generate(32, (_) => random.nextInt(256));
    final keyB64 = base64.encode(keyBytes);
    await _storage.write(key: _signingKeyKey, value: keyB64);
  }

  /// Get device ID
  Future<String?> getDeviceId() async {
    return await _storage.read(key: _deviceIdKey);
  }

  /// Get public key PEM
  Future<String?> getPublicKeyPem() async {
    if (_cryptoVersion == 'ecdsa' && _hardwareAvailable) {
      try {
        final pem = await _channel.invokeMethod<String>('getPublicKey');
        return pem;
      } catch (e) {
        print('Error getting hardware public key: $e');
        // Fall through to HMAC format
      }
    }

    // HMAC MVP format
    final deviceId = await getDeviceId();
    if (deviceId == null) return null;
    final publicKeyData = 'DEVICE:$deviceId';
    final publicKeyB64 = base64.encode(utf8.encode(publicKeyData));
    return '-----BEGIN PUBLIC KEY-----\n$publicKeyB64\n-----END PUBLIC KEY-----';
  }

  /// Sign data
  Future<String> signData(String data) async {
    if (_cryptoVersion == 'ecdsa' && _hardwareAvailable) {
      try {
        final signature = await _channel.invokeMethod<String>('sign', {'data': data});
        if (signature != null) return signature;
      } catch (e) {
        print('Hardware signing failed, falling back to HMAC: $e');
      }
    }

    // HMAC fallback
    final keyB64 = await _storage.read(key: _signingKeyKey);
    if (keyB64 == null) {
      throw Exception('Signing key not found');
    }

    final keyBytes = base64.decode(keyB64);
    final dataBytes = utf8.encode(data);
    final hmac = Hmac(sha256, keyBytes);
    final digest = hmac.convert(dataBytes);
    return base64.encode(digest.bytes);
  }

  /// Get crypto version string for display
  String getCryptoVersionDisplay() {
    if (_cryptoVersion == 'ecdsa') {
      return 'Hardware ECDSA (P-256)';
    }
    return 'Software HMAC-SHA256';
  }
}
