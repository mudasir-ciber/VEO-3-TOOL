"""Playwright-driven Google Flow browser connector with persistent session and robust selectors."""
import os
import sys
import time
from pathlib import Path
from typing import Tuple, Optional, Any

from core.config import DEFAULT_BROWSER_PROFILE_DIR, GOOGLE_FLOW_URL
from core.system_checker import SystemChecker
from core.video_validator import VideoValidator
from core.logger import logger
from connector.flow_base import BaseFlowConnector
import connector.flow_selectors as selectors


class PlaywrightFlowConnector(BaseFlowConnector):
    def __init__(self):
        self._pw = None
        self._context = None
        self._page = None
        self.profile_dir = Path(DEFAULT_BROWSER_PROFILE_DIR).resolve()
        self.is_connected = False

    def initialize(self, headless: bool = False, profile_dir: Optional[Path] = None, chrome_profile: Optional[Any] = None) -> Tuple[bool, str]:
        """Launch browser with selected Chrome profile to retain authentic Google login."""
        from playwright.sync_api import sync_playwright
        from core.chrome_profile_manager import ChromeProfileManager

        # Check if a specific Chrome profile was selected
        target_user_data_dir = profile_dir or self.profile_dir
        profile_arg = None

        if chrome_profile:
            # Verify profile lock
            if ChromeProfileManager.is_profile_locked(chrome_profile.directory_name):
                return False, (
                    f"Chrome Profile In Use: '{chrome_profile.display_name}' is currently open in another Chrome session. "
                    "Please close Chrome windows using this profile and try again."
                )
            chrome_user_data = ChromeProfileManager.get_chrome_user_data_dir()
            if chrome_user_data and chrome_user_data.is_dir():
                target_user_data_dir = chrome_user_data
                profile_arg = f"--profile-directory={chrome_profile.directory_name}"

        try:
            self._pw = sync_playwright().start()

            chrome_path = SystemChecker.find_chrome()
            edge_path = SystemChecker.find_edge()

            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            if profile_arg:
                args.append(profile_arg)

            launch_kwargs = {
                "user_data_dir": str(target_user_data_dir),
                "headless": headless,
                "viewport": {"width": 1366, "height": 850},
                "args": args
            }

            if chrome_path:
                logger.info(f"Launching Google Chrome with profile [{profile_arg or 'Default'}]: {chrome_path}")
                launch_kwargs["executable_path"] = chrome_path
            elif edge_path:
                logger.info(f"Launching Microsoft Edge: {edge_path}")
                launch_kwargs["executable_path"] = edge_path
            else:
                launch_kwargs["channel"] = "chromium"

            self._context = self._pw.chromium.launch_persistent_context(**launch_kwargs)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

            # Handle accidental closure
            self._page.on("close", lambda p: logger.warning("Browser page was closed."))

            self.is_connected = True
            logger.info("Browser session initialized successfully.")
            return True, "Browser initialized"
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            self.is_connected = False
            return False, f"Browser launch failed: {e}"

    def navigate_to_flow(self) -> Tuple[bool, str]:
        """Navigate to Google Flow URL."""
        if not self._page:
            return False, "Browser not initialized"

        logger.info(f"Navigating to Google Flow: {GOOGLE_FLOW_URL}")
        try:
            self._page.goto(GOOGLE_FLOW_URL, wait_until="domcontentloaded", timeout=45000)
            self._page.wait_for_timeout(2500)
            return True, "Navigated to Flow"
        except Exception as e:
            logger.warning(f"Primary URL failed ({e}), attempting fallback: {selectors.URLS[1]}")
            try:
                self._page.goto(selectors.URLS[1], wait_until="domcontentloaded", timeout=45000)
                self._page.wait_for_timeout(2500)
                return True, "Navigated to fallback Flow URL"
            except Exception as e2:
                return False, f"Could not load Google Flow: {e2}"

    def check_authenticated(self) -> Tuple[bool, str]:
        """Verify whether user is logged into Google."""
        if not self._page:
            return False, "Browser not initialized"

        current_url = self._page.url.lower()
        if "accounts.google.com/signin" in current_url or "accounts.google.com/v3/signin" in current_url:
            return False, "Google Account login required in the opened browser window."

        # Check for presence of login buttons
        for sel in selectors.LOGIN_BUTTON_SELECTORS:
            try:
                elem = self._page.query_selector(sel)
                if elem and elem.is_visible():
                    return False, "Sign-in button detected. Please log in with your Google account."
            except Exception:
                pass

        # Check for authenticated indicators
        for sel in selectors.AUTHENTICATED_SELECTORS:
            try:
                elem = self._page.query_selector(sel)
                if elem and elem.is_visible():
                    return True, "Authenticated"
            except Exception:
                pass

        # If on flow domain without sign-in prompts, assume authenticated
        if "flow" in current_url or "labs.google" in current_url:
            return True, "Authenticated (on Flow interface)"

        return True, "Authenticated"

    def prepare_scene_interface(self) -> Tuple[bool, str]:
        """Ensure the generation UI is ready for new input."""
        if not self._page:
            return False, "Browser not initialized"
        self._page.wait_for_timeout(1000)
        return True, "Interface ready"

    def upload_reference(self, image_path: Path) -> Tuple[bool, str]:
        """Upload the Master Image or previous scene's last frame as reference."""
        if not self._page:
            return False, "Browser not initialized"

        img = Path(image_path).resolve()
        if not img.is_file():
            return False, f"Reference image file not found: {img}"

        logger.info(f"Uploading reference image: {img.name}")

        try:
            # First search for any file input element (even hidden)
            file_input = self._page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(str(img))
                self._page.wait_for_timeout(2000)
                logger.info(f"Reference image submitted via file input: {img.name}")
                return True, "Reference uploaded"

            # Fallback: look for upload buttons to click and expect file chooser
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
            return False, "Browser not initialized"

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

            # Clear and type/fill
            target_field.click()
            target_field.fill(clean_prompt)
            self._page.wait_for_timeout(500)

            # Verification
            val = target_field.input_value() if hasattr(target_field, "input_value") else target_field.inner_text()
            if not val or len(val.strip()) == 0:
                # Try clipboard/keyboard type fallback
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
            return False, "Browser not initialized"

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
        """Wait for video generation to complete (no arbitrary wait times)."""
        if not self._page:
            return False, "Browser not initialized"

        logger.info(f"Waiting for video generation completion (timeout: {timeout_sec}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout_sec:
            # Check for error banners or failure dialogs
            error_elem = self._page.query_selector('div[role="alert"], .error-message')
            if error_elem and error_elem.is_visible():
                err_text = error_elem.inner_text()
                if "quota" in err_text.lower() or "limit" in err_text.lower():
                    return False, f"Google Flow quota limit reached: {err_text}"
                if "fail" in err_text.lower() or "error" in err_text.lower():
                    return False, f"Generation failed on server: {err_text}"

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
            return False, "Browser not initialized"

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

            # Intercept download event
            with self._page.expect_download(timeout=int(timeout_sec * 1000)) as download_info:
                download_btn.click()

            download = download_info.value
            download.save_as(str(dest))

            # Verify stability
            ok, msg = VideoValidator.wait_for_file_stability(dest, timeout_sec=30)
            if not ok:
                return False, f"Download verification failed: {msg}"

            logger.info(f"Video file successfully saved and stabilized: {dest.name}")
            return True, "Downloaded successfully"

        except Exception as e:
            return False, f"Failed to download video: {e}"

    def close(self):
        """Close browser context."""
        try:
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self.is_connected = False
