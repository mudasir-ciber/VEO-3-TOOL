// Background Service Worker for VEO 3 Chained Evolution Studio Bridge
// Supports Native Messaging Host connection + fallback Local IPC bridge

const NATIVE_HOST_NAME = "com.veo3.studio.bridge";
const FALLBACK_HTTP_URL = "http://127.0.0.1:18999";
const DEFAULT_TARGET_PROJECT_ID = "aa6e6e2c-c62d-43c6-88fe-56d75dff99e4";

let profileName = "Default";
let extensionInstanceId = "";
let nativePort = null;
let isNativeConnected = false;
let isHttpConnected = false;
let operationalStatus = "IDLE";

// Current Flow state cache
let flowTabState = {
  tabId: null,
  url: "",
  found: false,
  verified: false,
  mismatch: false,
  loading: false,
  authRequired: false,
  status: "FLOW_TAB_NOT_FOUND"
};

// 1. Initialize Profile Identity
function initIdentity() {
  chrome.storage.local.get(["profileName", "extensionInstanceId"], (data) => {
    if (data.profileName) {
      profileName = data.profileName;
    } else {
      profileName = "Profile-" + Math.floor(1000 + Math.random() * 9000);
      chrome.storage.local.set({ profileName: profileName });
    }

    if (data.extensionInstanceId) {
      extensionInstanceId = data.extensionInstanceId;
    } else {
      extensionInstanceId = "bridge-" + Math.random().toString(36).substring(2, 6).toUpperCase();
      chrome.storage.local.set({ extensionInstanceId: extensionInstanceId });
    }

    console.log(`[VEO3 Bridge] Identity initialized: ${profileName} (${extensionInstanceId})`);
    scanFlowTabs();
    connectNativeHost();
  });
}

// 2. Native Messaging Connection
function connectNativeHost() {
  try {
    console.log("[VEO3 Bridge] Attempting Native Messaging connection to", NATIVE_HOST_NAME);
    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

    nativePort.onMessage.addListener((msg) => {
      isNativeConnected = true;
      console.log("[VEO3 Bridge Native] Received message:", msg);
      if (msg && msg.command) {
        handleIncomingCommand(msg);
      }
    });

    nativePort.onDisconnect.addListener(() => {
      isNativeConnected = false;
      const err = chrome.runtime.lastError ? chrome.runtime.lastError.message : "Disconnected";
      console.log("[VEO3 Bridge Native] Disconnected:", err);
      nativePort = null;
      // Reconnect attempt after 5s
      setTimeout(connectNativeHost, 5000);
    });

    isNativeConnected = true;
    sendRegisterEvent();
  } catch (e) {
    isNativeConnected = false;
    console.warn("[VEO3 Bridge Native] Native host not available:", e);
  }
}

// 3. Fallback HTTP IPC Loop
async function pollHttpBridge() {
  try {
    const payload = {
      type: "HEARTBEAT",
      profileName: profileName,
      extensionInstanceId: extensionInstanceId,
      timestamp: new Date().toISOString(),
      flowStatus: flowTabState.status,
      flowTabId: flowTabState.tabId,
      flowUrl: flowTabState.url,
      projectVerified: flowTabState.verified
    };

    const res = await fetch(`${FALLBACK_HTTP_URL}/poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      isHttpConnected = true;
      const data = await res.json();
      if (data && data.command) {
        await handleIncomingCommand(data);
      }
    } else {
      isHttpConnected = false;
    }
  } catch (err) {
    isHttpConnected = false;
  }

  setTimeout(pollHttpBridge, 1500);
}

// 4. Send Message to Desktop App (via Native Messaging or HTTP)
function sendToDesktop(msg) {
  const enriched = {
    ...msg,
    profileName: profileName,
    extensionInstanceId: extensionInstanceId,
    timestamp: msg.timestamp || new Date().toISOString()
  };

  // 1. Try Native Messaging
  if (nativePort && isNativeConnected) {
    try {
      nativePort.postMessage(enriched);
    } catch (e) {
      isNativeConnected = false;
    }
  }

  // 2. Also send via HTTP report endpoint for redundancy
  fetch(`${FALLBACK_HTTP_URL}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(enriched)
  }).catch(() => {});
}

