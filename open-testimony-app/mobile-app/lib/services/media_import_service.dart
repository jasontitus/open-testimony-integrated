import 'dart:io';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:exif/exif.dart';
import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';
import 'package:geolocator/geolocator.dart';
import 'video_service.dart';

/// Result of processing an imported media file
class ImportResult {
  final VideoRecord record;
  final Map<String, dynamic> exifData;

  ImportResult({required this.record, required this.exifData});
}

/// Service for importing photos/videos from the device gallery
class MediaImportService {
  static const _channel = MethodChannel('com.opentestimony/crypto');
  final ImagePicker _picker = ImagePicker();
  final _uuid = const Uuid();

  /// Pick multiple media files from the device gallery
  Future<List<XFile>> pickMedia() async {
    final List<XFile> files = await _picker.pickMultipleMedia();
    return files;
  }

  /// Detect whether a file is a photo or video based on extension
  String detectMediaType(String path) {
    final ext = path.split('.').last.toLowerCase();
    const videoExts = {'mp4', 'mov', 'avi', 'mkv', 'm4v', '3gp', 'webm'};
    if (videoExts.contains(ext)) return 'video';
    return 'photo';
  }

  /// Extract EXIF metadata from an image file
  Future<Map<String, dynamic>> extractExif(File file) async {
    final result = <String, dynamic>{};
    try {
      final bytes = await file.readAsBytes();
      final tags = await readExifFromBytes(bytes);

      if (tags.isEmpty) return result;

      // GPS coordinates
      if (tags.containsKey('GPS GPSLatitude') && tags.containsKey('GPS GPSLongitude')) {
        result['gps_latitude'] = tags['GPS GPSLatitude']?.printable;
        result['gps_longitude'] = tags['GPS GPSLongitude']?.printable;
        result['gps_latitude_ref'] = tags['GPS GPSLatitudeRef']?.printable;
        result['gps_longitude_ref'] = tags['GPS GPSLongitudeRef']?.printable;
      }

      // Timestamp
      if (tags.containsKey('EXIF DateTimeOriginal')) {
        result['date_time_original'] = tags['EXIF DateTimeOriginal']?.printable;
      } else if (tags.containsKey('Image DateTime')) {
        result['date_time_original'] = tags['Image DateTime']?.printable;
      }

      // Camera info
      if (tags.containsKey('Image Make')) {
        result['camera_make'] = tags['Image Make']?.printable;
      }
      if (tags.containsKey('Image Model')) {
        result['camera_model'] = tags['Image Model']?.printable;
      }

      // Image dimensions
      if (tags.containsKey('EXIF ExifImageWidth')) {
        result['image_width'] = tags['EXIF ExifImageWidth']?.printable;
      }
      if (tags.containsKey('EXIF ExifImageLength')) {
        result['image_height'] = tags['EXIF ExifImageLength']?.printable;
      }
    } catch (e) {
      print('Error reading EXIF data: $e');
    }
    return result;
  }

  /// Process an imported media file: hash, extract EXIF, create VideoRecord
  Future<ImportResult> processImportedMedia(XFile xfile) async {
    final file = File(xfile.path);
    final mediaType = detectMediaType(xfile.path);

    // Calculate file hash
    final bytes = await file.readAsBytes();
    final hash = sha256.convert(bytes).toString();

    // Extract metadata based on media type
    Map<String, dynamic> exifData = {};
    double latitude = 0.0;
    double longitude = 0.0;

    if (mediaType == 'photo') {
      // Extract EXIF for photos
      exifData = await extractExif(file);
      if (exifData.containsKey('gps_latitude') && exifData.containsKey('gps_longitude')) {
        latitude = _parseExifGps(exifData['gps_latitude'], exifData['gps_latitude_ref']);
        longitude = _parseExifGps(exifData['gps_longitude'], exifData['gps_longitude_ref']);
      }
    } else {
      // Extract GPS + creation date from video container metadata via platform channel (AVAsset on iOS)
      try {
        final result = await _channel.invokeMethod('extractVideoLocation', {'path': xfile.path});
        if (result != null && result is Map) {
          latitude = (result['latitude'] as num?)?.toDouble() ?? 0.0;
          longitude = (result['longitude'] as num?)?.toDouble() ?? 0.0;
          if (latitude != 0.0 || longitude != 0.0) {
            print('📍 Extracted GPS from video metadata: $latitude, $longitude');
          }
          // Extract creation date from video metadata
          final creationDate = result['creation_date'] as String?;
          if (creationDate != null && creationDate.isNotEmpty) {
            exifData['date_time_original'] = creationDate;
          }
        }
      } catch (e) {
        print('Could not extract video location metadata: $e');
      }
    }

    // Fall back to current device position if no GPS from media metadata
    if (latitude == 0.0 && longitude == 0.0) {
      try {
        final position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        ).timeout(const Duration(seconds: 5));
        latitude = position.latitude;
        longitude = position.longitude;
        print('📍 Using device GPS fallback: $latitude, $longitude');
      } catch (e) {
        print('Could not get device location for import: $e');
      }
    }

