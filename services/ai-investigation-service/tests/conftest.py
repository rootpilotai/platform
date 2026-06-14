"""Shared fixtures for ai-investigation-service tests."""

import sys
from pathlib import Path

# Add service root and project root to sys.path
_service_root = Path(__file__).parent.parent
_project_root = _service_root.parent.parent
sys.path.insert(0, str(_service_root))
sys.path.insert(0, str(_project_root))