// 5. Registration & Heartbeat
function sendRegisterEvent() {
  sendToDesktop({
    type: "REGISTER",
    browser: "Chrome",
    status: "CONNECTED",
    flowStatus: flowTabState.status,
    flowTabId: flowTabState.tabId,
    flowUrl: flowTabState.url,
    projectVerified: flowTabState.verified,
    operationalStatus: operationalStatus
  });
}

function sendHeartbeat() {
  sendToDesktop({
    type: "HEARTBEAT",
    browser: "Chrome",
    status: "CONNECTED",
    flowStatus: flowTabState.status,
    flowTabId: flowTabState.tabId,
    flowUrl: flowTabState.url,
    projectVerified: flowTabState.verified,
    operationalStatus: operationalStatus
  });
}

// Periodic Heartbeat every 3s
setInterval(() => {
  scanFlowTabs().then(() => {
    sendHeartbeat();
  });
}, 3000);

// 6. Flow Tab Inspection & State Detection
async function scanFlowTabs() {
  try {
    const tabs = await chrome.tabs.query({});
    let targetProjectId = DEFAULT_TARGET_PROJECT_ID;

    // Find any tab with flow.google or labs.google
    const flowTabs = tabs.filter(t => t.url && (t.url.includes("flow.google") || t.url.includes("labs.google")));

    if (flowTabs.length === 0) {
      flowTabState = {
        tabId: null,
        url: "",
        found: false,
        verified: false,
        mismatch: false,
        loading: false,
        authRequired: false,
        status: "FLOW_TAB_NOT_FOUND"
      };
      return;
    }

    // Check for exact project match
    let exactTab = flowTabs.find(t => t.url && t.url.includes(targetProjectId));

    if (exactTab) {
      flowTabState.tabId = exactTab.id;
      flowTabState.url = exactTab.url;
      flowTabState.found = true;
      flowTabState.mismatch = false;

      // Ask content script for readiness
      try {
        const response = await chrome.tabs.sendMessage(exactTab.id, { action: "CHECK_READY" });
        if (response) {
          flowTabState.authRequired = !response.authenticated;
          flowTabState.loading = !response.isReady && !response.authenticated;
          flowTabState.verified = response.isReady && response.authenticated;
          if (flowTabState.authRequired) {
            flowTabState.status = "FLOW_AUTH_REQUIRED";
          } else if (flowTabState.loading) {
            flowTabState.status = "FLOW_LOADING";
          } else {
            flowTabState.status = "FLOW_READY";
          }
        } else {
          flowTabState.status = "FLOW_LOADING";
        }
      } catch (e) {
        flowTabState.status = "FLOW_LOADING";
      }
    } else {
      // Flow tab exists, but wrong project!
      const anyFlowTab = flowTabs[0];
      flowTabState.tabId = anyFlowTab.id;
      flowTabState.url = anyFlowTab.url;
      flowTabState.found = true;
      flowTabState.verified = false;
      flowTabState.mismatch = true;
      flowTabState.status = "FLOW_PROJECT_MISMATCH";
    }
  } catch (err) {
    console.error("[VEO3 Bridge] Error scanning Flow tabs:", err);
  }
}

