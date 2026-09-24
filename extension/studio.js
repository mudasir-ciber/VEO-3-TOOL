/**
 * Chained Evolution Studio - Complete In-Browser Execution Engine
 * Pure Chrome Extension Manifest V3 Architecture
 */

// Global State
const state = {
  projectName: "Airplane Evolution",
  targetFlowUrl: "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4",
  masterImageDataUrl: null,
  masterImageBlob: null,
  masterFilename: "master.png",
  scenes: [],
  currentSceneIndex: 0,
  currentChainReference: null, // DataURL of current reference
  currentChainRefName: "Master Image.png",
  isRunning: false,
  isPaused: false,
  flowTabId: null,
  flowStatus: "FLOW_TAB_NOT_FOUND", // FLOW_READY, FLOW_PROJECT_MISMATCH, FLOW_TAB_NOT_FOUND
  maxRetries: 3,
  pollIntervalSec: 3,
  autoDownload: true,
  soundEffects: true
};

// DOM Elements cache
const DOM = {};

document.addEventListener("DOMContentLoaded", () => {
  initDOM();
  loadStoredSettings();
  setupEventListeners();
  initFlowTabMonitor();
  log("Chained Evolution Studio Extension initialized. Ready.", "info");
});

function initDOM() {
  DOM.projectNameInput = document.getElementById("project-name-input");
  DOM.flowProjectIdDisplay = document.getElementById("flow-project-id-display");
  DOM.chainStatusText = document.getElementById("chain-status-text");

  // Sidebar
  DOM.sidebarStatusDot = document.getElementById("sidebar-status-dot");
  DOM.sidebarStatusTitle = document.getElementById("sidebar-status-title");
  DOM.sidebarStatusDesc = document.getElementById("sidebar-status-desc");
  DOM.btnOpenFlowTab = document.getElementById("btn-open-flow-tab");

  // Master Image
  DOM.masterDropzone = document.getElementById("master-dropzone");
  DOM.masterFileInput = document.getElementById("master-file-input");
  DOM.dropzoneEmpty = document.getElementById("dropzone-empty-state");
  DOM.dropzonePreview = document.getElementById("dropzone-preview-state");
  DOM.masterPreviewImg = document.getElementById("master-preview-img");
  DOM.masterFilename = document.getElementById("master-filename");
  DOM.masterFilesize = document.getElementById("master-filesize");
  DOM.btnRemoveMaster = document.getElementById("btn-remove-master");

  // Prompts
  DOM.promptTextarea = document.getElementById("prompt-batch-textarea");
  DOM.btnLoadSample = document.getElementById("btn-load-sample");
  DOM.btnClearPrompts = document.getElementById("btn-clear-prompts");
  DOM.sceneCounterBadge = document.getElementById("scene-counter-badge");
  DOM.btnRunChain = document.getElementById("btn-run-chain");
  DOM.btnPauseChain = document.getElementById("btn-pause-chain");
  DOM.btnStopChain = document.getElementById("btn-stop-chain");
  DOM.btnRetryScene = document.getElementById("btn-retry-scene");

  // Flow Monitor
  DOM.flowPill = document.getElementById("flow-pill");
  DOM.targetFlowUrlInput = document.getElementById("target-flow-url");
  DOM.btnSaveFlowUrl = document.getElementById("btn-save-flow-url");
  DOM.btnFocusFlow = document.getElementById("btn-focus-flow");
  DOM.flowBanner = document.getElementById("flow-banner");
  DOM.flowBannerText = document.getElementById("flow-banner-text");

  // Stepper & Active Monitor
  DOM.pipelineTitle = document.getElementById("pipeline-title");
  DOM.pipelineProgressText = document.getElementById("pipeline-progress-text");
  DOM.steps = {
    ref: document.getElementById("step-ref"),
    prompt: document.getElementById("step-prompt"),
    generate: document.getElementById("step-generate"),
    wait: document.getElementById("step-wait"),
    download: document.getElementById("step-download"),
    extract: document.getElementById("step-extract"),
    chain: document.getElementById("step-chain")
  };
  DOM.monitorRefImg = document.getElementById("monitor-ref-img");
  DOM.monitorRefEmpty = document.getElementById("monitor-ref-empty");
  DOM.monitorVideoPlayer = document.getElementById("monitor-video-player");
  DOM.monitorVideoEmpty = document.getElementById("monitor-video-empty");
  DOM.monitorFrameImg = document.getElementById("monitor-frame-img");
  DOM.monitorFrameEmpty = document.getElementById("monitor-frame-empty");

  // Console
  DOM.consoleLogs = document.getElementById("console-logs");
  DOM.btnClearConsole = document.getElementById("btn-clear-console");

  // Scenes Grid
  DOM.sceneCardsContainer = document.getElementById("scene-cards-container");
  DOM.emptyScenesMsg = document.getElementById("empty-scenes-msg");
  DOM.btnDownloadAllZip = document.getElementById("btn-download-all-zip");

  // Dialogs
  DOM.settingsDialog = document.getElementById("settings-dialog");
  DOM.helpDialog = document.getElementById("help-dialog");
}

