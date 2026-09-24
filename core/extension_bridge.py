"""
VEO 3 Multi-Profile Bridge & Router
Maintains live connections to all active Chrome Extension instances via Native Messaging and HTTP IPC.
Provides profile discovery, heartbeat tracking, strict single-profile command routing, and live event broadcasting.
"""
import os
import sys
import time
import base64
import json
import socket
import select
import threading
import urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple, List, Callable

from core.logger import logger
from core.video_validator import VideoValidator


class ExtensionProfile:
    def __init__(self, profile_name: str, instance_id: str):
        self.profile_name = profile_name.strip()
        self.instance_id = instance_id.strip()
        self.browser = "Chrome"
        self.status = "CONNECTED"  # "CONNECTED" or "OFFLINE"
        self.flow_status = "FLOW_TAB_NOT_FOUND"  # "FLOW_READY", "FLOW_LOADING", "FLOW_AUTH_REQUIRED", "FLOW_PROJECT_MISMATCH", "FLOW_TAB_NOT_FOUND"
        self.flow_tab_id: Optional[int] = None
        self.flow_url: str = ""
        self.project_verified: bool = False
        self.last_seen: float = time.time()
        self.operational_status: str = "IDLE"

    def is_online(self, max_age_sec: float = 8.0) -> bool:
        return (time.time() - self.last_seen) < max_age_sec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profileName": self.profile_name,
            "extensionInstanceId": self.instance_id,
            "browser": self.browser,
            "status": "CONNECTED" if self.is_online() else "OFFLINE",
            "flowStatus": self.flow_status if self.is_online() else "OFFLINE",
            "flowTabId": self.flow_tab_id,
            "flowUrl": self.flow_url,
            "projectVerified": self.project_verified,
            "operationalStatus": self.operational_status,
            "lastSeen": self.last_seen
        }


