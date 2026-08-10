# YOLO models directory

Weights used for object detection. Files matching `*.pt` are gitignored.

## Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `yolov8n.pt` | ~6 MB | Fastest | Good |
| `yolov8s.pt` | ~22 MB | Fast | Better |
| `yolov8m.pt` | ~52 MB | Medium | Very good |
| `yolov8l.pt` | ~88 MB | Slow | Excellent |
| `yolov8x.pt` | ~136 MB | Slowest | Best |

## Configuration

In `config/spectrax.yml`:

```yaml
detection:
  model: "yolov8n.pt"
```

Paths are resolved by `spectrax.utils.resolve_model_path` (checks `models/` under
the project root, then Ultralytics auto-download).

## Manual download

```bash
cd models
wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

Or let the first detection run download the model automatically.

## Tips

- Prefer `yolov8n` for multi-camera or lighter hardware.
- Lower `detection.resolution` for higher FPS.
- Raise `confidence` to reduce false positives.