function setupEventListeners() {
  // Navigation
  document.getElementById("nav-settings").addEventListener("click", () => DOM.settingsDialog.showModal());
  document.getElementById("btn-close-settings").addEventListener("click", () => DOM.settingsDialog.close());
  document.getElementById("btn-cancel-settings").addEventListener("click", () => DOM.settingsDialog.close());
  document.getElementById("btn-save-settings").addEventListener("click", saveSettings);

  document.getElementById("nav-help").addEventListener("click", () => DOM.helpDialog.showModal());
  document.getElementById("btn-close-help").addEventListener("click", () => DOM.helpDialog.close());
  document.getElementById("btn-understand-help").addEventListener("click", () => DOM.helpDialog.close());

  // Master Image Drag & Drop
  DOM.masterDropzone.addEventListener("click", () => DOM.masterFileInput.click());
  DOM.masterFileInput.addEventListener("change", handleMasterFileSelect);
  DOM.masterDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    DOM.masterDropzone.classList.add("dragover");
  });
  DOM.masterDropzone.addEventListener("dragleave", () => DOM.masterDropzone.classList.remove("dragover"));
  DOM.masterDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    DOM.masterDropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processMasterFile(e.dataTransfer.files[0]);
    }
  });
  DOM.btnRemoveMaster.addEventListener("click", (e) => {
    e.stopPropagation();
    removeMasterImage();
  });

  // Prompt Editor
  DOM.promptTextarea.addEventListener("input", handlePromptInput);
  DOM.btnLoadSample.addEventListener("click", loadSamplePrompts);
  DOM.btnClearPrompts.addEventListener("click", clearPrompts);

  // Execution
  DOM.btnRunChain.addEventListener("click", startChainExecution);
  DOM.btnPauseChain.addEventListener("click", togglePauseChain);
  DOM.btnStopChain.addEventListener("click", stopChainExecution);
  DOM.btnRetryScene.addEventListener("click", retryCurrentScene);

  // Flow Actions
  DOM.btnOpenFlowTab.addEventListener("click", openOrFocusFlowTab);
  DOM.btnFocusFlow.addEventListener("click", openOrFocusFlowTab);
  DOM.btnSaveFlowUrl.addEventListener("click", updateFlowUrl);

  // Console
  DOM.btnClearConsole.addEventListener("click", () => {
    DOM.consoleLogs.innerHTML = "";
    log("Console cleared.", "info");
  });

  // Project Name
  DOM.projectNameInput.addEventListener("change", (e) => {
    state.projectName = e.target.value.trim() || "Evolution Project";
    chrome.storage.local.set({ projectName: state.projectName });
  });

  // Download All Assets
  DOM.btnDownloadAllZip.addEventListener("click", downloadAllCompletedAssets);
}

// ----------------------------------------------------
// Flow Tab Discovery & Verification
// ----------------------------------------------------
async function initFlowTabMonitor() {
  await checkFlowTab();
  // Poll tab status every 3 seconds
  setInterval(checkFlowTab, 3000);
}

async function checkFlowTab() {
  try {
    const tabs = await chrome.tabs.query({});
    const targetUrl = state.targetFlowUrl.toLowerCase();
    const targetProjId = extractProjectId(targetUrl);

    let foundTab = null;
    let mismatchTab = null;

    for (const tab of tabs) {
      if (!tab.url) continue;
      const tabUrl = tab.url.toLowerCase();
      if (tabUrl.includes("flow.google.com") || tabUrl.includes("labs.google.com/flow")) {
        if (targetProjId && tabUrl.includes(targetProjId.toLowerCase())) {
          foundTab = tab;
          break;
        } else {
          mismatchTab = tab;
        }
      }
    }

    if (foundTab) {
      state.flowTabId = foundTab.id;
      state.flowStatus = "FLOW_READY";
      updateFlowUI("FLOW_READY", foundTab.url);
    } else if (mismatchTab) {
      state.flowTabId = mismatchTab.id;
      state.flowStatus = "FLOW_PROJECT_MISMATCH";
      updateFlowUI("FLOW_PROJECT_MISMATCH", mismatchTab.url);
    } else {
      state.flowTabId = null;
      state.flowStatus = "FLOW_TAB_NOT_FOUND";
      updateFlowUI("FLOW_TAB_NOT_FOUND", "");
    }
  } catch (err) {
    console.warn("Error checking Flow tabs:", err);
  }
}

