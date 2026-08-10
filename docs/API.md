# SpectraX API Documentation

This document provides a complete reference for the SpectraX REST API. Use these endpoints to build custom clients, integrate with other systems, or query surveillance data programmatically.

## Base URL

The API runs on the detection server port (default: 8080):

```
http://localhost:8080
```

For remote access, replace `localhost` with your server's IP address.

## Authentication

Currently, the API does not require authentication. For production deployments, consider placing the API behind a reverse proxy with authentication (e.g., nginx with basic auth).

## Response Format

All API responses are in JSON format unless otherwise specified.

**Success Response:**
```json
{
  "status": "success",
  "data": { ... }
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description"
}
```

---

## Endpoints

### System Status

#### GET /status

Get current system status and statistics.

**Response:**
```json
{
  "status": "running",
  "cameras": {
    "video/front-door": {
      "fps": 25.3,
      "detections": 42,
      "last_detection": "2025-10-12T19:05:30Z",
      "objects": {
        "person": 15,
        "car": 3
      }
    }
  },
  "uptime_seconds": 3600,
  "model": "yolov8n.pt",
  "tracking_enabled": true
}
```

**Example:**
```bash
curl http://localhost:8080/status
```

---

### Camera Paths

#### GET /paths

List all available camera stream paths.

**Response:**
```json
{
  "paths": [
    "video/front-door",
    "video/backyard",
    "video/garage"
  ]
}
```

**Example:**
```bash
curl http://localhost:8080/paths
```

---

### Video Streaming

#### GET /video/stream

Get MJPEG video stream with AI detection overlays.

**Query Parameters:**
- `path` (optional): Camera path to stream. If omitted, streams the first camera.

**Response:** MJPEG video stream (multipart/x-mixed-replace)

**Example:**
```bash
# Stream first camera
curl http://localhost:8080/video/stream

# Stream specific camera
curl http://localhost:8080/video/stream?path=video/front-door
```

**HTML Integration:**
```html
<img src="http://localhost:8080/video/stream?path=video/front-door" />
```

---

### Recordings

#### GET /api/recordings

List all recordings with metadata.

**Query Parameters:**
- `limit` (optional): Maximum number of recordings to return (default: 100, max: 1000)
- `offset` (optional): Number of recordings to skip (default: 0)
- `stream_id` (optional): Filter by stream ID
- `start_date` (optional): Filter recordings from this date (ISO format)
- `end_date` (optional): Filter recordings until this date (ISO format)
- `object_type` (optional): Filter by detected object class (e.g., "person", "car")
- `min_confidence` (optional): Filter by minimum confidence threshold (0.0-1.0)
- `sort_by` (optional): Sort field - "timestamp", "confidence", or "duration" (default: "timestamp")
- `sort_order` (optional): Sort order - "asc" or "desc" (default: "desc")

**Response:**
```json
{
  "total": 150,
  "limit": 100,
  "offset": 0,
  "recordings": [
    {
      "id": 42,
      "timestamp": "2025-10-12T19:05:30.123456",
      "stream_id": "fd778237-c3e5-49e8-be03-e588801943be",
      "stream_name": "front-door",
      "file_path": "/Users/user/video-feed-recordings/front-door_2025-10-12_19-05-30.mp4",
      "duration": 15.234567,
      "objects_detected": [
        {
          "class": "person",
          "confidence": 0.95,
          "bbox": [100, 200, 300, 400],
          "tracker_id": 42
        },
        {
          "class": "car",
          "confidence": 0.87,
          "bbox": [500, 100, 700, 300],
          "tracker_id": 15
        }
      ],
      "thumbnail_path": "/Users/user/video-feed-recordings/front-door_2025-10-12_19-05-30_thumb.jpg",
      "confidence": 0.95,
      "retained": 1,
      "tracker_ids": "[42, 15]",
      "file_url": "/recordings/front-door_2025-10-12_19-05-30.mp4",
      "thumbnail_url": "/recordings/front-door_2025-10-12_19-05-30_thumb.jpg",
      "mediaUrl": "/api/recordings/file/front-door_2025-10-12_19-05-30.mp4",
      "thumbnailMediaUrl": "/api/recordings/file/front-door_2025-10-12_19-05-30_thumb.jpg"
    }
  ]
}
```

