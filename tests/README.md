# SpectraX Test Suite

This directory contains all tests for the SpectraX surveillance system.

## Test Organization

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared pytest fixtures
├── test_db.py              # Database operations tests
├── test_db_connection.py   # Database connection tests
├── test_recording.py       # Recording manager tests
├── test_storage_location.py # Storage path tests
└── test_supervision_integration.py # Supervision library integration tests
```

## Running Tests

### Run all tests
```bash
cd video-feed
pytest
```

### Run specific test file
```bash
pytest tests/test_recording.py
```

### Run tests with specific markers
```bash
# Run only unit tests
pytest -m unit

# Run only database tests
pytest -m db

# Run only fast tests (exclude slow tests)
pytest -m "not slow"
```

### Run with verbose output
```bash
pytest -v
```

### Run with coverage report
```bash
pytest --cov=spectrax --cov-report=html
```

## Test Categories

Tests are organized using pytest markers:

- **`@pytest.mark.unit`** - Unit tests for individual functions/classes
- **`@pytest.mark.integration`** - Integration tests for component interaction
- **`@pytest.mark.db`** - Database-related tests
- **`@pytest.mark.recording`** - Recording functionality tests
- **`@pytest.mark.detection`** - Object detection tests
- **`@pytest.mark.slow`** - Tests that take significant time
- **`@pytest.mark.requires_mediamtx`** - Tests requiring MediaMTX installation

## Fixtures

Common test fixtures are defined in `conftest.py`:

- **`temp_dir`** - Temporary directory for test files
- **`test_db_path`** - Temporary database path
- **`test_recordings_dir`** - Temporary recordings directory
- **`sample_config`** - Sample configuration dictionary

## Writing New Tests

### Example test structure:

```python
import pytest
from spectrax.recorder import RecordingManager

@pytest.mark.unit
@pytest.mark.recording
def test_recording_manager_initialization(test_db_path, test_recordings_dir):
    """Test that RecordingManager initializes correctly."""
    manager = RecordingManager(
        db_path=test_db_path,
        recordings_dir=test_recordings_dir
    )
    
    assert manager.db_path == test_db_path
    assert manager.recordings_dir.exists()
```

## Best Practices

1. **Use fixtures** - Leverage shared fixtures from `conftest.py`
2. **Mark your tests** - Use appropriate markers for categorization
3. **Clean up** - Use fixtures with cleanup or context managers
4. **Isolate tests** - Each test should be independent
5. **Descriptive names** - Use clear, descriptive test function names
6. **Document** - Add docstrings explaining what each test validates

## CI/CD Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    cd video-feed
    pytest --cov=spectrax --cov-report=xml
```

## Troubleshooting

### Import errors
Make sure you're running pytest from the `video-feed` directory:
```bash
cd video-feed
pytest
```

### Database locked errors
Ensure no other processes are using the test database. Tests use temporary databases to avoid conflicts.

### Missing dependencies
Install test dependencies:
```bash
pip install pytest pytest-cov pytest-asyncio
```