function updateFlowUI(status, currentUrl) {
  if (status === "FLOW_READY") {
    DOM.sidebarStatusDot.className = "status-dot-pulse connected";
    DOM.sidebarStatusTitle.textContent = "FLOW READY";
    DOM.sidebarStatusDesc.textContent = "Connected to target project";
    DOM.flowPill.className = "status-pill status-ready";
    DOM.flowPill.textContent = "● Project Verified";
    DOM.flowBanner.classList.add("hidden");
  } else if (status === "FLOW_PROJECT_MISMATCH") {
    DOM.sidebarStatusDot.className = "status-dot-pulse error";
    DOM.sidebarStatusTitle.textContent = "PROJECT MISMATCH";
    DOM.sidebarStatusDesc.textContent = "Flow open to different project";
    DOM.flowPill.className = "status-pill status-error";
    DOM.flowPill.textContent = "● Project Mismatch";
    DOM.flowBanner.classList.remove("hidden");
    DOM.flowBannerText.textContent = "Google Flow is open, but displaying a different project. Please navigate to the configured project.";
  } else {
    DOM.sidebarStatusDot.className = "status-dot-pulse error";
    DOM.sidebarStatusTitle.textContent = "NO FLOW TAB";
    DOM.sidebarStatusDesc.textContent = "Google Flow tab not open";
    DOM.flowPill.className = "status-pill status-connecting";
    DOM.flowPill.textContent = "○ Searching...";
    DOM.flowBanner.classList.remove("hidden");
    DOM.flowBannerText.textContent = "Google Flow tab not found. Click 'Open Flow Tab' to launch.";
  }
}

async function openOrFocusFlowTab() {
  if (state.flowTabId) {
    try {
      await chrome.tabs.update(state.flowTabId, { active: true });
      const tab = await chrome.tabs.get(state.flowTabId);
      await chrome.windows.update(tab.windowId, { focused: true });
      return;
    } catch (e) {
      state.flowTabId = null;
    }
  }
  // Create tab if not open
  const newTab = await chrome.tabs.create({ url: state.targetFlowUrl });
  state.flowTabId = newTab.id;
  log("Opened Google Flow project tab.", "info");
}

function extractProjectId(url) {
  const m = url.match(/project\/([a-zA-Z0-9_-]+)/i);
  return m ? m[1] : "";
}

function updateFlowUrl() {
  const url = DOM.targetFlowUrlInput.value.trim();
  if (url) {
    state.targetFlowUrl = url;
    chrome.storage.local.set({ targetFlowUrl: url });
    const pId = extractProjectId(url);
    DOM.flowProjectIdDisplay.textContent = pId ? `${pId.slice(0, 14)}...` : "Custom Project";
    log(`Target Google Flow URL updated: ${url}`, "info");
    checkFlowTab();
  }
}

// ----------------------------------------------------
// Master Image Handling
// ----------------------------------------------------
function handleMasterFileSelect(e) {
  if (e.target.files && e.target.files.length > 0) {
    processMasterFile(e.target.files[0]);
  }
}

function processMasterFile(file) {
  if (!file.type.startsWith("image/")) {
    alert("Please select a valid image file (PNG, JPG, WebP).");
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    state.masterImageDataUrl = e.target.result;
    state.masterImageBlob = file;
    state.masterFilename = file.name;

    DOM.masterPreviewImg.src = state.masterImageDataUrl;
    DOM.masterFilename.textContent = file.name;
    DOM.masterFilesize.textContent = `${(file.size / 1024).toFixed(1)} KB`;

    DOM.dropzoneEmpty.classList.add("hidden");
    DOM.dropzonePreview.classList.remove("hidden");

    log(`✓ Master Image loaded: ${file.name} (${(file.size / 1024).toFixed(1)} KB). Ready for Scene 1.`, "success");
    playSound("ding");
    renderSceneCards();
  };
  reader.readAsDataURL(file);
}

function removeMasterImage() {
  state.masterImageDataUrl = null;
  state.masterImageBlob = null;
  DOM.dropzonePreview.classList.add("hidden");
  DOM.dropzoneEmpty.classList.remove("hidden");
  DOM.masterFileInput.value = "";
  log("Master Image removed.", "warning");
  renderSceneCards();
}

// ----------------------------------------------------
// Prompt Parsing & Scene Cards
// ----------------------------------------------------
function handlePromptInput() {
  parsePrompts();
}

function parsePrompts() {
  const text = DOM.promptTextarea.value.trim();
  if (!text) {
    state.scenes = [];
    DOM.sceneCounterBadge.textContent = "0 Scenes";
    renderSceneCards();
    return;
  }

  const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
  const parsed = [];
  let sceneIndex = 1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const match = line.match(/^SCENE\s*(\d+)[\s*:\-\.](.*)/i);
    if (match) {
      const sNum = parseInt(match[1], 10);
      const prompt = match[2].trim();
      parsed.push({ sceneNumber: sNum, promptText: prompt, status: "pending", videoBlob: null, videoUrl: "", lastFrameBlob: null, lastFrameDataUrl: "" });
      sceneIndex = sNum + 1;
    } else {
      parsed.push({ sceneNumber: sceneIndex, promptText: line, status: "pending", videoBlob: null, videoUrl: "", lastFrameBlob: null, lastFrameDataUrl: "" });
      sceneIndex++;
    }
  }

  state.scenes = parsed;
  DOM.sceneCounterBadge.textContent = `${parsed.length} Scene${parsed.length === 1 ? "" : "s"}`;
  renderSceneCards();
}

