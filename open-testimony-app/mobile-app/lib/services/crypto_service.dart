import 'dart:convert';
import 'dart:math';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';

/// Service for handling cryptographic operations
/// MVP version: Uses HMAC-SHA256 for signing (simpler than ECDSA)
/// TODO: Upgrade to hardware-backed ECDSA in production
class CryptoService {
  static const _storage = FlutterSecureStorage();
  static const _deviceIdKey = 'device_id';
  static const _signingKeyKey = 'signing_key';
  
  final uuid = const Uuid();

  /// Initialize crypto keys on first launch
  Future<void> initialize() async {
    try {
      String? deviceId = await _storage.read(key: _deviceIdKey);
      
      if (deviceId == null) {
        print('🔑 First launch - generating keys...');
        // First launch - generate keys
        deviceId = uuid.v4();
        await _generateAndStoreKeys(deviceId);
        print('✅ Keys generated successfully for device: $deviceId');
      } else {
        print('✅ Device already initialized: $deviceId');
        
        // Verify keys exist
        final signingKey = await _storage.read(key: _signingKeyKey);
        if (signingKey == null) {
          print('⚠️  Keys missing, regenerating...');
          await _generateAndStoreKeys(deviceId);
        }
      }
    } catch (e) {
      print('❌ Crypto initialization error: $e');
      rethrow;
    }
  }

  /// Generate signing key and store securely
  Future<void> _generateAndStoreKeys(String deviceId) async {
    try {
      // Generate a random 256-bit key for HMAC signing
      final random = Random.secure();
      final keyBytes = List<int>.generate(32, (_) => random.nextInt(256));
      final keyB64 = base64.encode(keyBytes);
      
      print('📝 Storing keys for device: $deviceId');
      
      // Store in secure storage
      await _storage.write(key: _deviceIdKey, value: deviceId);
      await _storage.write(key: _signingKeyKey, value: keyB64);
      
      // Verify storage
      final storedDeviceId = await _storage.read(key: _deviceIdKey);
      final storedKey = await _storage.read(key: _signingKeyKey);
      
      if (storedDeviceId == null || storedKey == null) {
        throw Exception('Failed to store keys in secure storage');
      }
      
      print('✅ Keys stored and verified');
    } catch (e) {
      print('❌ Key generation error: $e');
      rethrow;
    }
  }

  /// Get device ID
  Future<String?> getDeviceId() async {
    return await _storage.read(key: _deviceIdKey);
  }

  /// Get public key (for MVP, we use device ID as identifier)
  Future<String?> getPublicKeyPem() async {
    final deviceId = await getDeviceId();
    if (deviceId == null) return null;
    
    // Return a simple identifier for the MVP
    // In production, this would be the actual ECDSA public key
    final publicKeyData = 'DEVICE:$deviceId';
    final publicKeyB64 = base64.encode(utf8.encode(publicKeyData));
    return '-----BEGIN PUBLIC KEY-----\n$publicKeyB64\n-----END PUBLIC KEY-----';
  }

  /// Sign data using HMAC-SHA256
  /// In production, this would use hardware-backed ECDSA
  Future<String> signData(String data) async {
    final keyB64 = await _storage.read(key: _signingKeyKey);
    if (keyB64 == null) {
      throw Exception('Signing key not found');
    }
    
    try {
      final keyBytes = base64.decode(keyB64);
      final dataBytes = utf8.encode(data);
      
      // Create HMAC-SHA256 signature
      final hmac = Hmac(sha256, keyBytes);
      final digest = hmac.convert(dataBytes);
      
      // Return base64 encoded signature
      return base64.encode(digest.bytes);
    } catch (e) {
      print('Error signing data: $e');
      rethrow;
    }
  }
}
