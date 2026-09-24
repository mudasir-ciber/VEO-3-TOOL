"""Thread-safe application and project logger."""
import os
import sys
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

class AppLogger:
    _instance: Optional['AppLogger'] = None
    _lock = threading.Lock()

    def __init__(self):
        self._callbacks: list[Callable[[str, str, str], None]] = []  # (timestamp, level, message)
        self._project_log_file: Optional[Path] = None
        self._file_lock = threading.Lock()

        # Setup standard python logging to console
        self._logger = logging.getLogger("ChainedEvolutionStudio")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            import io
            stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True) if hasattr(sys.stdout, 'buffer') else sys.stdout
            ch = logging.StreamHandler(stream)
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            ch.setFormatter(formatter)
            self._logger.addHandler(ch)

    @classmethod
    def get_instance(cls) -> 'AppLogger':
        with cls._lock:
            if cls._instance is None:
                cls._instance = AppLogger()
            return cls._instance

    def set_project_log_file(self, log_path: Path):
        with self._file_lock:
            self._project_log_file = Path(log_path)
            self._project_log_file.parent.mkdir(parents=True, exist_ok=True)

    def register_callback(self, cb: Callable[[str, str, str], None]):
        """Register a callback for UI updates: cb(timestamp, level, message)"""
        with self._lock:
            if cb not in self._callbacks:
                self._callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[str, str, str], None]):
        with self._lock:
            if cb in self._callbacks:
                self._callbacks.remove(cb)

    def _log(self, level: str, message: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Standard console log
        if level == "DEBUG":
            self._logger.debug(message)
        elif level == "WARNING":
            self._logger.warning(message)
        elif level == "ERROR":
            self._logger.error(message)
        else:
            self._logger.info(message)

        # File log
        line = f"[{now_str}] [{level}] {message}\n"
        with self._file_lock:
            if self._project_log_file:
                try:
                    with open(self._project_log_file, "a", encoding="utf-8") as f:
                        f.write(line)
                except Exception:
                    pass

        # UI Callbacks
        with self._lock:
            for cb in self._callbacks:
                try:
                    cb(now_str, level, message)
                except Exception:
                    pass

    def info(self, message: str):
        self._log("INFO", message)

    def warning(self, message: str):
        self._log("WARNING", message)

    def error(self, message: str):
        self._log("ERROR", message)

    def debug(self, message: str):
        self._log("DEBUG", message)

    def success(self, message: str):
        self._log("SUCCESS", message)


# Convenience singleton accessor
logger = AppLogger.get_instance()
