"""
Extension-driven Google Flow Connector
Communicates strictly through the VEO 3 Chrome Extension Bridge without touching Chrome processes.
"""
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from connector.flow_base import BaseFlowConnector
from core.extension_bridge import ExtensionBridgeServer, ExtensionProfile
from core.logger import logger


class ExtensionFlowConnector(BaseFlowConnector):
    def __init__(self, target_profile_name: str = "Default"):
        self.profile_name = target_profile_name
        self.bridge = ExtensionBridgeServer.get_instance()
        self.is_connected = False
        self.current_scene = 1

    def set_profile_name(self, profile_name: str):
        self.profile_name = profile_name.strip()

    def set_current_scene(self, scene_number: int):
        self.current_scene = scene_number

    def initialize(self, headless: bool = False, profile_dir: Optional[Path] = None, chrome_profile: Optional[Any] = None) -> Tuple[bool, str]:
        """Check if selected profile extension is alive and connected."""
        if chrome_profile:
            self.profile_name = getattr(chrome_profile, "display_name", str(chrome_profile))

        if not self.bridge.is_running:
            self.bridge.start()

        if self.bridge.is_profile_connected(self.profile_name):
            self.is_connected = True
            logger.info(f"✓ Bound to Chrome Extension Profile: '{self.profile_name}'")
            return True, f"Connected to profile '{self.profile_name}'"

        return False, f"Profile '{self.profile_name}' is not currently connected. Please open Chrome with the extension."

    def is_flow_tab_ready(self) -> bool:
        """Check if selected profile extension is reporting FLOW_READY or connected."""
        prof = self.bridge.get_profile_by_name(self.profile_name)
        if prof and prof.is_online():
            return prof.flow_status == "FLOW_READY" or prof.project_verified or prof.flow_tab_id is not None
        return False

    def check_authenticated(self) -> Tuple[bool, str]:
        prof = self.bridge.get_profile_by_name(self.profile_name)
        if prof and prof.flow_status == "FLOW_AUTH_REQUIRED":
            return False, "Google Account login required in Chrome."
        return True, "Authenticated"

    def navigate_to_exact_project(self, project_url: str) -> Tuple[bool, str]:
        """Check existing Flow project tab."""
        ok, res = self.bridge.send_command(
            profile_name=self.profile_name,
            command_name="GET_FLOW_STATUS",
            wait_timeout_sec=5.0
        )
        if ok and res.get("flowStatus") == "FLOW_READY":
            return True, "Existing Google Flow project tab is ready"
        elif ok and res.get("flowStatus") == "FLOW_PROJECT_MISMATCH":
            return False, "FLOW_PROJECT_MISMATCH: Google Flow is open, but on a different project. Please navigate to the configured project."
        return True, "Flow status checked"

    def verify_exact_project(self, project_url: str, timeout_sec: float = 30.0) -> Tuple[bool, str]:
        """Verify the exact Google Flow project is ready in the selected profile."""
        return self.bridge.verify_exact_project(self.profile_name, timeout_sec=timeout_sec)

    def prepare_scene_interface(self) -> Tuple[bool, str]:
        """Focus the Flow tab in the selected profile."""
        self.bridge.send_command(
            profile_name=self.profile_name,
            command_name="ACTIVATE_FLOW_TAB",
            wait_timeout_sec=2.0
        )
        return True, "Flow interface ready"

    def upload_reference(self, image_path: Path) -> Tuple[bool, str]:
        """Upload reference image into Flow interface via the selected extension instance."""
        return self.bridge.upload_reference(self.profile_name, image_path, scene_num=self.current_scene)

    def submit_prompt(self, prompt_text: str) -> Tuple[bool, str]:
        """Submit scene prompt into Flow interface via the selected extension instance."""
        return self.bridge.submit_prompt(self.profile_name, prompt_text, scene_num=self.current_scene)

    def trigger_generation(self) -> Tuple[bool, str]:
        """Click Generate button in Flow interface via the selected extension instance."""
        return self.bridge.trigger_generation(self.profile_name, scene_num=self.current_scene)

    def wait_for_completion(self, timeout_sec: float = 600.0) -> Tuple[bool, str]:
        """Poll the selected extension instance until video generation completes."""
        return self.bridge.wait_for_completion(self.profile_name, scene_num=self.current_scene, timeout_sec=timeout_sec)

    def download_video(self, destination_mp4_path: Path, timeout_sec: float = 60.0) -> Tuple[bool, str]:
        """Download generated video from the selected extension instance and verify on disk."""
        return self.bridge.download_video(self.profile_name, destination_mp4_path, scene_num=self.current_scene, timeout_sec=timeout_sec)

    def close(self):
        """Clean disconnect without touching user Chrome windows or tabs."""
        self.is_connected = False
        logger.info(f"Disconnected from extension profile '{self.profile_name}'. Chrome windows remain untouched.")
