// Content Script for Google Flow page automation and monitoring
// Communicates with background service worker to automate the Flow web interface

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

function checkFlowReady() {
  const promptBox = document.querySelector(".prompt-box-container");
  const loadingPage = document.querySelector("flow-loading-page");
  const isLoading = loadingPage && window.getComputedStyle(loadingPage).display !== "none" && window.getComputedStyle(loadingPage).opacity !== "0";

  if (promptBox && !isLoading) {
    return true;
  }

  const header = document.querySelector("flow-tile-view-header");
  const content = document.querySelector(".aisandbox-content");
  return Boolean(header && content && !isLoading);
}

function checkAuthenticated() {
  const signInBtn = document.querySelector('button:has-text("Sign in"), a[href*="accounts.google.com"]');
  if (signInBtn) return false;

  const accountMeta = document.querySelector('meta[name="og-profile-acct"]');
  const userPic = document.querySelector('img[src*="googleusercontent.com"]');
  return Boolean(accountMeta || userPic || window.location.href.includes("flow.google.com"));
}

// Convert base64 dataURI to File object
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

  // 1. Check for visible or hidden file input
  let fileInput = document.querySelector('input[type="file"]');
  if (!fileInput) {
    // Try finding reference upload buttons to click and reveal file input
    const uploadSelectors = [
      '.prompt-box-container button:has(mat-icon:has-text("add"))',
      '.prompt-box-container button:has(mat-icon:has-text("image"))',
      '.prompt-box-container button.flow-icon-button-primary',
      'button[aria-label*="reference" i]',
      'button[aria-label*="add image" i]',
      'button[aria-label*="first frame" i]',
      'button:has-text("Add Reference")',
      'button:has-text("Upload Image")'
    ];
    for (const sel of uploadSelectors) {
      try {
        const btn = document.querySelector(sel);
        if (btn) {
          btn.click();
          await new Promise(r => setTimeout(r, 400));
          fileInput = document.querySelector('input[type="file"]');
          if (fileInput) break;
        }
      } catch (e) {}
    }
  }

  if (fileInput) {
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    fileInput.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 1000));
    return { success: true, message: `Reference image '${filename}' uploaded via input.` };
  }

  // 2. Try drag & drop on prompt-box-container or dropzone
  const dropTarget = document.querySelector('.prompt-box-container') || document.querySelector('.drop-images-overlay') || document.body;
  if (dropTarget) {
    const dragEvent = new DragEvent('drop', {
      bubbles: true,
      cancelable: true,
      dataTransfer: dt
    });
    dropTarget.dispatchEvent(dragEvent);
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
    '.prompt-box-container textarea',
    '.prompt-box-container [contenteditable="true"]',
    '.prompt-box-container div[role="textbox"]',
    'textarea[placeholder*="prompt" i]',
    'textarea[placeholder*="Describe" i]',
    'textarea[aria-label*="prompt" i]',
    'div[contenteditable="true"][role="textbox"]',
    'textarea',
    'input[type="text"][placeholder*="prompt" i]'
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
    targetField.dispatchEvent(new Event('input', { bubbles: true }));
    targetField.dispatchEvent(new Event('change', { bubbles: true }));
  } else {
    // Contenteditable div
    targetField.innerText = promptText;
    targetField.dispatchEvent(new Event('input', { bubbles: true }));
  }

  await new Promise(r => setTimeout(r, 500));
  return { success: true, message: "Prompt submitted to input field." };
}

// Trigger generation by clicking Generate button
async function handleTriggerGeneration() {
  const buttonSelectors = [
    '.prompt-box-container button.flow-button-primary',
    '.prompt-box-container button.flow-icon-button-primary',
    '.prompt-box-container button:has-text("Generate")',
    '.prompt-box-container button[type="submit"]',
    'button.flow-button-primary',
    'button:has-text("Generate")',
    'button:has-text("Create")',
    'button:has-text("Render")',
    'button[aria-label*="Generate" i]',
    'button[aria-label*="Create video" i]',
    'button[type="submit"]'
  ];

  let genBtn = null;
  for (const sel of buttonSelectors) {
    try {
      const elem = document.querySelector(sel);
      if (elem && !elem.disabled && window.getComputedStyle(elem).display !== "none") {
        genBtn = elem;
        break;
      }
    } catch (e) {}
  }

  if (!genBtn) {
    return { success: false, error: "Generate button not found or currently disabled." };
  }

  genBtn.click();
  await new Promise(r => setTimeout(r, 1500));
  return { success: true, message: "Generate button clicked." };
}

// Check generation status
async function handleCheckStatus() {
  // Check for error banners
  const errorSelectors = [
    '.error-tile',
    '.banner.error',
    '.banner.warning',
    'div[role="alert"]',
    '.flow-snackbar-panel'
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
    'flow-loading-page',
    '.loading-page-fade-in',
    '[role="progressbar"]',
    '.generating-spinner',
    'svg[aria-label*="loading" i]'
  ];

  for (const sel of progressSelectors) {
    const progElem = document.querySelector(sel);
    if (progElem && window.getComputedStyle(progElem).display !== "none") {
      return { status: "IN_PROGRESS" };
    }
  }

  // Check for completed video or download button
  const downloadSelectors = [
    'button.flow-icon-button-transparent:has(mat-icon:has-text("download"))',
    'button:has(mat-icon:has-text("download"))',
    '.batch-tiles-section button:has(mat-icon:has-text("download"))',
    '.tiles-container button:has(mat-icon:has-text("download"))',
    'button[aria-label*="Download" i]',
    'a[aria-label*="Download" i]',
    'button:has-text("Download")',
    'a[download]'
  ];

  for (const sel of downloadSelectors) {
    try {
      const dBtn = document.querySelector(sel);
      if (dBtn && window.getComputedStyle(dBtn).display !== "none") {
        const videoElem = document.querySelector('video[src], .batch-tiles-section video, .tiles-container video');
        const videoSrc = videoElem ? (videoElem.currentSrc || videoElem.src) : "";
        return { status: "COMPLETED", videoUrl: videoSrc };
      }
    } catch (e) {}
  }

  const videoElem = document.querySelector('video[src], .batch-tiles-section video, .tiles-container video');
  if (videoElem && (videoElem.currentSrc || videoElem.src)) {
    return { status: "COMPLETED", videoUrl: videoElem.currentSrc || videoElem.src };
  }

  return { status: "IDLE" };
}

// Get video URL
async function handleGetVideoUrl() {
  const videoElem = document.querySelector('video[src], .batch-tiles-section video, .tiles-container video, flow-video-player video');
  if (videoElem && (videoElem.currentSrc || videoElem.src)) {
    return { success: true, url: videoElem.currentSrc || videoElem.src };
  }
  return { success: false, error: "No video element with source found on page." };
}
