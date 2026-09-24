"""Chrome profile discovery, metadata extraction, and avatar processing."""
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from PySide6.QtGui import QPixmap, QImage, QPainter, QBrush, QColor, QFont, QPen
from PySide6.QtCore import Qt

from core.logger import logger


class ChromeProfile:
    def __init__(
        self,
        directory_name: str,
        display_name: str,
        email: str = "",
        gaia_name: str = "",
        avatar_path: Optional[Path] = None,
        is_default: bool = False
    ):
        self.directory_name = directory_name  # e.g. "Default", "Profile 17"
        self.display_name = display_name      # e.g. "YOUTUBE", "John"
        self.email = email                    # e.g. "youtubechannel4426@gmail.com"
        self.gaia_name = gaia_name            # e.g. "YOUTUBE CHANNEL"
        self.avatar_path = avatar_path
        self.is_default = is_default

    def to_dict(self) -> Dict[str, str]:
        return {
            "directory_name": self.directory_name,
            "display_name": self.display_name,
            "email": self.email,
            "gaia_name": self.gaia_name,
            "avatar_path": str(self.avatar_path) if self.avatar_path else None,
            "is_default": self.is_default
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ChromeProfile':
        return cls(
            directory_name=data.get("directory_name", "Default"),
            display_name=data.get("display_name", "Default Profile"),
            email=data.get("email", ""),
            gaia_name=data.get("gaia_name", ""),
            avatar_path=Path(data["avatar_path"]) if data.get("avatar_path") else None,
            is_default=data.get("is_default", False)
        )

    def get_avatar_pixmap(self, size: int = 40) -> QPixmap:
        """
        Returns a rounded circular QPixmap:
        - If a real Google Profile Picture.png exists, crops and scales it into a circle.
        - If missing, generates a stylish circular avatar with initial letter and color.
        """
        # 1. Try real Google Profile Picture
        if self.avatar_path and self.avatar_path.is_file():
            src_pix = QPixmap(str(self.avatar_path))
            if not src_pix.isNull():
                return self._render_circular_pixmap(src_pix, size)

        # 2. Fallback: Generate colored initial circle
        return self._generate_initial_avatar(size)

    def _render_circular_pixmap(self, src: QPixmap, size: int) -> QPixmap:
        scaled = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        out = QPixmap(size, size)
        out.fill(Qt.transparent)

        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        brush = QBrush(scaled)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return out

    def _generate_initial_avatar(self, size: int) -> QPixmap:
        initial = (self.display_name[:1] if self.display_name else "C").upper()
        # Hash display name to consistent pleasant background colors
        colors = [
            QColor("#4f46e5"), QColor("#0284c7"), QColor("#059669"),
            QColor("#d97706"), QColor("#dc2626"), QColor("#7c3aed"),
            QColor("#db2777"), QColor("#0891b2"), QColor("#475569")
        ]
        bg_color = colors[abs(hash(self.display_name)) % len(colors)]

        out = QPixmap(size, size)
        out.fill(Qt.transparent)

        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)

        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", int(size * 0.45), QFont.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, size, size, Qt.AlignCenter, initial)
        painter.end()
        return out


