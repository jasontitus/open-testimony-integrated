import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';
import 'dart:convert';
import 'dart:io';
import 'dart:async';
import '../services/hardware_crypto_service.dart';
import '../services/video_service.dart';
import '../services/upload_service.dart';

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription>? _cameras;
  bool _isRecording = false;
  bool _isInitializing = true;
  Position? _recordingStartPosition;
  Position? _lastKnownPosition;
  StreamSubscription<Position>? _positionStreamSubscription;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initializeCamera();
    _startLocationUpdates();
  }

  void _startLocationUpdates() async {
    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.whileInUse || permission == LocationPermission.always) {
        _positionStreamSubscription = Geolocator.getPositionStream(
          locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.high,
            distanceFilter: 10,
          ),
        ).listen(
          (Position position) {
            if (mounted) {
              setState(() {
                _lastKnownPosition = position;
              });
            }
          },
          onError: (error) {
            print('Location stream error: $error');
          },
          cancelOnError: false,
        );
      }
    } catch (e) {
      print('Error starting location updates: $e');
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _controller == null) {
      _initializeCamera();
    }
  }

  Future<void> _initializeCamera() async {
    setState(() {
      _isInitializing = true;
      _error = null;
    });

    try {
      _cameras = await availableCameras();
      if (_cameras == null || _cameras!.isEmpty) {
        throw Exception('No cameras found');
      }

      _controller = CameraController(
        _cameras!.first,
        ResolutionPreset.high,
        enableAudio: true,
      );

      await _controller!.initialize();
      await _controller!.prepareForVideoRecording();

      // Pre-warm the recording pipeline with a brief dummy recording.
      // AVFoundation (iOS) and MediaCodec (Android) perform expensive
      // one-time setup on the first recording: audio session, codec init,
      // hardware encoder buffer pools. Recording for 500ms forces the
      // encoder to fully spin up so the user's first real recording
      // starts instantly with no stutter.
      await _warmUpRecordingPipeline();

      if (mounted) {
        setState(() {
          _isInitializing = false;
        });
      }
    } catch (e) {
      print('Camera error: $e');
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isInitializing = false;
        });
      }
    }
  }

  /// Record for ~500ms so the hardware video encoder fully initializes
  /// its buffer pools and encoding session. A near-instant start+stop
  /// isn't enough — the encoder needs to process a few frames.
  Future<void> _warmUpRecordingPipeline() async {
    try {
      await _controller!.startVideoRecording();
      await Future.delayed(const Duration(milliseconds: 500));
      final file = await _controller!.stopVideoRecording();
      try {
        await File(file.path).delete();
      } catch (_) {}
    } catch (e) {
      // Non-fatal — first real recording will just have the usual delay.
      print('Recording warm-up failed (non-fatal): $e');
    }
  }

  Future<Position?> _getCurrentLocation() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) return null;

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) return null;
      }

      if (permission == LocationPermission.deniedForever) return null;

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );
      return position;
    } catch (e) {
      print('Error getting location: $e');
      return null;
    }
  }

  Future<void> _toggleRecording() async {
    if (_controller == null || !_controller!.value.isInitialized) {
      return;
    }

    if (_isRecording) {
      try {
        final endPosition = await _getCurrentLocation();

        final videoFile = await _controller!.stopVideoRecording();
        setState(() {
          _isRecording = false;
        });

        Position? bestPosition = _recordingStartPosition;
        if (endPosition != null) {
          if (bestPosition == null || endPosition.accuracy < bestPosition.accuracy) {
            bestPosition = endPosition;
          }
        }

        await _handleRecordingComplete(videoFile.path, bestPosition);
      } catch (e) {
        print('Error stopping recording: $e');
      }
    } else {
      try {
        // Grab cached position (non-blocking). Never delay recording for GPS.
        final position = _lastKnownPosition;

        // Update UI immediately so the user sees feedback with no delay.
        setState(() {
          _isRecording = true;
          _recordingStartPosition = position;
        });

        await _controller!.startVideoRecording();
      } catch (e) {
        // Revert UI if recording failed to start.
        setState(() {
          _isRecording = false;
          _recordingStartPosition = null;
        });
        print('Error starting recording: $e');
      }
    }
  }

  Future<void> _handleRecordingComplete(String videoPath, Position? finalPosition) async {
    final latitude = finalPosition?.latitude ?? 0.0;
    final longitude = finalPosition?.longitude ?? 0.0;

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Processing video...'),
          duration: Duration(seconds: 2),
        ),
      );
    }

    try {
      final videoService = context.read<VideoService>();
      final cryptoService = context.read<HardwareCryptoService>();
      final uploadService = context.read<UploadService>();

      final videoFile = File(videoPath);
      if (!await videoFile.exists()) {
        throw Exception('Video file not found at $videoPath');
      }

      final fileHash = await uploadService.calculateFileHash(videoFile);

      final timestamp = DateTime.now();
      final videoId = const Uuid().v4();

      final videoRecord = VideoRecord(
        id: videoId,
        filePath: videoPath,
        fileHash: fileHash,
        timestamp: timestamp,
        latitude: latitude,
        longitude: longitude,
        tags: [],
        uploadStatus: 'pending',
        createdAt: timestamp,
        source: 'live',
        mediaType: 'video',
      );

      await videoService.saveVideo(videoRecord);
      print('VIDEO SAVED LOCALLY: $videoId at $videoPath');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Video saved! Uploading...'),
            backgroundColor: Colors.blue,
            duration: Duration(seconds: 2),
          ),
        );
      }

      final payload = {
        'video_hash': fileHash,
        'timestamp': timestamp.toIso8601String(),
        'location': {
          'lat': latitude,
          'lon': longitude,
        },
        'incident_tags': [],
        'source': 'live',
        'media_type': 'video',
      };

      final payloadJson = jsonEncode(payload);
      final signature = await cryptoService.signData(payloadJson);

      final deviceId = await cryptoService.getDeviceId();
      final publicKeyPem = await cryptoService.getPublicKeyPem();

      if (deviceId == null || publicKeyPem == null) {
        throw Exception('Device credentials not available');
      }

      await videoService.updateUploadStatus(videoId, 'uploading');

      final result = await uploadService.uploadMedia(
        video: videoRecord,
        deviceId: deviceId,
        publicKeyPem: publicKeyPem,
        signature: signature,
        signedPayload: payloadJson,
      );

      if (result != null) {
        await videoService.updateUploadStatus(videoId, 'uploaded');
        final serverId = result['video_id'] as String?;
        if (serverId != null) {
          await videoService.updateServerId(videoId, serverId);
        }
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Uploaded successfully'),
              backgroundColor: Colors.green,
              duration: Duration(seconds: 3),
            ),
          );
        }
      } else {
        await videoService.updateUploadStatus(videoId, 'failed');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Video saved locally - upload failed, retry in Gallery'),
              backgroundColor: Colors.orange,
              duration: Duration(seconds: 4),
            ),
          );
        }
      }
    } catch (e) {
      print('Error processing video: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: ${e.toString()}'),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _positionStreamSubscription?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isInitializing) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(color: Colors.white),
              SizedBox(height: 16),
              Text(
                'Initializing camera...',
                style: TextStyle(color: Colors.white),
              ),
            ],
          ),
        ),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Camera Error'),
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 64, color: Colors.red),
                const SizedBox(height: 16),
                const Text(
                  'Camera initialization failed',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 14),
                ),
                const SizedBox(height: 24),
                const Text(
                  'Make sure you granted Camera, Microphone, and Location permissions in Settings.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: Colors.grey),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () async {
                    await openAppSettings();
                  },
                  child: const Text('Open Settings'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: _initializeCamera,
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (_controller == null || !_controller!.value.isInitialized) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: const Center(
          child: Text(
            'Camera not available',
            style: TextStyle(color: Colors.white),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          Center(
            child: CameraPreview(_controller!),
          ),

          if (_isRecording)
            Positioned(
              top: 60,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.8),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.fiber_manual_record, color: Colors.white, size: 16),
                      SizedBox(width: 8),
                      Text(
                        'Recording',
                        style: TextStyle(color: Colors.white, fontSize: 16),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          Positioned(
            bottom: 40,
            left: 0,
            right: 0,
            child: Center(
              child: GestureDetector(
                onTap: _toggleRecording,
                child: Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _isRecording ? Colors.red : Colors.white,
                    border: Border.all(
                      color: Colors.white,
                      width: 4,
                    ),
                  ),
                  child: _isRecording
                      ? const Icon(Icons.stop, size: 40, color: Colors.white)
                      : null,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
