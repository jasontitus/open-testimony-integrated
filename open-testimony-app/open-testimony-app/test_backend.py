#!/usr/bin/env python3
"""
Test script to verify backend upload functionality
"""
import requests
import hashlib
import json
import base64
import hmac
from datetime import datetime
import os

# Configuration
BASE_URL = "http://localhost/api"
DEVICE_ID = "test-device-001"
TEST_VIDEO_PATH = "/tmp/test_video.mp4"

def create_test_video():
    """Create a small test video file"""
    # Create a small dummy file (1KB)
    with open(TEST_VIDEO_PATH, 'wb') as f:
        f.write(b'0' * 1024)
    print(f"✅ Created test video: {TEST_VIDEO_PATH}")

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of file"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        sha256.update(f.read())
    return sha256.hexdigest()

def generate_signing_key():
    """Generate a test signing key"""
    import random
    key_bytes = bytes([random.randint(0, 255) for _ in range(32)])
    return base64.b64encode(key_bytes).decode()

def create_signature(data, key_b64):
    """Create HMAC signature"""
    key_bytes = base64.b64decode(key_b64)
    data_bytes = data.encode()
    signature = hmac.new(key_bytes, data_bytes, hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

def test_health():
    """Test health endpoint"""
    print("\n🔍 Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_register_device(device_id, signing_key):
    """Test device registration"""
    print(f"\n🔍 Testing device registration for: {device_id}")
    
    # Create public key in MVP format
    public_key_data = f'DEVICE:{device_id}'
    public_key_b64 = base64.b64encode(public_key_data.encode()).decode()
    public_key_pem = f'-----BEGIN PUBLIC KEY-----\n{public_key_b64}\n-----END PUBLIC KEY-----'
    
    data = {
        'device_id': device_id,
        'public_key_pem': public_key_pem,
        'device_info': 'Test client - macOS'
    }
    
    print(f"Payload: {data}")
    
    response = requests.post(f"{BASE_URL}/register-device", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    return response.status_code == 200, public_key_pem

def test_upload_video(device_id, public_key_pem, signing_key):
    """Test video upload"""
    print(f"\n🔍 Testing video upload for device: {device_id}")
    
    # Calculate video hash
    video_hash = calculate_file_hash(TEST_VIDEO_PATH)
    print(f"Video hash: {video_hash}")
    
    # Create metadata payload
    timestamp = datetime.utcnow().isoformat() + 'Z'
    payload = {
        'video_hash': video_hash,
        'timestamp': timestamp,
        'location': {
            'lat': 37.7749,
            'lon': -122.4194
        },
        'incident_tags': ['test'],
        'source': 'test'
    }
    
    # Sign payload
    payload_json = json.dumps(payload, sort_keys=True)
    signature = create_signature(payload_json, signing_key)
    
    # Create full metadata
    metadata = {
        'version': '1.0',
        'auth': {
            'device_id': device_id,
            'public_key_pem': public_key_pem
        },
        'payload': payload,
        'signature': signature
    }
    
    print(f"Metadata: {json.dumps(metadata, indent=2)}")
    
    # Upload
    with open(TEST_VIDEO_PATH, 'rb') as video_file:
        files = {
            'video': ('test_video.mp4', video_file, 'video/mp4')
        }
        data = {
            'metadata': json.dumps(metadata)
        }
        
        response = requests.post(f"{BASE_URL}/upload", files=files, data=data)
        
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    return response.status_code == 200

def test_list_videos():
    """Test video listing"""
    print(f"\n🔍 Testing video list...")
    response = requests.get(f"{BASE_URL}/videos")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def main():
    """Run all tests"""
    print("=" * 60)
    print("Backend Upload Test Suite")
    print("=" * 60)
    
    # Create test video
    create_test_video()
    
    # Generate signing key
    signing_key = generate_signing_key()
    print(f"\n🔑 Generated signing key: {signing_key[:20]}...")
    
    # Test 1: Health check
    if not test_health():
        print("❌ Health check failed!")
        return
    
    # Test 2: Register device
    success, public_key_pem = test_register_device(DEVICE_ID, signing_key)
    if not success:
        print("❌ Device registration failed!")
        return
    
    # Test 3: Upload video
    if not test_upload_video(DEVICE_ID, public_key_pem, signing_key):
        print("❌ Video upload failed!")
        return
    
    # Test 4: List videos
    if not test_list_videos():
        print("❌ Video listing failed!")
        return
    
    # Cleanup
    os.remove(TEST_VIDEO_PATH)
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