    // Determine original timestamp: prefer metadata, then file mod time, then now
    DateTime originalTimestamp = DateTime.now();
    if (exifData.containsKey('date_time_original')) {
      final parsed = _parseDateTime(exifData['date_time_original']);
      if (parsed != null) {
        originalTimestamp = parsed;
        print('📅 Using original timestamp from metadata: $originalTimestamp');
      }
    }
    // Fall back to file modification time if no metadata timestamp
    if (originalTimestamp.difference(DateTime.now()).abs() < const Duration(seconds: 2)) {
      try {
        final fileStat = await file.stat();
        final modTime = fileStat.modified;
        // Only use file mod time if it's meaningfully in the past
        if (DateTime.now().difference(modTime) > const Duration(minutes: 1)) {
          originalTimestamp = modTime;
          print('📅 Using file modification time: $originalTimestamp');
        }
      } catch (e) {
        print('Could not read file modification time: $e');
      }
    }

    final now = DateTime.now();
    final id = _uuid.v4();

    final record = VideoRecord(
      id: id,
      filePath: xfile.path,
      fileHash: hash,
      timestamp: originalTimestamp,
      latitude: latitude,
      longitude: longitude,
      tags: [],
      uploadStatus: 'pending',
      createdAt: now,
      source: 'upload',
      mediaType: mediaType,
    );

    return ImportResult(record: record, exifData: exifData);
  }

  /// Parse various date/time formats from EXIF and video metadata
  DateTime? _parseDateTime(String? dateStr) {
    if (dateStr == null || dateStr.isEmpty) return null;
    try {
      // Try ISO 8601 format first (from AVAsset: "2024-01-15T10:30:00+0000")
      final iso = DateTime.tryParse(dateStr);
      if (iso != null) return iso;

      // Try EXIF format: "2024:01:15 10:30:00"
      final exifPattern = RegExp(r'(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})');
      final match = exifPattern.firstMatch(dateStr);
      if (match != null) {
        return DateTime(
          int.parse(match.group(1)!),
          int.parse(match.group(2)!),
          int.parse(match.group(3)!),
          int.parse(match.group(4)!),
          int.parse(match.group(5)!),
          int.parse(match.group(6)!),
        );
      }
    } catch (e) {
      print('Error parsing date: $e');
    }
    return null;
  }

  /// Parse EXIF GPS string like "37, 46, 29.88" with ref "N"/"S"/"E"/"W" to decimal degrees
  double _parseExifGps(String? dms, String? ref) {
    if (dms == null || dms.isEmpty) return 0.0;
    try {
      // Format: "degrees, minutes, seconds" or "degrees/1, minutes/1, seconds/100"
      final parts = dms.split(',').map((s) => s.trim()).toList();
      if (parts.length < 2) return 0.0;

      double parsePart(String p) {
        if (p.contains('/')) {
          final frac = p.split('/');
          return double.parse(frac[0]) / double.parse(frac[1]);
        }
        return double.parse(p);
      }

      final degrees = parsePart(parts[0]);
      final minutes = parsePart(parts[1]);
      final seconds = parts.length >= 3 ? parsePart(parts[2]) : 0.0;

      double result = degrees + (minutes / 60.0) + (seconds / 3600.0);
      if (ref == 'S' || ref == 'W') result = -result;
      return result;
    } catch (e) {
      print('Error parsing EXIF GPS: $e');
      return 0.0;
    }
  }
}
