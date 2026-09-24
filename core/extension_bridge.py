"""Local HTTP bridge server enabling real-time communication between Chained Evolution Studio and the Chrome extension."""
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple, List

from core.logger import logger


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
        self.latest_reports: Dict[str, Dict[str, Any]] = {}  # profileName -> latest report dict
        self._report_events: Dict[str, threading.Event] = {}  # profileName -> Event

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

                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode("utf-8"))

                elif self.path == "/report":
                    profile = payload.get("profileName", "Default").strip()
                    bridge.connected_profiles[profile] = time.time()
                    bridge.latest_reports[profile] = payload

                    # Notify waiting threads
                    if profile in bridge._report_events:
                        bridge._report_events[profile].set()
                    if "*" in bridge._report_events:
                        bridge._report_events["*"].set()

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

    def is_profile_connected(self, profile_name: str, max_age_sec: float = 6.0) -> bool:
        """Check if heartbeat was received from Chrome extension within max_age_sec."""
        p_norm = profile_name.strip()
        now = time.time()
        for prof, last_seen in list(self.connected_profiles.items()):
            if (prof.lower() == p_norm.lower() or p_norm.lower() in prof.lower()) and (now - last_seen < max_age_sec):
                return True
        return False

    def get_connected_profiles(self, max_age_sec: float = 6.0) -> List[str]:
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
        wait_timeout_sec: float = 12.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """Queue a command for the extension and optionally wait for its response."""
        p_key = profile_name.strip()
        cmd_dict = {
            "command": command_name,
            "targetProfile": p_key,
            **(params or {})
        }

        if p_key not in self.pending_commands:
            self.pending_commands[p_key] = []
        self.pending_commands[p_key].append(cmd_dict)

        # Setup event
        evt = threading.Event()
        self._report_events[p_key] = evt

        # Wait for reply
        if wait_timeout_sec > 0:
            got_signal = evt.wait(timeout=wait_timeout_sec)
            self._report_events.pop(p_key, None)
            if got_signal:
                report = self.latest_reports.get(p_key, {})
                return True, report
            else:
                return False, {"error": "Timeout waiting for extension response"}

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
