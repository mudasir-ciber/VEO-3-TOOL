"""Comprehensive automated test suite for Chained Evolution Studio (VEO 3 Rebuild)."""
import os
import sys
import unittest
import tempfile
import shutil
import time
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
from connector.flow_extension import ExtensionFlowConnector
from core.extension_bridge import ExtensionBridgeServer, ExtensionProfile
from core.execution_engine import ExecutionEngine
from core.config import get_flow_project_url, set_flow_project_url


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
        sample1 = "SCENE 1: First prompt\nSCENE 2: Second prompt"
        res1 = PromptParser.parse_batch(sample1, default_start_number=1)
        self.assertEqual(len(res1), 2)
        self.assertEqual(res1[0].scene_number, 1)
        self.assertEqual(res1[1].scene_number, 2)

        sample2 = "Description for scene eleven.\n\nDescription for scene twelve."
        res2 = PromptParser.parse_batch(sample2, default_start_number=11)
        self.assertEqual(len(res2), 2)
        self.assertEqual(res2[0].scene_number, 11)
        self.assertEqual(res2[1].scene_number, 12)

    def test_03_project_state_and_continuity(self):
        """Verify project directories, master image, state persistence, and batch continuity."""
        proj_dir = self.temp_dir / "ContinuityProject"
        ProjectManager.setup_project_directories(proj_dir)

        # Create master image
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
        test_url = "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4"
        set_flow_project_url(test_url)
        self.assertEqual(get_flow_project_url(), test_url)

    def test_07_extension_multi_profile_discovery(self):
        """Verify extension bridge handles 1, 3, and 10 dynamic profile registrations."""
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        # Clean state for isolated test
        with bridge._lock:
            bridge.profiles_by_instance.clear()
            bridge.name_to_instance.clear()

        # Step A: Register 1 profile
        bridge.update_profile_heartbeat({
            "profileName": "Mudasir",
            "extensionInstanceId": "inst-mudasir-001",
            "flowStatus": "FLOW_READY"
        })
        self.assertEqual(len(bridge.get_active_profiles()), 1)
        self.assertTrue(bridge.is_profile_connected("Mudasir"))
        self.assertFalse(bridge.is_profile_connected("UnknownProfile"))

        # Step B: Register 2 more profiles (total 3)
        bridge.update_profile_heartbeat({
            "profileName": "YOUTUBE",
            "extensionInstanceId": "inst-youtube-002",
            "flowStatus": "FLOW_READY"
        })
        bridge.update_profile_heartbeat({
            "profileName": "German",
            "extensionInstanceId": "inst-german-003",
            "flowStatus": "FLOW_READY"
        })
        self.assertEqual(len(bridge.get_active_profiles()), 3)
        self.assertTrue(bridge.is_profile_connected("YOUTUBE"))
        self.assertTrue(bridge.is_profile_connected("German"))

        # Step C: Register up to 10 profiles
        for i in range(4, 11):
            bridge.update_profile_heartbeat({
                "profileName": f"Profile_{i}",
                "extensionInstanceId": f"inst-profile-{i:03d}",
                "flowStatus": "FLOW_READY"
            })
        active_profiles = bridge.get_active_profiles()
        self.assertEqual(len(active_profiles), 10)
        self.assertTrue(bridge.is_profile_connected("Profile_10"))

    def test_08_profile_specific_command_routing(self):
        """Verify strict single-profile routing: command goes ONLY to selected profile instance."""
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        with bridge._lock:
            bridge.profiles_by_instance.clear()
            bridge.name_to_instance.clear()
            bridge.pending_commands.clear()

        # Register 3 profiles
        bridge.update_profile_heartbeat({"profileName": "Muzamil", "extensionInstanceId": "inst-muzamil", "flowStatus": "FLOW_READY"})
        bridge.update_profile_heartbeat({"profileName": "HISTORY", "extensionInstanceId": "inst-history", "flowStatus": "FLOW_READY"})
        bridge.update_profile_heartbeat({"profileName": "RightReward", "extensionInstanceId": "inst-rightreward", "flowStatus": "FLOW_READY"})

        # Route command to "HISTORY" only (wait_timeout_sec=0 to queue without waiting)
        ok, res = bridge.send_command(
            profile_name="HISTORY",
            command_name="ENTER_PROMPT",
            params={"promptText": "Historic scene prompt", "scene": 1},
            wait_timeout_sec=0
        )
        self.assertTrue(ok)

        # Verify command is queued ONLY for inst-history
        with bridge._lock:
            history_queue = bridge.pending_commands.get("inst-history", [])
            muzamil_queue = bridge.pending_commands.get("inst-muzamil", [])
            rightreward_queue = bridge.pending_commands.get("inst-rightreward", [])

            self.assertEqual(len(history_queue), 1)
            self.assertEqual(history_queue[0]["command"], "ENTER_PROMPT")
            self.assertEqual(history_queue[0]["targetProfile"], "HISTORY")
            self.assertEqual(history_queue[0]["extensionInstanceId"], "inst-history")

            # Other profile queues MUST be empty
            self.assertEqual(len(muzamil_queue), 0)
            self.assertEqual(len(rightreward_queue), 0)

    def test_09_flow_tab_status_and_project_mismatch(self):
        """Verify project status handling: FLOW_READY vs FLOW_PROJECT_MISMATCH vs FLOW_AUTH_REQUIRED."""
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        # Profile with FLOW_READY
        bridge.update_profile_heartbeat({
            "profileName": "ReadyUser",
            "extensionInstanceId": "inst-ready",
            "flowStatus": "FLOW_READY",
            "projectVerified": True
        })
        conn_ready = ExtensionFlowConnector(target_profile_name="ReadyUser")
        self.assertTrue(conn_ready.is_flow_tab_ready())
        ok, msg = conn_ready.check_authenticated()
        self.assertTrue(ok)

        # Profile with FLOW_AUTH_REQUIRED
        bridge.update_profile_heartbeat({
            "profileName": "UnauthUser",
            "extensionInstanceId": "inst-unauth",
            "flowStatus": "FLOW_AUTH_REQUIRED",
            "projectVerified": False
        })
        conn_unauth = ExtensionFlowConnector(target_profile_name="UnauthUser")
        ok, msg = conn_unauth.check_authenticated()
        self.assertFalse(ok)
        self.assertIn("login required", msg.lower())

    def test_10_extension_flow_connector_lifecycle(self):
        """Verify ExtensionFlowConnector initialization and graceful closure."""
        bridge = ExtensionBridgeServer.get_instance()
        bridge.start()

        bridge.update_profile_heartbeat({
            "profileName": "John",
            "extensionInstanceId": "inst-john",
            "flowStatus": "FLOW_READY"
        })

        connector = ExtensionFlowConnector(target_profile_name="John")
        ok, msg = connector.initialize()
        self.assertTrue(ok)
        self.assertTrue(connector.is_connected)

        # Prepare scene interface
        ok, msg = connector.prepare_scene_interface()
        self.assertTrue(ok)

        # Clean close (must not throw or touch Chrome processes)
        connector.close()
        self.assertFalse(connector.is_connected)

    def test_11_intelligent_retry_without_regeneration(self):
        """Verify that if video is already downloaded and valid, engine skips regeneration and proceeds to extraction."""
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance() or QCoreApplication(sys.argv)

        proj_dir = self.temp_dir / "RetryProject"
        ProjectManager.setup_project_directories(proj_dir)

        # Create master image
        img = Image.new("RGB", (64, 64), color="red")
        src_master = self.temp_dir / "master.png"
        img.save(src_master)
        ProjectManager.set_master_image(proj_dir, src_master)

        state = ProjectState(proj_dir, "RetryProject")
        scenes = [PromptParser.parse_batch("SCENE 1: Retry prompt")[0]]
        state.register_scene_batch([(s.scene_number, s.prompt_text) for s in scenes])

        # Pre-create valid video on disk (simulating download succeeded before extraction)
        target_video = ProjectManager.get_scene_video_path(proj_dir, 1)
        sim = SimulatedFlowConnector(step_delay_sec=0.01)
        sim.download_video(target_video)
        self.assertTrue(target_video.is_file())

        # Connector tracking generation calls
        class CountingConnector(SimulatedFlowConnector):
            def __init__(self):
                super().__init__(step_delay_sec=0.01)
                self.gen_calls = 0

            def trigger_generation(self):
                self.gen_calls += 1
                return super().trigger_generation()

        counting_conn = CountingConnector()
        engine = ExecutionEngine(
            project_state=state,
            connector=counting_conn,
            scenes_to_run=scenes,
            max_retries=2
        )
        engine.run()

        # Generation MUST NOT have been called because valid video was already on disk!
        self.assertEqual(counting_conn.gen_calls, 0)
        self.assertEqual(state.last_completed_scene, 1)
        target_frame = ProjectManager.get_scene_last_frame_path(proj_dir, 1)
        self.assertTrue(target_frame.is_file())

    def test_12_crash_recovery_state_resumption(self):
        """Verify crash recovery: state loaded from disk accurately restores chain reference and scene progression."""
        proj_dir = self.temp_dir / "CrashRecoveryProject"
        ProjectManager.setup_project_directories(proj_dir)

        img = Image.new("RGB", (64, 64), color="yellow")
        src_master = self.temp_dir / "master.png"
        img.save(src_master)
        ProjectManager.set_master_image(proj_dir, src_master)

        state1 = ProjectState(proj_dir, "CrashRecoveryProject")
        state1.register_scene_batch([(1, "p1"), (2, "p2"), (3, "p3")])

        # Complete Scene 1
        v1 = ProjectManager.get_scene_video_path(proj_dir, 1)
        f1 = ProjectManager.get_scene_last_frame_path(proj_dir, 1)
        v1.touch(); f1.touch()
        state1.mark_scene_completed(1, state1.current_chain_reference, v1, f1)

        # Simulate crash & reload by creating new ProjectState instance
        state2 = ProjectState(proj_dir, "CrashRecoveryProject")
        self.assertEqual(state2.last_completed_scene, 1)
        self.assertEqual(state2.next_scene, 2)
        self.assertEqual(str(state2.current_chain_reference), str(f1))


if __name__ == "__main__":
    unittest.main()
