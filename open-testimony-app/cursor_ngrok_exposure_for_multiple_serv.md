# Ngrok exposure for multiple services
_Exported on 1/31/2026 at 12:36:34 PST from Cursor (2.4.23)_

---

**User**

How can I use ngrok to expose both the API endpoints and the webUI for this project?  I also have a video search project I will want to expose through ngrok as well.  Do I need to merge all of them into paths off the same server URL? 

---

**Cursor**

I'll help you set up ngrok to expose your services. Let me first understand your project architecture.

Perfect! I can see your architecture. You have nginx acting as a reverse proxy that routes to different services. Here's how to set up ngrok for your scenarios:

## Option 1: Single ngrok Tunnel (Recommended for Development)

Since you already have nginx routing everything through different paths, you can **use a single ngrok tunnel** to expose everything:

- Web UI: `https://<ngrok-url>/`
- API: `https://<ngrok-url>/api/`
- MinIO Console: `https://<ngrok-url>/minio/`
- Video Streaming: `https://<ngrok-url>/video-stream/`

### Setup:
```bash
# Start your services
docker-compose up -d

# Expose nginx on port 80
ngrok http 80
```

This is the **simplest approach** and leverages your existing nginx routing.

## Option 2: Separate Tunnels for Each Project

If you want your video search project on a separate URL, you can run **multiple ngrok tunnels simultaneously**:

```bash
# Terminal 1: Open Testimony (nginx on port 80)
ngrok http 80 --region us

# Terminal 2: Video Search Project (assuming it runs on port 3000)
ngrok http 3000 --region us
```

Each will get its own unique `*.ngrok-free.app` URL.

## Option 3: ngrok with Custom Domains (Paid Feature)

If you have an ngrok paid plan, you can use custom domains or subdomain routing:

```bash
ngrok http 80 --domain=testimony.yourdomain.com
ngrok http 3000 --domain=videosearch.yourdomain.com
```

## Recommendation for Your Use Case

Based on your nginx configuration, I'd recommend:

**For Development/Testing:**
- Use **Option 1** (single tunnel) for the open-testimony-app since nginx already handles routing
- Use **Option 2** if your video search project is completely separate

**Important Considerations:**

1. **Update API Base URL:** Your Flutter app will need to use the ngrok URL instead of localhost. You can set this in environment variables.

2. **ngrok Config File:** Create `~/.ngrok2/ngrok.yml` to manage multiple tunnels:

```yaml
version: "2"
authtoken: YOUR_NGROK_AUTH_TOKEN
tunnels:
  testimony:
    proto: http
    addr: 80
  videosearch:
    proto: http
    addr: 3000
```

Then start both:
```bash
ngrok start testimony videosearch
```

3. **CORS Configuration:** Make sure your FastAPI backend allows the ngrok domain in CORS settings.

Do you want me to help you set up any specific option, or configure your Flutter app to work with ngrok URLs?

---

**User**

I already have this custom tunnel and would want to use a single tunnel.  https://opentestimony.ngrok.app 

---

**Cursor**

Perfect! Since you already have `https://opentestimony.ngrok.app`, you can expose both projects through **path-based routing** under that single domain.

## Architecture Approach

You'll need a **unified reverse proxy** that routes requests to both projects. Here are two options:

### Option A: Add Video Search Routes to Your Existing Nginx

Modify your existing nginx config to add routes for the video search project:

```nginx
# Open Testimony Web UI
location / {
    proxy_pass http://web-ui:80/;
    ...
}

# Open Testimony API
location /api/ {
    proxy_pass http://api:8000/;
    ...
}

# Video Search Project (new)
location /search/ {
    proxy_pass http://localhost:3000/;  # or wherever your video search runs
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

**URLs would be:**
- Video Search: `https://opentestimony.ngrok.app/search/`
- Testimony Web UI: `https://opentestimony.ngrok.app/testimony/`
- Testimony API: `https://opentestimony.ngrok.app/api/`

### Option B: Top-Level Nginx Routing to Both Projects (Recommended)

Create a **new top-level nginx** that routes to both your existing Open Testimony nginx and your video search app:

**New file:** `nginx-unified/default.conf`

```nginx
server {
    listen 8080;
    server_name localhost;

    # Video Search Project (keep at root since it's already live)
    location / {
        proxy_pass http://localhost:3000/;  # Your video search port
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Open Testimony - Full Stack
    location /testimony/ {
        proxy_pass http://localhost:80/;  # Your existing nginx
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Open Testimony - Direct API Access
    location /testimony-api/ {
        proxy_pass http://localhost:80/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then:
```bash
# Start Open Testimony services
docker-compose up -d

# Start video search (on port 3000, for example)
# ...

# Start unified nginx (on port 8080)
nginx -c /path/to/nginx-unified/default.conf

# Expose unified nginx through ngrok
ngrok http 8080 --domain=opentestimony.ngrok.app
```

**URLs would be:**
- Video Search: `https://opentestimony.ngrok.app/` (current)
- Testimony Web UI: `https://opentestimony.ngrok.app/testimony/`
- Testimony API: `https://opentestimony.ngrok.app/testimony-api/`

## Which ports are your projects currently using?

To give you the exact configuration, I need to know:
1. What port is your video search app running on?
2. What port is your Open Testimony nginx currently exposed on? (Looks like 80 from docker-compose)

Would you like me to create the unified nginx configuration file for you once I know these details?