**Field Descriptions:**
- `id`: Unique recording identifier
- `timestamp`: Recording start time in ISO format
- `stream_id`: Unique identifier for the camera stream (UUID)
- `stream_name`: Human-readable name of the camera
- `file_path`: Absolute path to the video file on the server
- `duration`: Recording duration in seconds (float)
- `objects_detected`: Array of detected objects with their properties
  - `class`: Object class name (e.g., "person", "car", "dog")
  - `confidence`: Detection confidence score (0.0-1.0)
  - `bbox`: Bounding box coordinates [x1, y1, x2, y2]
  - `tracker_id`: Object tracker ID (optional, only if tracking is enabled)
- `thumbnail_path`: Absolute path to the thumbnail image on the server
- `confidence`: Highest confidence score among all detections
- `retained`: Whether the recording is retained (1) or marked for deletion (0)
- `tracker_ids`: JSON string of tracker IDs (e.g., "[42, 15]") or null
- `file_url`: Relative URL path to download/stream the video file
- `thumbnail_url`: Relative URL path to view the thumbnail image
- `mediaUrl`: Alternative URL path for the video file
- `thumbnailMediaUrl`: Alternative URL path for the thumbnail

**Examples:**
```bash
# Get all recordings
curl http://localhost:8080/api/recordings

# Get recordings with pagination
curl "http://localhost:8080/api/recordings?limit=10&offset=20"

# Filter by object class
curl "http://localhost:8080/api/recordings?object_type=person"

# Filter by stream ID
curl "http://localhost:8080/api/recordings?stream_id=fd778237-c3e5-49e8-be03-e588801943be"

# Filter by date range
curl "http://localhost:8080/api/recordings?start_date=2025-10-01&end_date=2025-10-12"

# Filter by minimum confidence and sort
curl "http://localhost:8080/api/recordings?min_confidence=0.8&sort_by=confidence&sort_order=desc"
```

---

#### GET /api/recordings/{id}

Get details for a specific recording.

**Path Parameters:**
- `id`: Recording ID

**Response:**
```json
{
  "id": 42,
  "timestamp": "2025-10-12T19:05:30.123456",
  "stream_id": "fd778237-c3e5-49e8-be03-e588801943be",
  "stream_name": "front-door",
  "file_path": "/Users/user/video-feed-recordings/front-door_2025-10-12_19-05-30.mp4",
  "duration": 15.234567,
  "objects_detected": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": [100, 200, 300, 400],
      "tracker_id": 42
    }
  ],
  "thumbnail_path": "/Users/user/video-feed-recordings/front-door_2025-10-12_19-05-30_thumb.jpg",
  "confidence": 0.95,
  "retained": 1,
  "tracker_ids": "[42, 15]",
  "file_url": "/recordings/front-door_2025-10-12_19-05-30.mp4",
  "thumbnail_url": "/recordings/front-door_2025-10-12_19-05-30_thumb.jpg",
  "mediaUrl": "/api/recordings/file/front-door_2025-10-12_19-05-30.mp4",
  "thumbnailMediaUrl": "/api/recordings/file/front-door_2025-10-12_19-05-30_thumb.jpg"
}
```

**Example:**
```bash
curl http://localhost:8080/api/recordings/42
```

---

#### GET /api/recordings/stats

Get recording statistics and analytics.

**Response:**
```json
{
  "total_recordings": 150,
  "total_duration_seconds": 2280,
  "total_size_bytes": 307200000,
  "total_size_gb": 0.29,
  "oldest_recording": "2025-10-01T10:00:00Z",
  "newest_recording": "2025-10-12T19:05:30Z",
  "objects": {
    "person": 450,
    "car": 120,
    "dog": 15
  },
  "trackers": {
    "total_unique_ids": 87,
    "most_frequent": [
      {"tracker_id": 42, "appearances": 12},
      {"tracker_id": 15, "appearances": 8}
    ]
  },
  "by_camera": {
    "video/front-door": {
      "count": 80,
      "duration_seconds": 1200
    },
    "video/backyard": {
      "count": 70,
      "duration_seconds": 1080
    }
  }
}
```

