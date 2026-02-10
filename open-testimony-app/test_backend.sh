#!/bin/bash
# Test backend with curl

BASE_URL="http://localhost/api"
DEVICE_ID="test-device-$(date +%s)"

echo "======================================"
echo "Backend Upload Test"
echo "======================================"

# Test 1: Health check
echo -e "\n🔍 Test 1: Health Check"
curl -s "$BASE_URL/health" | python3 -m json.tool

# Test 2: Register device
echo -e "\n🔍 Test 2: Register Device"
PUBLIC_KEY_B64=$(echo -n "DEVICE:$DEVICE_ID" | base64)
PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----
$PUBLIC_KEY_B64
-----END PUBLIC KEY-----"

curl -X POST "$BASE_URL/register-device" \
  -F "device_id=$DEVICE_ID" \
  -F "public_key_pem=$PUBLIC_KEY_PEM" \
  -F "device_info=Test Client - macOS" \
  -w "\nHTTP Status: %{http_code}\n"

# Test 3: Create test video
echo -e "\n🔍 Test 3: Create Test Video"
TEST_VIDEO="/tmp/test_video_$DEVICE_ID.mp4"
dd if=/dev/zero of="$TEST_VIDEO" bs=1024 count=1 2>/dev/null
echo "Created: $TEST_VIDEO"

# Calculate video hash
VIDEO_HASH=$(shasum -a 256 "$TEST_VIDEO" | awk '{print $1}')
echo "Video hash: $VIDEO_HASH"

# Test 4: Upload video
echo -e "\n🔍 Test 4: Upload Video"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000000Z")

# Create metadata JSON
METADATA=$(cat <<'EOF'
{
  "version": "1.0",
  "auth": {
    "device_id": "DEVICE_ID_PLACEHOLDER",
    "public_key_pem": "PUBLIC_KEY_PLACEHOLDER"
  },
  "payload": {
    "video_hash": "VIDEO_HASH_PLACEHOLDER",
    "timestamp": "TIMESTAMP_PLACEHOLDER",
    "location": {
      "lat": 37.7749,
      "lon": -122.4194
    },
    "incident_tags": ["test"],
    "source": "test"
  },
  "signature": "dGVzdC1zaWduYXR1cmU="
}
EOF
)

# Replace placeholders with escaped values
PUBLIC_KEY_ESCAPED=$(echo "$PUBLIC_KEY_PEM" | sed ':a;N;$!ba;s/\n/\\n/g')
METADATA=$(echo "$METADATA" | sed "s|DEVICE_ID_PLACEHOLDER|$DEVICE_ID|g")
METADATA=$(echo "$METADATA" | sed "s|PUBLIC_KEY_PLACEHOLDER|$PUBLIC_KEY_ESCAPED|g")
METADATA=$(echo "$METADATA" | sed "s|VIDEO_HASH_PLACEHOLDER|$VIDEO_HASH|g")
METADATA=$(echo "$METADATA" | sed "s|TIMESTAMP_PLACEHOLDER|$TIMESTAMP|g")

echo "Uploading..."
curl -X POST "$BASE_URL/upload" \
  -F "video=@$TEST_VIDEO;type=video/mp4" \
  -F "metadata=$METADATA" \
  -w "\nHTTP Status: %{http_code}\n" \
  -v 2>&1 | grep -E "(HTTP|status|error|success)"

# Test 5: List videos
echo -e "\n🔍 Test 5: List Videos"
curl -s "$BASE_URL/videos" | python3 -m json.tool

# Cleanup
rm -f "$TEST_VIDEO"

echo -e "\n======================================"
echo "Tests Complete!"
echo "======================================"
