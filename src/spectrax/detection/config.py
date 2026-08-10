"""Configuration dataclasses for detector module."""

from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Dict, Any
import supervision as sv


# Color mapping for string-based color configuration
COLOR_MAP = {
    "green": sv.Color.GREEN,
    "red": sv.Color.RED,
    "blue": sv.Color.BLUE,
    "yellow": sv.Color.YELLOW,
    "white": sv.Color.WHITE,
    "black": sv.Color.BLACK,
    "roboflow": sv.Color.ROBOFLOW,
}

# Position mapping for string-based position configuration
POSITION_MAP = {
    "top_left": sv.Position.TOP_LEFT,
    "top_center": sv.Position.TOP_CENTER,
    "top_right": sv.Position.TOP_RIGHT,
    "center_left": sv.Position.CENTER_LEFT,
    "center": sv.Position.CENTER,
    "center_right": sv.Position.CENTER_RIGHT,
    "bottom_left": sv.Position.BOTTOM_LEFT,
    "bottom_center": sv.Position.BOTTOM_CENTER,
    "bottom_right": sv.Position.BOTTOM_RIGHT,
}


@dataclass
class AnnotatorConfig:
    """Configuration for Supervision annotators."""
    
    # Box annotator settings
    box_thickness: int = 2
    box_color: sv.Color = sv.Color.GREEN
    
    # Label annotator settings
    label_text_scale: float = 0.5
    label_text_thickness: int = 1
    label_text_padding: int = 10
    label_text_position: sv.Position = sv.Position.TOP_LEFT
    
    # Border settings (optional)
    label_border_radius: int = 0
    
    @classmethod
    def from_appearance_config(cls, appearance_config: Dict[str, Any]) -> 'AnnotatorConfig':
        """Create AnnotatorConfig from appearance section of surveillance.yml.
        
        Args:
            appearance_config: Dictionary from surveillance.yml appearance section
            
        Returns:
            AnnotatorConfig instance
        """
        box_config = appearance_config.get('box', {})
        label_config = appearance_config.get('label', {})
        
        # Parse box color from string
        box_color_str = box_config.get('color', 'green').lower()
        box_color = COLOR_MAP.get(box_color_str, sv.Color.GREEN)
        
        # Parse label position from string
        position_str = label_config.get('position', 'top_left').lower()
        label_position = POSITION_MAP.get(position_str, sv.Position.TOP_LEFT)
        
        return cls(
            box_thickness=box_config.get('thickness', 2),
            box_color=box_color,
            label_text_scale=label_config.get('text_scale', 0.5),
            label_text_thickness=label_config.get('text_thickness', 1),
            label_text_padding=label_config.get('text_padding', 10),
            label_text_position=label_position,
            label_border_radius=label_config.get('border_radius', 0)
        )


@dataclass
class TrackingConfig:
    """Configuration for ByteTrack object tracking."""
    
    enabled: bool = True
    track_thresh: float = 0.25      # Detection confidence threshold for track activation
    track_buffer: int = 30           # Number of frames to buffer when track is lost
    match_thresh: float = 0.8        # Threshold for matching tracks with detections
    frame_rate: int = 30             # Frame rate of video


