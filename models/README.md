# YOLO Models Directory

This directory contains YOLO model files used for object detection.

## Available Models

The system automatically uses models from this directory when you specify a model name in the configuration.

### Model Options

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| `yolov8n.pt` | ~6 MB | Fastest | Good | Real-time on limited hardware |
| `yolov8s.pt` | ~22 MB | Fast | Better | Balanced performance |
| `yolov8m.pt` | ~52 MB | Medium | Very Good | Better accuracy needed |
| `yolov8l.pt` | ~88 MB | Slow | Excellent | Maximum accuracy |
| `yolov8x.pt` | ~136 MB | Slowest | Best | Production quality |

## Usage

Models are automatically loaded from this directory when you specify them in:

1. **Configuration file** (`config/spectrax.yml`):
   ```yaml
   detection:
     model: "yolov8l.pt"
   ```

2. **Command line**:
   ```bash
   spectrax start --model yolov8n.pt
   ```

## Automatic Download

If a model is not found in this directory, it will be automatically downloaded from Ultralytics on first use.

## Model Management

### Download a specific model
```bash
# The system will download it automatically on first use
# Or manually download:
cd video-feed/models
wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

### Remove unused models
```bash
cd video-feed/models
rm yolov8*.pt  # Remove all models
```

## Git Ignore

Model files (*.pt) are ignored by git to avoid committing large binary files. You'll need to download them on each new installation.

## Performance Tips

- **yolov8n.pt**: Use for multiple cameras or limited hardware
- **yolov8l.pt**: Use for single camera with good hardware
- **Resolution matters**: Lower resolution = faster processing
- **Confidence threshold**: Higher threshold = fewer false positives

## More Information

- [Ultralytics YOLO Documentation](https://docs.ultralytics.com/)
- [Model Comparison](https://docs.ultralytics.com/models/yolov8/#performance-metrics)
