# SpectraX Architecture Guide

This document provides a comprehensive overview of the SpectraX codebase architecture for developers who want to contribute to or modify the system.

## Table of Contents

- [Project Structure](#project-structure)
- [Core Modules](#core-modules)
- [Data Flow](#data-flow)
- [Key Components](#key-components)
- [Development Setup](#development-setup)
- [Testing](#testing)
- [Contributing Guidelines](#contributing-guidelines)

---

## Project Structure

```
root/
├── video-feed/                 # 📦 Main Python package
│   ├── spectrax/              # Core modules
│   │   ├── surveillance.py    # 🎯 MAIN ENTRY POINT - Unified CLI
│   │   ├── config.py          # 🔧 Configuration management
│   │   ├── detector.py        # 🎯 YOLO object detection
│   │   ├── recorder.py        # 📹 Event-based recording
│   │   ├── visualizer.py      # 🌐 Web interface & API
│   │   ├── credentials.py     # 🔐 Secure credential management
│   │   ├── api.py             # 🔗 Recordings database API
│   │   ├── utils.py           # 🛠️ Utility functions
│   │   ├── constants.py       # 📋 Shared constants
│   │   └── templates/         # 🎨 Web interface templates
│   ├── config/                # ⚙️ Configuration files
│   │   └── surveillance.yml   # Main config file
│   ├── models/                # 🤖 YOLO models
│   ├── ui/                    # 🖥️ Web dashboards
│   ├── tests/                 # 🧪 Test suite
│   ├── setup.py               # Package setup
│   └── requirements.txt       # Python dependencies
├── scripts/                   # 🚀 Helper scripts
│   ├── surveillance.sh        # Main launcher
│   └── surveillance.service   # Systemd service
├── docs/                      # 📚 Documentation
└── README.md                  # Project overview
```

---

## Core Modules

### 1. surveillance.py - Main Entry Point

**Purpose:** Unified command-line interface for all system operations.

**Key Functions:**
- `main()` - Entry point with argument parsing
- `cmd_config()` - Start with YAML configuration
- `cmd_start()` - Start with CLI options
- `cmd_quick()` - Quick start with defaults
- `cmd_run()` - Start streaming server only
- `cmd_detect()` - Start detection only
- `cmd_reset()` - Reset credentials

**Architecture:**
```python
# Command pattern with subcommands
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

# Each command is a separate function
config_parser = subparsers.add_parser('config')
config_parser.set_defaults(func=cmd_config)
```

**Dependencies:**
- `config.py` - Configuration loading
- `credentials.py` - Credential management
- `detector.py` - Object detection
- `visualizer.py` - Web interface

---

### 2. config.py - Configuration Management

**Purpose:** Parse and validate YAML configuration files.

**Key Classes:**
- `SurveillanceConfig` - Main configuration class
  - `load_from_yaml()` - Load and parse YAML
  - `validate()` - Validate configuration
  - `get_camera_paths()` - Extract camera paths
  - `get_detection_config()` - Extract detection settings

**Configuration Schema:**
```python
@dataclass
class SurveillanceConfig:
    cameras: List[str]
    network: NetworkConfig
    detection: DetectionConfig
    recording: RecordingConfig
    appearance: AppearanceConfig
    security: SecurityConfig
```

**Usage:**
```python
from spectrax.config import SurveillanceConfig

config = SurveillanceConfig.load_from_yaml('config/surveillance.yml')
cameras = config.get_camera_paths()
```

---

### 3. detector.py - Object Detection

**Purpose:** YOLO-based object detection with multi-camera support and tracking.

**Key Classes:**
- `ObjectDetector` - Main detection class
  - `__init__(model_path, confidence, ...)` - Initialize YOLO model
  - `detect(frame)` - Run detection on single frame
  - `process_stream(rtsp_url)` - Process video stream
  - `get_detections()` - Get current detections

**Architecture:**
```python
class ObjectDetector:
    def __init__(self, model_path, confidence=0.4):
        self.model = YOLO(model_path)
        self.tracker = ByteTrack() if tracking_enabled else None
        self.frame_buffer = deque(maxlen=buffer_size)
    
    def detect(self, frame):
        # Run YOLO inference
        results = self.model(frame, conf=self.confidence)
        
        # Apply tracking if enabled
        if self.tracker:
            detections = self._apply_tracking(results)
        
        # Filter detections
        filtered = self._filter_detections(detections)
        
        return filtered
```

**Detection Pipeline:**
1. Read frame from RTSP stream
2. Run YOLO inference
3. Apply ByteTrack tracking (if enabled)
4. Filter by class, confidence, area
5. Draw bounding boxes and labels
6. Buffer frames for recording
7. Trigger recording on detection

**Integration with Supervision:**
```python
from supervision import ByteTrack, Detections

# Convert YOLO results to Supervision format
detections = Detections.from_ultralytics(results)

# Apply tracking
tracked = self.tracker.update_with_detections(detections)
```

---

### 4. recorder.py - Event-Based Recording

**Purpose:** Record video clips when objects are detected.

**Key Classes:**
- `EventRecorder` - Main recording class
  - `__init__(output_dir, pre_buffer, post_buffer)` - Initialize recorder
  - `add_frame(frame, timestamp)` - Add frame to buffer
  - `start_recording(detections)` - Start recording on detection
  - `stop_recording()` - Finalize recording
  - `save_metadata(detections)` - Save to database

**Recording State Machine:**
```
IDLE → RECORDING → POST_BUFFER → IDLE
  ↑                                  ↓
  └──────────────────────────────────┘
```

**Architecture:**
```python
class EventRecorder:
    def __init__(self, output_dir, pre_buffer_seconds=10, post_buffer_seconds=10):
        self.state = RecordingState.IDLE
        self.frame_buffer = deque(maxlen=pre_buffer_frames)
        self.recording_frames = []
        self.post_buffer_counter = 0
    
    def add_frame(self, frame, timestamp, detections):
        # Always buffer frames
        self.frame_buffer.append((frame, timestamp))
        
        if detections and self.state == RecordingState.IDLE:
            # Start recording with pre-buffer
            self.start_recording()
        
        if self.state == RecordingState.RECORDING:
            self.recording_frames.append((frame, timestamp))
            
            if not detections:
                self.post_buffer_counter += 1
                if self.post_buffer_counter > post_buffer_frames:
                    self.stop_recording()
```

**Database Schema:**
```sql
CREATE TABLE recordings (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    stream_path TEXT,
    duration_seconds REAL,
    file_path TEXT,
    objects_detected TEXT,  -- JSON
    tracker_ids TEXT,       -- JSON
    max_confidence REAL
);
```

---

### 5. visualizer.py - Web Interface

**Purpose:** FastAPI web server with live video streaming and recordings browser.

**Key Components:**
- FastAPI app with routes
- MJPEG video streaming
- Jinja2 templates
- REST API endpoints

**Architecture:**
```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/video/stream")
async def video_stream(path: str = None):
    return StreamingResponse(
        generate_frames(path),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/api/recordings")
async def list_recordings(limit: int = 100, offset: int = 0):
    recordings = db.query_recordings(limit, offset)
    return {"recordings": recordings}
```

**MJPEG Streaming:**
```python
async def generate_frames(camera_path):
    while True:
        frame = detector.get_latest_frame(camera_path)
        if frame is not None:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            
            # Yield as multipart response
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + 
                   buffer.tobytes() + b'\r\n')
        
        await asyncio.sleep(0.033)  # ~30 FPS
```

---

### 6. credentials.py - Credential Management

**Purpose:** Secure storage and retrieval of RTSP credentials using OS keyring.

**Key Functions:**
- `generate_credentials()` - Generate random passwords
- `store_credentials(service, username, password)` - Store in keyring
- `get_credentials(service, username)` - Retrieve from keyring
- `delete_credentials(service, username)` - Remove from keyring

**Implementation:**
```python
import keyring
import secrets
import string

def generate_password(length=16):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def store_credentials(service, username, password):
    keyring.set_password(service, username, password)

def get_credentials(service, username):
    return keyring.get_password(service, username)
```

**Security:**
- Uses OS-native credential storage (Keychain on macOS, Credential Manager on Windows)
- Passwords are never stored in plain text
- Cryptographically secure random generation

---

### 7. api.py - Database API

**Purpose:** SQLite database interface for recordings metadata.

**Key Classes:**
- `RecordingsDB` - Database wrapper
  - `add_recording(metadata)` - Insert new recording
  - `query_recordings(filters)` - Query with filters
  - `get_recording(id)` - Get by ID
  - `get_stats()` - Get statistics
  - `delete_old_recordings(max_size)` - Cleanup

**Architecture:**
```python
import sqlite3
import json

class RecordingsDB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()
    
    def add_recording(self, metadata):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO recordings 
            (timestamp, stream_path, objects_detected, tracker_ids)
            VALUES (?, ?, ?, ?)
        """, (
            metadata['timestamp'],
            metadata['stream_path'],
            json.dumps(metadata['objects']),
            json.dumps(metadata['tracker_ids'])
        ))
        self.conn.commit()
    
    def query_recordings(self, object_class=None, tracker_id=None):
        query = "SELECT * FROM recordings WHERE 1=1"
        params = []
        
        if object_class:
            query += " AND objects_detected LIKE ?"
            params.append(f'%{object_class}%')
        
        if tracker_id:
            query += " AND tracker_ids LIKE ?"
            params.append(f'%{tracker_id}%')
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
```

---

## Data Flow

### 1. System Startup

```
surveillance.py (main)
    ↓
config.py (load YAML)
    ↓
credentials.py (generate/retrieve)
    ↓
MediaMTX (start server)
    ↓
detector.py (load YOLO model)
    ↓
visualizer.py (start web server)
    ↓
System Ready
```

### 2. Detection Pipeline

```
RTSP Stream
    ↓
detector.py (read frame)
    ↓
YOLO (inference)
    ↓
ByteTrack (tracking)
    ↓
Filter (class, confidence, area)
    ↓
Draw (bounding boxes, labels)
    ↓
recorder.py (buffer frame)
    ↓
visualizer.py (stream to web)
```

### 3. Recording Flow

```
Detection Event
    ↓
recorder.py (start recording)
    ↓
Collect frames (pre-buffer + live + post-buffer)
    ↓
Encode to MP4 (H.264)
    ↓
Save file
    ↓
api.py (save metadata to DB)
    ↓
Check storage limit
    ↓
Delete old recordings if needed
```

### 4. API Request Flow

```
HTTP Request
    ↓
FastAPI (route handler)
    ↓
api.py (query database)
    ↓
Format response (JSON)
    ↓
HTTP Response
```

---

## Key Components

### MediaMTX Integration

SpectraX wraps MediaMTX for RTSP/HLS streaming:

```bash
# Start MediaMTX with custom config
mediamtx /path/to/mediamtx.yml
```

**Configuration:**
- RTSP port: 8554 (unencrypted)
- RTSPS port: 8322 (TLS encrypted)
- HLS port: 8888 (browser streaming)
- Authentication: username/password per path

**Connection:**
```python
import cv2

# Connect to RTSP stream
rtsp_url = f"rtsps://{username}:{password}@{host}:8322/{path}"
cap = cv2.VideoCapture(rtsp_url)

while True:
    ret, frame = cap.read()
    if ret:
        # Process frame
        detections = detector.detect(frame)
```

---

### YOLO Model Management

**Model Loading:**
```python
from ultralytics import YOLO

# Load model (auto-downloads if not found)
model = YOLO('yolov8n.pt')

# Run inference
results = model(frame, conf=0.4)

# Access detections
for result in results:
    boxes = result.boxes
    for box in boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        xyxy = box.xyxy[0].tolist()
```

**Model Selection:**
- `yolov8n.pt` - Nano (fastest, 6MB)
- `yolov8s.pt` - Small (fast, 22MB)
- `yolov8m.pt` - Medium (balanced, 52MB)
- `yolov8l.pt` - Large (accurate, 88MB)
- `yolov8x.pt` - Extra Large (best, 136MB)

---

### ByteTrack Integration

**Tracking Setup:**
```python
from supervision import ByteTrack, Detections

# Initialize tracker
tracker = ByteTrack(
    track_thresh=0.25,
    track_buffer=30,
    match_thresh=0.8,
    frame_rate=30
)

# Convert YOLO to Supervision format
detections = Detections.from_ultralytics(yolo_results)

# Apply tracking
tracked = tracker.update_with_detections(detections)

# Access tracker IDs
for detection, tracker_id in zip(tracked, tracked.tracker_id):
    print(f"Object {detection.class_name} has ID {tracker_id}")
```

**Tracker ID Lifecycle:**
- IDs start at 1 and increment
- IDs persist across frames during occlusion
- IDs reset on system restart
- IDs are per-camera (not global)

---

## Development Setup

### 1. Clone and Install

```bash
# Clone repository
git clone https://github.com/SpectraCoreX/SpectraX.git
cd SpectraX

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
cd video-feed
pip install -e .
pip install -r requirements.txt
```

### 2. Install MediaMTX

```bash
# macOS
brew install mediamtx

# Linux
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_amd64.tar.gz
tar -xzf mediamtx_linux_amd64.tar.gz
sudo mv mediamtx /usr/local/bin/
```

### 3. Run Tests

```bash
cd video-feed
pytest tests/
```

### 4. Run Development Server

```bash
# Start with config file
python -m spectrax.surveillance config

# Or use the shell script
./scripts/surveillance.sh config
```

---

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── test_config.py           # Configuration tests
├── test_detector.py         # Detection tests
├── test_recorder.py         # Recording tests
├── test_api.py              # API tests
└── test_integration.py      # End-to-end tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_detector.py

# Run with coverage
pytest --cov=spectrax tests/

# Run with verbose output
pytest -v
```

### Writing Tests

```python
import pytest
from spectrax.detector import ObjectDetector

def test_detector_initialization():
    detector = ObjectDetector(model_path="yolov8n.pt", confidence=0.4)
    assert detector.model is not None
    assert detector.confidence == 0.4

def test_detection_filtering():
    detector = ObjectDetector(
        model_path="yolov8n.pt",
        filter_classes=["person", "car"]
    )
    
    # Mock detection
    frame = create_test_frame()
    detections = detector.detect(frame)
    
    # Verify filtering
    for det in detections:
        assert det['class'] in ["person", "car"]
```

---

## Contributing Guidelines

### Code Style

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for all public functions
- Keep functions focused and small (<50 lines)

**Example:**
```python
def process_detections(
    detections: List[Dict],
    confidence_threshold: float = 0.5
) -> List[Dict]:
    """
    Filter detections by confidence threshold.
    
    Args:
        detections: List of detection dictionaries
        confidence_threshold: Minimum confidence score
    
    Returns:
        Filtered list of detections
    """
    return [d for d in detections if d['confidence'] >= confidence_threshold]
```

### Git Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and commit: `git commit -am "Add my feature"`
4. Push to branch: `git push origin feature/my-feature`
5. Create Pull Request

### Commit Messages

Use conventional commits format:

```
feat: Add tracker ID filtering to API
fix: Resolve memory leak in frame buffer
docs: Update architecture guide
test: Add tests for recorder module
refactor: Simplify detection pipeline
```

### Pull Request Checklist

- [ ] Tests pass (`pytest`)
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)
- [ ] No breaking changes (or clearly documented)

---

## Performance Considerations

### Memory Management

**Frame Buffers:**
- Use `deque` with `maxlen` for automatic size limiting
- Release frames after processing
- Avoid keeping large objects in memory

```python
from collections import deque

# Good: Limited buffer
frame_buffer = deque(maxlen=300)  # ~10 seconds at 30 FPS

# Bad: Unlimited buffer
frame_buffer = []  # Will grow indefinitely
```

### CPU Optimization

**Model Selection:**
- Use smaller models for multiple cameras
- Use larger models for single camera with good hardware
- Consider GPU acceleration for better performance

**Frame Processing:**
- Skip frames if processing is slow
- Use lower resolution for detection
- Process frames in separate thread

```python
import threading

def process_frames():
    while running:
        if not frame_queue.empty():
            frame = frame_queue.get()
            detections = detector.detect(frame)

# Start processing thread
thread = threading.Thread(target=process_frames, daemon=True)
thread.start()
```

### Storage Optimization

**Recording:**
- Use H.264 encoding for efficient compression
- Implement automatic cleanup when storage limit reached
- Store only metadata in database (not frames)

**Database:**
- Use indexes on frequently queried columns
- Periodically vacuum database to reclaim space
- Archive old recordings to external storage

---

## Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Common Issues

**RTSP Connection Failures:**
- Check MediaMTX is running: `ps aux | grep mediamtx`
- Verify credentials are correct
- Test with VLC: `vlc rtsps://user:pass@host:8322/path`

**Detection Performance:**
- Monitor FPS in web dashboard
- Check CPU usage: `top` or `htop`
- Try smaller model or lower resolution

**Recording Issues:**
- Check disk space: `df -h`
- Verify write permissions on recordings directory
- Check database integrity: `sqlite3 recordings.db "PRAGMA integrity_check;"`

---

## Future Architecture

See [Development Roadmap](roadmap_summary.md) for planned features:

- **Phase 3**: Zone analytics with line crossing detection
- **Phase 4**: Persistent tracker IDs across sessions
- **Phase 5**: Cross-camera tracking
- **Phase 6**: Advanced analytics (heatmaps, trails)

---

## Additional Resources

- [API Documentation](API.md) - REST API reference
- [Configuration Guide](CONFIGURATION_GUIDE.md) - All config options
- [Supervision Docs](https://supervision.roboflow.com/) - ByteTrack integration
- [Ultralytics Docs](https://docs.ultralytics.com/) - YOLO models
- [FastAPI Docs](https://fastapi.tiangolo.com/) - Web framework
- [MediaMTX Docs](https://github.com/bluenviron/mediamtx) - Streaming server
