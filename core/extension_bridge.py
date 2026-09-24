"""Local HTTP bridge server enabling real-time communication between Chained Evolution Studio and the Chrome extension."""
import os
import sys
import time
import base64
import json
import urllib.request
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple, List

from core.logger import logger
from core.video_validator import VideoValidator


class ExtensionBridgeServer:
    _instance: Optional['ExtensionBridgeServer'] = None
    PORT = 18999

    def __init__(self, port: int = 18999):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.is_running = False

        # State storage
        self.connected_profiles: Dict[str, float] = {}  # profileName -> last_seen_timestamp
        self.pending_commands: Dict[str, List[Dict[str, Any]]] = {}  # profileName -> list of cmd dicts
        self.latest_reports: Dict[str, Dict[str, Any]] = {}  # key -> latest report dict
        self._report_events: Dict[str, threading.Event] = {}  # key -> Event

    @classmethod
    def get_instance(cls) -> 'ExtensionBridgeServer':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self):
        """Start the bridge server in a background daemon thread."""
        if self.is_running:
            return

        bridge = self

        class BridgeHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # suppress standard HTTP logging

            def _send_cors_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def do_OPTIONS(self):
                self.send_response(200)
                self._send_cors_headers()
                self.end_headers()

            def do_GET(self):
                if self.path == "/status":
                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    resp = {
                        "status": "OK",
                        "app": "Chained Evolution Studio",
                        "profiles": list(bridge.connected_profiles.keys())
                    }
                    self.wfile.write(json.dumps(resp).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_len) if content_len > 0 else b"{}"
                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    payload = {}

                if self.path == "/poll":
                    profile = payload.get("profileName", "Default").strip()
                    bridge.connected_profiles[profile] = time.time()

                    # Check for queued commands
                    response_data = {}
                    if profile in bridge.pending_commands and bridge.pending_commands[profile]:
                        response_data = bridge.pending_commands[profile].pop(0)
                    elif "*" in bridge.pending_commands and bridge.pending_commands["*"]:
                        response_data = bridge.pending_commands["*"].pop(0)
                    else:
                        # Fallback: if any command is queued for any profile, dispatch to active client
                        for k in list(bridge.pending_commands.keys()):
                            if bridge.pending_commands[k]:
                                response_data = bridge.pending_commands[k].pop(0)
                                break

                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode("utf-8"))

                elif self.path == "/report":
                    profile = payload.get("profileName", "Default").strip()
                    cmd_name = payload.get("command", "")
                    bridge.connected_profiles[profile] = time.time()

                    bridge.latest_reports[profile] = payload
                    bridge.latest_reports["*"] = payload
                    if cmd_name:
                        bridge.latest_reports[f"{profile}_{cmd_name}"] = payload
                        bridge.latest_reports[f"*_{cmd_name}"] = payload

                    # Notify all waiting threads
                    for evt in list(bridge._report_events.values()):
                        evt.set()

                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "ACK"}')
                else:
                    self.send_response(404)
                    self.end_headers()

        try:
            self.server = HTTPServer(("127.0.0.1", self.port), BridgeHandler)
            self.is_running = True
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Extension Bridge server started on http://127.0.0.1:{self.port}")
        except Exception as e:
            logger.warning(f"Could not start Extension Bridge server: {e}")

    def is_profile_connected(self, profile_name: str = "", max_age_sec: float = 10.0) -> bool:
        """
        Check if heartbeat was received from Chrome extension within max_age_sec.
        If ANY extension client is currently polling on 127.0.0.1, it returns True.
        """
        now = time.time()
        active = [prof for prof, last_seen in self.connected_profiles.items() if (now - last_seen < max_age_sec)]
        if not active:
            return False

        # If specific profile requested, check match or fallback to any active extension
        p_norm = profile_name.strip().lower()
        if not p_norm:
            return True

        for prof in active:
            p_curr = prof.lower()
            if p_curr == p_norm or p_norm in p_curr or p_curr in p_norm or p_curr == "default":
                return True

        # Any active extension is connected
        return len(active) > 0

    def get_connected_profiles(self, max_age_sec: float = 10.0) -> List[str]:
        """Return list of active Chrome profiles currently communicating via extension."""
        now = time.time()
        return [
            prof for prof, last_seen in self.connected_profiles.items()
            if now - last_seen < max_age_sec
        ]

    def send_command(
        self,
        profile_name: str,
        command_name: str,
        params: Optional[Dict[str, Any]] = None,
        wait_timeout_sec: float = 15.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """Queue a command for the extension and wait for its response."""
        p_key = profile_name.strip() or "Default"
        cmd_dict = {
            "command": command_name,
            "targetProfile": p_key,
            **(params or {})
        }

        if p_key not in self.pending_commands:
            self.pending_commands[p_key] = []
        self.pending_commands[p_key].append(cmd_dict)

        # Event for this command
        evt_key = f"{p_key}_{command_name}"
        evt = threading.Event()
        self._report_events[evt_key] = evt

        # Clear prior stale report
        self.latest_reports.pop(evt_key, None)
        self.latest_reports.pop(f"*_{command_name}", None)

        if wait_timeout_sec > 0:
            got_signal = evt.wait(timeout=wait_timeout_sec)
            self._report_events.pop(evt_key, None)
            if got_signal:
                report = (
                    self.latest_reports.get(evt_key) or
                    self.latest_reports.get(f"*_{command_name}") or
                    self.latest_reports.get(p_key) or
                    self.latest_reports.get("*", {})
                )
                return True, report
            else:
                return False, {"error": f"Timeout ({wait_timeout_sec}s) waiting for extension response to {command_name}"}

        return True, {"queued": True}

    def open_flow_project(self, profile_name: str, project_url: str, timeout_sec: float = 15.0) -> Tuple[bool, str]:
        """Send OPEN_FLOW_PROJECT command to extension in specified profile."""
        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="OPEN_FLOW_PROJECT",
            params={"url": project_url},
            wait_timeout_sec=timeout_sec
        )
        if ok and res.get("flowProjectOpened"):
            return True, "Google Flow project opened in existing Chrome tab"
        return False, res.get("error", "Failed to open project in extension")

    def verify_flow_project(self, profile_name: str, timeout_sec: float = 10.0) -> Tuple[bool, Dict[str, Any]]:
        """Send VERIFY_FLOW_PROJECT command to extension to inspect DOM readiness."""
        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="VERIFY_FLOW_PROJECT",
            params={},
            wait_timeout_sec=timeout_sec
        )
        return ok, res

    def upload_reference(self, profile_name: str, image_path: Path, timeout_sec: float = 20.0) -> Tuple[bool, str]:
        """Upload reference image into Flow interface via extension."""
        img = Path(image_path).resolve()
        if not img.is_file():
            return False, f"Reference image file not found: {img}"

        with open(img, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_data}"

        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="UPLOAD_REFERENCE",
            params={"base64Data": data_uri, "filename": img.name},
            wait_timeout_sec=timeout_sec
        )
        if ok and res.get("success"):
            return True, res.get("message", "Reference image uploaded successfully")
        return False, res.get("error", "Failed to upload reference image via extension")

    def submit_prompt(self, profile_name: str, prompt_text: str, timeout_sec: float = 15.0) -> Tuple[bool, str]:
        """Submit prompt text into Flow interface via extension."""
        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="SUBMIT_PROMPT",
            params={"promptText": prompt_text.strip()},
            wait_timeout_sec=timeout_sec
        )
        if ok and res.get("success"):
            return True, res.get("message", "Prompt submitted successfully")
        return False, res.get("error", "Failed to submit prompt via extension")

    def trigger_generation(self, profile_name: str, timeout_sec: float = 15.0) -> Tuple[bool, str]:
        """Click Generate button in Flow interface via extension."""
        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="TRIGGER_GENERATION",
            params={},
            wait_timeout_sec=timeout_sec
        )
        if ok and res.get("success"):
            return True, res.get("message", "Generation triggered successfully")
        return False, res.get("error", "Failed to click generate button via extension")

    def wait_for_completion(self, profile_name: str, timeout_sec: float = 600.0) -> Tuple[bool, str]:
        """Poll extension status until generation completes or errors out."""
        start_time = time.time()
        logger.info(f"Waiting for video generation via extension (timeout: {timeout_sec}s)...")

        while time.time() - start_time < timeout_sec:
            ok, res = self.send_command(
                profile_name=profile_name,
                command_name="CHECK_GENERATION_STATUS",
                params={},
                wait_timeout_sec=6.0
            )
            if ok:
                status = res.get("status", "")
                if status == "COMPLETED":
                    logger.info("Video generation completed via extension!")
                    return True, "Generation completed"
                elif status == "ERROR":
                    err = res.get("error", "Generation error on server")
                    return False, f"Generation failed: {err}"

            time.sleep(2.5)

        return False, f"Timeout ({timeout_sec}s) reached waiting for video generation via extension."

    def download_video(self, profile_name: str, dest_path: Path, timeout_sec: float = 60.0) -> Tuple[bool, str]:
        """Download generated video and verify."""
        dest = Path(dest_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="DOWNLOAD_VIDEO",
            params={},
            wait_timeout_sec=timeout_sec
        )

        if not ok or not res.get("success"):
            return False, res.get("error", "Failed to retrieve video stream from extension")

        # 1. Base64 data URI returned
        data_uri = res.get("videoDataUri", "")
        if data_uri and "," in data_uri:
            b64_str = data_uri.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_str)
            with open(dest, "wb") as f:
                f.write(raw_bytes)
            v_ok, v_msg = VideoValidator.validate_video_integrity(dest)
            if v_ok:
                logger.info(f"Video saved and validated: {dest.name}")
                return True, "Video downloaded and verified successfully"

        # 2. Remote URL returned
        vid_url = res.get("url", "")
        if vid_url and vid_url.startswith("http"):
            try:
                urllib.request.urlretrieve(vid_url, str(dest))
                v_ok, v_msg = VideoValidator.validate_video_integrity(dest)
                if v_ok:
                    logger.info(f"Video retrieved from URL and validated: {dest.name}")
                    return True, "Video downloaded and verified successfully"
            except Exception as e:
                return False, f"Failed downloading video stream from URL: {e}"

        return False, "Received video data could not be validated on disk"

    def stop(self):
        """Shutdown the bridge server."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        self.is_running = False
        logger.info("Extension Bridge server stopped.")
