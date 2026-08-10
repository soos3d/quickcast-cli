# Route Modules

This directory contains modular FastAPI route handlers extracted from `visualizer.py` for better code organization and maintainability.

## Structure

```
routes/
├── __init__.py          # Route module exports
├── video.py            # Video streaming endpoints
├── pages.py            # HTML page rendering
├── files.py            # Secure file serving
├── recordings.py       # Recording CRUD operations
├── statistics.py       # Analytics and stats endpoints
└── auth.py             # Authentication
```

## Route Modules

### `video.py` - Video Streaming Routes
**Prefix**: `/video`  
**Endpoints**:
- `GET /video/stream` - MJPEG video stream with detection overlay
- `GET /video/jpeg/{detector_id}` - Single frame as JPEG

### `pages.py` - Page Rendering Routes
**No prefix**  
**Endpoints**:
- `GET /` - Main viewer page
- `GET /recordings.html` - Recordings page

### `files.py` - File Serving Routes
**Prefix**: `/recordings`  
**Endpoints**:
- `GET /recordings/{file_path:path}` - Serve recording files with security checks

**Security Features**:
- Path traversal protection
- File type validation
- Access logging

### `recordings.py` - Recording Management Routes
**Prefix**: `/api/recordings`  
**Endpoints**:
- `GET /api/recordings` - List recordings with filtering/sorting
- `GET /api/recordings/{recording_id}` - Get recording details
- `DELETE /api/recordings/{recording_id}` - Delete a recording

### `statistics.py` - Statistics Routes
**Prefix**: `/api`  
**Endpoints**:
- `GET /api/alerts` - Detection alerts
- `GET /api/stats/objects` - Object detection statistics
- `GET /api/stats/times` - Time-based statistics
- `GET /api/streams` - Stream information with stats

### `auth.py` - Authentication Routes
**Prefix**: `/auth`  
**Endpoints**:
- `POST /auth/verify` - Verify user credentials

## Usage

Routes are automatically included in the main FastAPI app via `visualizer.py`:

```python
from spectrax.routes import (
    video_router,
    pages_router,
    files_router,
    recordings_router,
    statistics_router,
    auth_router
)

app.include_router(video_router)
app.include_router(pages_router)
app.include_router(files_router)
app.include_router(recordings_router)
app.include_router(statistics_router)
app.include_router(auth_router)
```

## Global State Management

Some route modules require access to global instances (detector_manager, recordings_api, recordings_directory). These are set via module-level setter functions:

```python
# Set detector manager
import spectrax.routes.video as video_routes
video_routes.set_detector_manager(detector_manager)

# Set recordings directory
import spectrax.routes.files as files_routes
files_routes.set_recordings_directory(recordings_directory)

# Set recordings API
import spectrax.routes.recordings as recordings_routes
recordings_routes.set_recordings_api(recordings_api)
```

## Benefits

1. **Separation of Concerns** - Each module handles a specific domain
2. **Maintainability** - Smaller, focused files are easier to understand and modify
3. **Testability** - Individual route modules can be tested in isolation
4. **Scalability** - Easy to add new route modules without cluttering main file
5. **Code Organization** - Clear structure makes navigation easier

## Migration Notes

This refactoring reduced `visualizer.py` from 722 lines to 287 lines (60% reduction) while maintaining all functionality and backward compatibility.