function loadSamplePrompts() {
  DOM.promptTextarea.value = `SCENE 1: Vintage 1903 Wright brothers glider taking off over ocean dunes, wings shaking gently in the coastal wind, golden hour sunlight.
SCENE 2: 1930s twin-engine commercial monoplane climbing through dense cumulus clouds, metallic propeller glare, aerodynamic motion.
SCENE 3: Modern supersonic military stealth fighter jet accelerating past Mach 2 into the dark stratosphere, twin afterburners glowing violet.`;
  parsePrompts();
  log("Sample prompts loaded (3 continuous scenes).", "info");
}

function clearPrompts() {
  DOM.promptTextarea.value = "";
  parsePrompts();
  log("Prompts cleared.", "info");
}

function renderSceneCards() {
  if (state.scenes.length === 0) {
    DOM.emptyScenesMsg.classList.remove("hidden");
    DOM.sceneCardsContainer.innerHTML = "";
    DOM.sceneCardsContainer.appendChild(DOM.emptyScenesMsg);
    return;
  }

  DOM.emptyScenesMsg.classList.add("hidden");
  DOM.sceneCardsContainer.innerHTML = "";

  state.scenes.forEach((scene, idx) => {
    const card = document.createElement("div");
    card.className = `scene-card scene-card-${scene.status}`;
    card.id = `card-scene-${scene.sceneNumber}`;

    // Ref image: Scene 1 uses Master Image, subsequent scenes use previous scene's last frame
    let refImgSrc = "";
    if (idx === 0) {
      refImgSrc = state.masterImageDataUrl || "";
    } else {
      refImgSrc = state.scenes[idx - 1].lastFrameDataUrl || "";
    }

    card.innerHTML = `
      <div class="scene-card-header">
        <span class="scene-num-badge">SCENE ${scene.sceneNumber}</span>
        <span class="scene-status-badge ${scene.status}">${scene.status.toUpperCase()}</span>
      </div>
      <div class="scene-card-preview-grid">
        <div class="scene-preview-box">
          ${refImgSrc ? `<img src="${refImgSrc}" alt="Reference">` : `<div class="monitor-empty">${idx === 0 ? "Master Image required" : "Awaiting Scene " + idx + " frame"}</div>`}
          <span class="scene-box-label">REF IN</span>
        </div>
        <div class="scene-preview-box">
          ${scene.videoUrl ? `<video src="${scene.videoUrl}" controls muted loop></video>` : (scene.lastFrameDataUrl ? `<img src="${scene.lastFrameDataUrl}" alt="Last Frame">` : `<div class="monitor-empty">No video yet</div>`)}
          <span class="scene-box-label">RESULT</span>
        </div>
      </div>
      <div class="scene-prompt-snippet" title="${escapeHtml(scene.promptText)}">
        ${escapeHtml(scene.promptText)}
      </div>
      <div class="scene-card-actions">
        <button class="btn btn-secondary btn-xs btn-card-retry" data-scene="${scene.sceneNumber}">🔄 Retry</button>
        ${scene.videoUrl ? `<button class="btn btn-primary btn-xs btn-card-download" data-scene="${scene.sceneNumber}">💾 Save MP4</button>` : ""}
      </div>
    `;

    // Bind card buttons
    const btnRetry = card.querySelector(".btn-card-retry");
    btnRetry.addEventListener("click", () => retrySceneByNumber(scene.sceneNumber));

    const btnDl = card.querySelector(".btn-card-download");
    if (btnDl) {
      btnDl.addEventListener("click", () => downloadSceneVideo(scene));
    }

    DOM.sceneCardsContainer.appendChild(card);
  });
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ----------------------------------------------------
// Stepper Helper
// ----------------------------------------------------
function updateStepper(activeKey) {
  const stepKeys = ["ref", "prompt", "generate", "wait", "download", "extract", "chain"];
  let foundActive = false;

  stepKeys.forEach(k => {
    const el = DOM.steps[k];
    if (!el) return;
    if (k === activeKey) {
      el.className = "step-item active";
      foundActive = true;
    } else if (!foundActive && activeKey !== null) {
      el.className = "step-item complete";
    } else {
      el.className = "step-item";
    }
  });
}

function resetStepper() {
  Object.values(DOM.steps).forEach(el => {
    if (el) el.className = "step-item";
  });
}

// ----------------------------------------------------
// THE CORE CONTINUOUS CHAIN EXECUTION ENGINE
// ----------------------------------------------------
async function startChainExecution() {
  if (state.isRunning) return;

  // 1. Validations
  if (!state.masterImageDataUrl) {
    alert("⚠️ Please upload a Master Image first (required as the reference for Scene 1).");
    return;
  }

  if (state.scenes.length === 0) {
    alert("⚠️ Please enter at least one scene prompt.");
    return;
  }

  await checkFlowTab();
  if (state.flowStatus !== "FLOW_READY") {
    const confirmLaunch = confirm("Google Flow target project tab is not open or not verified.\nWould you like to open it now?");
    if (confirmLaunch) {
      await openOrFocusFlowTab();
      alert("Please ensure Google Flow is loaded and signed in, then click RUN CONTINUOUS CHAIN again.");
    }
    return;
  }

  state.isRunning = true;
  state.isPaused = false;

  DOM.btnRunChain.disabled = true;
  DOM.btnPauseChain.disabled = false;
  DOM.btnStopChain.disabled = false;
  DOM.btnRetryScene.disabled = false;
  DOM.chainStatusText.textContent = "RUNNING";
  DOM.chainStatusText.className = "badge-value status-running";

  log(`🚀 Starting Continuous Evolution Chain: ${state.scenes.length} scenes queued.`, "info");
  playSound("start");

  // Determine starting scene index
  let startIndex = 0;
  for (let i = 0; i < state.scenes.length; i++) {
    if (state.scenes[i].status !== "completed") {
      startIndex = i;
      break;
    }
  }

  // Set initial chain reference
  if (startIndex === 0) {
    state.currentChainReference = state.masterImageDataUrl;
    state.currentChainRefName = state.masterFilename;
  } else {
    state.currentChainReference = state.scenes[startIndex - 1].lastFrameDataUrl;
    state.currentChainRefName = `Scene_${startIndex}_last_frame.png`;
  }

  for (let idx = startIndex; idx < state.scenes.length; idx++) {
    if (!state.isRunning) break;

    while (state.isPaused) {
      await sleep(1000);
      if (!state.isRunning) break;
    }
    if (!state.isRunning) break;

    state.currentSceneIndex = idx;
    const currentScene = state.scenes[idx];

    const success = await executeSingleScene(currentScene, idx);
    if (!success) {
      log(`⛔ Scene ${currentScene.sceneNumber} failed. Pausing continuous chain.`, "error");
      playSound("error");
      state.isPaused = true;
      DOM.chainStatusText.textContent = "PAUSED (ERROR)";
      DOM.chainStatusText.className = "badge-value status-paused";
      DOM.btnPauseChain.textContent = "▶️ Resume";
      break;
    }
  }

  if (state.isRunning && !state.isPaused) {
    log(`🎉 All ${state.scenes.length} scenes completed successfully! Unbroken evolution chain achieved.`, "success");
    playSound("fanfare");
    DOM.chainStatusText.textContent = "COMPLETED";
    DOM.chainStatusText.className = "badge-value status-running";
  }

  state.isRunning = false;
  DOM.btnRunChain.disabled = false;
  DOM.btnPauseChain.disabled = true;
  DOM.btnStopChain.disabled = true;
  resetStepper();
}

async function executeSingleScene(scene, sceneIndex) {
  const sNum = scene.sceneNumber;
  log(`========== SCENE ${sNum} STARTED ==========`, "info");
  scene.status = "generating";
  renderSceneCards();

  DOM.pipelineTitle.textContent = `Active Scene Pipeline: Scene ${sNum} of ${state.scenes.length}`;
  DOM.pipelineProgressText.textContent = `${sceneIndex} / ${state.scenes.length} Completed`;

  // Display active reference in monitor
  DOM.monitorRefImg.src = state.currentChainReference;
  DOM.monitorRefImg.classList.remove("hidden");
  DOM.monitorRefEmpty.classList.add("hidden");

  DOM.monitorVideoPlayer.classList.add("hidden");
  DOM.monitorVideoEmpty.classList.remove("hidden");
  DOM.monitorVideoEmpty.textContent = "Generating video in Google Flow...";
  DOM.monitorFrameImg.classList.add("hidden");
  DOM.monitorFrameEmpty.classList.remove("hidden");
  DOM.monitorFrameEmpty.textContent = "Waiting for video completion...";

  // 1. STEP: Upload Reference
  updateStepper("ref");
  log(`[Scene ${sNum}] Injecting reference: ${state.currentChainRefName}...`, "info");
  const refRes = await sendFlowCommand("UPLOAD_REFERENCE", {
    base64Data: state.currentChainReference,
    filename: state.currentChainRefName,
    scene: sNum
  });

  if (!refRes.success) {
    log(`Reference upload failed: ${refRes.error || "Unknown error"}`, "error");
    scene.status = "failed";
    renderSceneCards();
    return false;
  }
  log(`✓ Reference image injected into Flow interface.`, "success");

  // 2. STEP: Submit Prompt
  updateStepper("prompt");
  log(`[Scene ${sNum}] Submitting prompt: "${scene.promptText.slice(0, 60)}..."`, "info");
  const promptRes = await sendFlowCommand("SUBMIT_PROMPT", {
    promptText: scene.promptText,
    scene: sNum
  });

  if (!promptRes.success) {
    log(`Prompt injection failed: ${promptRes.error || "Unknown error"}`, "error");
    scene.status = "failed";
    renderSceneCards();
    return false;
  }
  log(`✓ Prompt entered successfully.`, "success");

  // 3. STEP: Trigger Generation
  updateStepper("generate");
  log(`[Scene ${sNum}] Triggering video generation...`, "info");
  const genRes = await sendFlowCommand("TRIGGER_GENERATION", { scene: sNum });
  if (!genRes.success) {
    log(`Failed to trigger generation: ${genRes.error}`, "error");
    scene.status = "failed";
    renderSceneCards();
    return false;
  }
  log(`✓ Generation button triggered in Flow.`, "success");

  // 4. STEP: Wait for 100% Completion
  updateStepper("wait");
  log(`[Scene ${sNum}] Waiting for generation completion (polling Flow status)...`, "info");
  const waitRes = await waitForGenerationCompletion(sNum, 600);
  if (!waitRes.success) {
    log(`Video generation did not complete: ${waitRes.error}`, "error");
    scene.status = "failed";
    renderSceneCards();
    return false;
  }
  log(`✓ Scene ${sNum} video generation complete!`, "success");

  // 5. STEP: Download MP4
  updateStepper("download");
  log(`[Scene ${sNum}] Retrieving generated video stream...`, "info");
  const videoData = await fetchVideoBlob(waitRes.videoUrl);
  if (!videoData) {
    log(`Failed to retrieve video stream from Flow.`, "error");
    scene.status = "failed";
    renderSceneCards();
    return false;
  }

  scene.videoBlob = videoData.blob;
  scene.videoUrl = videoData.url;

  // Update monitor preview
  DOM.monitorVideoPlayer.src = scene.videoUrl;
  DOM.monitorVideoPlayer.classList.remove("hidden");
  DOM.monitorVideoEmpty.classList.add("hidden");

  // Auto browser download
  if (state.autoDownload) {
    const videoFilename = `${sanitize(state.projectName)}_Scene_${sNum}.mp4`;
    chrome.downloads.download({
      url: scene.videoUrl,
      filename: `VEO3/${sanitize(state.projectName)}/${videoFilename}`,
      saveAs: false
    });
    log(`💾 Video saved to downloads: ${videoFilename}`, "info");
  }

  // 6. STEP: Extract Exact Last Frame via HTML5 Canvas
  updateStepper("extract");
  log(`[Scene ${sNum}] Extracting exact last video frame using high-resolution Canvas...`, "info");
  const frameResult = await extractLastFrameFromVideo(scene.videoBlob || scene.videoUrl);
  if (!frameResult) {
    log(`Last frame extraction failed.`, "error");
    scene.status = "failed";
    renderSceneCards();
    return false;
  }

  scene.lastFrameBlob = frameResult.blob;
  scene.lastFrameDataUrl = frameResult.dataUrl;

  DOM.monitorFrameImg.src = scene.lastFrameDataUrl;
  DOM.monitorFrameImg.classList.remove("hidden");
  DOM.monitorFrameEmpty.classList.add("hidden");

  if (state.autoDownload) {
    const frameFilename = `${sanitize(state.projectName)}_Scene_${sNum}_last_frame.png`;
    chrome.downloads.download({
      url: scene.lastFrameDataUrl,
      filename: `VEO3/${sanitize(state.projectName)}/${frameFilename}`,
      saveAs: false
    });
    log(`💾 Last frame saved to downloads: ${frameFilename}`, "info");
  }

  // 7. STEP: Chain to Next Scene
  updateStepper("chain");
  state.currentChainReference = scene.lastFrameDataUrl;
  state.currentChainRefName = `Scene_${sNum}_last_frame.png`;

  scene.status = "completed";
  renderSceneCards();
  log(`========== SCENE ${sNum} 100% COMPLETE ==========`, "success");
  log(`🔗 Chain Reference for Scene ${sNum + 1} locked: Scene ${sNum} exact last frame.`, "info");
  playSound("ding");

  return true;
}

// ----------------------------------------------------
// Video Generation Polling Loop
// ----------------------------------------------------
async function waitForGenerationCompletion(sceneNum, timeoutSec = 600) {
  const startTime = Date.now();
  const maxTime = timeoutSec * 1000;

  while (Date.now() - startTime < maxTime) {
    if (!state.isRunning) return { success: false, error: "Stopped by user" };

    const statusRes = await sendFlowCommand("CHECK_GENERATION_STATUS", { scene: sceneNum });
    if (statusRes.status === "COMPLETED") {
      let vUrl = statusRes.videoUrl;
      if (!vUrl) {
        const vRes = await sendFlowCommand("GET_VIDEO_URL", { scene: sceneNum });
        vUrl = vRes.url;
      }
      return { success: true, videoUrl: vUrl };
    } else if (statusRes.status === "ERROR") {
      return { success: false, error: statusRes.error || "Flow returned generation error" };
    }

    await sleep(state.pollIntervalSec * 1000);
  }

  return { success: false, error: `Generation timed out after ${timeoutSec} seconds` };
}

// ----------------------------------------------------
// Video Blob Fetcher
// ----------------------------------------------------
async function fetchVideoBlob(videoUrl) {
  if (!videoUrl) return null;

  try {
    const resp = await fetch(videoUrl);
    const blob = await resp.blob();
    const objectUrl = URL.createObjectURL(blob);
    return { blob, url: objectUrl };
  } catch (err) {
    console.warn("Direct video fetch failed, using URL:", err);
    return { blob: null, url: videoUrl };
  }
}

// ----------------------------------------------------
// EXACT LAST FRAME EXTRACTION (HTML5 <video> + <canvas>)
// Zero Python FFmpeg required - 100% Native Browser
// ----------------------------------------------------
async function extractLastFrameFromVideo(videoSource) {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.crossOrigin = "anonymous";
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";

    let srcUrl = "";
    if (videoSource instanceof Blob) {
      srcUrl = URL.createObjectURL(videoSource);
    } else {
      srcUrl = videoSource;
    }
    video.src = srcUrl;

    video.onloadedmetadata = () => {
      // Seek to 0.04s before the end to ensure a valid final video frame
      const targetTime = Math.max(0, video.duration - 0.04);
      video.currentTime = targetTime;
    };

    video.onseeked = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const dataUrl = canvas.toDataURL("image/png");
        canvas.toBlob((blob) => {
          if (videoSource instanceof Blob) {
            URL.revokeObjectURL(srcUrl);
          }
          resolve({ blob, dataUrl });
        }, "image/png");
      } catch (err) {
        console.error("Frame extraction error:", err);
        if (videoSource instanceof Blob) URL.revokeObjectURL(srcUrl);
        resolve(null);
      }
    };

    video.onerror = (e) => {
      console.error("Video load error for frame extraction:", e);
      if (videoSource instanceof Blob) URL.revokeObjectURL(srcUrl);
      resolve(null);
    };
  });
}

