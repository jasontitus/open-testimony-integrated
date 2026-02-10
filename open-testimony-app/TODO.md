# Open Testimony - TODO & Future Enhancements

## 🔴 Critical - Security Upgrades

### Hardware-Backed Cryptography
**Priority: HIGH for Production**

**Current State (MVP):**
- Using HMAC-SHA256 for signing
- Keys stored in Flutter Secure Storage (iOS Keychain/Android Keystore)
- Works reliably but not hardware-backed

**Target State (Production):**
- P-256 ECDSA with hardware-backed key storage
- iOS: Secure Enclave
- Android: StrongBox Keystore
- Private keys never leave hardware security module

**Implementation Options:**
1. **Option A**: Use `flutter_secure_storage` with hardware-backed flag enabled
2. **Option B**: Native platform channels to directly access Secure Enclave/StrongBox
3. **Option C**: Use `biometric_signature` package for hardware-backed ECDSA
4. **Option D**: Custom native implementation with platform-specific code

**Files to Update:**
- `mobile-app/lib/services/crypto_service.dart` - Main crypto implementation
- Backend verification logic to handle ECDSA signatures

**Testing Required:**
- Verify keys are truly in hardware (not software fallback)
- Test signature generation and verification
- Ensure keys survive app reinstall
- Test on various device models

---

## 🟡 High Priority

### Location Permission Handling
- **Current**: Location is optional (uses 0,0 if denied)
- **Enhancement**: Better UX for requesting location permission
- **Enhancement**: Show map preview of location when recording
- **Enhancement**: Allow manual location entry if GPS unavailable

### Video Compression
- **Current**: Videos uploaded at full camera resolution
- **Issue**: Large file sizes, slow uploads
- **Enhancement**: Compress videos before upload while maintaining quality
- **Consider**: Configurable quality settings

### Offline Upload Queue
- **Current**: Upload happens immediately after recording
- **Enhancement**: Better offline handling with retry logic
- **Enhancement**: Batch upload when connection restored
- **Enhancement**: Show network status indicator

### Video Playback in App
- **Current**: Videos only viewable in Gallery tab (no playback)
- **Enhancement**: In-app video player
- **Enhancement**: Share videos
- **Enhancement**: Export videos

---

## 🟢 Medium Priority

### UI/UX Improvements
- [ ] Dark mode support
- [ ] Better loading states and animations
- [ ] Customizable recording duration limit
- [ ] Recording timer display
- [ ] Battery level warning when recording
- [ ] Storage space warning

### Incident Tagging
- [ ] UI for adding incident tags during/after recording
- [ ] Predefined tag categories
- [ ] Custom tag creation
- [ ] Tag-based filtering in Gallery

### Device Registration Flow
- [ ] Onboarding wizard
- [ ] Better Settings UI
- [ ] QR code for easy device registration
- [ ] Device nickname/description

### Backend Enhancements
- [ ] User authentication (multi-user support)
- [ ] Web dashboard for viewing videos
- [ ] Video search and filtering
- [ ] Analytics and reporting
- [ ] Export verified videos with proof

---

## 🔵 Low Priority / Nice to Have

### Advanced Features
- [ ] Photo capture mode (in addition to video)
- [ ] Multiple camera support (front/back/external)
- [ ] Pause/resume recording
- [ ] Audio-only recording mode
- [ ] Watermarking with timestamp/location

### Backup & Sync
- [ ] Implement Restic automated backups (per SPEC.md)
- [ ] Cross-device sync
- [ ] Cloud backup options (S3, Google Drive, etc.)

### Developer Tools
- [ ] Debug mode with detailed logs
- [ ] Network traffic monitor
- [ ] Crypto key export/import for testing
- [ ] Mock location for testing

### Accessibility
- [ ] Voice commands for recording start/stop
- [ ] Screen reader support
- [ ] High contrast mode
- [ ] Larger touch targets

---

## 📝 Documentation Needs

- [ ] Video tutorial for first-time setup
- [ ] FAQ section
- [ ] Troubleshooting guide
- [ ] Legal considerations document
- [ ] Privacy policy
- [ ] Terms of service

---

## 🐛 Known Issues

### iOS 26.3 Beta
- **Issue**: Debug mode crashes on iOS 26.3 (beta)
- **Workaround**: Use `--profile` or `--release` mode
- **Status**: Waiting for Flutter fix (Issue #163984)
- **ETA**: Unknown

### Camera Initialization
- **Issue**: First-time permission dialogs can be confusing
- **Solution**: Added better error messages and "Open Settings" button
- **Status**: Improved but could be better

---

## 🎯 Current Sprint (MVP)

- [x] Backend API with signature verification
- [x] Docker infrastructure
- [x] Flutter app with camera recording
- [x] Basic cryptographic signing (HMAC-SHA256)
- [x] Video upload with metadata
- [x] Local video gallery
- [x] Device registration
- [ ] **Test end-to-end recording and upload** ← YOU ARE HERE
- [ ] UI polish and iteration

---

## 📅 Roadmap

### Phase 1: MVP (Current)
Get basic functionality working end-to-end

### Phase 2: Security Hardening
Implement hardware-backed crypto, audit security

### Phase 3: Production Polish
UI/UX improvements, better error handling, documentation

### Phase 4: Advanced Features
Web dashboard, multi-user, advanced filtering

### Phase 5: Scale & Optimize
Performance improvements, backup automation, monitoring

---

**Last Updated**: 2026-01-31
**Status**: MVP Development
**Next Milestone**: First successful end-to-end test recording
