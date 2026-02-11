import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'video_service.dart';

/// Preset server configurations.
/// Add new regional servers here as needed.
class ServerPreset {
  final String label;
  final String url;
  const ServerPreset(this.label, this.url);
}

const List<ServerPreset> serverPresets = [
  ServerPreset('Open Testimony (Main)', 'https://opentestimony.ngrok.app/api'),
  // Add regional servers here, e.g.:
  // ServerPreset('EU Server', 'https://eu.opentestimony.org/api'),
  // ServerPreset('Local Dev', 'http://192.168.1.100:18080/api'),
];

const String _serverUrlStorageKey = 'server_url';

/// Service for uploading videos to the backend
class UploadService {
  static String _baseUrl = serverPresets.first.url;
  static String get baseUrl => _baseUrl;

  final Dio _dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(minutes: 5),
    sendTimeout: const Duration(minutes: 5),
  ));

  /// Load saved server URL from secure storage.
  /// Call once at app startup.
  Future<void> init() async {
    const storage = FlutterSecureStorage();
    final saved = await storage.read(key: _serverUrlStorageKey);
    if (saved != null && saved.isNotEmpty) {
      _baseUrl = saved;
    }
  }

  /// Update and persist the server URL.
  Future<void> setServerUrl(String url) async {
    _baseUrl = url;
    const storage = FlutterSecureStorage();
    await storage.write(key: _serverUrlStorageKey, value: url);
  }

  /// Register device with backend
  Future<bool> registerDevice(
    String deviceId,
    String publicKeyPem, {
    String cryptoVersion = 'hmac',
  }) async {
    try {
      print('Attempting to register device: $deviceId (crypto: $cryptoVersion)');
      final response = await _dio.post(
        '$baseUrl/register-device',
        data: FormData.fromMap({
          'device_id': deviceId,
          'public_key_pem': publicKeyPem,
          'device_info': Platform.operatingSystem,
          'crypto_version': cryptoVersion,
        }),
      );

      if (response.statusCode == 200) {
        print('Device registration successful');
        return true;
      } else {
        print('Device registration returned status: ${response.statusCode}');
        return false;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 409) {
        print('Device already registered');
        return true;
      }
      print('Device registration error: ${e.message}');
      return false;
    } catch (e) {
      print('Unexpected error registering device: $e');
      return false;
    }
  }

  /// Calculate SHA-256 hash of file
  Future<String> calculateFileHash(File file) async {
    final bytes = await file.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// Upload video/photo with metadata.
  /// Retries up to [maxRetries] times with exponential backoff on network errors.
  /// [onProgress] callback receives a value from 0.0 to 1.0.
  Future<Map<String, dynamic>?> uploadMedia({
    required VideoRecord video,
    required String deviceId,
    required String publicKeyPem,
    required String signature,
    String? signedPayload,
    String? source,
    String? mediaType,
    Map<String, dynamic>? exifMetadata,
    void Function(double progress)? onProgress,
    int maxRetries = 3,
  }) async {
    final videoFile = File(video.filePath);

    if (!await videoFile.exists()) {
      print('Media file not found: ${video.filePath}');
      return null;
    }

    final effectiveSource = source ?? video.source;
    final effectiveMediaType = mediaType ?? video.mediaType;

    bool didReRegister = false;

    for (int attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        final payload = {
          'video_hash': video.fileHash,
          'timestamp': video.timestamp.toIso8601String(),
          'location': {
            'lat': video.latitude,
            'lon': video.longitude,
          },
          'incident_tags': video.tags,
          'source': effectiveSource,
          'media_type': effectiveMediaType,
        };

        if (exifMetadata != null) {
          payload['exif_metadata'] = exifMetadata;
        }

        final metadata = {
          'version': '1.0',
          'auth': {
            'device_id': deviceId,
            'public_key_pem': publicKeyPem,
          },
          'payload': payload,
          'signature': signature,
          if (signedPayload != null) 'signed_payload': signedPayload,
        };

        final extension = effectiveMediaType == 'photo' ? 'jpg' : 'mp4';
        final formData = FormData.fromMap({
          'video': await MultipartFile.fromFile(
            videoFile.path,
            filename: '${video.id}.$extension',
          ),
          'metadata': jsonEncode(metadata),
        });

        final response = await _dio.post(
          '$baseUrl/upload',
          data: formData,
          onSendProgress: (sent, total) {
            if (total > 0) {
              onProgress?.call(sent / total);
            }
          },
        );

        if (response.statusCode == 200) {
          return Map<String, dynamic>.from(response.data);
        }
        return null;
      } on DioException catch (e) {
        // 403 = device not registered — re-register once and retry immediately
        if (e.response?.statusCode == 403 && !didReRegister) {
          print('Upload failed: Device not registered. Re-registering...');
          didReRegister = true;
          final registered = await registerDevice(deviceId, publicKeyPem);
          if (registered) {
            continue; // retry immediately, don't count as a backoff attempt
          }
          return null;
        }

        // 4xx client errors (other than 403) — don't retry
        final statusCode = e.response?.statusCode;
        if (statusCode != null && statusCode >= 400 && statusCode < 500) {
          print('Upload failed with client error $statusCode, not retrying');
          return null;
        }

        // Network / server errors — retry with backoff
        if (attempt < maxRetries) {
          final delay = Duration(seconds: attempt * 2); // 2s, 4s, 6s
          print('Upload attempt $attempt failed (${e.type}), retrying in ${delay.inSeconds}s...');
          await Future.delayed(delay);
        } else {
          print('Upload failed after $maxRetries attempts: ${e.message}');
          return null;
        }
      } catch (e) {
        if (attempt < maxRetries) {
          final delay = Duration(seconds: attempt * 2);
          print('Upload attempt $attempt error: $e, retrying in ${delay.inSeconds}s...');
          await Future.delayed(delay);
        } else {
          print('Upload failed after $maxRetries attempts: $e');
          return null;
        }
      }
    }
    return null;
  }

  /// Legacy upload method for backward compatibility
  Future<bool> uploadVideo({
    required VideoRecord video,
    required String deviceId,
    required String publicKeyPem,
    required String signature,
  }) async {
    final result = await uploadMedia(
      video: video,
      deviceId: deviceId,
      publicKeyPem: publicKeyPem,
      signature: signature,
    );
    return result != null;
  }

  /// Update annotations on the server
  Future<bool> updateAnnotations({
    required String serverId,
    required String deviceId,
    String? category,
    String? locationDescription,
    String? notes,
    List<String>? tags,
  }) async {
    try {
      final data = <String, dynamic>{
        'device_id': deviceId,
        'category': category ?? '',
        'location_description': locationDescription,
        'notes': notes,
      };
      if (tags != null) {
        data['incident_tags'] = tags;
      }
      final response = await _dio.put(
        '$baseUrl/videos/$serverId/annotations',
        data: data,
      );
      return response.statusCode == 200;
    } catch (e) {
      print('Error updating annotations: $e');
      return false;
    }
  }

  /// Fetch available tags from server for autocomplete
  Future<List<String>> fetchTags() async {
    try {
      final response = await _dio.get('$baseUrl/tags');
      if (response.statusCode == 200) {
        return List<String>.from(response.data['all_tags'] ?? []);
      }
      return [];
    } catch (e) {
      print('Error fetching tags: $e');
      return [];
    }
  }

  /// Fetch video details from server
  Future<Map<String, dynamic>?> fetchVideoDetails(String serverId) async {
    try {
      final response = await _dio.get('$baseUrl/videos/$serverId');
      if (response.statusCode == 200) {
        return Map<String, dynamic>.from(response.data);
      }
      return null;
    } catch (e) {
      print('Error fetching video details: $e');
      return null;
    }
  }

  /// Get audit trail for a video
  Future<List<Map<String, dynamic>>> getVideoAuditTrail(String serverId) async {
    try {
      final response = await _dio.get('$baseUrl/videos/$serverId/audit');
      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(response.data['entries']);
      }
      return [];
    } catch (e) {
      print('Error fetching audit trail: $e');
      return [];
    }
  }

  /// Get list of videos from server
  Future<List<Map<String, dynamic>>> getVideos({
    String? deviceId,
    bool verifiedOnly = false,
  }) async {
    try {
      final queryParams = <String, dynamic>{};
      if (deviceId != null) queryParams['device_id'] = deviceId;
      if (verifiedOnly) queryParams['verified_only'] = 'true';

      final response = await _dio.get(
        '$baseUrl/videos',
        queryParameters: queryParams,
      );

      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(response.data['videos']);
      }
      return [];
    } catch (e) {
      print('Error fetching videos: $e');
      return [];
    }
  }
}