// 7. Command Dispatcher & Handler
async function handleIncomingCommand(cmd) {
  const targetProf = cmd.targetProfile || "";
  const targetInst = cmd.extensionInstanceId || "";

  // Routing check: ONLY process if targeted to this profile or broadcast
  if (targetProf && targetProf !== "*" && targetProf.toLowerCase() !== profileName.toLowerCase()) {
    return;
  }
  if (targetInst && targetInst !== "*" && targetInst !== extensionInstanceId) {
    return;
  }

  console.log(`[VEO3 Bridge] Processing command '${cmd.command}' for ${profileName}`);
  const cmdName = cmd.command;
  const correlationId = cmd.correlationId || ("cmd-" + Date.now());
  const sceneNum = cmd.scene || 0;

  if (cmdName === "PING") {
    sendToDesktop({
      type: "PONG",
      correlationId: correlationId,
      status: "OK",
      timestamp: new Date().toISOString()
    });
    return;
  }

  if (cmdName === "GET_FLOW_STATUS" || cmdName === "CHECK_FLOW") {
    await scanFlowTabs();
    sendToDesktop({
      type: "FLOW_STATUS_REPORT",
      correlationId: correlationId,
      flowStatus: flowTabState.status,
      flowTabId: flowTabState.tabId,
      flowUrl: flowTabState.url,
      verified: flowTabState.verified,
      mismatch: flowTabState.mismatch
    });
    return;
  }

  if (cmdName === "ACTIVATE_FLOW_TAB") {
    if (flowTabState.tabId) {
      await chrome.tabs.update(flowTabState.tabId, { active: true });
      const tab = await chrome.tabs.get(flowTabState.tabId);
      if (tab.windowId) {
        await chrome.windows.update(tab.windowId, { focused: true });
      }
      sendToDesktop({
        type: "FLOW_TAB_ACTIVATED",
        correlationId: correlationId,
        flowTabId: flowTabState.tabId
      });
    }
    return;
  }

  if (cmdName === "UPLOAD_REFERENCE") {
    operationalStatus = "PROCESSING";
    sendToDesktop({
      type: "REFERENCE_UPLOAD_STARTED",
      scene: sceneNum,
      correlationId: correlationId,
      status: "running"
    });

    if (!flowTabState.tabId) {
      sendToDesktop({
        type: "FLOW_ERROR",
        scene: sceneNum,
        correlationId: correlationId,
        errorCode: "FLOW_TAB_NOT_FOUND",
        message: "No active Google Flow tab found in this profile."
      });
      operationalStatus = "IDLE";
      return;
    }

    try {
      const resp = await chrome.tabs.sendMessage(flowTabState.tabId, {
        action: "UPLOAD_REFERENCE",
        payload: {
          base64Data: cmd.base64Data,
          filename: cmd.filename
        }
      });
      if (resp && resp.success) {
        sendToDesktop({
          type: "REFERENCE_UPLOADED",
          scene: sceneNum,
          correlationId: correlationId,
          status: "success",
          message: resp.message
        });
      } else {
        sendToDesktop({
          type: "FLOW_ERROR",
          scene: sceneNum,
          correlationId: correlationId,
          errorCode: "REFERENCE_UPLOAD_FAILED",
          message: resp ? resp.error : "Failed to upload reference"
        });
      }
    } catch (e) {
      sendToDesktop({
        type: "FLOW_ERROR",
        scene: sceneNum,
        correlationId: correlationId,
        errorCode: "COMMUNICATION_ERROR",
        message: e.toString()
      });
    }
    operationalStatus = "IDLE";
    return;
  }

  if (cmdName === "ENTER_PROMPT" || cmdName === "SUBMIT_PROMPT") {
    operationalStatus = "PROCESSING";
    try {
      const resp = await chrome.tabs.sendMessage(flowTabState.tabId, {
        action: "SUBMIT_PROMPT",
        payload: { promptText: cmd.promptText }
      });
      if (resp && resp.success) {
        sendToDesktop({
          type: "PROMPT_ENTERED",
          scene: sceneNum,
          correlationId: correlationId,
          status: "success",
          message: resp.message
        });
      } else {
        sendToDesktop({
          type: "FLOW_ERROR",
          scene: sceneNum,
          correlationId: correlationId,
          errorCode: "PROMPT_ENTRY_FAILED",
          message: resp ? resp.error : "Failed to enter prompt"
        });
      }
    } catch (e) {
      sendToDesktop({
        type: "FLOW_ERROR",
        scene: sceneNum,
        correlationId: correlationId,
        errorCode: "COMMUNICATION_ERROR",
        message: e.toString()
      });
    }
    operationalStatus = "IDLE";
    return;
  }

  if (cmdName === "START_GENERATION" || cmdName === "TRIGGER_GENERATION") {
    operationalStatus = "PROCESSING";
    try {
      const resp = await chrome.tabs.sendMessage(flowTabState.tabId, { action: "TRIGGER_GENERATION" });
      if (resp && resp.success) {
        sendToDesktop({
          type: "GENERATION_STARTED",
          scene: sceneNum,
          correlationId: correlationId,
          status: "running",
          message: "Generation triggered successfully"
        });
      } else {
        sendToDesktop({
          type: "FLOW_ERROR",
          scene: sceneNum,
          correlationId: correlationId,
          errorCode: "GENERATION_TRIGGER_FAILED",
          message: resp ? resp.error : "Could not click generate button"
        });
      }
    } catch (e) {
      sendToDesktop({
        type: "FLOW_ERROR",
        scene: sceneNum,
        correlationId: correlationId,
        errorCode: "COMMUNICATION_ERROR",
        message: e.toString()
      });
    }
    return;
  }

  if (cmdName === "GET_GENERATION_STATUS" || cmdName === "CHECK_GENERATION_STATUS") {
    try {
      const resp = await chrome.tabs.sendMessage(flowTabState.tabId, { action: "CHECK_GENERATION_STATUS" });
      const statusVal = resp ? resp.status : "UNKNOWN";
      if (statusVal === "COMPLETED") {
        operationalStatus = "IDLE";
        sendToDesktop({
          type: "GENERATION_COMPLETE",
          scene: sceneNum,
          correlationId: correlationId,
          status: "complete",
          videoUrl: resp.videoUrl
        });
      } else if (statusVal === "ERROR") {
        operationalStatus = "IDLE";
        sendToDesktop({
          type: "GENERATION_FAILED",
          scene: sceneNum,
          correlationId: correlationId,
          errorCode: "GENERATION_SERVER_ERROR",
          message: resp.error
        });
      } else {
        sendToDesktop({
          type: "GENERATION_PROGRESS",
          scene: sceneNum,
          correlationId: correlationId,
          status: "running"
        });
      }
    } catch (e) {
      sendToDesktop({
        type: "FLOW_ERROR",
        scene: sceneNum,
        correlationId: correlationId,
        errorCode: "COMMUNICATION_ERROR",
        message: e.toString()
      });
    }
    return;
  }

  if (cmdName === "DOWNLOAD_RESULT" || cmdName === "DOWNLOAD_VIDEO") {
    operationalStatus = "PROCESSING";
    sendToDesktop({
      type: "DOWNLOAD_STARTED",
      scene: sceneNum,
      correlationId: correlationId,
      status: "downloading"
    });

    try {
      const resp = await chrome.tabs.sendMessage(flowTabState.tabId, { action: "GET_VIDEO_URL" });
      if (resp && resp.success && resp.url) {
        const vidResp = await fetch(resp.url);
        const vidBlob = await vidResp.blob();
        const reader = new FileReader();
        reader.onloadend = () => {
          sendToDesktop({
            type: "DOWNLOAD_COMPLETE",
            scene: sceneNum,
            correlationId: correlationId,
            status: "complete",
            videoDataUri: reader.result,
            url: resp.url
          });
          operationalStatus = "IDLE";
        };
        reader.readAsDataURL(vidBlob);
      } else {
        sendToDesktop({
          type: "DOWNLOAD_FAILED",
          scene: sceneNum,
          correlationId: correlationId,
          errorCode: "VIDEO_URL_NOT_FOUND",
          message: resp ? resp.error : "Could not find video URL in Flow UI"
        });
        operationalStatus = "IDLE";
      }
    } catch (e) {
      sendToDesktop({
        type: "DOWNLOAD_FAILED",
        scene: sceneNum,
        correlationId: correlationId,
        errorCode: "DOWNLOAD_STREAM_ERROR",
        message: e.toString()
      });
      operationalStatus = "IDLE";
    }
  }
}

// 8. Communication with Popup
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "GET_LIVE_STATUS") {
    sendResponse({
      profileName: profileName,
      extensionInstanceId: extensionInstanceId,
      appConnected: isNativeConnected || isHttpConnected,
      flowTabFound: flowTabState.found,
      projectVerified: flowTabState.verified,
      projectMismatch: flowTabState.mismatch,
      flowLoading: flowTabState.loading,
      flowTabId: flowTabState.tabId,
      operationalStatus: operationalStatus
    });
    return true;
  }

  if (req.action === "SET_PROFILE_NAME") {
    profileName = req.profileName;
    console.log(`[VEO3 Bridge] Profile name updated to: ${profileName}`);
    sendRegisterEvent();
    sendResponse({ success: true });
    return true;
  }

  if (req.action === "SCAN_FLOW_TABS") {
    scanFlowTabs().then(() => {
      sendResponse({ success: true, status: flowTabState.status });
    });
    return true;
  }

  return true;
});

// Start initialization
initIdentity();
pollHttpBridge();
