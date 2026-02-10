import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/video_service.dart';
import '../services/upload_service.dart';
import '../services/hardware_crypto_service.dart';
import '../services/media_import_service.dart';
import 'video_detail_screen.dart';
import 'dart:convert';

class GalleryScreen extends StatefulWidget {
  const GalleryScreen({super.key});

  @override
  State<GalleryScreen> createState() => _GalleryScreenState();
}

class _GalleryScreenState extends State<GalleryScreen> {
  List<VideoRecord> _videos = [];
  bool _isLoading = true;
  bool _isImporting = false;
  int _importTotal = 0;
  int _importCurrent = 0;
  double _importFileProgress = 0.0; // 0.0 to 1.0 for current file
  int _importSucceeded = 0;
  int _importFailed = 0;

  @override
  void initState() {
    super.initState();
    _loadVideos();
  }

  Future<void> _loadVideos() async {
    final videoService = context.read<VideoService>();
    final videos = await videoService.getAllVideos();

    setState(() {
      _videos = videos;
      _isLoading = false;
    });
  }

  Future<void> _importFromGallery() async {
    final importService = context.read<MediaImportService>();
    final videoService = context.read<VideoService>();
    final cryptoService = context.read<HardwareCryptoService>();
    final uploadService = context.read<UploadService>();

    final files = await importService.pickMedia();
    if (files.isEmpty) return;

    setState(() {
      _isImporting = true;
      _importTotal = files.length;
      _importCurrent = 0;
      _importFileProgress = 0.0;
      _importSucceeded = 0;
      _importFailed = 0;
    });

    final deviceId = await cryptoService.getDeviceId();
    final publicKeyPem = await cryptoService.getPublicKeyPem();

    for (final file in files) {
      setState(() {
        _importCurrent++;
        _importFileProgress = 0.0;
      });

      try {
        // Process the imported media
        final importResult = await importService.processImportedMedia(file);
        final record = importResult.record;
        await videoService.saveVideo(record);

        // Refresh list so user can see new item
        _loadVideos();

        // Attempt upload
        if (deviceId != null && publicKeyPem != null) {
          final payload = {
            'video_hash': record.fileHash,
            'timestamp': record.timestamp.toIso8601String(),
            'location': {
              'lat': record.latitude,
              'lon': record.longitude,
            },
            'incident_tags': <String>[],
            'source': 'upload',
            'media_type': record.mediaType,
          };
          final payloadJson = jsonEncode(payload);
          final signature = await cryptoService.signData(payloadJson);

          await videoService.updateUploadStatus(record.id, 'uploading');
          _loadVideos();

          final result = await uploadService.uploadMedia(
            video: record,
            deviceId: deviceId,
            publicKeyPem: publicKeyPem,
            signature: signature,
            signedPayload: payloadJson,
            source: 'upload',
            mediaType: record.mediaType,
            exifMetadata: importResult.exifData.isNotEmpty ? importResult.exifData : null,
            onProgress: (progress) {
              if (mounted) {
                setState(() => _importFileProgress = progress);
              }
            },
          );

          if (result != null) {
            await videoService.updateUploadStatus(record.id, 'uploaded');
            final serverId = result['video_id'] as String?;
            if (serverId != null) {
              await videoService.updateServerId(record.id, serverId);
            }
            _importSucceeded++;
          } else {
            await videoService.updateUploadStatus(record.id, 'failed');
            _importFailed++;
          }
        } else {
          _importFailed++;
        }
      } catch (e) {
        print('Error processing imported file: $e');
        _importFailed++;
      }

      _loadVideos();
    }

    if (mounted) {
      String message;
      Color color;
      if (_importFailed == 0) {
        message = 'Uploaded $_importSucceeded of $_importTotal';
        color = Colors.green;
      } else {
        message = 'Uploaded $_importSucceeded of $_importTotal ($_importFailed failed)';
        color = Colors.orange;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message), backgroundColor: color),
      );
    }

    setState(() => _isImporting = false);
  }

  Future<void> _retryUpload(VideoRecord video) async {
    try {
      final cryptoService = context.read<HardwareCryptoService>();
      final uploadService = context.read<UploadService>();
      final videoService = context.read<VideoService>();

      await videoService.updateUploadStatus(video.id, 'uploading');
      _loadVideos();

      final payload = {
        'video_hash': video.fileHash,
        'timestamp': video.timestamp.toIso8601String(),
        'location': {
          'lat': video.latitude,
          'lon': video.longitude,
        },
        'incident_tags': video.tags,
        'source': video.source,
        'media_type': video.mediaType,
      };

      final payloadJson = jsonEncode(payload);
      final signature = await cryptoService.signData(payloadJson);

      final deviceId = await cryptoService.getDeviceId();
      final publicKeyPem = await cryptoService.getPublicKeyPem();

      if (deviceId == null || publicKeyPem == null) {
        throw Exception('Device credentials not available');
      }

      final result = await uploadService.uploadMedia(
        video: video,
        deviceId: deviceId,
        publicKeyPem: publicKeyPem,
        signature: signature,
        signedPayload: payloadJson,
      );

      if (result != null) {
        await videoService.updateUploadStatus(video.id, 'uploaded');
        final serverId = result['video_id'] as String?;
        if (serverId != null) {
          await videoService.updateServerId(video.id, serverId);
        }
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Uploaded successfully'),
              backgroundColor: Colors.green,
            ),
          );
        }
      } else {
        await videoService.updateUploadStatus(video.id, 'failed');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Upload failed')),
          );
        }
      }

      _loadVideos();
    } catch (e) {
      print('Error retrying upload: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _deleteVideo(VideoRecord video) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete'),
        content: Text('Are you sure you want to delete this ${video.mediaType}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirm == true) {
      final videoService = context.read<VideoService>();
      await videoService.deleteVideo(video.id);
      _loadVideos();
    }
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'uploaded':
        return Colors.green;
      case 'uploading':
        return Colors.blue;
      case 'failed':
        return Colors.red;
      default:
        return Colors.orange;
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status) {
      case 'uploaded':
        return Icons.check_circle;
      case 'uploading':
        return Icons.upload;
      case 'failed':
        return Icons.error;
      default:
        return Icons.pending;
    }
  }

  IconData _getMediaIcon(String mediaType) {
    return mediaType == 'photo' ? Icons.photo : Icons.videocam;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gallery'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadVideos,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _isImporting ? null : _importFromGallery,
        child: _isImporting
            ? const SizedBox(
                width: 24, height: 24,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              )
            : const Icon(Icons.add_photo_alternate),
      ),
      body: Column(
        children: [
          // Import progress banner
          if (_isImporting)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              color: Colors.blue[800],
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Uploading $_importCurrent of $_importTotal'
                    '${_importSucceeded > 0 ? '  ($_importSucceeded done)' : ''}'
                    '${_importFailed > 0 ? '  ($_importFailed failed)' : ''}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: _importFileProgress,
                      backgroundColor: Colors.blue[600],
                      valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                      minHeight: 6,
                    ),
                  ),
                ],
              ),
            ),
          Expanded(
            child: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _videos.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.video_library_outlined,
                        size: 64,
                        color: Colors.grey[400],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'No videos or photos yet',
                        style: TextStyle(
                          fontSize: 16,
                          color: Colors.grey[600],
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Record a video or import from gallery',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _videos.length,
                  itemBuilder: (context, index) {
                    final video = _videos[index];

                    return Card(
                      margin: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      child: InkWell(
                        onTap: () async {
                          await Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => VideoDetailScreen(video: video),
                            ),
                          );
                          _loadVideos();
                        },
                        child: ListTile(
                          leading: Container(
                            width: 60,
                            height: 60,
                            decoration: BoxDecoration(
                              color: Colors.grey[300],
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(_getMediaIcon(video.mediaType), size: 32),
                          ),
                          title: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  '${video.mediaType == 'photo' ? 'Photo' : 'Video'} ${index + 1}',
                                  style: const TextStyle(fontWeight: FontWeight.bold),
                                ),
                              ),
                              // Source badge
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: video.source == 'upload'
                                      ? Colors.purple.withValues(alpha: 0.1)
                                      : Colors.blue.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  video.source == 'upload' ? 'IMPORTED' : 'LIVE',
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    color: video.source == 'upload' ? Colors.purple : Colors.blue,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const SizedBox(height: 4),
                              Text(
                                'Recorded: ${_formatDateTime(video.timestamp)}',
                                style: const TextStyle(fontSize: 12),
                              ),
                              Text(
                                'Location: ${video.latitude.toStringAsFixed(4)}, ${video.longitude.toStringAsFixed(4)}',
                                style: const TextStyle(fontSize: 12),
                              ),
                              if (video.category != null)
                                Padding(
                                  padding: const EdgeInsets.only(top: 2),
                                  child: Text(
                                    video.category!.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.indigo[400],
                                    ),
                                  ),
                                ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  Icon(
                                    _getStatusIcon(video.uploadStatus),
                                    size: 16,
                                    color: _getStatusColor(video.uploadStatus),
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    video.uploadStatus.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.bold,
                                      color: _getStatusColor(video.uploadStatus),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          trailing: PopupMenuButton<String>(
                            onSelected: (value) {
                              if (value == 'retry') {
                                _retryUpload(video);
                              } else if (value == 'delete') {
                                _deleteVideo(video);
                              }
                            },
                            itemBuilder: (context) => [
                              if (video.uploadStatus == 'failed' ||
                                  video.uploadStatus == 'pending')
                                const PopupMenuItem(
                                  value: 'retry',
                                  child: Row(
                                    children: [
                                      Icon(Icons.refresh),
                                      SizedBox(width: 8),
                                      Text('Retry Upload'),
                                    ],
                                  ),
                                ),
                              const PopupMenuItem(
                                value: 'delete',
                                child: Row(
                                  children: [
                                    Icon(Icons.delete, color: Colors.red),
                                    SizedBox(width: 8),
                                    Text('Delete'),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
          ),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime dateTime) {
    return '${dateTime.year}-${dateTime.month.toString().padLeft(2, '0')}-${dateTime.day.toString().padLeft(2, '0')} '
        '${dateTime.hour.toString().padLeft(2, '0')}:${dateTime.minute.toString().padLeft(2, '0')}';
  }
}