class ExtensionBridgeServer:
    _instance: Optional['ExtensionBridgeServer'] = None
    PORT = 18999

    def __init__(self, port: int = 18999):
        self.port = port
        self.is_running = False

        # Live Extension Registry: instance_id -> ExtensionProfile
        self.profiles_by_instance: Dict[str, ExtensionProfile] = {}
        # Mapping: profile_name.lower() -> instance_id
        self.name_to_instance: Dict[str, str] = {}

        # Command queues: instance_id -> list of command dicts
        self.pending_commands: Dict[str, List[Dict[str, Any]]] = {}

        # Reports and events
        self.latest_reports: Dict[str, Dict[str, Any]] = {}
        self._report_events: Dict[str, threading.Event] = {}

        # Event Listeners (for UI live log & engine)
        self.event_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.RLock()

        # Servers
        self.http_server: Optional[HTTPServer] = None
        self.http_thread: Optional[threading.Thread] = None

        self.tcp_server: Optional[socket.socket] = None
        self.tcp_thread: Optional[threading.Thread] = None
        # Native Host sockets: instance_id -> socket
        self.native_client_socks: Dict[str, socket.socket] = {}

    @classmethod
    def get_instance(cls) -> 'ExtensionBridgeServer':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_event_listener(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to live event updates from all connected extensions."""
        with self._lock:
            if callback not in self.event_listeners:
                self.event_listeners.append(callback)

    def remove_event_listener(self, callback: Callable[[Dict[str, Any]], None]):
        with self._lock:
            if callback in self.event_listeners:
                self.event_listeners.remove(callback)

    def _broadcast_event(self, event_data: Dict[str, Any]):
        """Dispatch event object to all subscribed listeners."""
        with self._lock:
            listeners = list(self.event_listeners)

        for listener in listeners:
            try:
                listener(event_data)
            except Exception as e:
                logger.debug(f"Error in event listener: {e}")

    def update_profile_heartbeat(self, payload: Dict[str, Any]):
        """Update or register an extension profile from heartbeat or register payload."""
        p_name = payload.get("profileName", "Default").strip()
        inst_id = payload.get("extensionInstanceId", "").strip() or f"bridge-{p_name}"

        with self._lock:
            if inst_id not in self.profiles_by_instance:
                # New Profile Detected!
                prof = ExtensionProfile(p_name, inst_id)
                self.profiles_by_instance[inst_id] = prof
                logger.info(f"✨ NEW PROFILE DETECTED: {p_name} ({inst_id})")
                self._broadcast_event({
                    "type": "NEW_PROFILE_DETECTED",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                    "profileName": p_name,
                    "extensionInstanceId": inst_id,
                    "status": "CONNECTED"
                })
            else:
                prof = self.profiles_by_instance[inst_id]
                prof.profile_name = p_name

            prof.last_seen = time.time()
            prof.status = "CONNECTED"
            prof.flow_status = payload.get("flowStatus", prof.flow_status)
            prof.flow_tab_id = payload.get("flowTabId", prof.flow_tab_id)
            prof.flow_url = payload.get("flowUrl", prof.flow_url)
            prof.project_verified = payload.get("projectVerified", prof.project_verified)
            prof.operational_status = payload.get("operationalStatus", prof.operational_status)

            self.name_to_instance[p_name.lower()] = inst_id

    def get_active_profiles(self, max_age_sec: float = 8.0) -> List[ExtensionProfile]:
        """
        Return the live list of currently connected extension profiles.
        Never returns fake or fixed profiles.
        """
        with self._lock:
            now = time.time()
            return [
                prof for prof in self.profiles_by_instance.values()
                if (now - prof.last_seen < max_age_sec)
            ]

    def get_all_registered_profiles(self) -> List[ExtensionProfile]:
        with self._lock:
            return list(self.profiles_by_instance.values())

    def get_profile_by_name(self, profile_name: str) -> Optional[ExtensionProfile]:
        """Find profile by exact or normalized display name."""
        with self._lock:
            p_clean = profile_name.strip().lower()
            inst_id = self.name_to_instance.get(p_clean)
            if inst_id and inst_id in self.profiles_by_instance:
                return self.profiles_by_instance[inst_id]

            # Substring match
            for prof in self.profiles_by_instance.values():
                if p_clean in prof.profile_name.lower() or prof.profile_name.lower() in p_clean:
                    return prof
            return None

    def is_profile_connected(self, profile_name: str = "", max_age_sec: float = 8.0) -> bool:
        """Check if specified profile (or any profile if empty) is actively connected."""
        if not profile_name:
            return len(self.get_active_profiles(max_age_sec)) > 0

        prof = self.get_profile_by_name(profile_name)
        if prof and prof.is_online(max_age_sec):
            return True
        return False

    def start(self):
        """Start both HTTP bridge and Native Messaging TCP socket server."""
        if self.is_running:
            return

        self.is_running = True
        self._start_http_server()
        self._start_tcp_server()
        logger.info(f"VEO 3 Multi-Profile Bridge Server listening on port {self.port}")

    def _start_http_server(self):
        bridge = self

        class BridgeHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress HTTP access logs

            def _send_cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def do_OPTIONS(self):
                self.send_response(200)
                self._send_cors()
                self.end_headers()

            def do_GET(self):
                if self.path == "/status" or self.path == "/profiles":
                    self.send_response(200)
                    self._send_cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    profiles_data = [p.to_dict() for p in bridge.get_all_registered_profiles()]
                    resp = {
                        "status": "OK",
                        "app": "Chained Evolution Studio",
                        "activeProfileCount": len(bridge.get_active_profiles()),
                        "profiles": profiles_data
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
                    bridge.update_profile_heartbeat(payload)
                    inst_id = payload.get("extensionInstanceId") or bridge.name_to_instance.get(payload.get("profileName", "").lower(), "")

                    # Check for pending commands targeted to THIS instance or profile
                    response_data = {}
                    with bridge._lock:
                        if inst_id in bridge.pending_commands and bridge.pending_commands[inst_id]:
                            response_data = bridge.pending_commands[inst_id].pop(0)

                    self.send_response(200)
                    self._send_cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode("utf-8"))

                elif self.path == "/report":
                    bridge.update_profile_heartbeat(payload)
                    inst_id = payload.get("extensionInstanceId") or bridge.name_to_instance.get(payload.get("profileName", "").lower(), "")
                    cmd_type = payload.get("type") or payload.get("command") or ""

                    # Save report
                    with bridge._lock:
                        bridge.latest_reports[inst_id] = payload
                        if cmd_type:
                            bridge.latest_reports[f"{inst_id}_{cmd_type}"] = payload

                        # Wake up waiting threads for this instance
                        for evt_k, evt in list(bridge._report_events.items()):
                            if evt_k.startswith(inst_id) or evt_k.startswith("*"):
                                evt.set()

                    # Broadcast event to UI
                    bridge._broadcast_event(payload)

                    self.send_response(200)
                    self._send_cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "ACK"}')
                else:
                    self.send_response(404)
                    self.end_headers()

        try:
            self.http_server = HTTPServer(("127.0.0.1", self.port), BridgeHandler)
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
        except Exception as e:
            logger.warning(f"Could not start HTTP bridge server on port {self.port}: {e}")

    def _start_tcp_server(self):
        """TCP server for Native Messaging Host instances."""
        try:
            # We use port + 1 for native host socket connections, or same if shared
            self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Try binding to port (if HTTP already bound to port, use port + 10 for TCP)
            tcp_port = self.port + 10
            self.tcp_server.bind(("127.0.0.1", tcp_port))
            self.tcp_server.listen(15)
            self.tcp_thread = threading.Thread(target=self._tcp_listen_loop, daemon=True)
            self.tcp_thread.start()
            logger.info(f"Native Host TCP socket listening on 127.0.0.1:{tcp_port}")
        except Exception as e:
            logger.warning(f"Could not start TCP server for Native Host: {e}")

    def _tcp_listen_loop(self):
        while self.is_running and self.tcp_server:
            try:
                client_sock, addr = self.tcp_server.accept()
                threading.Thread(target=self._handle_tcp_client, args=(client_sock,), daemon=True).start()
            except Exception:
                break

    def _handle_tcp_client(self, client_sock: socket.socket):
        buffer = b""
        client_inst_id = ""

        try:
            while self.is_running:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        msg = json.loads(line.decode("utf-8"))
                        self.update_profile_heartbeat(msg)
                        client_inst_id = msg.get("extensionInstanceId", "")
                        if client_inst_id:
                            with self._lock:
                                self.native_client_socks[client_inst_id] = client_sock

                        # Broadcast event
                        self._broadcast_event(msg)

                        # Check if waiting event exists
                        cmd_type = msg.get("type", "")
                        with self._lock:
                            if client_inst_id:
                                self.latest_reports[client_inst_id] = msg
                                if cmd_type:
                                    self.latest_reports[f"{client_inst_id}_{cmd_type}"] = msg

                            for evt_k, evt in list(self._report_events.items()):
                                if evt_k.startswith(client_inst_id) or evt_k.startswith("*"):
                                    evt.set()
        except Exception:
            pass
        finally:
            if client_inst_id:
                with self._lock:
                    self.native_client_socks.pop(client_inst_id, None)
                    if client_inst_id in self.profiles_by_instance:
                        self.profiles_by_instance[client_inst_id].status = "OFFLINE"
            try:
                client_sock.close()
            except Exception:
                pass

    def send_command(
        self,
        profile_name: str,
        command_name: str,
        params: Optional[Dict[str, Any]] = None,
        wait_timeout_sec: float = 15.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Strict Single-Profile Routing:
        Sends the command ONLY to the selected profile's extension instance.
        """
        prof = self.get_profile_by_name(profile_name)
        if not prof:
            return False, {"error": f"Profile '{profile_name}' is not currently connected."}

        inst_id = prof.instance_id
        correlation_id = f"{command_name}-{int(time.time() * 1000)}"

        cmd_dict = {
            "command": command_name,
            "targetProfile": prof.profile_name,
            "extensionInstanceId": inst_id,
            "correlationId": correlation_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            **(params or {})
        }

        # 1. Try sending directly to Native Host socket if active
        sent_native = False
        with self._lock:
            client_sock = self.native_client_socks.get(inst_id)
            if client_sock:
                try:
                    payload = json.dumps(cmd_dict).encode("utf-8") + b"\n"
                    client_sock.sendall(payload)
                    sent_native = True
                except Exception:
                    self.native_client_socks.pop(inst_id, None)

        # 2. Queue for HTTP polling delivery
        with self._lock:
            if inst_id not in self.pending_commands:
                self.pending_commands[inst_id] = []
            self.pending_commands[inst_id].append(cmd_dict)

        # 3. Setup response event
        evt_key = f"{inst_id}_{command_name}"
        evt = threading.Event()
        with self._lock:
            self._report_events[evt_key] = evt
            self.latest_reports.pop(evt_key, None)

        # 4. Wait for event
        if wait_timeout_sec > 0:
            got_signal = evt.wait(timeout=wait_timeout_sec)
            with self._lock:
                self._report_events.pop(evt_key, None)
                if got_signal:
                    report = (
                        self.latest_reports.get(evt_key) or
                        self.latest_reports.get(inst_id, {})
                    )
                    return True, report
                else:
                    return False, {"error": f"Timeout ({wait_timeout_sec}s) waiting for {command_name} from profile '{prof.profile_name}'"}

        return True, {"queued": True, "correlationId": correlation_id}

    def verify_exact_project(self, profile_name: str, timeout_sec: float = 15.0) -> Tuple[bool, str]:
        """Verify the exact Google Flow project is loaded and ready in the selected profile."""
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            ok, res = self.send_command(
                profile_name=profile_name,
                command_name="GET_FLOW_STATUS",
                wait_timeout_sec=3.0
            )
            if ok:
                flow_status = res.get("flowStatus", "")
                if flow_status == "FLOW_READY" or res.get("verified"):
                    return True, "Google Flow project is loaded and verified."
                elif flow_status == "FLOW_PROJECT_MISMATCH" or res.get("mismatch"):
                    return False, "FLOW_PROJECT_MISMATCH: Google Flow is open, but displaying a different project. Please open the required project."
                elif flow_status == "FLOW_AUTH_REQUIRED":
                    return False, "FLOW_AUTH_REQUIRED: Please sign into your Google account in this Chrome profile."
                elif flow_status == "FLOW_TAB_NOT_FOUND":
                    return False, "FLOW_TAB_NOT_FOUND: Please open the Google Flow project tab in this Chrome profile."
            time.sleep(1.0)

        return False, f"Timeout ({timeout_sec}s) verifying Google Flow project readiness."

    def upload_reference(self, profile_name: str, image_path: Path, scene_num: int = 1, timeout_sec: float = 25.0) -> Tuple[bool, str]:
        """Upload reference image into Flow interface via the selected extension instance."""
        img = Path(image_path).resolve()
        if not img.is_file():
            return False, f"Reference image file not found: {img}"

        with open(img, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_data}"

        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="UPLOAD_REFERENCE",
            params={
                "base64Data": data_uri,
                "filename": img.name,
                "scene": scene_num
            },
            wait_timeout_sec=timeout_sec
        )

        if ok and (res.get("type") == "REFERENCE_UPLOADED" or res.get("status") == "success"):
            return True, res.get("message", "Reference image uploaded successfully")
        err = res.get("message") or res.get("error", "Reference upload failed")
        return False, err

    def submit_prompt(self, profile_name: str, prompt_text: str, scene_num: int = 1, timeout_sec: float = 15.0) -> Tuple[bool, str]:
        """Submit scene prompt into Flow interface via the selected extension instance."""
        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="ENTER_PROMPT",
            params={
                "promptText": prompt_text.strip(),
                "scene": scene_num
            },
            wait_timeout_sec=timeout_sec
        )

        if ok and (res.get("type") == "PROMPT_ENTERED" or res.get("status") == "success"):
            return True, res.get("message", "Prompt entered successfully")
        err = res.get("message") or res.get("error", "Prompt submission failed")
        return False, err

    def trigger_generation(self, profile_name: str, scene_num: int = 1, timeout_sec: float = 15.0) -> Tuple[bool, str]:
        """Click Generate button in Flow interface via the selected extension instance."""
        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="START_GENERATION",
            params={"scene": scene_num},
            wait_timeout_sec=timeout_sec
        )

        if ok and (res.get("type") == "GENERATION_STARTED" or res.get("status") == "running"):
            return True, "Generation triggered successfully"
        err = res.get("message") or res.get("error", "Failed to trigger generation")
        return False, err

    def wait_for_completion(self, profile_name: str, scene_num: int = 1, timeout_sec: float = 600.0) -> Tuple[bool, str]:
        """Poll the selected extension instance until video generation completes or errors."""
        start_time = time.time()
        logger.info(f"[{profile_name}] Waiting for Scene {scene_num} video generation completion (timeout: {timeout_sec}s)...")

        while time.time() - start_time < timeout_sec:
            # Check connection alive
            if not self.is_profile_connected(profile_name):
                return False, f"EXTENSION_DISCONNECTED: Chrome profile '{profile_name}' disconnected during generation."

            ok, res = self.send_command(
                profile_name=profile_name,
                command_name="GET_GENERATION_STATUS",
                params={"scene": scene_num},
                wait_timeout_sec=5.0
            )

            if ok:
                ev_type = res.get("type", "")
                if ev_type == "GENERATION_COMPLETE" or res.get("status") == "complete":
                    logger.info(f"[{profile_name}] Scene {scene_num} generation completed successfully!")
                    return True, "Generation complete"
                elif ev_type == "GENERATION_FAILED":
                    err = res.get("message", "Server error during video generation")
                    return False, f"Generation failed: {err}"
                elif ev_type == "FLOW_ERROR":
                    err_code = res.get("errorCode", "")
                    if err_code == "FLOW_TAB_NOT_FOUND":
                        return False, "FLOW_TAB_LOST: The Google Flow tab was closed during generation."
                    return False, f"Flow error: {res.get('message', err_code)}"

            time.sleep(2.5)

        return False, f"Timeout ({timeout_sec}s) reached waiting for video generation completion."

    def download_video(self, profile_name: str, dest_path: Path, scene_num: int = 1, timeout_sec: float = 60.0) -> Tuple[bool, str]:
        """Download generated video from the selected extension instance and verify on disk."""
        dest = Path(dest_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        ok, res = self.send_command(
            profile_name=profile_name,
            command_name="DOWNLOAD_RESULT",
            params={"scene": scene_num},
            wait_timeout_sec=timeout_sec
        )

        if not ok or res.get("type") == "DOWNLOAD_FAILED":
            err = res.get("message") or res.get("error", "Download failed from extension")
            return False, err

        # 1. Base64 data URI
        data_uri = res.get("videoDataUri", "")
        if data_uri and "," in data_uri:
            b64_str = data_uri.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_str)
            with open(dest, "wb") as f:
                f.write(raw_bytes)
            v_ok, v_msg = VideoValidator.validate_video_integrity(dest)
            if v_ok:
                logger.info(f"[{profile_name}] Video validated on disk: {dest.name}")
                return True, "Downloaded and verified successfully"
            else:
                return False, f"Video verification failed: {v_msg}"

        # 2. Remote URL
        vid_url = res.get("url", "")
        if vid_url and vid_url.startswith("http"):
            try:
                urllib.request.urlretrieve(vid_url, str(dest))
                v_ok, v_msg = VideoValidator.validate_video_integrity(dest)
                if v_ok:
                    logger.info(f"[{profile_name}] Video stream downloaded and verified: {dest.name}")
                    return True, "Downloaded and verified successfully"
                else:
                    return False, f"Video verification failed: {v_msg}"
            except Exception as e:
                return False, f"Download error from stream URL: {e}"

        return False, "No valid video data or URL received from extension"

    def stop(self):
        """Clean shutdown of servers."""
        self.is_running = False
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception:
                pass

        if self.tcp_server:
            try:
                self.tcp_server.close()
            except Exception:
                pass

        with self._lock:
            for sock in list(self.native_client_socks.values()):
                try:
                    sock.close()
                except Exception:
                    pass
            self.native_client_socks.clear()

        logger.info("Extension Bridge server stopped.")
