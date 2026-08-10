# Object Tracking - Usage Guide

**How to use the tracking feature effectively**

Tracking is configured under `detection.tracking` in `config/spectrax.yml` and
implemented with [Roboflow supervision](https://github.com/roboflow/supervision)
ByteTrack. Query stored tracker IDs via the authenticated recordings API or
`scripts/query_recordings.py`.

---

## 🎯 What Tracking Gives You

With object tracking enabled, you can now:

1. **Track individual objects** across frames with persistent IDs
2. **Query recordings** by specific tracker ID
3. **Analyze object behavior** - how long objects stay in frame
4. **Count unique objects** - know how many different people/cars appeared
5. **Build movement patterns** - track where objects go

---

## 📊 Data Storage

### What's Stored in Database

Every recording now includes:

```json
{
  "id": 1,
  "timestamp": "2025-10-12 19:00:00",
  "stream_name": "iphone",
  "duration": 25.3,
  "confidence": 0.95,
  "tracker_ids": [1, 2, 5],  // ← NEW: Unique tracker IDs in this recording
  "objects_detected": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": [100, 200, 300, 400],
      "tracker_id": 1  // ← NEW: Persistent ID for this object
    },
    {
      "class": "laptop",
      "confidence": 0.51,
      "bbox": [150, 250, 350, 450],
      "tracker_id": 28
    }
  ]
}
```

---

## 🔍 Querying Recordings

### Using the Query Tool

I've created a helper script: `scripts/query_recordings.py`

#### 1. List Recent Recordings

```bash
python scripts/query_recordings.py list --limit 10
```

**Output:**
```
📹 Recent Recordings (last 10):
================================================================================

🎬 Recording #5
   Time: 2025-10-12 19:05:30
   Stream: iphone
   Duration: 15.2s
   Confidence: 0.95
   Objects: person, laptop
   Tracker IDs: [1, 28]
```

#### 2. Find All Recordings of a Specific Object

**Example: Find all recordings where person #1 appeared**

```bash
python scripts/query_recordings.py tracker 1
```

**Output:**
```
🔍 Found 3 recording(s) with tracker ID #1:
================================================================================

🎬 Recording #5
   Time: 2025-10-12 19:05:30
   Stream: iphone
   Duration: 15.2s
   All Tracker IDs: [1, 28]
   Tracker #1: person (confidence: 0.95)

🎬 Recording #3
   Time: 2025-10-12 19:02:15
   Stream: iphone
   Duration: 20.5s
   All Tracker IDs: [1]
   Tracker #1: person (confidence: 0.92)
```

**Use Case:** "Show me all times this person appeared"

#### 3. Find Recordings by Object Class

```bash
python scripts/query_recordings.py object person
```

**Output:**
```
🔍 Found 5 recording(s) with 'person':
================================================================================

🎬 Recording #5
   Time: 2025-10-12 19:05:30
   Stream: iphone
   Duration: 15.2s
   Tracker IDs: [1, 28]
   Person instances: 1
      - Tracker #1: confidence 0.95
```

#### 4. Get Tracker Statistics

```bash
python scripts/query_recordings.py stats
```

**Output:**
```
📊 Tracker Statistics:
================================================================================

Total unique trackers: 15

Most frequently recorded trackers:
   Tracker #1: 5 recording(s) - mostly 'person'
   Tracker #28: 3 recording(s) - mostly 'laptop'
   Tracker #5: 2 recording(s) - mostly 'person'
```

---

## 💡 Practical Use Cases

### 1. **Security Monitoring**

**Scenario:** Someone suspicious appeared. Find all their appearances.

```bash
# Watch live stream, note their tracker ID (e.g., #42)
# Later, query all recordings:
python scripts/query_recordings.py tracker 42
```

**Result:** See all times that person appeared, with timestamps and durations.

---

### 2. **Visitor Tracking**

**Scenario:** Count how many different people visited today.

```bash
# Get statistics
python scripts/query_recordings.py stats

# Look for unique person tracker IDs
```

**Result:** Each unique person gets a unique tracker ID (within a session).

---

### 3. **Object Dwell Time**

**Scenario:** How long did a car stay in the driveway?

```bash
# Note the car's tracker ID (e.g., #15)
python scripts/query_recordings.py tracker 15

# Check duration of recordings
```

**Result:** See total time the car was detected.

---

### 4. **Movement Patterns**

**Scenario:** Track a person's path through multiple cameras.

```bash
# If you have multiple cameras
python scripts/query_recordings.py tracker 7

# See which cameras detected this person
```

**Result:** Understand movement patterns across zones.

---

## 🗄️ Direct Database Queries

You can also query the database directly with SQL:

```bash
sqlite3 ~/video-feed-recordings/recordings.db
```

### Example Queries

#### Find recordings with multiple objects

```sql
SELECT id, timestamp, tracker_ids, 
       json_array_length(tracker_ids) as num_objects
FROM recordings
WHERE json_array_length(tracker_ids) > 1
ORDER BY num_objects DESC;
```

#### Find recordings with specific tracker ID

```sql
SELECT id, timestamp, stream_name, duration
FROM recordings
WHERE tracker_ids LIKE '%5%'
ORDER BY timestamp DESC;
```

#### Count recordings per tracker

```sql
SELECT 
    json_each.value as tracker_id,
    COUNT(*) as recording_count
FROM recordings, json_each(recordings.tracker_ids)
GROUP BY json_each.value
ORDER BY recording_count DESC;
```

---

## 📈 Advanced Analytics (Future)

### What You Can Build

With this tracking data, you can create:

1. **Heatmaps** - Where objects spend most time
2. **Traffic counters** - How many people/cars passed
3. **Dwell time analysis** - Average time objects stay
4. **Zone violations** - Detect objects in restricted areas
5. **Behavior patterns** - Identify unusual movements

### Example: Daily Traffic Report

```python
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('~/video-feed-recordings/recordings.db')
cursor = conn.cursor()

# Get unique trackers from last 24 hours
yesterday = (datetime.now() - timedelta(days=1)).isoformat()

cursor.execute('''
    SELECT DISTINCT json_each.value
    FROM recordings, json_each(recordings.tracker_ids)
    WHERE timestamp > ?
    AND json_extract(objects_detected, '$[0].class') = 'person'
''', (yesterday,))

unique_people = len(cursor.fetchall())
print(f"Unique people detected in last 24h: {unique_people}")
```

---

## ⚠️ Important Notes

### Tracker ID Lifecycle

- **IDs are session-based**: Tracker IDs reset when you restart the system
- **IDs are per-camera**: Camera A's tracker #1 ≠ Camera B's tracker #1
- **IDs persist during occlusion**: Brief hiding maintains the same ID
- **IDs are lost after 30 frames**: If object leaves for >30 frames, new ID assigned

### Best Practices

1. **Note important tracker IDs**: When you see something interesting, write down the tracker ID
2. **Query soon**: Since IDs reset on restart, query while system is running or shortly after
3. **Use object class filters**: Combine tracker ID with object class for better results
4. **Check timestamps**: Recordings are timestamped for easy correlation

---

## 🚀 Next Steps

### Phase 3: Enhanced Tracking (Future)

- **Persistent IDs across sessions**: Save tracker ID mappings
- **Cross-camera tracking**: Track objects across multiple cameras
- **Re-identification**: Recognize returning objects even after ID reset

### Phase 4: Zone Analytics (Future)

- **Define zones**: Mark areas in configuration
- **Line crossing**: Count objects crossing boundaries
- **Restricted areas**: Alert when objects enter forbidden zones
- **Dwell time**: Measure how long objects stay in zones

---

## 📝 Quick Reference

```bash
# List recent recordings
python scripts/query_recordings.py list

# Find specific tracker
python scripts/query_recordings.py tracker 1

# Find object class
python scripts/query_recordings.py object person

# Get statistics
python scripts/query_recordings.py stats

# Direct database access
sqlite3 ~/video-feed-recordings/recordings.db
```

---

## 🎓 Example Workflow

1. **Start system**: `./scripts/surveillance.sh config`
2. **Watch live stream**: Note interesting tracker IDs
3. **Query later**: `python scripts/query_recordings.py tracker 5`
4. **Analyze**: See all appearances of that object
5. **Export**: Use SQL queries for custom reports

---

**The tracking feature is now fully functional and storing data!** 🎉

Start using it to gain insights into object movements and behaviors in your surveillance footage.