// ----------------------------------------------------
// Messaging to Content Script in Google Flow Tab
// ----------------------------------------------------
async function sendFlowCommand(action, payload = {}) {
  await checkFlowTab();
  if (!state.flowTabId) {
    return { success: false, error: "Google Flow tab not found." };
  }

  try {
    return await chrome.tabs.sendMessage(state.flowTabId, { action, payload });
  } catch (err) {
    return { success: false, error: `Content script communication error: ${err.message}` };
  }
}

// ----------------------------------------------------
// Controls & Pause/Resume
// ----------------------------------------------------
function togglePauseChain() {
  if (!state.isRunning) return;
  state.isPaused = !state.isPaused;

  if (state.isPaused) {
    DOM.btnPauseChain.textContent = "▶️ Resume";
    DOM.chainStatusText.textContent = "PAUSED";
    DOM.chainStatusText.className = "badge-value status-paused";
    log("Continuous chain paused.", "warning");
  } else {
    DOM.btnPauseChain.textContent = "⏸️ Pause";
    DOM.chainStatusText.textContent = "RUNNING";
    DOM.chainStatusText.className = "badge-value status-running";
    log("Resuming continuous chain...", "info");
  }
}

function stopChainExecution() {
  if (!state.isRunning) return;
  state.isRunning = false;
  state.isPaused = false;
  DOM.btnRunChain.disabled = false;
  DOM.btnPauseChain.disabled = true;
  DOM.btnStopChain.disabled = true;
  DOM.chainStatusText.textContent = "STOPPED";
  DOM.chainStatusText.className = "badge-value status-idle";
  log("Continuous chain stopped by user.", "warning");
  resetStepper();
}

