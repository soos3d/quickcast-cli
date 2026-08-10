#!/usr/bin/env python3
import os
import sqlite3
import sys

def check_db(path):
    """Check if a SQLite database exists and is accessible."""
    expanded_path = os.path.expanduser(path)
    print(f"Checking database at: {expanded_path}")
    
    if not os.path.exists(expanded_path):
        print(f"ERROR: Database file does not exist: {expanded_path}")
        return False
    
    try:
        conn = sqlite3.connect(expanded_path)
        cursor = conn.cursor()
        
        # Check if the recordings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recordings'")
        if not cursor.fetchone():
            print("ERROR: 'recordings' table does not exist in the database")
            return False
        
        # Check the schema
        cursor.execute("PRAGMA table_info(recordings)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Table columns: {columns}")
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM recordings")
        count = cursor.fetchone()[0]
        print(f"Found {count} recordings in the database")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR: Failed to access database: {e}")
        return False

if __name__ == "__main__":
    db_path = "~/video-feed-recordings/recordings.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    success = check_db(db_path)
    print(f"Database check {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
