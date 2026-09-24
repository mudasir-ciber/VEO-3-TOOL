"""Abstract base class for Google Flow connectors."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Optional

class BaseFlowConnector(ABC):
    @abstractmethod
    def initialize(self, headless: bool = False, profile_dir: Optional[Path] = None) -> Tuple[bool, str]:
        """Launch or connect to browser session."""
        pass

    @abstractmethod
    def check_authenticated(self) -> Tuple[bool, str]:
        """Verify whether the session is currently authenticated to Google Flow."""
        pass

    @abstractmethod
    def prepare_scene_interface(self) -> Tuple[bool, str]:
        """Ensure the generation UI is ready for new input."""
        pass

    @abstractmethod
    def upload_reference(self, image_path: Path) -> Tuple[bool, str]:
        """Upload the Master Image or previous scene's last frame as reference."""
        pass

    @abstractmethod
    def submit_prompt(self, prompt_text: str) -> Tuple[bool, str]:
        """Paste and verify prompt text in the prompt field."""
        pass

    @abstractmethod
    def trigger_generation(self) -> Tuple[bool, str]:
        """Click the generate button."""
        pass

    @abstractmethod
    def wait_for_completion(self, timeout_sec: float = 600.0) -> Tuple[bool, str]:
        """Wait for video generation to genuinely finish (no fixed timers)."""
        pass

    @abstractmethod
    def download_video(self, destination_mp4_path: Path, timeout_sec: float = 300.0) -> Tuple[bool, str]:
        """Download the generated video file directly to the project's destination."""
        pass

    @abstractmethod
    def close(self):
        """Clean up browser session."""
        pass
