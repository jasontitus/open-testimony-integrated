FROM python:3.11-slim

# System dependencies for OpenCV and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install PE-Core (perception_models) from source for vision encoding
# NOTE: decord==0.6.0 (transitive dep) may not build on macOS/ARM.
#       This works on Linux x86_64 Docker builds.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && git clone --depth 1 https://github.com/facebookresearch/perception_models.git /opt/perception_models \
    && pip install --no-cache-dir -e /opt/perception_models \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
