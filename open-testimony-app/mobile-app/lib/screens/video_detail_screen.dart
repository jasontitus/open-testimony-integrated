import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/video_service.dart';
import '../services/upload_service.dart';
import '../services/hardware_crypto_service.dart';

class VideoDetailScreen extends StatefulWidget {
  final VideoRecord video;

  const VideoDetailScreen({super.key, required this.video});

  @override
  State<VideoDetailScreen> createState() => _VideoDetailScreenState();
}

class _VideoDetailScreenState extends State<VideoDetailScreen> {
  late VideoRecord _video;
  late TextEditingController _locationController;
  late TextEditingController _notesController;
  String? _selectedCategory;
  bool _isSaving = false;
  bool _hasChanges = false;
  List<Map<String, dynamic>> _auditTrail = [];
  bool _loadingAudit = false;

  // Tags state
  List<String> _tags = [];
  List<String> _availableTags = [];
  TextEditingController? _tagTextController;
  final _tagAutocompleteKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    _video = widget.video;
    _selectedCategory = _video.category;
    _locationController = TextEditingController(text: _video.locationDescription ?? '');
    _notesController = TextEditingController(text: _video.notes ?? '');
    _tags = List<String>.from(_video.tags);

    _locationController.addListener(_onFieldChanged);
    _notesController.addListener(_onFieldChanged);

