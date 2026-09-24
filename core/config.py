"""Configuration, constants, and default settings for Chained Evolution Studio."""
import os
import sys
from pathlib import Path

# Application Metadata
APP_NAME = "Chained Evolution Studio"
APP_VERSION = "1.0.0"
AUTHOR = "DeepMind / Pair Programmer"

# Base paths
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR))
else:
    BASE_DIR = Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    BUNDLE_DIR = BASE_DIR

DEFAULT_PROJECTS_DIR = BASE_DIR / "Projects"
DEFAULT_BROWSER_PROFILE_DIR = BASE_DIR / "browser_profile"
LOGS_DIR = BASE_DIR / "logs"

# Sub-folder names inside every project
DIR_MASTER = "Master"
DIR_VIDEOS = "Videos"
DIR_LAST_FRAMES = "Last Frames"
DIR_PROMPTS = "Prompts"
DIR_STATE = "Project State"
DIR_LOGS = "Logs"

STATE_FILE_NAME = "state.json"
MASTER_IMAGE_NAME = "Master Image.png"

# Default Execution Parameters
DEFAULT_MAX_RETRIES = 3
DEFAULT_VIDEO_POLL_INTERVAL_SEC = 2.0
DEFAULT_DOWNLOAD_STABILIZE_SEC = 2.0
DEFAULT_DOWNLOAD_TIMEOUT_SEC = 300  # 5 minutes
DEFAULT_GENERATION_TIMEOUT_SEC = 600  # 10 minutes

# Browser Defaults
DEFAULT_BROWSER_CHANNEL = "chrome"  # use installed Google Chrome
GOOGLE_FLOW_URL = "https://flow.google"
FALLBACK_LABS_URL = "https://labs.google/fx/tools/flow"
DEFAULT_FLOW_PROJECT_URL = "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4"

SETTINGS_FILE = BASE_DIR / "app_settings.json"

def get_flow_project_url() -> str:
    """Retrieve saved Google Flow project URL or return default."""
    import json
    if SETTINGS_FILE.is_file():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("flow_project_url", DEFAULT_FLOW_PROJECT_URL)
        except Exception:
            pass
    return DEFAULT_FLOW_PROJECT_URL

def set_flow_project_url(url: str):
    """Save Google Flow project URL to settings file."""
    import json
    data = {}
    if SETTINGS_FILE.is_file():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["flow_project_url"] = url.strip()
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# Sound configurations
ENABLE_SOUNDS = True

