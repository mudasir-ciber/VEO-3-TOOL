"""Comprehensive automated test suite for Chained Evolution Studio."""
import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.system_checker import SystemChecker
from core.prompt_parser import PromptParser
from core.project_manager import ProjectManager
from core.state_manager import ProjectState
from core.ffmpeg_extractor import FFmpegExtractor
from core.video_validator import VideoValidator
from connector.flow_mock import SimulatedFlowConnector
from core.execution_engine import ExecutionEngine


class TestChainedEvolutionStudio(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_system_checker(self):
        """Verify Windows system detection and dependencies."""
        info = SystemChecker.get_system_info()
        self.assertEqual(info["os_name"], "Windows")
        self.assertTrue(info["is_64bit"])
        self.assertTrue(info["ffmpeg_available"])
        self.assertTrue(info["chrome_available"])
        self.assertGreater(info["storage_free_gb"], 1.0)

    def test_02_prompt_parser(self):
        """Verify prompt parsing with continuity numbering."""
        # Explicit numbering
        sample1 = "SCENE 1: First prompt\nSCENE 2: Second prompt"
        res1 = PromptParser.parse_batch(sample1, default_start_number=1)
        self.assertEqual(len(res1), 2)
        self.assertEqual(res1[0].scene_number, 1)
        self.assertEqual(res1[1].scene_number, 2)

        # Batch 2 without explicit labels, starting at Scene 11
        sample2 = "Description for scene eleven.\n\nDescription for scene twelve."
        res2 = PromptParser.parse_batch(sample2, default_start_number=11)
        self.assertEqual(len(res2), 2)
        self.assertEqual(res2[0].scene_number, 11)
        self.assertEqual(res2[1].scene_number, 12)

    def test_03_project_state_and_continuity(self):
        """Verify project directories, master image, state persistence, and batch continuity."""
        proj_dir = self.temp_dir / "ContinuityProject"
        ProjectManager.setup_project_directories(proj_dir)

        # Create dummy master image
        img = Image.new("RGB", (64, 64), color="blue")
        src_master = self.temp_dir / "master.png"
        img.save(src_master)

        ok, msg, dest = ProjectManager.set_master_image(proj_dir, src_master)
        self.assertTrue(ok)
        self.assertTrue(dest.is_file())

        state = ProjectState(proj_dir, "ContinuityProject")
        self.assertEqual(state.last_completed_scene, 0)
        self.assertEqual(str(state.current_chain_reference), str(dest))

        # Register Batch 1 (Scenes 1 & 2)
        state.register_scene_batch([(1, "p1"), (2, "p2")])

        # Complete Scene 1
        v1 = ProjectManager.get_scene_video_path(proj_dir, 1)
        f1 = ProjectManager.get_scene_last_frame_path(proj_dir, 1)
        v1.touch(); f1.touch()
        state.mark_scene_completed(1, state.current_chain_reference, v1, f1)

        self.assertEqual(state.last_completed_scene, 1)
        self.assertEqual(str(state.current_chain_reference), str(f1))
        self.assertEqual(state.next_scene, 2)

        # Batch 2 Continuity: Register Scene 3
        state.register_scene_batch([(3, "p3")])
        # Current reference must STILL be Scene 1's frame, NEVER Master Image!
        self.assertEqual(str(state.current_chain_reference), str(f1))

    def test_04_ffmpeg_frame_extraction(self):
        """Verify exact last frame extraction from genuine video."""
        test_video = self.temp_dir / "test.mp4"
        test_frame = self.temp_dir / "test_frame.png"

        # Generate 2 second synthetic mp4 with lavfi
        connector = SimulatedFlowConnector(step_delay_sec=0.1)
        connector.download_video(test_video)
        self.assertTrue(test_video.is_file())

        # Extract last frame
        ok, msg = FFmpegExtractor.extract_last_frame(test_video, test_frame)
        self.assertTrue(ok, f"Extraction failed: {msg}")
        self.assertTrue(test_frame.is_file())

        # Verify extracted frame with Pillow
        valid, err = FFmpegExtractor.verify_image(test_frame)
        self.assertTrue(valid, f"Verification failed: {err}")

    def test_05_end_to_end_sequential_chain(self):
        """Verify end-to-end execution of a 2-scene batch using ExecutionEngine in simulation mode."""
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance() or QCoreApplication(sys.argv)

        proj_dir = self.temp_dir / "E2EProject"
        ProjectManager.setup_project_directories(proj_dir)

        # Create master image
        img = Image.new("RGB", (128, 128), color="green")
        src_master = self.temp_dir / "master.png"
        img.save(src_master)
        ProjectManager.set_master_image(proj_dir, src_master)

        state = ProjectState(proj_dir, "E2EProject")
        scenes = [
            PromptParser.parse_batch("SCENE 1: First scene prompt")[0],
            PromptParser.parse_batch("SCENE 2: Second scene prompt")[0]
        ]
        state.register_scene_batch([(s.scene_number, s.prompt_text) for s in scenes])

        connector = SimulatedFlowConnector(step_delay_sec=0.05)
        engine = ExecutionEngine(
            project_state=state,
            connector=connector,
            scenes_to_run=scenes,
            max_retries=2
        )

        completed_scenes = []
        engine.sig_scene_completed.connect(lambda s: completed_scenes.append(s))

        # Run synchronously in test
        engine.run()

        self.assertEqual(completed_scenes, [1, 2])
        self.assertEqual(state.last_completed_scene, 2)

        # Check files exist
        v1 = ProjectManager.get_scene_video_path(proj_dir, 1)
        f1 = ProjectManager.get_scene_last_frame_path(proj_dir, 1)
        v2 = ProjectManager.get_scene_video_path(proj_dir, 2)
        f2 = ProjectManager.get_scene_last_frame_path(proj_dir, 2)

        self.assertTrue(v1.is_file())
        self.assertTrue(f1.is_file())
        self.assertTrue(v2.is_file())
        self.assertTrue(f2.is_file())

        # Scene 2 MUST have used Scene 1's last frame as reference!
        scene_2_data = state.data["scenes"]["2"]
        self.assertEqual(scene_2_data["reference_used"], str(f1))

    def test_06_flow_project_url_config(self):
        """Verify Google Flow project URL getter, setter, and persistence."""
        from core.config import get_flow_project_url, set_flow_project_url, DEFAULT_FLOW_PROJECT_URL
        test_url = "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4"
        set_flow_project_url(test_url)
        self.assertEqual(get_flow_project_url(), test_url)

    def test_07_extension_bridge_and_exact_project(self):
        """Verify extension bridge server HTTP endpoints and exact project navigation."""
        import urllib.request
        import json
        from core.extension_bridge import ExtensionBridgeServer
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        # Test GET /status
        req = urllib.request.urlopen("http://127.0.0.1:18999/status", timeout=3.0)
        data = json.loads(req.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "OK")
        self.assertEqual(data.get("app"), "Chained Evolution Studio")

        # Test POST /poll
        poll_req = urllib.request.Request(
            "http://127.0.0.1:18999/poll",
            data=json.dumps({"profileName": "YOUTUBE"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        poll_resp = urllib.request.urlopen(poll_req, timeout=3.0)
        self.assertEqual(poll_resp.status, 200)

        # Check if profile is reported connected
        self.assertTrue(bridge.is_profile_connected("YOUTUBE"))

        # Test SimulatedFlowConnector exact project methods
        connector = SimulatedFlowConnector(step_delay_sec=0.01)
        ok, msg = connector.navigate_to_exact_project("https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4")
        self.assertTrue(ok)
        ok, msg = connector.verify_exact_project("https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4")
        self.assertTrue(ok)

    def test_08_extension_profile_mismatch_fallback(self):
        """Verify extension bridge handles profile name mismatches smoothly."""
        import urllib.request
        import json
        from core.extension_bridge import ExtensionBridgeServer
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        # Simulate client polling with 'Default'
        poll_req = urllib.request.Request(
            "http://127.0.0.1:18999/poll",
            data=json.dumps({"profileName": "Default"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        poll_resp = urllib.request.urlopen(poll_req, timeout=3.0)
        self.assertEqual(poll_resp.status, 200)

        # Checking any profile name like 'John Snow (John)' must return True
        self.assertTrue(bridge.is_profile_connected("John Snow (John)"))
        self.assertTrue(bridge.is_profile_connected("Default"))
        self.assertTrue(bridge.is_profile_connected(""))

    def test_09_flow_browser_extension_fallback(self):
        """Verify PlaywrightFlowConnector routes commands to extension bridge when CDP page is None."""
        from connector.flow_browser import PlaywrightFlowConnector
        from core.extension_bridge import ExtensionBridgeServer
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        # Make sure bridge has active heartbeat
        bridge.connected_profiles["Default"] = bridge.connected_profiles.get("Default", 0) + 1000

        connector = PlaywrightFlowConnector(cdp_port=9222)
        # Should report flow ready via extension bridge
        self.assertTrue(connector.is_flow_tab_ready())


if __name__ == "__main__":
    unittest.main()
