import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../services/hardware_crypto_service.dart';
import '../services/upload_service.dart';
import '../services/video_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String? _deviceId;
  String? _publicKey;
  bool _isRegistered = false;
  String _cryptoDisplay = 'Loading...';
  String _selectedServer = UploadService.baseUrl;
  bool _isOther = false;
  final _customUrlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadDeviceInfo();
    // Check if current URL matches a preset
    final match = serverPresets.any((p) => p.url == _selectedServer);
    if (!match) {
      _isOther = true;
      _customUrlController.text = _selectedServer;
    }
  }

  Future<void> _loadDeviceInfo() async {
    final cryptoService = context.read<HardwareCryptoService>();
    final deviceId = await cryptoService.getDeviceId();
    final publicKey = await cryptoService.getPublicKeyPem();

    setState(() {
      _deviceId = deviceId;
      _publicKey = publicKey;
      _cryptoDisplay = cryptoService.getCryptoVersionDisplay();
    });
  }

  Future<void> _registerDevice() async {
    if (_deviceId == null || _publicKey == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Device credentials not available')),
      );
      return;
    }

    final uploadService = context.read<UploadService>();
    final cryptoService = context.read<HardwareCryptoService>();
    final success = await uploadService.registerDevice(
      _deviceId!,
      _publicKey!,
      cryptoVersion: cryptoService.cryptoVersion,
    );

    if (mounted) {
      if (success) {
        setState(() {
          _isRegistered = true;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Device registered successfully'),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Registration failed - check server URL'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _confirmClearAllVideos() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear All Local Videos?'),
        content: const Text(
          'This will delete all videos and photos stored on this device. '
          'Files already uploaded to the server will not be affected.\n\n'
          'This cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete All'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      final videoService = context.read<VideoService>();
      final count = await videoService.deleteAllVideos();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Cleared $count local videos'),
            backgroundColor: Colors.green,
          ),
        );
      }
    }
  }

  void _copyToClipboard(String text, String label) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copied to clipboard')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        children: [
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text(
              'Device Information',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.smartphone),
            title: const Text('Device ID'),
            subtitle: Text(
              _deviceId ?? 'Loading...',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
            trailing: IconButton(
              icon: const Icon(Icons.copy),
              onPressed: _deviceId != null
                  ? () => _copyToClipboard(_deviceId!, 'Device ID')
                  : null,
            ),
          ),
          const Divider(),
          ExpansionTile(
            leading: const Icon(Icons.key),
            title: const Text('Public Key'),
            children: [
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _publicKey ?? 'Loading...',
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 10,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    ElevatedButton.icon(
                      onPressed: _publicKey != null
                          ? () => _copyToClipboard(_publicKey!, 'Public key')
                          : null,
                      icon: const Icon(Icons.copy),
                      label: const Text('Copy Public Key'),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const Divider(),
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text(
              'Server Configuration',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: DropdownButtonFormField<String>(
              value: _isOther ? 'other' : _selectedServer,
              decoration: const InputDecoration(
                labelText: 'Server',
                border: OutlineInputBorder(),
              ),
              items: [
                ...serverPresets.map((p) => DropdownMenuItem(
                  value: p.url,
                  child: Text(p.label),
                )),
                const DropdownMenuItem(
                  value: 'other',
                  child: Text('Other...'),
                ),
              ],
              onChanged: (value) async {
                if (value == null) return;
                final uploadService = context.read<UploadService>();
                if (value == 'other') {
                  setState(() { _isOther = true; });
                } else {
                  setState(() {
                    _isOther = false;
                    _selectedServer = value;
                  });
                  await uploadService.setServerUrl(value);
                }
              },
            ),
          ),
          if (_isOther) ...[
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: TextField(
                controller: _customUrlController,
                decoration: const InputDecoration(
                  labelText: 'Custom Server URL',
                  hintText: 'http://192.168.1.100:18080/api',
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (value) async {
                  if (value.trim().isEmpty) return;
                  final uploadService = context.read<UploadService>();
                  setState(() { _selectedServer = value.trim(); });
                  await uploadService.setServerUrl(value.trim());
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Server URL saved'),
                        backgroundColor: Colors.green,
                      ),
                    );
                  }
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
              child: Text(
                'Press return to save',
                style: TextStyle(fontSize: 12, color: Colors.grey[600]),
              ),
            ),
          ],
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: ElevatedButton.icon(
              onPressed: _registerDevice,
              icon: _isRegistered
                  ? const Icon(Icons.check_circle)
                  : const Icon(Icons.cloud_upload),
              label: Text(
                _isRegistered ? 'Re-register Device' : 'Register Device',
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isRegistered ? Colors.green : null,
                padding: const EdgeInsets.all(16),
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Divider(),
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text(
              'Data Management',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: ElevatedButton.icon(
              onPressed: () => _confirmClearAllVideos(),
              icon: const Icon(Icons.delete_sweep),
              label: const Text('Clear All Local Videos'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red[700],
                foregroundColor: Colors.white,
                padding: const EdgeInsets.all(16),
              ),
            ),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Text(
              'Removes all videos and photos from this device. '
              'Already-uploaded files on the server are not affected.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ),
          const SizedBox(height: 16),
          const Divider(),
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text(
              'About',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const ListTile(
            leading: Icon(Icons.info),
            title: Text('Version'),
            subtitle: Text('2.0.0'),
          ),
          ListTile(
            leading: const Icon(Icons.shield),
            title: const Text('Cryptography'),
            subtitle: Text(_cryptoDisplay),
          ),
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text(
              'Open Testimony\n\n'
              'This app uses hardware-backed cryptography (when available) '
              'to ensure the authenticity and integrity of recorded videos. '
              'Falls back to software HMAC on devices without Secure Enclave/StrongBox.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _customUrlController.dispose();
    super.dispose();
  }
}
