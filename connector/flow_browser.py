"""Playwright-driven Google Flow browser connector connecting to existing automation-capable Chrome sessions."""
import os
import sys
import time
from pathlib import Path
from typing import Tuple, Optional, Any, List, Dict

from core.config import DEFAULT_BROWSER_PROFILE_DIR, GOOGLE_FLOW_URL, get_flow_project_url
from core.chrome_profile_manager import ChromeProfileManager
from core.video_validator import VideoValidator
from core.extension_bridge import ExtensionBridgeServer
from core.logger import logger
from connector.flow_base import BaseFlowConnector
import connector.flow_selectors as selectors


class PlaywrightFlowConnector(BaseFlowConnector):
    def __init__(self, cdp_port: int = 9222):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self.cdp_port = cdp_port
        self.profile_dir = Path(DEFAULT_BROWSER_PROFILE_DIR).resolve()
        self.is_connected = False
        self.is_flow_connected = False
        self.connected_tab_info: Dict[str, Any] = {}
        self.chrome_profile: Optional[Any] = None

    def is_flow_tab_ready(self) -> bool:
        """Check if attached Google Flow tab is alive and responsive."""
        if not self._page:
            return False
        try:
            if self._page.is_closed():
                return False
            url = self._page.url or ""
            return "flow.google" in url.lower() or "labs.google" in url.lower()
        except Exception:
            return False

    def connect_to_existing_chrome(
        self,
        port: Optional[int] = None,
        target_tab_id: Optional[str] = None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Connect to an existing automation-capable Chrome session via CDP.
        Enumerates tabs, finds the Google Flow tab, and attaches without creating about:blank.
        """
        active_port = port or self.cdp_port

        # 1. Check if CDP port is open
        if not ChromeProfileManager.is_cdp_available(active_port):
            if ChromeProfileManager.is_chrome_running():
                logger.info("Chrome process is running, but no CDP automation port is listening.")
                return False, "CHROME_RUNNING_WITHOUT_CDP", []
            else:
                logger.info("Chrome is not currently running.")
                return False, "CHROME_NOT_RUNNING", []

        # 2. Start Playwright if not active
        if not self._pw:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()

        # 3. Connect over CDP
        try:
            logger.info(f"Connecting to Chrome DevTools Protocol at http://127.0.0.1:{active_port}...")
            self._browser = self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{active_port}")
        except Exception as e:
            logger.error(f"CDP connection failed: {e}")
            return False, f"CDP connection error: {e}", []

        if not self._browser.contexts:
            return False, "No browser contexts available in Chrome session", []

        self._context = self._browser.contexts[0]
        self.is_connected = True

        # 4. Enumerate open pages / tabs
        pages = self._context.pages
        logger.info(f"Connected to Chrome session. Found {len(pages)} open browser tab(s).")

        flow_tabs: List[Dict[str, Any]] = []
        for idx, p in enumerate(pages):
            try:
                url = p.url or ""
                title = p.title() or ""
                is_flow = (
                    "flow.google" in url.lower() or
                    "labs.google/flow" in url.lower() or
                    "labs.google/fx/tools/flow" in url.lower() or
                    "google flow" in title.lower() or
                    ("flow" in title.lower() and "google" in title.lower())
                )
                if is_flow:
                    flow_tabs.append({
                        "index": idx,
                        "title": title or "Google Flow",
                        "url": url,
                        "page": p
                    })
            except Exception:
                pass

        # 5. Handle Tab Selection
        if target_tab_id is not None:
            for t in flow_tabs:
                if str(t["index"]) == str(target_tab_id) or target_tab_id in t["url"]:
                    self._attach_tab(t)
                    return True, "CONNECTED_TO_FLOW", [t]

        if len(flow_tabs) == 1:
            self._attach_tab(flow_tabs[0])
            return True, "CONNECTED_TO_FLOW", flow_tabs
        elif len(flow_tabs) > 1:
            logger.info(f"Multiple Google Flow tabs detected ({len(flow_tabs)}). User selection required.")
            return True, "MULTIPLE_FLOW_TABS", flow_tabs
        else:
            logger.warning("No Google Flow tab detected among currently open tabs.")
            self.is_flow_connected = False
            return False, "FLOW_TAB_NOT_FOUND", []

    def _attach_tab(self, tab_dict: Dict[str, Any]):
        """Attach to specified tab page and configure lifecycle handlers."""
        self._page = tab_dict["page"]
        self.is_connected = True
        self.is_flow_connected = True
        self.connected_tab_info = {
            "index": tab_dict["index"],
            "title": tab_dict["title"],
            "url": tab_dict["url"]
        }
        try:
            self._page.bring_to_front()
        except Exception:
            pass

        self._page.on("close", lambda p: self._on_page_closed())
        logger.info(f"Attached to Google Flow tab: '{tab_dict['title']}' ({tab_dict['url']})")

    def _on_page_closed(self):
        logger.warning("The attached Google Flow tab was closed by user or browser.")
        self.is_flow_connected = False
        self._page = None

    def open_flow_tab_in_existing_chrome(self) -> Tuple[bool, str]:
        """Open a new Google Flow tab inside the currently connected Chrome session."""
        if not self._context:
            return False, "Browser context is not connected"

        try:
            logger.info(f"Opening Google Flow in existing Chrome session: {GOOGLE_FLOW_URL}")
            new_page = self._context.new_page()
            new_page.goto(GOOGLE_FLOW_URL, wait_until="domcontentloaded", timeout=45000)
            new_page.wait_for_timeout(2000)
            self._attach_tab({
                "index": len(self._context.pages) - 1,
                "title": new_page.title() or "Google Flow",
                "url": new_page.url,
                "page": new_page
            })
            return True, "Opened Google Flow tab successfully"
        except Exception as e:
            return False, f"Could not open Google Flow tab: {e}"

    def initialize(
        self,
        headless: bool = False,
        profile_dir: Optional[Path] = None,
        chrome_profile: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Check for existing automation session first.
        Never launch a second conflicting Chrome process if profile is already open.
        """
        self.chrome_profile = chrome_profile

        # 1. Already connected to live Flow tab?
        if self.is_connected and self.is_flow_tab_ready():
            logger.info("Using currently attached Google Flow tab.")
            return True, "Browser connected to Google Flow"

        # 2. Try connecting to existing automation session
        ok, status, tabs = self.connect_to_existing_chrome(port=self.cdp_port)
        if ok and status == "CONNECTED_TO_FLOW":
            return True, "Connected to existing Google Flow tab"
        elif status == "MULTIPLE_FLOW_TABS":
            # Auto-select the first tab if non-interactive
            self._attach_tab(tabs[0])
            return True, "Connected to first Google Flow tab"
        elif status == "FLOW_TAB_NOT_FOUND":
            return False, "Google Flow tab not found in connected Chrome. Please open Google Flow in this Chrome profile."

        # 3. If Chrome is already running without automation port, DO NOT spawn second Chrome!
        if status == "CHROME_RUNNING_WITHOUT_CDP":
            return False, (
                "CHROME_RUNNING_WITHOUT_CDP: The selected Chrome profile is already open, but does not have an automation endpoint. "
                "Please use 'Connect to Open Chrome' or restart Chrome with automation enabled."
            )

        # 4. If Chrome is not running at all, launch controlled Chrome with CDP
        if status == "CHROME_NOT_RUNNING":
            prof_dir_name = chrome_profile.directory_name if chrome_profile else "Default"
            logger.info(f"Launching Chrome with profile '{prof_dir_name}' and automation port {self.cdp_port}...")
            launch_ok, launch_msg = ChromeProfileManager.launch_chrome_with_cdp(
                profile_dir_name=prof_dir_name,
                port=self.cdp_port,
                url=GOOGLE_FLOW_URL
            )
            if not launch_ok:
                return False, launch_msg

            # Wait for CDP endpoint to become ready
            for _ in range(20):
                time.sleep(0.5)
                if ChromeProfileManager.is_cdp_available(self.cdp_port):
                    break

            if ChromeProfileManager.is_cdp_available(self.cdp_port):
                conn_ok, conn_status, conn_tabs = self.connect_to_existing_chrome(port=self.cdp_port)
                if conn_ok and conn_status == "CONNECTED_TO_FLOW":
                    return True, "Connected to Google Flow tab"
                elif conn_status == "MULTIPLE_FLOW_TABS":
                    self._attach_tab(conn_tabs[0])
                    return True, "Connected to Google Flow tab"

        return False, "Could not initialize automation session with Google Flow."

    def navigate_to_exact_project(self, project_url: str) -> Tuple[bool, str]:
        """Navigate or switch to the exact Google Flow project tab without launching extra Chrome."""
        clean_url = project_url.strip()
        prof_name = self.chrome_profile.display_name if self.chrome_profile else "Default"

        # 1. Try CDP session first if connected
        if self._context and self._context.pages:
            # Check if any tab already matches project URL or project ID
            proj_id = clean_url.strip("/").split("/")[-1] if "/" in clean_url else clean_url
            for p in self._context.pages:
                try:
                    p_url = p.url or ""
                    if (clean_url and clean_url in p_url) or (proj_id and proj_id in p_url):
                        self._attach_tab({
                            "index": self._context.pages.index(p),
                            "title": p.title() or "Google Flow",
                            "url": p_url,
                            "page": p
                        })
                        p.bring_to_front()
                        logger.info(f"Switched to existing Google Flow project tab: {p_url}")
                        return True, "Switched to existing project tab"
                except Exception:
                    pass

            # If current page is open, navigate it
            if self._page and not self._page.is_closed():
                try:
                    logger.info(f"Navigating current tab to exact project: {clean_url}")
                    self._page.goto(clean_url, wait_until="domcontentloaded", timeout=45000)
                    return True, "Navigated existing tab to Flow project"
                except Exception as e:
                    logger.warning(f"Error navigating page via CDP: {e}")

            # Or open new page in same context
            try:
                logger.info(f"Opening exact project tab in existing Chrome: {clean_url}")
                new_page = self._context.new_page()
                new_page.goto(clean_url, wait_until="domcontentloaded", timeout=45000)
                self._attach_tab({
                    "index": len(self._context.pages) - 1,
                    "title": new_page.title() or "Google Flow",
                    "url": new_page.url,
                    "page": new_page
                })
                return True, "Opened Flow project in existing Chrome context"
            except Exception as e:
                logger.warning(f"Failed to open page in CDP context: {e}")

        # 2. Check Extension Bridge
        bridge = ExtensionBridgeServer.get_instance()
        if bridge.is_profile_connected(prof_name):
            logger.info(f"Using Chrome Extension bridge in profile '{prof_name}' to open Flow project...")
            ok, msg = bridge.open_flow_project(prof_name, clean_url, timeout_sec=15.0)
            if ok:
                return True, msg

        return False, "Could not navigate to Flow project: No active Chrome connection (CDP or Extension)"

    def verify_exact_project(self, project_url: str, timeout_sec: float = 45.0) -> Tuple[bool, str]:
        """
        Verify the exact Flow project is fully loaded and ready for automation.
        State-based detection: waits until flow-loading-page is gone and prompt container is ready.
        """
        clean_url = project_url.strip()
        proj_id = clean_url.strip("/").split("/")[-1] if "/" in clean_url else clean_url
        prof_name = self.chrome_profile.display_name if self.chrome_profile else "Default"
        start_time = time.time()

        logger.info(f"Verifying project '{proj_id}' readiness (timeout: {timeout_sec}s)...")

        # 1. Verification via CDP if page attached
        if self._page and not self._page.is_closed():
            while time.time() - start_time < timeout_sec:
                try:
                    curr_url = self._page.url or ""
                    # Check sign-in redirection
                    if "accounts.google.com/signin" in curr_url or "accounts.google.com/v3/signin" in curr_url:
                        return False, "Google Account login required in Chrome."

                    # Check loading page indicator
                    loading_elem = self._page.query_selector("flow-loading-page")
                    if loading_elem and loading_elem.is_visible():
                        time.sleep(0.5)
                        continue

                    # Check for prompt input or interactive controls
                    ready = False
                    for sel in [".prompt-box-container", "flow-tile-view-header", ".aisandbox-content"] + selectors.PROMPT_INPUT_SELECTORS:
                        elem = self._page.query_selector(sel)
                        if elem and elem.is_visible():
                            ready = True
                            break

                    if ready:
                        logger.info(f"Google Flow project {proj_id} verified loaded and interactive.")
                        return True, f"Project {proj_id} loaded and ready"

                except Exception as e:
                    logger.debug(f"Transient error verifying Flow page: {e}")

                time.sleep(0.5)

            return False, f"Timeout ({timeout_sec}s) waiting for Flow project {proj_id} to load."

        # 2. Verification via Extension Bridge
        bridge = ExtensionBridgeServer.get_instance()
        if bridge.is_profile_connected(prof_name):
            while time.time() - start_time < timeout_sec:
                ok, res = bridge.verify_flow_project(prof_name, timeout_sec=3.0)
                if ok and res.get("verified"):
                    logger.info(f"Google Flow project verified ready via Extension.")
                    return True, "Project verified ready via extension"
                time.sleep(1.0)
            return False, f"Timeout ({timeout_sec}s) waiting for extension to verify project readiness."

        return False, "Neither CDP page nor Extension bridge is available for verification."

    def navigate_to_flow(self) -> Tuple[bool, str]:
        """Ensure current tab is on Google Flow."""
        if not self._page:
            return False, "Browser tab not attached"

        current_url = self._page.url.lower()
        if "flow.google" in current_url or "labs.google" in current_url:
            return True, "Already on Google Flow"

        logger.info(f"Navigating tab to Google Flow: {GOOGLE_FLOW_URL}")
        try:
            self._page.goto(GOOGLE_FLOW_URL, wait_until="domcontentloaded", timeout=45000)
            self._page.wait_for_timeout(2000)
            return True, "Navigated to Flow"
        except Exception as e:
            return False, f"Could not navigate to Google Flow: {e}"

    def check_authenticated(self) -> Tuple[bool, str]:
        """Verify whether user is logged into Google Flow."""
        if not self._page:
            return False, "Browser tab not attached"

        current_url = self._page.url.lower()
        if "accounts.google.com/signin" in current_url or "accounts.google.com/v3/signin" in current_url:
            return False, "Google Account login required in the opened browser window."

        for sel in selectors.LOGIN_BUTTON_SELECTORS:
            try:
                elem = self._page.query_selector(sel)
                if elem and elem.is_visible():
                    return False, "Sign-in button detected. Please log in with your Google account."
            except Exception:
                pass

        for sel in selectors.AUTHENTICATED_SELECTORS:
            try:
                elem = self._page.query_selector(sel)
                if elem and elem.is_visible():
                    return True, "Authenticated"
            except Exception:
                pass

        if "flow" in current_url or "labs.google" in current_url:
            return True, "Authenticated (on Flow interface)"

        return True, "Authenticated"

    def prepare_scene_interface(self) -> Tuple[bool, str]:
        """Ensure the generation UI is ready for new input."""
        if not self._page:
            return False, "Browser tab not attached"
        self._page.wait_for_timeout(1000)
        return True, "Interface ready"

    def upload_reference(self, image_path: Path) -> Tuple[bool, str]:
        """Upload Master Image or previous scene's last frame as reference."""
        if not self._page:
            return False, "Browser tab not attached"

        img = Path(image_path).resolve()
        if not img.is_file():
            return False, f"Reference image file not found: {img}"

        logger.info(f"Uploading reference image: {img.name}")

        try:
            # 1. Look for existing file input
            file_input = self._page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(str(img))
                self._page.wait_for_timeout(2000)
                logger.info(f"Reference image submitted via file input: {img.name}")
                return True, "Reference uploaded"

            # 2. Look for upload buttons
            for sel in selectors.REFERENCE_UPLOAD_SELECTORS:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    with self._page.expect_file_chooser(timeout=5000) as fc_info:
                        btn.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(str(img))
                    self._page.wait_for_timeout(2000)
                    return True, "Reference uploaded"

            return False, "Could not find reference image upload button or file input in current Flow UI."
        except Exception as e:
            return False, f"Error uploading reference image: {e}"

    def submit_prompt(self, prompt_text: str) -> Tuple[bool, str]:
        """Paste and verify prompt text in the prompt field."""
        if not self._page:
            return False, "Browser tab not attached"

        clean_prompt = prompt_text.strip()
        logger.info(f"Entering prompt: {clean_prompt[:50]}...")

        try:
            target_field = None
            for sel in selectors.PROMPT_INPUT_SELECTORS:
                elem = self._page.query_selector(sel)
                if elem and elem.is_visible():
                    target_field = elem
                    break

            if not target_field:
                return False, "Could not locate prompt input field in current Flow UI."

            target_field.click()
            target_field.fill(clean_prompt)
            self._page.wait_for_timeout(500)

            # Verification
            val = target_field.input_value() if hasattr(target_field, "input_value") else target_field.inner_text()
            if not val or len(val.strip()) == 0:
                target_field.focus()
                self._page.keyboard.type(clean_prompt)
                self._page.wait_for_timeout(500)

            logger.info("Prompt verified in input field.")
            return True, "Prompt submitted"
        except Exception as e:
            return False, f"Failed to enter prompt: {e}"

    def trigger_generation(self) -> Tuple[bool, str]:
        """Click the generate button."""
        if not self._page:
            return False, "Browser tab not attached"

        try:
            gen_btn = None
            for sel in selectors.GENERATE_BUTTON_SELECTORS:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    gen_btn = btn
                    break

            if not gen_btn:
                return False, "Generate button not found or currently disabled."

            logger.info("Clicking Generate button...")
            gen_btn.click()
            self._page.wait_for_timeout(2000)
            return True, "Generation triggered"
        except Exception as e:
            return False, f"Failed to trigger generation: {e}"

    def wait_for_completion(self, timeout_sec: float = 600.0) -> Tuple[bool, str]:
        """Wait for video generation to complete."""
        if not self._page:
            return False, "Browser tab not attached"

        logger.info(f"Waiting for video generation completion (timeout: {timeout_sec}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout_sec:
            if not self.is_flow_tab_ready():
                return False, "Browser connection lost during video generation."

            # Check for error banners or failure dialogs
            for err_sel in getattr(selectors, "ERROR_INDICATORS", ['div[role="alert"]']):
                try:
                    error_elem = self._page.query_selector(err_sel)
                    if error_elem and error_elem.is_visible():
                        err_text = error_elem.inner_text().strip()
                        if err_text:
                            if "quota" in err_text.lower() or "limit" in err_text.lower():
                                return False, f"Google Flow quota limit reached: {err_text}"
                            if "fail" in err_text.lower() or "error" in err_text.lower():
                                return False, f"Generation failed on server: {err_text}"
                except Exception:
                    pass

            # Check if progress spinner is active
            is_generating = False
            for sel in selectors.GENERATING_INDICATORS:
                try:
                    elem = self._page.query_selector(sel)
                    if elem and elem.is_visible():
                        is_generating = True
                        break
                except Exception:
                    pass

            # Check if download button or video element is present
            has_download = False
            for sel in selectors.DOWNLOAD_BUTTON_SELECTORS:
                try:
                    elem = self._page.query_selector(sel)
                    if elem and elem.is_visible():
                        has_download = True
                        break
                except Exception:
                    pass

            if not is_generating and has_download:
                logger.info("Video generation completed successfully!")
                return True, "Generation completed"

            time.sleep(2.0)

        return False, f"Timeout ({timeout_sec}s) reached waiting for video generation."

    def download_video(self, destination_mp4_path: Path, timeout_sec: float = 300.0) -> Tuple[bool, str]:
        """Download the generated video and verify."""
        if not self._page:
            return False, "Browser tab not attached"

        dest = Path(destination_mp4_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initiating video download to: {dest.name}")

        try:
            download_btn = None
            for sel in selectors.DOWNLOAD_BUTTON_SELECTORS:
                elem = self._page.query_selector(sel)
                if elem and elem.is_visible():
                    download_btn = elem
                    break

            if not download_btn:
                # Check if there is a video tag with direct src URL
                video_elem = self._page.query_selector("video")
                if video_elem:
                    src = video_elem.get_attribute("src")
                    if src and src.startswith("http"):
                        logger.info("Direct video source URL detected. Downloading stream...")
                        resp = self._page.request.get(src)
                        with open(dest, "wb") as f:
                            f.write(resp.body())
                        ok, msg = VideoValidator.wait_for_file_stability(dest, timeout_sec=20)
                        if ok:
                            return True, "Downloaded directly via video source"

                return False, "Download button not found in Flow UI"

            with self._page.expect_download(timeout=int(timeout_sec * 1000)) as download_info:
                download_btn.click()

            download = download_info.value
            download.save_as(str(dest))

            ok, msg = VideoValidator.wait_for_file_stability(dest, timeout_sec=30)
            if not ok:
                return False, f"Download verification failed: {msg}"

            logger.info(f"Video file successfully saved and stabilized: {dest.name}")
            return True, "Downloaded successfully"

        except Exception as e:
            return False, f"Failed to download video: {e}"

    def close(self):
        """
        Disconnect from Chrome session.
        Never closes user's Chrome browser or other tabs.
        """
        try:
            if self._browser:
                # In Playwright, closing a CDP browser only disconnects, leaving Chrome running
                self._browser.close()
                self._browser = None
            if self._pw:
                self._pw.stop()
                self._pw = None
        except Exception:
            pass

        self._page = None
        self._context = None
        self.is_connected = False
        self.is_flow_connected = False
        self.connected_tab_info = {}
        logger.info("Disconnected from browser. User's Chrome browser remains completely open.")
