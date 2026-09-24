// Content Script for Google Flow page automation
// Runs directly inside https://flow.google.com/*

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const action = request.action;

  if (action === "CHECK_READY") {
    const isReady = checkFlowReady();
    const isAuthenticated = checkAuthenticated();
    sendResponse({
      isReady: isReady,
      authenticated: isAuthenticated,
      url: window.location.href
    });
    return true;
  }

  if (action === "UPLOAD_REFERENCE") {
    handleUploadReference(request.payload)
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }

  if (action === "SUBMIT_PROMPT") {
    handleSubmitPrompt(request.payload)
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }

  if (action === "TRIGGER_GENERATION") {
    handleTriggerGeneration()
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }

  if (action === "CHECK_GENERATION_STATUS") {
    handleCheckStatus()
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }

  if (action === "GET_VIDEO_URL") {
    handleGetVideoUrl()
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }

  return true;
});

// Robust DOM search helpers (no non-standard CSS selectors)
function findButtonByText(text, container = document) {
  const buttons = container.querySelectorAll("button, [role='button'], div[role='button']");
  for (const b of buttons) {
    if (b.innerText && b.innerText.toLowerCase().includes(text.toLowerCase())) {
      if (window.getComputedStyle(b).display !== "none") {
        return b;
      }
    }
  }
  return null;
}

function findButtonWithIcon(iconText, container = document) {
  const icons = container.querySelectorAll("mat-icon, .material-icons, span, i");
  for (const icon of icons) {
    if (icon.innerText && icon.innerText.toLowerCase().includes(iconText.toLowerCase())) {
      const btn = icon.closest("button, [role='button'], a");
      if (btn && window.getComputedStyle(btn).display !== "none") {
        return btn;
      }
    }
  }
  return null;
}

function checkFlowReady() {
  const promptBox = document.querySelector(".prompt-box-container") || document.querySelector("textarea") || document.querySelector("[contenteditable='true']");
  const loadingPage = document.querySelector("flow-loading-page");
  const isLoading = loadingPage && window.getComputedStyle(loadingPage).display !== "none" && window.getComputedStyle(loadingPage).opacity !== "0";

  if (promptBox && !isLoading) {
    return true;
  }

  const header = document.querySelector("flow-tile-view-header");
  const content = document.querySelector(".aisandbox-content") || document.querySelector("main");
  return Boolean((header || content) && !isLoading);
}

function checkAuthenticated() {
  const signInBtn = findButtonByText("Sign in");
  if (signInBtn) return false;

  const userPic = document.querySelector("img[src*='googleusercontent.com']") || document.querySelector("header img");
  return Boolean(userPic || window.location.href.includes("flow.google.com"));
}

// Convert base64 dataURI to genuine File object
function dataURItoFile(dataURI, filename) {
  const arr = dataURI.split(',');
  const mime = arr[0].match(/:(.*?);/)[1] || 'image/png';
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n);
  }
  return new File([u8arr], filename, { type: mime });
}

// Upload reference image via file input or DataTransfer drop
async function handleUploadReference(payload) {
  const base64Data = payload.base64Data;
  const filename = payload.filename || "reference.png";

  const file = dataURItoFile(base64Data, filename);
  const dt = new DataTransfer();
  dt.items.add(file);

  // 1. Try finding existing file input
  let fileInput = document.querySelector("input[type='file']");
  if (!fileInput) {
    // Look for add / reference image button
    const uploadBtn = findButtonWithIcon("add") ||
                      findButtonWithIcon("image") ||
                      findButtonByText("Add Reference") ||
                      findButtonByText("Upload Image") ||
                      document.querySelector("button[aria-label*='reference' i]") ||
                      document.querySelector("button[aria-label*='image' i]");

    if (uploadBtn) {
      uploadBtn.click();
      await new Promise(r => setTimeout(r, 400));
      fileInput = document.querySelector("input[type='file']");
    }
  }

  if (fileInput) {
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    fileInput.dispatchEvent(new Event("input", { bubbles: true }));
    await new Promise(r => setTimeout(r, 800));
    return { success: true, message: `Reference image '${filename}' uploaded via input.` };
  }

  // 2. Drag & Drop onto dropzone or prompt container
  const dropTarget = document.querySelector(".prompt-box-container") ||
                     document.querySelector(".drop-images-overlay") ||
                     document.querySelector("textarea")?.parentElement ||
                     document.body;

  if (dropTarget) {
    const dragEnter = new DragEvent("dragenter", { bubbles: true, cancelable: true, dataTransfer: dt });
    const dragOver = new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt });
    const dropEvent = new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt });

    dropTarget.dispatchEvent(dragEnter);
    dropTarget.dispatchEvent(dragOver);
    dropTarget.dispatchEvent(dropEvent);
    await new Promise(r => setTimeout(r, 1000));
    return { success: true, message: `Reference image '${filename}' dropped on container.` };
  }

  return { success: false, error: "Could not locate file input or dropzone in Flow interface." };
}