    _loadTags();
    if (_video.serverId != null) {
      _loadServerData();
      _loadAuditTrail();
    }
  }

  void _onFieldChanged() {
    if (!_hasChanges) {
      setState(() => _hasChanges = true);
    }
  }

  Future<void> _loadTags() async {
    try {
      final uploadService = context.read<UploadService>();
      final tags = await uploadService.fetchTags();
      if (mounted) {
        setState(() => _availableTags = tags);
      }
    } catch (e) {
      // Silently fail — autocomplete just won't show suggestions
    }
  }

  Future<void> _loadServerData() async {
    if (_video.serverId == null) return;
    try {
      final uploadService = context.read<UploadService>();
      final videoService = context.read<VideoService>();
      final serverData = await uploadService.fetchVideoDetails(_video.serverId!);
      if (serverData == null || !mounted) return;

      final serverCategory = serverData['category'] as String?;
      final serverLocation = serverData['location_description'] as String?;
      final serverNotes = serverData['notes'] as String?;
      final serverTags = List<String>.from(serverData['incident_tags'] ?? []);

      // Update local DB to stay in sync
      await videoService.updateAnnotations(
        _video.id,
        category: serverCategory,
        locationDescription: serverLocation,
        notes: serverNotes,
        tags: serverTags,
      );

      // Update form fields (only if user hasn't started editing)
      if (mounted && !_hasChanges) {
        // Remove listeners temporarily to avoid triggering _hasChanges
        _locationController.removeListener(_onFieldChanged);
        _notesController.removeListener(_onFieldChanged);
        setState(() {
          _selectedCategory = serverCategory;
          _locationController.text = serverLocation ?? '';
          _notesController.text = serverNotes ?? '';
          _tags = serverTags;
        });
        _locationController.addListener(_onFieldChanged);
        _notesController.addListener(_onFieldChanged);
      }
    } catch (e) {
      // Silently fail — local data is still shown
      print('Error loading server data: $e');
    }
  }

  Future<void> _loadAuditTrail() async {
    if (_video.serverId == null) return;
    setState(() => _loadingAudit = true);
    try {
      final uploadService = context.read<UploadService>();
      final trail = await uploadService.getVideoAuditTrail(_video.serverId!);
      if (mounted) {
        setState(() {
          _auditTrail = trail;
          _loadingAudit = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loadingAudit = false);
      }
    }
  }

  Future<void> _saveAnnotations() async {
    setState(() => _isSaving = true);

    try {
      final videoService = context.read<VideoService>();
      final uploadService = context.read<UploadService>();
      final cryptoService = context.read<HardwareCryptoService>();

      final category = _selectedCategory;
      final locationDescription = _locationController.text.trim().isEmpty
          ? null
          : _locationController.text.trim();
      final notes = _notesController.text.trim().isEmpty
          ? null
          : _notesController.text.trim();

      // Save locally
      await videoService.updateAnnotations(
        _video.id,
        category: category,
        locationDescription: locationDescription,
        notes: notes,
        tags: _tags,
      );

      // Push to server if uploaded
      if (_video.serverId != null) {
        final deviceId = await cryptoService.getDeviceId();
        if (deviceId != null) {
          final success = await uploadService.updateAnnotations(
            serverId: _video.serverId!,
            deviceId: deviceId,
            category: category,
            locationDescription: locationDescription,
            notes: notes,
            tags: _tags,
          );

          if (!success && mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Saved locally, but server update failed'),
                backgroundColor: Colors.orange,
              ),
            );
          }
        }
      }

      // Reload video
      final updated = await videoService.getVideo(_video.id);
      if (updated != null && mounted) {
        setState(() {
          _video = updated;
          _hasChanges = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Annotations saved'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSaving = false);
      }
    }
  }

  void _addTag(String tag) {
    final trimmed = tag.trim().toLowerCase();
    if (trimmed.isNotEmpty && !_tags.contains(trimmed)) {
      setState(() {
        _tags.add(trimmed);
        _hasChanges = true;
      });
    }
  }

  void _removeTag(String tag) {
    setState(() {
      _tags.remove(tag);
      _hasChanges = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_video.mediaType == 'photo' ? 'Photo Details' : 'Video Details'),
        actions: [
          if (_hasChanges)
            TextButton(
              onPressed: _isSaving ? null : _saveAnnotations,
              child: _isSaving
                  ? const SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // --- Context banner ---
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.grey[100],
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  _video.mediaType == 'photo' ? Icons.photo : Icons.videocam,
                  size: 18,
                  color: Colors.grey[600],
                ),
                const SizedBox(width: 8),
                Text(
                  '${_video.source == 'upload' ? 'Imported' : 'Live'} ${_video.mediaType}',
                  style: TextStyle(fontSize: 13, color: Colors.grey[700], fontWeight: FontWeight.w500),
                ),
                const Spacer(),
                Text(
                  _formatDateTime(_video.timestamp),
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
                if (_video.uploadStatus == 'uploaded') ...[
                  const SizedBox(width: 8),
                  Icon(Icons.cloud_done, size: 16, color: Colors.green[400]),
                ] else if (_video.uploadStatus == 'pending') ...[
                  const SizedBox(width: 8),
                  Icon(Icons.cloud_queue, size: 16, color: Colors.orange[400]),
                ],
              ],
            ),
          ),

          const SizedBox(height: 20),

          // --- Category dropdown ---
          DropdownButtonFormField<String>(
            value: _selectedCategory,
            decoration: const InputDecoration(
              labelText: 'Category',
              border: OutlineInputBorder(),
            ),
            items: const [
              DropdownMenuItem(value: null, child: Text('None')),
              DropdownMenuItem(value: 'interview', child: Text('Interview')),
              DropdownMenuItem(value: 'incident', child: Text('Incident')),
              DropdownMenuItem(value: 'documentation', child: Text('Documentation')),
              DropdownMenuItem(value: 'other', child: Text('Other')),
            ],
            onChanged: (value) {
              setState(() {
                _selectedCategory = value;
                _hasChanges = true;
              });
            },
          ),
          const SizedBox(height: 16),

          // --- Tags ---
          Text('Tags', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
          const SizedBox(height: 6),

          if (_tags.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Wrap(
                spacing: 6,
                runSpacing: 4,
                children: _tags.map((tag) => Chip(
                  label: Text(tag, style: const TextStyle(fontSize: 12)),
                  deleteIcon: const Icon(Icons.close, size: 16),
                  onDeleted: () => _removeTag(tag),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                )).toList(),
              ),
            ),

          LayoutBuilder(
            builder: (context, constraints) {
              return Autocomplete<String>(
                key: _tagAutocompleteKey,
                optionsBuilder: (TextEditingValue textEditingValue) {
                  if (textEditingValue.text.isEmpty) {
                    return _availableTags.where((tag) => !_tags.contains(tag)).take(10);
                  }
                  return _availableTags.where((tag) =>
                    tag.toLowerCase().contains(textEditingValue.text.toLowerCase()) &&
                    !_tags.contains(tag)
                  ).take(10);
                },
                onSelected: (String selection) {
                  // Defer to avoid mutating layout during the Autocomplete's build
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    _addTag(selection);
                    _tagTextController?.clear();
                  });
                },
                optionsViewOpenDirection: OptionsViewOpenDirection.down,
                optionsViewBuilder: (context, onSelected, options) {
                  return Align(
                    alignment: Alignment.topLeft,
                    child: Material(
                      elevation: 4,
                      borderRadius: BorderRadius.circular(8),
                      child: ConstrainedBox(
                        constraints: BoxConstraints(
                          maxHeight: 200,
                          maxWidth: constraints.maxWidth,
                        ),
                        child: ListView.builder(
                          padding: EdgeInsets.zero,
                          shrinkWrap: true,
                          itemCount: options.length,
                          itemBuilder: (context, index) {
                            final option = options.elementAt(index);
                            return ListTile(
                              dense: true,
                              title: Text(option, style: const TextStyle(fontSize: 13)),
                              onTap: () => onSelected(option),
                            );
                          },
                        ),
                      ),
                    ),
                  );
                },
                fieldViewBuilder: (context, textEditingController, focusNode, onFieldSubmitted) {
                  _tagTextController = textEditingController;
                  return TextField(
                    controller: textEditingController,
                    focusNode: focusNode,
                    decoration: InputDecoration(
                      hintText: 'Add tag...',
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.add),
                        onPressed: () {
                          final text = textEditingController.text.trim();
                          if (text.isNotEmpty) {
                            textEditingController.clear();
                            _addTag(text);
                          }
                        },
                      ),
                    ),
                    onSubmitted: (text) {
                      final trimmed = text.trim();
                      if (trimmed.isNotEmpty) {
                        textEditingController.clear();
                        _addTag(trimmed);
                      }
                    },
                  );
                },
              );
            },
          ),
          const SizedBox(height: 16),

          // --- Location description ---
          TextField(
            controller: _locationController,
            decoration: const InputDecoration(
              labelText: 'Location Description',
              hintText: 'e.g., City Hall, Main St & 5th Ave',
              border: OutlineInputBorder(),
            ),
            maxLines: 2,
          ),
          const SizedBox(height: 12),

          // --- Notes ---
          TextField(
            controller: _notesController,
            decoration: const InputDecoration(
              labelText: 'Notes',
              hintText: 'What happened? Who was involved? Any other details...',
              border: OutlineInputBorder(),
            ),
            maxLines: 4,
          ),

          // --- Audit Trail section ---
          if (_video.serverId != null) ...[
            const SizedBox(height: 24),
            _buildSectionHeader('Audit Trail'),
            if (_loadingAudit)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_auditTrail.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('No audit entries', style: TextStyle(color: Colors.grey)),
              )
            else
              ..._auditTrail.map((entry) => Card(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    child: ListTile(
                      dense: true,
                      leading: Icon(
                        _getAuditIcon(entry['event_type']),
                        size: 20,
                        color: Colors.indigo,
                      ),
                      title: Text(
                        entry['event_type'] ?? '',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                      ),
                      subtitle: Text(
                        entry['created_at'] ?? '',
                        style: const TextStyle(fontSize: 11),
                      ),
                      trailing: Text(
                        '#${entry['sequence_number']}',
                        style: const TextStyle(fontSize: 11, color: Colors.grey),
                      ),
                    ),
                  )),
          ],

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: TextStyle(color: Colors.grey[600], fontSize: 13),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 13, fontFamily: 'monospace'),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getAuditIcon(String? eventType) {
    switch (eventType) {
      case 'upload':
        return Icons.cloud_upload;
      case 'annotation_update':
        return Icons.edit_note;
      case 'device_register':
        return Icons.smartphone;
      default:
        return Icons.info;
    }
  }

  String _formatDateTime(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }

  @override
  void dispose() {
    _locationController.dispose();
    _notesController.dispose();
    super.dispose();
  }
}