@dataclass
class DetectorConfig:
    """Configuration for RTSP object detector."""
    
    # Model settings
    model_path: str = "yolov8n.pt"
    confidence: float = 0.5
    
    # Stream settings
    resolution: Tuple[int, int] = (960, 540)
    buffer_size: int = 10
    reconnect_interval: int = 5
    
    # Filtering settings
    min_detection_area: Optional[int] = None  # Minimum area in pixels
    max_detection_area: Optional[int] = None  # Maximum area in pixels
    filter_classes: List[str] = field(default_factory=list)  # Only detect these classes (empty = all)
    
    # Annotator configuration
    annotator: AnnotatorConfig = field(default_factory=AnnotatorConfig)
    
    # Tracking configuration
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    
    @classmethod
    def from_settings(cls, settings) -> "DetectorConfig":
        """Create DetectorConfig from SpectraXSettings."""
        det = settings.detection
        appearance = settings.appearance.model_dump()
        annotator_config = AnnotatorConfig.from_appearance_config(appearance)
        tracking = TrackingConfig(
            enabled=det.tracking.enabled,
            track_thresh=det.tracking.track_thresh,
            track_buffer=det.tracking.track_buffer,
            match_thresh=det.tracking.match_thresh,
            frame_rate=det.tracking.frame_rate,
        )
        # None = all classes (empty list for detector internals)
        filter_classes = list(det.filters.classes) if det.filters.classes else []
        return cls(
            model_path=det.model,
            confidence=det.confidence,
            resolution=(det.resolution.width, det.resolution.height),
            buffer_size=det.stream.buffer_size,
            reconnect_interval=det.stream.reconnect_interval,
            filter_classes=filter_classes,
            min_detection_area=det.filters.min_area,
            max_detection_area=det.filters.max_area,
            annotator=annotator_config,
            tracking=tracking,
        )

    @classmethod
    def from_surveillance_config(cls, surveillance_config) -> "DetectorConfig":
        """Create DetectorConfig from SurveillanceConfig (legacy adapter)."""
        if hasattr(surveillance_config, "settings"):
            return cls.from_settings(surveillance_config.settings)
        detection_config = surveillance_config.get_detection_config()
        stream_config = detection_config.get("stream", {})
        filter_config = detection_config.get("filters", {})
        filter_classes = filter_config.get("classes") or []
        appearance_config = surveillance_config.config_data.get("appearance", {})
        annotator_config = AnnotatorConfig.from_appearance_config(appearance_config)
        tracking_config_dict = detection_config.get("tracking", {})
        tracking_config = TrackingConfig(
            enabled=tracking_config_dict.get("enabled", True),
            track_thresh=tracking_config_dict.get("track_thresh", 0.25),
            track_buffer=tracking_config_dict.get("track_buffer", 30),
            match_thresh=tracking_config_dict.get("match_thresh", 0.8),
            frame_rate=tracking_config_dict.get("frame_rate", 30),
        )
        res = detection_config.get("resolution", {})
        if isinstance(res, dict):
            resolution = (res.get("width", 960), res.get("height", 540))
        else:
            resolution = (960, 540)
        return cls(
            model_path=detection_config.get("model", "yolov8n.pt"),
            confidence=detection_config.get("confidence", 0.4),
            resolution=resolution,
            buffer_size=stream_config.get("buffer_size", 10),
            reconnect_interval=stream_config.get("reconnect_interval", 5),
            filter_classes=filter_classes if filter_classes else [],
            min_detection_area=filter_config.get("min_area"),
            max_detection_area=filter_config.get("max_area"),
            annotator=annotator_config,
            tracking=tracking_config,
        )
    
    def create_box_annotator(self) -> sv.BoxAnnotator:
        """Create configured BoxAnnotator instance."""
        return sv.BoxAnnotator(
            thickness=self.annotator.box_thickness,
            color=self.annotator.box_color
        )
    
    def create_label_annotator(self) -> sv.LabelAnnotator:
        """Create configured LabelAnnotator instance."""
        return sv.LabelAnnotator(
            text_position=self.annotator.label_text_position,
            text_thickness=self.annotator.label_text_thickness,
            text_scale=self.annotator.label_text_scale,
            text_padding=self.annotator.label_text_padding,
            border_radius=self.annotator.label_border_radius
        )
    
    def create_tracker(self) -> Optional[sv.ByteTrack]:
        """Create configured ByteTrack tracker instance if tracking is enabled."""
        if not self.tracking.enabled:
            return None
        
        return sv.ByteTrack(
            track_activation_threshold=self.tracking.track_thresh,
            lost_track_buffer=self.tracking.track_buffer,
            minimum_matching_threshold=self.tracking.match_thresh,
            frame_rate=self.tracking.frame_rate
        )
