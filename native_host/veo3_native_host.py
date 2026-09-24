"""
VEO 3 Chained Evolution Studio - Native Messaging Host
Bridges Chrome Extension instances to the Desktop Application via standard Chrome Native Messaging protocol.
"""
import sys
import os
import json
import struct
import socket
import threading
import time

DESKTOP_APP_HOST = "127.0.0.1"
DESKTOP_APP_PORT = 18999

# Configure binary stdio on Windows
if sys.platform == "win32":
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


def read_chrome_message():
    """Read a 4-byte length-prefixed message from Chrome stdin."""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if len(raw_length) < 4:
            return None
        msg_length = struct.unpack("<I", raw_length)[0]
        msg_bytes = sys.stdin.buffer.read(msg_length)
        if len(msg_bytes) < msg_length:
            return None
        return json.loads(msg_bytes.decode("utf-8"))
    except Exception:
        return None


def write_chrome_message(msg_dict):
    """Write a 4-byte length-prefixed JSON message to Chrome stdout."""
    try:
        data = json.dumps(msg_dict).encode("utf-8")
        length = len(data)
        sys.stdout.buffer.write(struct.pack("<I", length))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return True
    except Exception:
        return False


class NativeHostBridge:
    def __init__(self):
        self.sock = None
        self.is_connected = False
        self.lock = threading.Lock()
        self.instance_id = None
        self.profile_name = None

    def connect_to_desktop_app(self, retries=5):
        """Connect to the Desktop App IPC server."""
        for attempt in range(retries):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((DESKTOP_APP_HOST, DESKTOP_APP_PORT))
                self.is_connected = True
                return True
            except Exception:
                time.sleep(0.5)
        return False

    def forward_from_desktop(self):
        """Thread listening to commands from Desktop App and forwarding to Chrome."""
        buffer = b""
        while self.is_connected:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        msg = json.loads(line.decode("utf-8"))
                        write_chrome_message(msg)
            except Exception:
                break
        self.is_connected = False

    def send_to_desktop(self, msg_dict):
        """Send message from Chrome extension to Desktop App."""
        with self.lock:
            if not self.is_connected:
                if not self.connect_to_desktop_app(retries=2):
                    return False
            try:
                payload = json.dumps(msg_dict).encode("utf-8") + b"\n"
                self.sock.sendall(payload)
                return True
            except Exception:
                self.is_connected = False
                return False

    def run(self):
        # Initial connection attempt
        self.connect_to_desktop_app(retries=3)

        # Start desktop receiver thread if connected
        if self.is_connected:
            recv_thread = threading.Thread(target=self.forward_from_desktop, daemon=True)
            recv_thread.start()

        # Read loop from Chrome stdin
        while True:
            msg = read_chrome_message()
            if msg is None:
                # Chrome extension closed native port
                break

            # Track profile details
            if "profileName" in msg:
                self.profile_name = msg["profileName"]
            if "extensionInstanceId" in msg:
                self.instance_id = msg["extensionInstanceId"]

            # Forward to desktop app
            sent = self.send_to_desktop(msg)

            # Echo ACK back to Chrome if needed
            if msg.get("type") == "PING":
                write_chrome_message({"type": "PONG", "timestamp": time.time()})


if __name__ == "__main__":
    bridge = NativeHostBridge()
    bridge.run()
