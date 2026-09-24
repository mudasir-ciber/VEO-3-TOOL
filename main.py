"""Desktop Entrypoint for Chained Evolution Studio."""
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.config import APP_NAME, APP_VERSION
from core.system_checker import SystemChecker
from core.logger import logger
from ui.main_window import MainWindow


def main():
    # Windows high-DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ChainedEvolution")

    # Run initial system check
    sys_info = SystemChecker.get_system_info()
    logger.info(f"Starting {APP_NAME} v{APP_VERSION} on {sys_info['platform_detail']} ({sys_info['architecture']})")
    if not sys_info["compatibility_passed"]:
        for msg in sys_info["compatibility_messages"]:
            logger.warning(f"Compatibility alert: {msg}")

    # Launch UI
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
