# Running the Mobile App

## Quick Options

### Option 1: Use Android Studio Emulator

1. **Open Android Studio**
2. Click **Device Manager** (phone icon in top right)
3. Click **Create Device**
4. Select a device (e.g., Pixel 7) → Next
5. Select a system image (e.g., API 34) → Next → Finish
6. Click the **Play** button to start the emulator

Once the emulator is running:
```bash
cd mobile-app
flutter run
```

### Option 2: Use iOS Simulator (Mac with Xcode)

1. **Open Xcode** → Preferences → Components
2. Download an iOS Simulator if needed
3. Launch simulator:
   ```bash
   xcrun simctl list devices
   # Find a device like "iPhone 15 Pro"
   xcrun simctl boot "iPhone 15 Pro"
   open -a "Simulator"
   ```

Once the simulator is running:
```bash
cd mobile-app
flutter run
```

### Option 3: Use Physical Device (Recommended for Camera Testing)

**For Android:**
1. Enable **Developer Options** on your Android phone:
   - Settings → About Phone → Tap "Build Number" 7 times
2. Enable **USB Debugging**:
   - Settings → Developer Options → USB Debugging
3. Connect phone via USB
4. Run:
   ```bash
   cd mobile-app
   flutter run
   ```

**For iPhone:**
1. Connect iPhone via USB
2. Open `ios/Runner.xcworkspace` in Xcode
3. Select your device in Xcode
4. Change Bundle Identifier to something unique (e.g., com.yourname.opentestimony)
5. Select your Apple Developer account in Signing & Capabilities
6. Run from Xcode or:
   ```bash
   flutter run
   ```

## Common Issues

### Flutter Permission Error
If you see lockfile permission errors:
```bash
sudo chown -R $(whoami) /opt/homebrew/Caskroom/flutter/
```

### No Devices Available
```bash
# Check available devices
flutter devices

# If no devices, you need to:
# - Launch an emulator/simulator, OR
# - Connect a physical device
```

### Camera Won't Work on Simulator
**Note:** Camera functionality requires a physical device. Simulators/emulators have limited camera support. For full testing, use a real phone.

## Before Running - Configure Server URL

Edit `lib/services/upload_service.dart`:

```dart
static const String baseUrl = 'http://YOUR_IP_HERE/api';
```

**Find your IP:**
- Mac: System Settings → Network → WiFi → Details → IP Address
- Linux: `ip addr show`
- Windows: `ipconfig`

**Important:** Use your computer's local IP (e.g., `192.168.1.100`), not `localhost`, if testing on a physical device.

## Full Development Setup

If this is your first time with Flutter, install the prerequisites:

### macOS
```bash
# Install Xcode from App Store
# Install Xcode command line tools
xcode-select --install

# Install Android Studio from https://developer.android.com/studio
```

### All Platforms
```bash
# Verify Flutter is set up correctly
flutter doctor

# Fix any issues flutter doctor reports
```

## Testing Workflow

1. **Start backend:**
   ```bash
   cd open-testimony-app
   docker-compose up -d
   ```

2. **Update server URL** in `upload_service.dart`

3. **Launch device/emulator**

4. **Run app:**
   ```bash
   cd mobile-app
   flutter run
   ```

5. **In the app:**
   - Go to Settings → Register Device
   - Go to Record → Grant permissions
   - Record a test video

6. **Verify upload:**
   ```bash
   curl http://localhost/api/videos
   ```