async function retryCurrentScene() {
  if (state.scenes.length === 0) return;
  const currentScene = state.scenes[state.currentSceneIndex] || state.scenes[0];
  await retrySceneByNumber(currentScene.sceneNumber);
}

async function retrySceneByNumber(sceneNum) {
  const sceneIdx = state.scenes.findIndex(s => s.sceneNumber === sceneNum);
  if (sceneIdx === -1) return;

  const scene = state.scenes[sceneIdx];
  log(`Retrying Scene ${sceneNum}...`, "info");

  // Determine reference for this scene
  if (sceneIdx === 0) {
    state.currentChainReference = state.masterImageDataUrl;
    state.currentChainRefName = state.masterFilename;
  } else {
    const prevScene = state.scenes[sceneIdx - 1];
    if (!prevScene.lastFrameDataUrl) {
      alert(`Cannot retry Scene ${sceneNum}: Scene ${prevScene.sceneNumber} does not have an extracted last frame.`);
      return;
    }
    state.currentChainReference = prevScene.lastFrameDataUrl;
    state.currentChainRefName = `Scene_${prevScene.sceneNumber}_last_frame.png`;
  }

  state.isRunning = true;
  state.isPaused = false;
  DOM.btnRunChain.disabled = true;
  DOM.btnPauseChain.disabled = false;
  DOM.btnStopChain.disabled = false;

  await executeSingleScene(scene, sceneIdx);

  state.isRunning = false;
  DOM.btnRunChain.disabled = false;
  DOM.btnPauseChain.disabled = true;
  DOM.btnStopChain.disabled = true;
}