**Example:**
```bash
curl http://localhost:8080/api/recordings/stats
```

---

#### GET /recordings/{filename}

Download a recording file.

**Path Parameters:**
- `filename`: Recording filename (from `/api/recordings` response)

**Response:** MP4 video file (video/mp4)

**Example:**
```bash
# Download recording
curl -O http://localhost:8080/recordings/recording_20251012_190530_front-door.mp4

# Stream in VLC
vlc http://localhost:8080/recordings/recording_20251012_190530_front-door.mp4
```

---

## Client Examples

### Python Client

```python
import requests
import json

class SpectraXClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
    
    def get_status(self):
        """Get system status"""
        response = requests.get(f"{self.base_url}/status")
        return response.json()
    
    def get_recordings(self, limit=100, offset=0, object_type=None, stream_id=None, 
                       start_date=None, end_date=None, min_confidence=None,
                       sort_by="timestamp", sort_order="desc"):
        """List recordings with optional filters"""
        params = {"limit": limit, "offset": offset, "sort_by": sort_by, "sort_order": sort_order}
        if object_type:
            params["object_type"] = object_type
        if stream_id:
            params["stream_id"] = stream_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if min_confidence is not None:
            params["min_confidence"] = min_confidence
        
        response = requests.get(f"{self.base_url}/api/recordings", params=params)
        return response.json()
    
    def get_recording(self, recording_id):
        """Get specific recording details"""
        response = requests.get(f"{self.base_url}/api/recordings/{recording_id}")
        return response.json()
    
    def download_recording(self, file_url, output_path):
        """Download recording file using file_url from recording metadata"""
        response = requests.get(f"{self.base_url}{file_url}", stream=True)
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    
    def get_stats(self):
        """Get recording statistics"""
        response = requests.get(f"{self.base_url}/api/recordings/stats")
        return response.json()

# Usage
client = SpectraXClient()

# Get system status
status = client.get_status()
print(f"System uptime: {status['uptime_seconds']}s")

# Find recordings with people
recordings = client.get_recordings(object_type="person", limit=10)
print(f"Found {recordings['total']} recordings with people")

# Download a recording
if recordings['recordings']:
    first = recordings['recordings'][0]
    print(f"Recording: {first['stream_name']} at {first['timestamp']}")
    print(f"Duration: {first['duration']:.2f}s, Confidence: {first['confidence']:.2f}")
    client.download_recording(first['file_url'], "output.mp4")
```

---

### JavaScript Client

