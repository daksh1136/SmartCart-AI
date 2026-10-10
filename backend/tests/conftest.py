"""Tests must never touch a developer's persistent SmartCart demo database."""
import os
import tempfile
from pathlib import Path

os.environ["SMARTCART_DB"] = str(Path(tempfile.mkdtemp(prefix="smartcart-tests-")) / "test.db")