function downloadSceneVideo(scene) {
  if (!scene.videoUrl) return;
  const filename = `${sanitize(state.projectName)}_Scene_${scene.sceneNumber}.mp4`;
  chrome.downloads.download({
    url: scene.videoUrl,
    filename: `VEO3/${sanitize(state.projectName)}/${filename}`,
    saveAs: true
  });
}

function downloadAllCompletedAssets() {
  let count = 0;
  state.scenes.forEach(scene => {
    if (scene.videoUrl) {
      chrome.downloads.download({
        url: scene.videoUrl,
        filename: `VEO3/${sanitize(state.projectName)}/Scene_${scene.sceneNumber}.mp4`
      });
      count++;
    }
    if (scene.lastFrameDataUrl) {
      chrome.downloads.download({
        url: scene.lastFrameDataUrl,
        filename: `VEO3/${sanitize(state.projectName)}/Scene_${scene.sceneNumber}_last_frame.png`
      });
      count++;
    }
  });

  if (count === 0) {
    alert("No completed video or frame assets to download yet.");
  } else {
    log(`Downloaded ${count} project assets to Downloads/VEO3/${state.projectName}/`, "success");
  }
}

// ----------------------------------------------------
// Audio Synthesizer (Zero External MP3s Needed)
// ----------------------------------------------------
function playSound(type) {
  if (!state.soundEffects) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    const now = ctx.currentTime;

    if (type === "ding") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(1760, now + 0.15);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
      osc.start(now);
      osc.stop(now + 0.3);
    } else if (type === "start") {
      osc.type = "triangle";
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.2);
      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
      osc.start(now);
      osc.stop(now + 0.3);
    } else if (type === "fanfare") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.1); // E5
      osc.frequency.setValueAtTime(783.99, now + 0.2); // G5
      osc.frequency.setValueAtTime(1046.50, now + 0.3); // C6
      gain.gain.setValueAtTime(0.3, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.6);
      osc.start(now);
      osc.stop(now + 0.6);
    } else if (type === "error") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.linearRampToValueAtTime(110, now + 0.3);
      gain.gain.setValueAtTime(0.3, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.4);
      osc.start(now);
      osc.stop(now + 0.4);
    }
  } catch (e) {
    // AudioContext might be blocked until user gesture
  }
}

