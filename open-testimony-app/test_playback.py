import requests
import sys
from urllib.parse import urlparse

def test_video_playback():
    print("--- Open Testimony Playback Tester ---")
    
    # 1. Get the list of videos
    print("\n1. Fetching video list from API...")
    try:
        resp = requests.get("http://localhost/api/videos")
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        
        if not videos:
            print("❌ No videos found in the database. Please upload a video first.")
            return
        
        video = videos[0]
        video_id = video['id']
        print(f"✅ Found {len(videos)} videos. Testing video ID: {video_id}")
        
    except Exception as e:
        print(f"❌ Failed to fetch videos: {e}")
        return

    # 2. Get the presigned URL
    print(f"\n2. Fetching presigned URL for video {video_id}...")
    try:
        resp = requests.get(f"http://localhost/api/videos/{video_id}/url")
        resp.raise_for_status()
        url = resp.json().get("url")
        print(f"✅ Received URL: {url}")
    except Exception as e:
        print(f"❌ Failed to fetch URL: {e}")
        return

    # 3. Test the original URL (likely localhost:9000)
    print("\n3. Testing original URL...")
    try:
        resp = requests.head(url)
        
        if resp.status_code == 200:
            print(f"✅ SUCCESS on {url}")
            print(f"   Content-Type: {resp.headers.get('Content-Type')}")
            print(f"   Content-Length: {resp.headers.get('Content-Length')} bytes")
            return
        elif resp.status_code == 403:
            print(f"❌ FORBIDDEN (403) on {url}")
        else:
            print(f"❌ FAILED with status code: {resp.status_code}")
            
    except Exception as e:
        print(f"❌ Network error: {e}")
    
    # 4. Try the Nginx proxy path
    print("\n4. Testing through Nginx proxy at /video-stream/...")
    try:
        # Replace localhost:9000 with localhost/video-stream
        parsed = urlparse(url)
        proxy_url = f"http://localhost/video-stream{parsed.path}?{parsed.query}"
        print(f"   Proxy URL: {proxy_url[:80]}...")
        
        resp = requests.head(proxy_url)
        
        if resp.status_code == 200:
            print("✅ SUCCESS through Nginx proxy!")
            print(f"   Content-Type: {resp.headers.get('Content-Type')}")
            print(f"   Content-Length: {resp.headers.get('Content-Length')} bytes")
        elif resp.status_code == 403:
            print("❌ Still FORBIDDEN through Nginx proxy")
        else:
            print(f"❌ Status: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            
    except Exception as e:
        print(f"❌ Network error: {e}")

if __name__ == "__main__":
    test_video_playback()
