#!/usr/bin/env python3
"""
Test script for the recording functionality.
This script helps verify that the recording system is working correctly.
"""

import os
import sys
import time
from pathlib import Path


from spectrax.recorder import RecordingManager
import numpy as np
import cv2

def create_test_frame(width=640, height=480, text="Test Frame", frame_num=0):
    """Create a test frame with some text."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Add some color gradient
    for i in range(height):
        frame[i, :, 0] = int(255 * i / height)  # Blue gradient
        frame[i, :, 1] = int(128 * (1 - i / height))  # Green gradient
    
    # Add text
    cv2.putText(frame, f"{text} #{frame_num}", (50, height//2), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Add timestamp
    timestamp = time.strftime("%H:%M:%S")
    cv2.putText(frame, timestamp, (50, height - 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    return frame

def test_recording_system(filter_objects=False):
    """Test the recording system with simulated frames and detections."""
    print("🧪 Testing Recording System")
    print("=" * 50)
    
    # Initialize recording manager
    recordings_dir = Path.home() / "test-recordings"
    print(f"📁 Using recordings directory: {recordings_dir}")
    
    # Set up object filtering if requested
    record_objects = []
    if filter_objects:
        record_objects = ["person", "car"]
        print(f"🔍 Filtering recordings to only include: {', '.join(record_objects)}")
    
    recorder = RecordingManager(
        recordings_dir=str(recordings_dir),
        pre_detection_buffer=5,  # 5 seconds for faster testing
        post_detection_buffer=5,
        min_confidence=0.3,
        target_fps=10,  # Lower FPS for testing
        record_objects=record_objects
    )
    
    try:
        # Start the recording manager
        recorder.start()
        print("✅ Recording manager started")
        
        # Register a test stream
        stream_id = "test-stream-001"
        stream_name = "Test Camera"
        recorder.register_stream(stream_id, stream_name)
        print(f"✅ Registered stream: {stream_name}")
        
        # Simulate adding frames to build up the buffer
        print("📹 Adding frames to buffer...")
        for i in range(60):  # 6 seconds of frames at 10 FPS
            frame = create_test_frame(text="Pre-Detection", frame_num=i)
            recorder.add_frame(stream_id, frame)
            time.sleep(0.1)  # 10 FPS
            
            if i % 10 == 0:
                print(f"  Added {i+1} frames...")
        
        print("✅ Buffer filled with pre-detection frames")
        
        # Simulate a detection event
        print("🎯 Simulating object detection...")
        detection_frame = create_test_frame(text="DETECTION!", frame_num=61)
        
        # Create mock detection objects
        mock_objects = [
            {
                "class": "person",
                "confidence": 0.85,
                "bbox": [100, 100, 200, 300]
            },
            {
                "class": "car", 
                "confidence": 0.72,
                "bbox": [300, 150, 500, 350]
            }
        ]
        
        # Trigger recording
        recorder.handle_detection(stream_id, mock_objects, 0.85, detection_frame)
        print("✅ Detection event triggered")
        
        # Continue adding frames during detection
        print("📹 Adding frames during detection period...")
        for i in range(30):  # 3 seconds of detection frames
            frame = create_test_frame(text="DURING DETECTION", frame_num=62+i)
            recorder.add_frame(stream_id, frame)
            time.sleep(0.1)
        
        # Add post-detection frames
        print("📹 Adding post-detection frames...")
        for i in range(50):  # 5 seconds of post-detection frames
            frame = create_test_frame(text="Post-Detection", frame_num=92+i)
            recorder.add_frame(stream_id, frame)
            time.sleep(0.1)
        
        print("✅ Recording should be complete")
        
        # Wait a bit for recording to finalize
        print("⏳ Waiting for recording to finalize...")
        time.sleep(8)  # Wait longer than post_detection_buffer
        
        # Check if recording was created
        recording_files = list(recordings_dir.glob("*.mp4"))
        if recording_files:
            print(f"✅ Recording created: {recording_files[0]}")
            print(f"📊 File size: {recording_files[0].stat().st_size} bytes")
            
            # Check for thumbnail
            thumbnail_files = list(recordings_dir.glob("*_thumb.jpg"))
            if thumbnail_files:
                print(f"✅ Thumbnail created: {thumbnail_files[0]}")
            else:
                print("⚠️  No thumbnail found")
        else:
            print("❌ No recording file found!")
        
        # Get recording stats
        stats = recorder.get_recording_stats()
        print(f"📈 Recording stats: {stats}")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        recorder.stop()
        print("🛑 Recording manager stopped")

def test_with_object_filtering():
    """Test recording with object filtering."""
    print("\n\n🧪 Testing Recording System WITH Object Filtering")
    print("=" * 50)
    
    # Test with object filtering
    test_recording_system(filter_objects=True)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--filter":
        # Test with object filtering
        test_with_object_filtering()
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Test both modes
        test_recording_system(filter_objects=False)
        test_with_object_filtering()
    else:
        # Default: test without filtering
        test_recording_system(filter_objects=False)
