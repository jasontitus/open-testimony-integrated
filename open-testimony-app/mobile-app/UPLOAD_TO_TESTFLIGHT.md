# Upload to TestFlight when “Copy failed” happens

Both **Distribute App** in Xcode and **flutter build ipa** can fail with “Copy failed” / “exportArchive Copy failed”. Use the archive Flutter already built and upload from Xcode Organizer with a path that has **no spaces**.

**Important:** Do **not** distribute from archives in `~/Library/Developer/Xcode/Archives/` (e.g. `Runner 2.xcarchive`) — the space and suffix often trigger “Copy failed”. Always use the Flutter-built archive path below (or the `/tmp` copy if that still fails).

## Step 1: Use the archive Flutter built

Flutter created the archive here (path has **no spaces**):

**`mobile-app/build/ios/archive/Runner.xcarchive`**

## Step 2: Open it in Xcode and distribute

1. **Open the archive in Xcode:**
   ```bash
   open /Users/jasontitus/experiments/open-testimony-app/mobile-app/build/ios/archive/Runner.xcarchive
   ```
   Xcode Organizer will open with this archive.

2. **Distribute App**
   - Click **Distribute App**.
   - Choose **App Store Connect** → **Upload**.
   - Use your Apple ID and follow the prompts.

Because the archive path is `.../Runner.xcarchive` (no spaces or commas), the copy step may succeed here when it failed for archives under `~/Library/Developer/Xcode/Archives/` (e.g. `OpenTestimony 1-31-26, 4.12 PM.xcarchive`).

## If it still fails: try from a minimal path

1. Copy the archive to a short path with no spaces:
   ```bash
   cp -R /Users/jasontitus/experiments/open-testimony-app/mobile-app/build/ios/archive/Runner.xcarchive /tmp/Runner.xcarchive
   ```
2. Open that copy:
   ```bash
   open /tmp/Runner.xcarchive
   ```
3. In Organizer, click **Distribute App** again and upload.

## After a successful upload

1. Go to [App Store Connect](https://appstoreconnect.apple.com) → **My Apps** → your app → **TestFlight**.
2. Wait for the build to finish processing (often 5–15 minutes).
3. Add testers by **email** (their Apple ID). They get an invite to install via the TestFlight app.

---

**Note:** `flutter build ipa` fails at the same “Copy failed” step when creating the IPA. The `ios/ExportOptions.plist` file is for manual `xcodebuild -exportArchive`; if that also fails, the Organizer method above is the main workaround.
