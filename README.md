# SpectraX — Unified Surveillance System

SpectraX is a streamlined surveillance system for turning any phone, tablet, or IP camera into a secure RTSP/HLS streaming source with object detection capabilities. It's built for people who need a simple, powerful, and private way to set up a surveillance system or a quick streaming solution.

> ⚠️ Note: SpectraX uses a self-signed certificate for RTSPS by default, which can trigger security warnings in some clients. For production use, replace it with a certificate from a trusted CA.

## Table of Contents

- [What It Does](#what-it-does)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Connecting Your Cameras](#connecting-your-cameras)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## What It Does

SpectraX wraps [MediaMTX](https://github.com/bluenviron/mediamtx), a powerful RTSP/HLS server, with intelligent object detection, tracking, and recording capabilities. The vision pipeline is built on [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) for detection and [Roboflow's supervision](https://github.com/roboflow/supervision) library for annotations and ByteTrack tracking. Turn any device with a camera into a smart surveillance system with advanced analytics in minutes.

## Key Features

### 🎥 Streaming
- **Multiple Protocols**: RTSP (low latency), RTSPS (encrypted), and HLS (browser-compatible)
- **Mobile-Ready**: Works with Larix Broadcaster and other RTSP apps
- **Multi-Camera Support**: Monitor multiple streams simultaneously
- **Automatic Credentials**: Secure, randomly generated passwords stored in system keychain

### 🤖 AI Object Detection
- **YOLO Integration**: Real-time object detection using YOLOv8 models
- **Customizable Models**: Choose from nano (fast) to large (accurate) models
- **Smart Filtering**: Detect specific objects (person, car, dog, etc.)
- **Visual Overlays**: Bounding boxes and labels rendered with [Roboflow supervision](https://github.com/roboflow/supervision) annotators
- **Adjustable Confidence**: Fine-tune detection sensitivity

### 🎯 Object Tracking (NEW!)
- **Persistent IDs**: Track individual objects across frames with unique IDs
- **ByteTrack Integration**: State-of-the-art multi-object tracking via [Roboflow supervision](https://github.com/roboflow/supervision)
- **Visual Feedback**: See tracker IDs in labels (e.g., "person #42 0.95")
- **Database Storage**: Query recordings by specific tracker ID
- **Analytics**: Track which objects appear most frequently
- **Configurable**: Adjust tracking parameters for your use case

### 📹 Event-Based Recording
- **Intelligent Recording**: Automatically record when objects are detected
- **Pre/Post Buffers**: Capture 10 seconds before and after detections
- **Selective Recording**: Only record specific object types
- **SQLite Database**: Searchable metadata for all recordings
- **Storage Management**: Automatic cleanup when storage limits reached

### 🌐 Web Dashboard
- **Live Viewing**: Real-time video with AI detection overlays
- **Recordings Browser**: View and manage all recorded clips
- **Multi-Camera Grid**: Monitor all cameras in one interface
- **REST API**: Access recordings and statistics programmatically
- **Responsive Design**: Works on desktop and mobile browsers

### 🔐 Security
- **RTSPS Encryption**: TLS-encrypted RTSP streams
- **Credential Management**: Secure storage using OS keyring
- **Network Isolation**: Bind to localhost or specific interfaces
- **Self-Signed Certificates**: Included for immediate use

## Quick Start

### Prerequisites

**System Requirements:**
- macOS, Linux, or Windows
- Python 3.8 or higher
- 4GB RAM minimum (8GB recommended for multiple cameras)
- Tested on macOS Sequoia 15.4.1

**Required Software:**

1. **MediaMTX** - RTSP/HLS streaming server
   ```bash
   # macOS
   brew install mediamtx
   
   # Linux
   # Download from https://github.com/bluenviron/mediamtx/releases
   
   # Windows
   # Download from https://github.com/bluenviron/mediamtx/releases
   ```

2. **Python 3.8+**
   ```bash
   python3 --version  # Check your version
   ```

**Recommended Clients:**
- **Mobile Publishing**: [Larix Broadcaster](https://softvelum.com/larix/) (iOS/Android)
- **Desktop Viewing**: [OBS Studio](https://obsproject.com/) or VLC Media Player

### Installation

1. **Clone and Setup**

```bash
# Clone the repository
git clone https://github.com/SpectraCoreX/SpectraX.git
cd SpectraX

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: .\venv\Scripts\activate  # Windows

# Install dependencies
cd video-feed
pip install -r requirements.txt
cd ..
```

2. **Download YOLO Models** (optional - will auto-download on first use)

```bash
cd video-feed/models
wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8l.pt
cd ../..
```

3. **Configure Your System**

Edit `video-feed/config/surveillance.yml` to set your camera paths and preferences (see [Configuration Guide](docs/CONFIGURATION_GUIDE.md) for details).

### Start the System

```bash
# Start with configuration file (recommended)
./scripts/surveillance.sh config

# Quick start with defaults (1 camera at video/camera-1)
./scripts/surveillance.sh quick

# Open standalone web dashboard
./scripts/surveillance.sh dashboard
```

The system will display connection URLs for your cameras and the web interface.

## Basic Usage

### Web Dashboard

Access the web interface at the URL shown when starting the system (e.g., `http://192.168.x.x:8080`):

- **Live Video**: Real-time streams with AI detection overlays
- **Multi-Camera Grid**: View all cameras simultaneously
- **Recordings Browser**: Search and play recorded clips
- **Statistics**: FPS, detection counts, and system status

### Command Line

```bash
# Start with configuration file (recommended)
./scripts/surveillance.sh config

# Quick start with defaults
./scripts/surveillance.sh quick

# Start streaming server only (no detection)
python -m spectrax.surveillance run --path video/front-door

# Start detection only (existing stream)
python -m spectrax.surveillance detect --rtsp-url "rtsps://viewer:pass@host:8322/video/cam"

# Query recordings by tracker ID
python scripts/query_recordings.py tracker 42

# Reset stored credentials
python -m spectrax.surveillance reset
```

### REST API

Access recordings and system data programmatically:

```bash
# Get system status
curl http://localhost:8080/status

# List all recordings
curl http://localhost:8080/api/recordings

# Get recording statistics
curl http://localhost:8080/api/recordings/stats
```

See [API Documentation](docs/API.md) for complete endpoint reference.

## Configuration

All settings are managed in `video-feed/config/surveillance.yml`. 

**Quick example:**
```yaml
cameras:
  - video/front-door
  - video/backyard

detection:
  enabled: true
  model: "yolov8n.pt"
  confidence: 0.4
  filters:
    classes: ["person", "car", "dog"]

recording:
  enabled: true
  max_storage_gb: 10.0
```

For complete configuration options, see the [Configuration Guide](docs/CONFIGURATION_GUIDE.md).

## Connecting Your Cameras

When the system starts, it displays connection URLs:

**📱 For Mobile Cameras (Publishing):**
1. Install [Larix Broadcaster](https://softvelum.com/larix/) on your phone
2. Use the RTSPS URL shown in the terminal
3. Enter the publisher username and password
4. Start streaming!

**🖥️ For Viewing:**
- **Web Dashboard**: Open the URL shown (e.g., `http://192.168.x.x:8080`)
- **OBS/VLC**: Use the viewer RTSPS URL with credentials
- **Browser HLS**: Use the HLS URL for browser-based viewing

## Documentation

### For Users
- **[Configuration Guide](docs/CONFIGURATION_GUIDE.md)** - Complete configuration reference
- **[Tracking Guide](docs/tracking_usage_guide.md)** - Object tracking features and usage
- **[Recording Setup](docs/RECORDING_SETUP.md)** - Event-based recording configuration

### For Developers
- **[API Documentation](docs/API.md)** - REST API reference for building clients
- **[Architecture Guide](docs/ARCHITECTURE.md)** - Codebase structure and development guide

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

See the [Architecture Guide](docs/ARCHITECTURE.md) for codebase details.

## License

See [LICENSE](LICENSE) file for details.

## Acknowledgments

- [MediaMTX](https://github.com/bluenviron/mediamtx) - Excellent RTSP/HLS server
- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) - State-of-the-art object detection
- [Roboflow Supervision](https://github.com/roboflow/supervision) - Computer vision utilities, annotators, and ByteTrack integration
- [ByteTrack](https://github.com/ifzhang/ByteTrack) - Multi-object tracking algorithm
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
