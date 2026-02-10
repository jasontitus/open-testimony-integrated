#!/bin/bash
# Upload IPA to App Store Connect / TestFlight
#
# Prerequisites:
#   - API key file at ~/.appstoreconnect/private_keys/AuthKey_9FY5W363V5.p8
#   - IPA built via: flutter build ipa --export-options-plist=ios/ExportOptions.plist
#
# Usage: ./scripts/upload-testflight.sh

set -euo pipefail

API_KEY="9FY5W363V5"
API_ISSUER="69a6de81-894e-47e3-e053-5b8c7c11a4d1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IPA_DIR="$SCRIPT_DIR/../build/ios/ipa"
IPA_FILE="$IPA_DIR/open_testimony.ipa"

if [ ! -f "$IPA_FILE" ]; then
  echo "No IPA found. Building..."
  cd "$SCRIPT_DIR/.."
  flutter build ipa --export-options-plist=ios/ExportOptions.plist
fi

echo "Uploading $(basename "$IPA_FILE") to TestFlight..."
xcrun altool --upload-app --type ios \
  -f "$IPA_FILE" \
  --apiKey "$API_KEY" \
  --apiIssuer "$API_ISSUER"
