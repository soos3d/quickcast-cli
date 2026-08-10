#!/usr/bin/env python3
"""Test script to verify data storage location."""

import os
import sys
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('storage-test')


# Import relevant modules
from spectrax.recorder import RecordingManager
from spectrax.recording.db import RecordingsAPI
from spectrax.config import SurveillanceConfig

def test_path_expansion():
    """Test that paths with ~ are properly expanded."""
    
    # Test 1: RecordingManager path expansion
    logger.info("=== Testing RecordingManager path expansion ===")
    
    # Test with default path
    rm1 = RecordingManager()
    logger.info(f"Default recordings dir: {rm1.recordings_dir}")
    logger.info(f"Default DB path: {rm1.db_path}")
    
    # Test with explicit path containing ~
    test_path = "~/test-video-recordings"
    rm2 = RecordingManager(recordings_dir=test_path)
    logger.info(f"Custom recordings dir: {rm2.recordings_dir}")
    logger.info(f"Custom DB path: {rm2.db_path}")
    
    # Verify expansion
    expanded_path = os.path.expanduser(test_path)
    assert str(rm2.recordings_dir) == expanded_path, "Path expansion failed in RecordingManager"
    logger.info("RecordingManager path expansion test passed")
    
    # Test 2: RecordingsAPI path expansion
    logger.info("\n=== Testing RecordingsAPI path expansion ===")
    
    # Test with path containing ~
    test_db_path = "~/test-db.sqlite"
    api = RecordingsAPI(db_path=test_db_path)
    logger.info(f"API DB path: {api.db_path}")
    
    # Verify expansion
    expanded_db_path = os.path.expanduser(test_db_path)
    assert api.db_path == expanded_db_path, "Path expansion failed in RecordingsAPI"
    logger.info("RecordingsAPI path expansion test passed")
    
    # Test 3: SurveillanceConfig path expansion
    logger.info("\n=== Testing SurveillanceConfig path expansion ===")
    
    # Create a test config
    config = SurveillanceConfig()
    
    # Get recordings directory
    recordings_dir = config.get_recordings_directory()
    logger.info(f"Config recordings dir: {recordings_dir}")
    
    # Verify expansion
    default_path = "~/video-feed-recordings"
    expanded_default = os.path.expanduser(default_path)
    assert recordings_dir == expanded_default, "Path expansion failed in SurveillanceConfig"
    logger.info("SurveillanceConfig path expansion test passed")
    
    logger.info("\nAll path expansion tests passed!")

if __name__ == "__main__":
    test_path_expansion()
