# Quick Start Guide

## Backend Setup (5 minutes)

1. **Start the backend:**
   ```bash
   cd open-testimony-app
   docker-compose up -d
   ```

2. **Verify it's running:**
   ```bash
   curl http://localhost/api/health
   ```

3. **Find your server IP address:**
   ```bash
   # On Linux/Mac:
   ifconfig | grep "inet "
   
   # Or:
   hostname -I
   ```

## Mobile App Setup (10 minutes)

1. **Install dependencies:**
   ```bash
   cd mobile-app
   flutter pub get
   ```

2. **Configure server URL:**
   
   Edit `lib/services/upload_service.dart`, line 8:
   ```dart
   static const String baseUrl = 'http://YOUR_SERVER_IP/api';
   ```
   
   Replace `YOUR_SERVER_IP` with the IP from step 3 above.

3. **Run the app:**
   ```bash
   # For Android:
   flutter run
   
   # For iOS:
   open ios/Runner.xcworkspace
   # Then run from Xcode
   ```

4. **Register your device:**
   - Open app → Settings tab
   - Tap "Register Device"
   - Wait for success message

5. **Record a video:**
   - Go to Record tab
   - Grant permissions (camera, mic, location)
   - Tap red button to record
   - Tap again to stop
   - Video uploads automatically

## Troubleshooting

**Backend won't start:**
```bash
docker-compose logs -f
```

**Mobile app can't connect:**
- Check server IP is correct in `upload_service.dart`
- Make sure phone and server are on same network
- Try `http://` not `https://` for local testing
- Check firewall allows port 80

**Camera won't open:**
- Grant all permissions in device settings
- Restart the app

**Upload fails:**
- Register device first in Settings
- Check server is running: `curl http://YOUR_SERVER_IP/api/health`
- Check logs: `docker-compose logs api`

## Need Help?

Check the full [README.md](README.md) for detailed documentation.
