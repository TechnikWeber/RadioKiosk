"""Tests run against a throwaway settings folder, never the user's own."""

import os
import tempfile

os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="radiokiosk-test-")
os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp(prefix="radiokiosk-test-")
