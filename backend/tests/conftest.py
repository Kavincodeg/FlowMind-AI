"""
Global pytest configuration for FlowMind backend tests.
Sets DEMO_MODE=true by default during test runs so preset test tokens authenticate,
while test_demo_mode.py explicitly tests DEMO_MODE=false behavior via monkeypatch / patch.dict.
"""
import os

os.environ.setdefault("DEMO_MODE", "true")
