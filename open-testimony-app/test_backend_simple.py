#!/usr/bin/env python3
"""Simple backend test using only standard library"""
import urllib.request
import urllib.parse
import json
import hashlib
import base64
import hmac
from datetime import datetime
import os

BASE_URL = "http://localhost/api"
DEVICE_ID = f"test-device-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def test_health():
    """Test health endpoint"""
    print("\n🔍 Test 1: Health Check")
    req = urllib.request.Request(f"{BASE_URL}/health")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"✅ Status: {data['status']}")
        return True

def test_register():
    """Test device registration"""
    print(f"\n🔍 Test 2: Register Device ({DEVICE_ID})")
    
    # Create simple public key
    public_key_data = f'DEVICE:{DEVICE_ID}'
    public_key_b64 = base64.b64encode(public_key_data.encode()).decode()
    public_key_pem = f'-----BEGIN PUBLIC KEY-----\\n{public_key_b64}\\n-----END PUBLIC KEY-----'
    
    # Create form data
    data = {
        'device_id': DEVICE_ID,
        'public_key_pem': public_key_pem,
        'device_info': 'Test Client - macOS'
    }
    
    # Encode as form data
    encoded_data = urllib.parse.urlencode(data).encode()
    
    req = urllib.request.Request(f"{BASE_URL}/register-device", data=encoded_data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"✅ {result['message']}")
            return True, public_key_pem
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False, None

def test_upload(public_key_pem):
    """Test video upload"""
    print(f"\n🔍 Test 3: Upload Video")
    
    # Create test video
    test_video = f'/tmp/test_video_{DEVICE_ID}.mp4'
    with open(test_video, 'wb') as f:
        f.write(b'0' * 1024)
    
    # Calculate hash
    with open(test_video, 'rb') as f:
        video_hash = hashlib.sha256(f.read()).hexdigest()
    
    print(f"  Video hash: {video_hash}")
    
    # Create metadata
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    metadata = {
        'version': '1.0',
        'auth': {
            'device_id': DEVICE_ID,
            'public_key_pem': public_key_pem
        },
        'payload': {
            'video_hash': video_hash,
            'timestamp': timestamp,
            'location': {'lat': 37.7749, 'lon': -122.4194},
            'incident_tags': ['test'],
            'source': 'test'
        },
        'signature': 'dGVzdC1zaWduYXR1cmU='
    }
    
    metadata_json = json.dumps(metadata)
    
    # Create multipart form data manually
    boundary = '----WebKitFormBoundary' + base64.b64encode(os.urandom(16)).decode()[:16]
    
    with open(test_video, 'rb') as f:
        video_data = f.read()
    
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="metadata"\r\n\r\n'
        f'{metadata_json}\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="video"; filename="test.mp4"\r\n'
        f'Content-Type: video/mp4\r\n\r\n'
    ).encode() + video_data + f'\r\n--{boundary}--\r\n'.encode()
    
    req = urllib.request.Request(f"{BASE_URL}/upload", data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"✅ Uploaded! Video ID: {result['video_id']}")
            print(f"  Verification: {result['verification_status']}")
            os.remove(test_video)
            return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"❌ Upload failed ({e.code}): {error_body}")
        os.remove(test_video)
        return False
    except Exception as e:
        print(f"❌ Upload error: {e}")
        os.remove(test_video)
        return False

def test_list():
    """Test listing videos"""
    print(f"\n🔍 Test 4: List Videos")
    req = urllib.request.Request(f"{BASE_URL}/videos")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"✅ Found {data['count']} video(s)")
        for v in data['videos']:
            print(f"  - {v['id']}: {v['verification_status']}")
        return True

if __name__ == "__main__":
    print("=" * 60)
    print("Backend Upload Test (Standard Library)")
    print("=" * 60)
    
    try:
        test_health()
        success, public_key = test_register()
        if success:
            test_upload(public_key)
            test_list()
        
        print("\n" + "=" * 60)
        print("✅ Test Suite Complete!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