// Submit prompt to textarea or contenteditable input
async function handleSubmitPrompt(payload) {
  const promptText = (payload.promptText || "").trim();
  if (!promptText) {
    return { success: false, error: "Empty prompt text" };
  }

  const inputSelectors = [
    ".prompt-box-container textarea",
    ".prompt-box-container [contenteditable='true']",
    ".prompt-box-container div[role='textbox']",
    "textarea[placeholder*='prompt' i]",
    "textarea[placeholder*='Describe' i]",
    "textarea[aria-label*='prompt' i]",
    "div[contenteditable='true'][role='textbox']",
    "textarea",
    "input[type='text'][placeholder*='prompt' i]"
  ];

  let targetField = null;
  for (const sel of inputSelectors) {
    const elem = document.querySelector(sel);
    if (elem && window.getComputedStyle(elem).display !== "none") {
      targetField = elem;
      break;
    }
  }

  if (!targetField) {
    return { success: false, error: "Could not locate prompt input field." };
  }

  targetField.focus();

  if (targetField.tagName.toLowerCase() === "textarea" || targetField.tagName.toLowerCase() === "input") {
    targetField.value = promptText;
    targetField.dispatchEvent(new Event("input", { bubbles: true }));
    targetField.dispatchEvent(new Event("change", { bubbles: true }));
  } else {
    targetField.innerText = promptText;
    targetField.dispatchEvent(new Event("input", { bubbles: true }));
  }

  await new Promise(r => setTimeout(r, 400));
  return { success: true, message: "Prompt submitted to input field." };
}

// Trigger generation
async function handleTriggerGeneration() {
  const buttonSelectors = [
    ".prompt-box-container button.flow-button-primary",
    ".prompt-box-container button.flow-icon-button-primary",
    ".prompt-box-container button[type='submit']",
    "button.flow-button-primary",
    "button[aria-label*='Generate' i]",
    "button[aria-label*='Create' i]",
    "button[type='submit']"
  ];

  let genBtn = null;
  for (const sel of buttonSelectors) {
    const elem = document.querySelector(sel);
    if (elem && !elem.disabled && window.getComputedStyle(elem).display !== "none") {
      genBtn = elem;
      break;
    }
  }

  if (!genBtn) {
    genBtn = findButtonByText("Generate") || findButtonByText("Create") || findButtonByText("Render");
  }

  if (!genBtn) {
    return { success: false, error: "Generate button not found or disabled." };
  }

  genBtn.click();
  await new Promise(r => setTimeout(r, 1200));
  return { success: true, message: "Generate button clicked." };
}

// Check generation status
async function handleCheckStatus() {
  // Check for error banners
  const errorSelectors = [
    ".error-tile",
    ".banner.error",
    ".banner.warning",
    "div[role='alert']",
    ".flow-snackbar-panel"
  ];

  for (const sel of errorSelectors) {
    const errElem = document.querySelector(sel);
    if (errElem && window.getComputedStyle(errElem).display !== "none") {
      const text = errElem.innerText.trim();
      if (text && (text.toLowerCase().includes("error") || text.toLowerCase().includes("quota") || text.toLowerCase().includes("failed"))) {
        return { status: "ERROR", error: text };
      }
    }
  }

  // Check progress indicators
  const progressSelectors = [
    "flow-loading-page",
    ".loading-page-fade-in",
    "[role='progressbar']",
    ".generating-spinner",
    "svg[aria-label*='loading' i]"
  ];

  for (const sel of progressSelectors) {
    const progElem = document.querySelector(sel);
    if (progElem && window.getComputedStyle(progElem).display !== "none") {
      return { status: "IN_PROGRESS" };
    }
  }

  // Check for download button or completed video
  const downloadBtn = findButtonWithIcon("download") ||
                      findButtonByText("Download") ||
                      document.querySelector("button[aria-label*='Download' i]") ||
                      document.querySelector("a[download]");

  const videoElem = document.querySelector("video[src], .batch-tiles-section video, .tiles-container video, flow-video-player video");

  if (downloadBtn || videoElem) {
    const videoSrc = videoElem ? (videoElem.currentSrc || videoElem.src) : "";
    return { status: "COMPLETED", videoUrl: videoSrc };
  }

  return { status: "IDLE" };
}

// Get video URL
async function handleGetVideoUrl() {
  const videoElem = document.querySelector("video[src], .batch-tiles-section video, .tiles-container video, flow-video-player video");
  if (videoElem && (videoElem.currentSrc || videoElem.src)) {
    return { success: true, url: videoElem.currentSrc || videoElem.src };
  }
  return { success: false, error: "No video element with source found on page." };
}
