#!/usr/bin/env python3
"""Test script to verify database connection."""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db-connection-test')


# Import relevant modules
from spectrax.api import RecordingsAPI
from spectrax.recorder import RecordingManager

def test_db_connection():
    """Test database connection with expanded paths."""
    
    # Test with default path in home directory
    logger.info("=== Testing database connection with default path ===")
    
    # Create recordings directory if it doesn't exist
    home_recordings_dir = os.path.expanduser("~/video-feed-recordings")
    os.makedirs(home_recordings_dir, exist_ok=True)
    
    # Initialize recording manager (this will create the DB if it doesn't exist)
    recording_manager = RecordingManager()
    
    # Get the database path
    db_path = recording_manager.get_database_path()
    logger.info(f"Database path: {db_path}")
    
    # Check if the database file exists
    if os.path.exists(db_path):
        logger.info(f"Database file exists at: {db_path}")
    else:
        logger.warning(f"Database file does not exist at: {db_path}")
    
    # Test API connection using the database
    logger.info("\n=== Testing API connection ===")
    api = RecordingsAPI(db_path=db_path)
    
    # Try to get recordings count
    try:
        count = api.get_recordings_count()
        logger.info(f"Found {count} recordings in the database")
    except Exception as e:
        logger.error(f"Error accessing database: {e}")
    
    logger.info("Database connection tests completed!")

if __name__ == "__main__":
    test_db_connection()
