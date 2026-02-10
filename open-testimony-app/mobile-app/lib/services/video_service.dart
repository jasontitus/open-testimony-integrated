import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

/// Model for video/photo recordings
class VideoRecord {
  final String id;
  final String filePath;
  final String fileHash;
  final DateTime timestamp;
  final double latitude;
  final double longitude;
  final List<String> tags;
  final String uploadStatus; // 'pending', 'uploading', 'uploaded', 'failed'
  final DateTime createdAt;
  final String source; // 'live' or 'upload'
  final String mediaType; // 'video' or 'photo'
  final String? category; // 'interview' or 'incident'
  final String? locationDescription;
  final String? notes;
  final String? serverId; // UUID from server after upload

  VideoRecord({
    required this.id,
    required this.filePath,
    required this.fileHash,
    required this.timestamp,
    required this.latitude,
    required this.longitude,
    required this.tags,
    required this.uploadStatus,
    required this.createdAt,
    this.source = 'live',
    this.mediaType = 'video',
    this.category,
    this.locationDescription,
    this.notes,
    this.serverId,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'file_path': filePath,
      'file_hash': fileHash,
      'timestamp': timestamp.toIso8601String(),
      'latitude': latitude,
      'longitude': longitude,
      'tags': tags.join(','),
      'upload_status': uploadStatus,
      'created_at': createdAt.toIso8601String(),
      'source': source,
      'media_type': mediaType,
      'category': category,
      'location_description': locationDescription,
      'notes': notes,
      'server_id': serverId,
    };
  }

  factory VideoRecord.fromMap(Map<String, dynamic> map) {
    return VideoRecord(
      id: map['id'],
      filePath: map['file_path'],
      fileHash: map['file_hash'],
      timestamp: DateTime.parse(map['timestamp']),
      latitude: map['latitude'],
      longitude: map['longitude'],
      tags: map['tags'].toString().split(',').where((s) => s.isNotEmpty).toList(),
      uploadStatus: map['upload_status'],
      createdAt: DateTime.parse(map['created_at']),
      source: map['source'] ?? 'live',
      mediaType: map['media_type'] ?? 'video',
      category: map['category'],
      locationDescription: map['location_description'],
      notes: map['notes'],
      serverId: map['server_id'],
    );
  }

  VideoRecord copyWith({
    String? id,
    String? filePath,
    String? fileHash,
    DateTime? timestamp,
    double? latitude,
    double? longitude,
    List<String>? tags,
    String? uploadStatus,
    DateTime? createdAt,
    String? source,
    String? mediaType,
    String? category,
    String? locationDescription,
    String? notes,
    String? serverId,
  }) {
    return VideoRecord(
      id: id ?? this.id,
      filePath: filePath ?? this.filePath,
      fileHash: fileHash ?? this.fileHash,
      timestamp: timestamp ?? this.timestamp,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      tags: tags ?? this.tags,
      uploadStatus: uploadStatus ?? this.uploadStatus,
      createdAt: createdAt ?? this.createdAt,
      source: source ?? this.source,
      mediaType: mediaType ?? this.mediaType,
      category: category ?? this.category,
      locationDescription: locationDescription ?? this.locationDescription,
      notes: notes ?? this.notes,
      serverId: serverId ?? this.serverId,
    );
  }
}

/// Service for managing video files and metadata
class VideoService {
  Database? _database;

  /// Initialize database
  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    final documentsDirectory = await getApplicationDocumentsDirectory();
    final path = join(documentsDirectory.path, 'open_testimony.db');

    return await openDatabase(
      path,
      version: 2,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE videos (
            id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            tags TEXT,
            upload_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source TEXT DEFAULT 'live',
            media_type TEXT DEFAULT 'video',
            category TEXT,
            location_description TEXT,
            notes TEXT,
            server_id TEXT
          )
        ''');
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          await db.execute('ALTER TABLE videos ADD COLUMN source TEXT DEFAULT \'live\'');
          await db.execute('ALTER TABLE videos ADD COLUMN media_type TEXT DEFAULT \'video\'');
          await db.execute('ALTER TABLE videos ADD COLUMN category TEXT');
          await db.execute('ALTER TABLE videos ADD COLUMN location_description TEXT');
          await db.execute('ALTER TABLE videos ADD COLUMN notes TEXT');
          await db.execute('ALTER TABLE videos ADD COLUMN server_id TEXT');
        }
      },
    );
  }

  /// Get videos directory
  Future<Directory> getVideosDirectory() async {
    final appDir = await getApplicationDocumentsDirectory();
    final videosDir = Directory('${appDir.path}/videos');
    if (!await videosDir.exists()) {
      await videosDir.create(recursive: true);
    }
    return videosDir;
  }

  /// Save video record to database
  Future<void> saveVideo(VideoRecord video) async {
    final db = await database;
    await db.insert(
      'videos',
      video.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Get all videos
  Future<List<VideoRecord>> getAllVideos() async {
    final db = await database;
    final maps = await db.query('videos', orderBy: 'created_at DESC');
    return maps.map((map) => VideoRecord.fromMap(map)).toList();
  }

  /// Get a single video by ID
  Future<VideoRecord?> getVideo(String id) async {
    final db = await database;
    final maps = await db.query('videos', where: 'id = ?', whereArgs: [id]);
    if (maps.isEmpty) return null;
    return VideoRecord.fromMap(maps.first);
  }

  /// Get pending upload videos
  Future<List<VideoRecord>> getPendingUploads() async {
    final db = await database;
    final maps = await db.query(
      'videos',
      where: 'upload_status = ?',
      whereArgs: ['pending'],
    );
    return maps.map((map) => VideoRecord.fromMap(map)).toList();
  }

  /// Update video upload status
  Future<void> updateUploadStatus(String id, String status) async {
    final db = await database;
    await db.update(
      'videos',
      {'upload_status': status},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  /// Update server ID after upload
  Future<void> updateServerId(String id, String serverId) async {
    final db = await database;
    await db.update(
      'videos',
      {'server_id': serverId},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  /// Update annotations locally
  Future<void> updateAnnotations(
    String id, {
    String? category,
    String? locationDescription,
    String? notes,
    List<String>? tags,
  }) async {
    final db = await database;
    final updates = <String, dynamic>{
      'category': category,
      'location_description': locationDescription,
      'notes': notes,
    };
    if (tags != null) {
      updates['tags'] = tags.join(',');
    }
    await db.update(
      'videos',
      updates,
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  /// Delete all local videos (clears database and files)
  Future<int> deleteAllVideos() async {
    final db = await database;

    // Get all file paths
    final maps = await db.query('videos');
    int count = 0;
    for (final map in maps) {
      final filePath = map['file_path'] as String;
      final file = File(filePath);
      if (await file.exists()) {
        await file.delete();
      }
      count++;
    }

    // Clear the table
    await db.delete('videos');
    return count;
  }

  /// Delete video
  Future<void> deleteVideo(String id) async {
    final db = await database;

    // Get file path before deleting
    final maps = await db.query('videos', where: 'id = ?', whereArgs: [id]);
    if (maps.isNotEmpty) {
      final video = VideoRecord.fromMap(maps.first);
      final file = File(video.filePath);
      if (await file.exists()) {
        await file.delete();
      }
    }

    await db.delete('videos', where: 'id = ?', whereArgs: [id]);
  }
}