```javascript
class SpectraXClient {
  constructor(baseUrl = 'http://localhost:8080') {
    this.baseUrl = baseUrl;
  }

  async getStatus() {
    const response = await fetch(`${this.baseUrl}/status`);
    return response.json();
  }

  async getRecordings(options = {}) {
    const params = new URLSearchParams({
      limit: options.limit || 100,
      offset: options.offset || 0,
      sort_by: options.sort_by || 'timestamp',
      sort_order: options.sort_order || 'desc',
      ...(options.object_type && { object_type: options.object_type }),
      ...(options.stream_id && { stream_id: options.stream_id }),
      ...(options.start_date && { start_date: options.start_date }),
      ...(options.end_date && { end_date: options.end_date }),
      ...(options.min_confidence !== undefined && { min_confidence: options.min_confidence })
    });
    
    const response = await fetch(`${this.baseUrl}/api/recordings?${params}`);
    return response.json();
  }

  async getRecording(id) {
    const response = await fetch(`${this.baseUrl}/api/recordings/${id}`);
    return response.json();
  }

  async getStats() {
    const response = await fetch(`${this.baseUrl}/api/recordings/stats`);
    return response.json();
  }

  getStreamUrl(cameraPath = null) {
    const params = cameraPath ? `?path=${cameraPath}` : '';
    return `${this.baseUrl}/video/stream${params}`;
  }

  getRecordingUrl(fileUrl) {
    // fileUrl should be the file_url from recording metadata (e.g., "/recordings/video.mp4")
    return `${this.baseUrl}${fileUrl}`;
  }
}

// Usage
const client = new SpectraXClient();

// Get system status
const status = await client.getStatus();
console.log(`System uptime: ${status.uptime_seconds}s`);

// Find recordings with people, sorted by confidence
const recordings = await client.getRecordings({ 
  object_type: 'person', 
  min_confidence: 0.8,
  sort_by: 'confidence',
  sort_order: 'desc'
});
console.log(`Found ${recordings.total} recordings`);

// Display first recording
if (recordings.recordings.length > 0) {
  const rec = recordings.recordings[0];
  console.log(`Recording: ${rec.stream_name} at ${rec.timestamp}`);
  console.log(`Duration: ${rec.duration.toFixed(2)}s, Confidence: ${rec.confidence.toFixed(2)}`);
  
  // Create video element
  const video = document.createElement('video');
  video.src = client.getRecordingUrl(rec.file_url);
  video.controls = true;
  document.body.appendChild(video);
}
```

---

### cURL Examples

```bash
# Get system status
curl http://localhost:8080/status | jq

# List recent recordings
curl http://localhost:8080/api/recordings?limit=10 | jq

# Find recordings with people
curl "http://localhost:8080/api/recordings?object_type=person" | jq

# Find recordings with high confidence, sorted by confidence
curl "http://localhost:8080/api/recordings?min_confidence=0.8&sort_by=confidence&sort_order=desc" | jq

# Filter by date range
curl "http://localhost:8080/api/recordings?start_date=2025-10-01&end_date=2025-10-12" | jq

# Get recording statistics
curl http://localhost:8080/api/recordings/stats | jq

# Download a recording (use file_url from API response)
curl -O http://localhost:8080/recordings/front-door_2025-10-12_19-05-30.mp4

# Get a specific recording's details
curl http://localhost:8080/api/recordings/42 | jq

# Stream video to file
curl "http://localhost:8080/video/stream?path=video/front-door" > stream.mjpeg
```

---

## WebSocket Support (Future)

WebSocket support for real-time detection events is planned for a future release. This will enable:

- Real-time detection notifications
- Live tracker updates
- System event streaming

Stay tuned for updates in the [Development Roadmap](roadmap_summary.md).

---

## Rate Limiting

Currently, there are no rate limits on API endpoints. For production deployments, consider implementing rate limiting at the reverse proxy level.

---

## CORS

Cross-Origin Resource Sharing (CORS) is enabled by default for all origins. To restrict access, modify the FastAPI CORS middleware configuration in `spectrax/visualizer.py`.

---

## Error Codes

| HTTP Status | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |

---

## Database Schema

For direct database access, recordings are stored in SQLite with the following schema:

```sql
CREATE TABLE recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    stream_path TEXT NOT NULL,
    duration_seconds REAL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    objects_detected TEXT,  -- JSON array
    tracker_ids TEXT,       -- JSON array
    max_confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON recordings(timestamp);
CREATE INDEX idx_stream_path ON recordings(stream_path);
CREATE INDEX idx_tracker_ids ON recordings(tracker_ids);
```

**Database Location:** `~/video-feed-recordings/recordings.db`

**Direct Query Example:**
```bash
sqlite3 ~/video-feed-recordings/recordings.db "SELECT * FROM recordings WHERE tracker_ids LIKE '%42%' ORDER BY timestamp DESC LIMIT 10;"
```

---

## Support

For issues or questions:
- Check the [main README](../README.md) for troubleshooting
- Review the [Architecture Guide](ARCHITECTURE.md) for implementation details
- Open an issue on GitHub
