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

# Sound configurations
ENABLE_SOUNDS = True