// ----------------------------------------------------
// Utilities & Logging
// ----------------------------------------------------
function log(msg, type = "info") {
  const time = new Date().toLocaleTimeString("en-GB", { hour12: false });
  const line = document.createElement("div");
  line.className = `log-line log-${type}`;
  line.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-msg">${escapeHtml(msg)}</span>`;
  DOM.consoleLogs.appendChild(line);
  DOM.consoleLogs.scrollTop = DOM.consoleLogs.scrollHeight;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function sanitize(str) {
  return (str || "Project").replace(/[^a-zA-Z0-9_\-]/g, "_");
}

function loadStoredSettings() {
  chrome.storage.local.get([
    "projectName",
    "targetFlowUrl",
    "maxRetries",
    "pollIntervalSec",
    "autoDownload",
    "soundEffects"
  ], (res) => {
    if (res.projectName) {
      state.projectName = res.projectName;
      DOM.projectNameInput.value = res.projectName;
    }
    if (res.targetFlowUrl) {
      state.targetFlowUrl = res.targetFlowUrl;
      DOM.targetFlowUrlInput.value = res.targetFlowUrl;
      const pId = extractProjectId(res.targetFlowUrl);
      DOM.flowProjectIdDisplay.textContent = pId ? `${pId.slice(0, 14)}...` : "Custom";
    }
    if (res.maxRetries) state.maxRetries = res.maxRetries;
    if (res.pollIntervalSec) state.pollIntervalSec = res.pollIntervalSec;
    if (res.autoDownload !== undefined) state.autoDownload = res.autoDownload;
    if (res.soundEffects !== undefined) state.soundEffects = res.soundEffects;

    // Update settings dialog inputs
    document.getElementById("setting-flow-url").value = state.targetFlowUrl;
    document.getElementById("setting-max-retries").value = state.maxRetries;
    document.getElementById("setting-poll-interval").value = state.pollIntervalSec;
    document.getElementById("setting-auto-download").checked = state.autoDownload;
    document.getElementById("setting-sound-effects").checked = state.soundEffects;
  });
}

function saveSettings() {
  state.targetFlowUrl = document.getElementById("setting-flow-url").value.trim() || state.targetFlowUrl;
  state.maxRetries = parseInt(document.getElementById("setting-max-retries").value, 10) || 3;
  state.pollIntervalSec = parseInt(document.getElementById("setting-poll-interval").value, 10) || 3;
  state.autoDownload = document.getElementById("setting-auto-download").checked;
  state.soundEffects = document.getElementById("setting-sound-effects").checked;

  DOM.targetFlowUrlInput.value = state.targetFlowUrl;

  chrome.storage.local.set({
    targetFlowUrl: state.targetFlowUrl,
    maxRetries: state.maxRetries,
    pollIntervalSec: state.pollIntervalSec,
    autoDownload: state.autoDownload,
    soundEffects: state.soundEffects
  });

  DOM.settingsDialog.close();
  log("Settings saved successfully.", "success");
  checkFlowTab();
}