class ChromeProfileManager:
    _CONFIG_FILE = Path(__file__).resolve().parent.parent / "chrome_account_config.json"

    @classmethod
    def get_chrome_user_data_dir(cls) -> Optional[Path]:
        """Detect standard Windows Chrome User Data directory."""
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if not local_app_data:
            return None

        candidates = [
            Path(local_app_data) / "Google" / "Chrome" / "User Data",
            Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return None

    @classmethod
    def detect_all_profiles(cls) -> List[ChromeProfile]:
        """
        Dynamically scan Chrome's Local State file and detect ALL valid profiles.
        Excludes Guest and System profiles.
        """
        user_data = cls.get_chrome_user_data_dir()
        if not user_data:
            logger.warning("Google Chrome User Data directory could not be found.")
            return []

        local_state_file = user_data / "Local State"
        profiles: List[ChromeProfile] = []

        if local_state_file.is_file():
            try:
                with open(local_state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                info_cache = data.get("profile", {}).get("info_cache", {})
                for dir_name, p_data in info_cache.items():
                    # Strictly exclude Guest and System profiles
                    if "guest" in dir_name.lower() or "system" in dir_name.lower():
                        continue

                    raw_name = p_data.get("name", "")
                    gaia_name = p_data.get("gaia_name", "")
                    email = p_data.get("user_name", "")
                    avatar_file = p_data.get("gaia_picture_file_name", "Google Profile Picture.png")

                    # Friendly display name
                    display_name = raw_name or gaia_name or dir_name
                    # E.g. if name is "Work" and gaia is "HISTORY WARS" -> "HISTORY (Work)"
                    if gaia_name and raw_name and gaia_name.lower() != raw_name.lower():
                        if len(gaia_name) < 20:
                            display_name = f"{gaia_name} ({raw_name})"

                    # Look for profile picture
                    avatar_path = user_data / dir_name / avatar_file
                    if not avatar_path.is_file():
                        # Try standard fallback
                        fallback = user_data / dir_name / "Google Profile Picture.png"
                        avatar_path = fallback if fallback.is_file() else None

                    is_default = (dir_name.lower() == "default")

                    profiles.append(ChromeProfile(
                        directory_name=dir_name,
                        display_name=display_name,
                        email=email,
                        gaia_name=gaia_name,
                        avatar_path=avatar_path,
                        is_default=is_default
                    ))

            except Exception as e:
                logger.error(f"Error parsing Chrome Local State: {e}")

        # Fallback: scan disk directories if Local State info_cache had issues
        if not profiles:
            logger.info("Scanning User Data directory directly for profile folders...")
            for entry in user_data.iterdir():
                if entry.is_dir() and (entry.name == "Default" or entry.name.startswith("Profile ")):
                    if "guest" in entry.name.lower():
                        continue
                    profiles.append(ChromeProfile(
                        directory_name=entry.name,
                        display_name=entry.name,
                        email="",
                        is_default=(entry.name == "Default")
                    ))

        # Sort profiles: Default first, then alphabetically
        profiles.sort(key=lambda p: (0 if p.is_default else 1, p.display_name.lower()))
        logger.info(f"Detected {len(profiles)} Chrome profiles dynamically.")
        return profiles

    @classmethod
    def get_saved_profile(cls) -> Optional[ChromeProfile]:
        """Load currently linked profile configuration."""
        if cls._CONFIG_FILE.is_file():
            try:
                with open(cls._CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return ChromeProfile.from_dict(data)
            except Exception:
                pass
        return None

    @classmethod
    def save_linked_profile(cls, profile: ChromeProfile):
        """Save selected profile configuration."""
        try:
            with open(cls._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2)
            logger.info(f"Saved linked Chrome profile: {profile.display_name} ({profile.directory_name})")
        except Exception as e:
            logger.error(f"Failed to save linked profile: {e}")

    @classmethod
    def is_chrome_running(cls) -> bool:
        """Check if any Google Chrome process is currently running on Windows."""
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                text=True,
                errors="ignore"
            )
            return "chrome.exe" in output.lower()
        except Exception:
            return False

    @classmethod
    def is_cdp_available(cls, port: int = 9222) -> bool:
        """Check if Chrome DevTools Protocol (CDP) port is open and responding."""
        import urllib.request
        url = f"http://127.0.0.1:{port}/json/version"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ChainedEvolutionStudio"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    return "Browser" in data or "webSocketDebuggerUrl" in data
        except Exception:
            pass
        return False

    @classmethod
    def get_cdp_tabs(cls, port: int = 9222) -> List[Dict]:
        """Fetch list of open browser tabs via Chrome's CDP HTTP endpoint."""
        import urllib.request
        url = f"http://127.0.0.1:{port}/json/list"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ChainedEvolutionStudio"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    targets = json.loads(resp.read().decode())
                    return [t for t in targets if t.get("type") == "page"]
        except Exception as e:
            logger.debug(f"Could not fetch CDP tabs: {e}")
        return []

    @classmethod
    def find_flow_tabs(cls, port: int = 9222) -> List[Dict]:
        """Find any tabs that correspond to Google Flow."""
        tabs = cls.get_cdp_tabs(port=port)
        flow_tabs = []
        for t in tabs:
            url = t.get("url", "").lower()
            title = t.get("title", "").lower()
            if (
                "flow.google" in url or
                "labs.google/flow" in url or
                "labs.google/fx/tools/flow" in url or
                "google flow" in title or
                ("flow" in title and "google" in title)
            ):
                flow_tabs.append(t)
        return flow_tabs

    @classmethod
    def launch_chrome_with_cdp(
        cls,
        profile_dir_name: str = "Default",
        port: int = 9222,
        url: str = "https://flow.google.com/"
    ) -> Tuple[bool, str]:
        """Launch user's Chrome with remote debugging enabled for the specified profile."""
        from core.system_checker import SystemChecker
        chrome_exe = SystemChecker.find_chrome()
        if not chrome_exe or not Path(chrome_exe).is_file():
            return False, "Google Chrome executable was not found on this computer."

        user_data = cls.get_chrome_user_data_dir()
        if not user_data:
            return False, "Chrome User Data directory not found."

        cmd = [
            str(chrome_exe),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}",
            f"--profile-directory={profile_dir_name}",
            "--no-first-run",
            "--no-default-browser-check",
            url
        ]

        try:
            logger.info(f"Launching Chrome with CDP on port {port} (profile: {profile_dir_name})...")
            subprocess.Popen(cmd)
            return True, "Chrome launched with automation endpoint"
        except Exception as e:
            return False, f"Failed to launch Chrome: {e}"

