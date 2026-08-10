"""API for querying and managing surveillance recordings."""

import os
import json
import logging
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('video-recorder-api')

class RecordingsAPI:
    """API for accessing and managing surveillance recordings database."""
    
    def __init__(self, db_path: str = None, db_connection=None):
        """Initialize the API with database connection.
        
        Args:
            db_path: Path to SQLite database file (if creating new connection)
            db_connection: Existing database connection to reuse
        """
        # Ensure path is expanded if it contains ~ or $HOME
        if db_path:
            self.db_path = os.path.expanduser(db_path)
        else:
            self.db_path = db_path
            
        self.db_conn = db_connection
        self._owns_connection = db_connection is None
        
        if self._owns_connection and self.db_path:
            self._init_connection()
        
    def _init_connection(self):
        """Initialize database connection."""
        try:
            self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.db_conn and self._owns_connection:
            self.db_conn.close()
            self.db_conn = None
            
    def get_recordings(self, 
                       stream_id: Optional[str] = None, 
                       limit: int = 100, 
                       offset: int = 0,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       object_type: Optional[str] = None,
                       min_confidence: Optional[float] = None,
                       sort_by: str = "timestamp",
                       sort_order: str = "desc") -> List[Dict]:
        """Get recordings from the database.
        
        Args:
            stream_id: Filter by stream ID (optional)
            limit: Maximum number of recordings to return
            offset: Offset for pagination
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            object_type: Filter by object type
            min_confidence: Minimum confidence threshold
            sort_by: Field to sort by
            sort_order: Sort direction (asc, desc)
            
        Returns:
            List of recording information dictionaries
        """
        query = 'SELECT * FROM recordings WHERE retained = 1'
        params = []
        
        if stream_id:
            query += ' AND stream_id = ?'
            params.append(stream_id)
            
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
            
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        # Filter by object type if specified
        if object_type:
            query += " AND objects_detected LIKE ? "
            params.append(f'%"{object_type}"%')
        
        # Filter by minimum confidence if specified
        if min_confidence is not None:
            query += " AND confidence >= ? "
            params.append(min_confidence)
        
        # Handle sorting (with SQL injection protection by validating in the FastAPI endpoint)
        if sort_order.lower() not in ('asc', 'desc'):
            sort_order = 'DESC'
        else:
            sort_order = sort_order.upper()
            
        if sort_by == 'timestamp':
            sort_column = 'timestamp'
        elif sort_by == 'confidence':
            sort_column = 'confidence'
        elif sort_by == 'duration':
            sort_column = 'duration'
        else:
            sort_column = 'timestamp'
            
        query += f' ORDER BY {sort_column} {sort_order} LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(query, params)
            
            columns = [col[0] for col in cursor.description]
            recordings = []
            
            for row in cursor.fetchall():
                recording = dict(zip(columns, row))
                
                # Parse JSON fields
                recording['objects_detected'] = json.loads(recording['objects_detected'])
                
                recordings.append(recording)
                
            return recordings
        except Exception as e:
            logger.error(f"Error retrieving recordings: {e}")
            return []
            
    def get_recordings_count(self, 
                          stream_id: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          object_type: Optional[str] = None,
                          min_confidence: Optional[float] = None) -> int:
        """Get total count of recordings matching the filters.
        
        Args:
            stream_id: Filter by stream ID (optional)
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            object_type: Filter by object type
            min_confidence: Filter by minimum confidence
            
        Returns:
            Total count of matching recordings
        """
        query = 'SELECT COUNT(*) FROM recordings WHERE retained = 1'
        params = []
        
        if stream_id:
            query += ' AND stream_id = ?'
            params.append(stream_id)
            
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
            
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        # Filter by object type if specified
        if object_type:
            query += " AND objects_detected LIKE ? "
            params.append(f'%"{object_type}"%')
        
        # Filter by minimum confidence if specified
        if min_confidence is not None:
            query += " AND confidence >= ? "
            params.append(min_confidence)
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting recordings count: {e}")
            return 0
    
    def get_recording_by_id(self, recording_id: int) -> Optional[Dict]:
        """Get a specific recording by ID.
        
        Args:
            recording_id: The ID of the recording to retrieve
            
        Returns:
            Recording information or None if not found
        """
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('SELECT * FROM recordings WHERE id = ? AND retained = 1', (recording_id,))
            result = cursor.fetchone()
            
            if not result:
                return None
                
            columns = [col[0] for col in cursor.description]
            recording = dict(zip(columns, result))
            
            # Parse JSON fields
            recording['objects_detected'] = json.loads(recording['objects_detected'])
            
            return recording
        except Exception as e:
            logger.error(f"Error retrieving recording {recording_id}: {e}")
            return None
    
    def delete_recording(self, recording_id: int) -> bool:
        """Delete a recording and its files.
        
        Args:
            recording_id: ID of the recording to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('SELECT file_path, thumbnail_path FROM recordings WHERE id = ?', (recording_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
                
            file_path, thumbnail_path = result
            
            # Delete the files
            if os.path.exists(file_path):
                os.remove(file_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                
            # Delete from database
            cursor.execute('DELETE FROM recordings WHERE id = ?', (recording_id,))
            self.db_conn.commit()
            
            logger.info(f"Deleted recording {recording_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting recording {recording_id}: {e}")
            return False
    
    def get_alerts(self, 
                   limit: int = 100, 
                   offset: int = 0,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   object_type: Optional[str] = None,
                   min_confidence: float = 0.5) -> List[Dict]:
        """Get detection alerts from recordings.
        
        Args:
            limit: Maximum number of alerts to return
            offset: Offset for pagination
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            object_type: Filter by object type
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of alerts with detection information
        """
        try:
            cursor = self.db_conn.cursor()
            
            query = '''
            SELECT id, timestamp, stream_id, stream_name, confidence, objects_detected, thumbnail_path
            FROM recordings WHERE retained = 1 AND confidence >= ?
            '''
            params = [min_confidence]
            
            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)
                
            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)
            
            # Filter by object type if specified
            if object_type:
                query += " AND objects_detected LIKE ? "
                params.append(f'%"{object_type}"%')
                
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            
            columns = [col[0] for col in cursor.description]
            alerts = []
            
            for row in cursor.fetchall():
                alert = dict(zip(columns, row))
                
                # Parse JSON objects
                alert['objects_detected'] = json.loads(alert['objects_detected'])
                
                # Filter objects in results if object_type is specified
                if object_type:
                    alert['objects_detected'] = [
                        obj for obj in alert['objects_detected'] 
                        if obj.get('class') == object_type
                    ]
                
                # Restructure for API
                object_counts = {}
                for obj in alert['objects_detected']:
                    obj_class = obj.get('class')
                    if obj_class not in object_counts:
                        object_counts[obj_class] = 0
                    object_counts[obj_class] += 1
                
                alert['object_counts'] = object_counts
                alerts.append(alert)
                
            return alerts
        except Exception as e:
            logger.error(f"Error retrieving alerts: {e}")
            return []
    
    def get_alerts_count(self, 
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        object_type: Optional[str] = None,
                        min_confidence: float = 0.5) -> int:
        """Get total count of alerts matching the filters.
        
        Args:
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            object_type: Filter by object type
            min_confidence: Minimum confidence threshold
            
        Returns:
            Total count of matching alerts
        """
        query = 'SELECT COUNT(*) FROM recordings WHERE retained = 1 AND confidence >= ?'
        params = [min_confidence]
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
            
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        # Filter by object type if specified
        if object_type:
            query += " AND objects_detected LIKE ? "
            params.append(f'%"{object_type}"%')
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting alerts count: {e}")
            return 0
    
    def get_object_stats(self, 
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        stream_id: Optional[str] = None) -> Dict:
        """Get statistics about detected objects over time.
        
        Args:
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            stream_id: Stream ID filter
            
        Returns:
            Dictionary with object statistics
        """
        try:
            cursor = self.db_conn.cursor()
            
            query = 'SELECT objects_detected FROM recordings WHERE retained = 1'
            params = []
            
            if stream_id:
                query += ' AND stream_id = ?'
                params.append(stream_id)
                
            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)
                
            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)
                
            cursor.execute(query, params)
            
            # Process results
            object_counts = {}
            total_recordings = 0
            for row in cursor.fetchall():
                total_recordings += 1
                objects = json.loads(row[0])
                
                # Count unique object types per recording
                seen_objects = set()
                for obj in objects:
                    obj_class = obj.get('class')
                    if obj_class:
                        seen_objects.add(obj_class)
                
                # Update global counts
                for obj_class in seen_objects:
                    if obj_class not in object_counts:
                        object_counts[obj_class] = 0
                    object_counts[obj_class] += 1
            
            # Format results
            result = {
                'total_recordings': total_recordings,
                'object_counts': object_counts,
                'object_percentages': {}
            }
            
            # Calculate percentages
            if total_recordings > 0:
                for obj_class, count in object_counts.items():
                    result['object_percentages'][obj_class] = round(count / total_recordings * 100, 2)
                    
            return result
        except Exception as e:
            logger.error(f"Error getting object stats: {e}")
            return {'total_recordings': 0, 'object_counts': {}, 'object_percentages': {}}
    
    def get_time_stats(self, 
                      object_type: Optional[str] = None,
                      days: int = 7,
                      stream_id: Optional[str] = None) -> Dict:
        """Get detection statistics by time of day.
        
        Args:
            object_type: Filter by object type
            days: Number of days to analyze
            stream_id: Stream ID filter
            
        Returns:
            Dictionary with time statistics
        """
        try:
            cursor = self.db_conn.cursor()
            
            # Calculate date for filtering
            now = datetime.now()
            start_date = (now - timedelta(days=days)).strftime('%Y-%m-%d')
            
            query = 'SELECT timestamp, objects_detected FROM recordings WHERE retained = 1 AND timestamp >= ?'
            params = [start_date]
            
            if stream_id:
                query += ' AND stream_id = ?'
                params.append(stream_id)
                
            cursor.execute(query, params)
            
            # Process results
            hour_counts = {h: 0 for h in range(24)}  # One count for each hour of the day
            day_counts = {d: 0 for d in range(7)}    # One count for each day of the week
            
            for row in cursor.fetchall():
                timestamp, objects_json = row
                objects = json.loads(objects_json)
                
                # Skip if filtering by object type and it's not present
                if object_type and not any(obj.get('class') == object_type for obj in objects):
                    continue
                    
                # Parse timestamp
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                # Count by hour of day
                hour_counts[dt.hour] += 1
                
                # Count by day of week (0 = Monday, 6 = Sunday)
                day_counts[dt.weekday()] += 1
                
            # Format results
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            result = {
                'hours': [
                    {'hour': h, 'detections': hour_counts[h]} for h in range(24)
                ],
                'days': [
                    {'day': day_names[d], 'detections': day_counts[d]} for d in range(7)
                ]
            }
                    
            return result
        except Exception as e:
            logger.error(f"Error getting time stats: {e}")
            return {'hours': [], 'days': []}
    
    def get_stream_stats(self, stream_id: str) -> Dict:
        """Get recording statistics for a specific stream.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            Dictionary with stream statistics
        """
        try:
            cursor = self.db_conn.cursor()
            
            # Get total recordings and total duration
            cursor.execute(
                'SELECT COUNT(*), SUM(duration) FROM recordings WHERE stream_id = ? AND retained = 1',
                (stream_id,)
            )
            count, total_duration = cursor.fetchone()
            
            # Get latest recording time
            cursor.execute(
                'SELECT timestamp FROM recordings WHERE stream_id = ? AND retained = 1 ORDER BY timestamp DESC LIMIT 1',
                (stream_id,)
            )
            latest = cursor.fetchone()
            
            return {
                'recording_count': count or 0,
                'total_duration': total_duration or 0,
                'latest_recording': latest[0] if latest else None
            }
        except Exception as e:
            logger.error(f"Error getting stream stats: {e}")
            return {'recording_count': 0, 'total_duration': 0, 'latest_recording': None}
    
    def get_comprehensive_stats(self,
                               stream_id: Optional[str] = None,
                               start_date: Optional[str] = None,
                               end_date: Optional[str] = None) -> Dict:
        """Get comprehensive recording statistics.
        
        Args:
            stream_id: Filter by stream ID (optional)
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            
        Returns:
            Dictionary with comprehensive statistics matching API spec
        """
        try:
            cursor = self.db_conn.cursor()
            
            # Build base query with filters
            query = 'SELECT * FROM recordings WHERE retained = 1'
            params = []
            
            if stream_id:
                query += ' AND stream_id = ?'
                params.append(stream_id)
            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)
            
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            recordings = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Initialize stats
            total_recordings = len(recordings)
            total_duration = 0
            total_size = 0
            object_counts = {}
            tracker_counts = {}
            camera_stats = {}
            oldest_timestamp = None
            newest_timestamp = None
            
            # Process each recording
            for rec in recordings:
                # Duration
                if rec.get('duration'):
                    total_duration += rec['duration']
                
                # File size
                if rec.get('file_size'):
                    total_size += rec['file_size']
                
                # Timestamps
                timestamp = rec.get('timestamp')
                if timestamp:
                    if oldest_timestamp is None or timestamp < oldest_timestamp:
                        oldest_timestamp = timestamp
                    if newest_timestamp is None or timestamp > newest_timestamp:
                        newest_timestamp = timestamp
                
                # Objects
                if rec.get('objects_detected'):
                    try:
                        objects = json.loads(rec['objects_detected'])
                        seen_objects = set()
                        for obj in objects:
                            obj_class = obj.get('class')
                            if obj_class:
                                seen_objects.add(obj_class)
                        
                        for obj_class in seen_objects:
                            object_counts[obj_class] = object_counts.get(obj_class, 0) + 1
                    except:
                        pass
                
                # Trackers
                if rec.get('tracker_ids'):
                    try:
                        tracker_ids = json.loads(rec['tracker_ids'])
                        for tracker_id in tracker_ids:
                            tracker_counts[tracker_id] = tracker_counts.get(tracker_id, 0) + 1
                    except:
                        pass
                
                # Camera/stream stats
                stream = rec.get('stream_id') or rec.get('stream_name', 'unknown')
                if stream not in camera_stats:
                    camera_stats[stream] = {'count': 0, 'duration_seconds': 0}
                camera_stats[stream]['count'] += 1
                if rec.get('duration'):
                    camera_stats[stream]['duration_seconds'] += rec['duration']
            
            # Get most frequent trackers
            most_frequent_trackers = sorted(
                [{'tracker_id': tid, 'appearances': count} for tid, count in tracker_counts.items()],
                key=lambda x: x['appearances'],
                reverse=True
            )[:10]  # Top 10
            
            # Build response
            return {
                'total_recordings': total_recordings,
                'total_duration_seconds': round(total_duration, 2),
                'total_size_bytes': total_size,
                'total_size_gb': round(total_size / (1024**3), 2) if total_size > 0 else 0,
                'oldest_recording': oldest_timestamp,
                'newest_recording': newest_timestamp,
                'objects': object_counts,
                'trackers': {
                    'total_unique_ids': len(tracker_counts),
                    'most_frequent': most_frequent_trackers
                },
                'by_camera': camera_stats
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive stats: {e}")
            return {
                'total_recordings': 0,
                'total_duration_seconds': 0,
                'total_size_bytes': 0,
                'total_size_gb': 0,
                'oldest_recording': None,
                'newest_recording': None,
                'objects': {},
                'trackers': {'total_unique_ids': 0, 'most_frequent': []},
                'by_camera': {}
            }
