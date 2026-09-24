// Background Service Worker for Chained Evolution Studio Bridge
const BRIDGE_URL = "http://127.0.0.1:18999";
let currentProfileName = "Default";
let isPolling = false;

// Load configured profile name from extension storage
chrome.storage.local.get(["profileName"], (res) => {
  if (res.profileName) {
    currentProfileName = res.profileName;
  }
});

// Setup Alarm Keepalive to prevent Manifest V3 service worker from terminating
chrome.alarms.create("bridge_keepalive", { periodInMinutes: 0.1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "bridge_keepalive") {
    triggerPoll();
  }
});

// Lifecycle wakeups
chrome.runtime.onStartup.addListener(triggerPoll);
chrome.runtime.onInstalled.addListener(triggerPoll);
chrome.tabs.onActivated.addListener(triggerPoll);
chrome.tabs.onUpdated.addListener(triggerPoll);

function triggerPoll() {
  if (!isPolling) {
    pollBridge();
  }
}

// Polling loop to communicate with Chained Evolution Studio
async function pollBridge() {
  isPolling = true;
  try {
    const response = await fetch(`${BRIDGE_URL}/poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profileName: currentProfileName,
        timestamp: Date.now()
      })
    });

    if (response.ok) {
      const data = await response.json();
      if (data && data.command) {
        await handleCommand(data);
      }
    }
  } catch (err) {
    // Desktop app may be idle or closed
  }

  // Next poll
  setTimeout(pollBridge, 1000);
}

// Find the active or matching Google Flow tab
async function getFlowTab() {
  const tabs = await chrome.tabs.query({});
  // Exact project first
  let tab = tabs.find(t => t.url && t.url.includes("flow.google.com/project"));
  if (!tab) {
    tab = tabs.find(t => t.url && (t.url.includes("flow.google.com") || t.url.includes("labs.google")));
  }
  return tab;
}

// Handle desktop commands
async function handleCommand(cmd) {
  console.log("[Bridge] Received command:", cmd);
  const cmdName = cmd.command;
  const expectedProfile = cmd.targetProfile || "";

  if (expectedProfile && expectedProfile !== currentProfileName) {
    currentProfileName = expectedProfile;
    chrome.storage.local.set({ profileName: expectedProfile });
  }

  if (cmdName === "OPEN_FLOW_PROJECT") {
    const targetUrl = cmd.url || "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4";
    const tabs = await chrome.tabs.query({});
    let targetTab = null;

    // Check if exact project tab exists
    const exactTab = tabs.find(t => t.url && t.url.includes("aa6e6e2c-c62d-43c6-88fe-56d75dff99e4"));
    if (exactTab) {
      console.log("[Bridge] Exact Flow project tab found:", exactTab.id);
      await chrome.tabs.update(exactTab.id, { active: true });
      if (exactTab.windowId) {
        await chrome.windows.update(exactTab.windowId, { focused: true });
      }
      targetTab = exactTab;
    } else {
      const flowTab = tabs.find(t => t.url && (t.url.includes("flow.google") || t.url.includes("labs.google/flow")));
      if (flowTab) {
        console.log("[Bridge] Navigating existing Flow tab to project:", flowTab.id);
        await chrome.tabs.update(flowTab.id, { url: targetUrl, active: true });
        if (flowTab.windowId) {
          await chrome.windows.update(flowTab.windowId, { focused: true });
        }
        targetTab = flowTab;
      } else {
        console.log("[Bridge] Opening new tab for Flow project");
        targetTab = await chrome.tabs.create({ url: targetUrl, active: true });
      }
    }

    await reportStatus({
      profileName: currentProfileName,
      command: cmdName,
      flowProjectOpened: true,
      tabId: targetTab ? targetTab.id : null,
      url: targetUrl,
      status: "NAVIGATING"
    });

  } else if (cmdName === "VERIFY_FLOW_PROJECT") {
    const targetTab = await getFlowTab();
    if (!targetTab) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        verified: false,
        reason: "FLOW_PROJECT_TAB_NOT_FOUND"
      });
      return;
    }

    try {
      const response = await chrome.tabs.sendMessage(targetTab.id, { action: "CHECK_READY" });
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        verified: response ? response.isReady : false,
        authenticated: response ? response.authenticated : false,
        url: targetTab.url,
        status: response && response.isReady ? "READY" : "LOADING"
      });
    } catch (e) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        verified: false,
        url: targetTab.url,
        status: "LOADING"
      });
    }

  } else if (cmdName === "UPLOAD_REFERENCE") {
    const targetTab = await getFlowTab();
    if (!targetTab) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: "Flow tab not found"
      });
      return;
    }

    try {
      const response = await chrome.tabs.sendMessage(targetTab.id, {
        action: "UPLOAD_REFERENCE",
        payload: {
          base64Data: cmd.base64Data,
          filename: cmd.filename
        }
      });
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: response ? response.success : false,
        message: response ? response.message : "",
        error: response ? response.error : "No response from tab"
      });
    } catch (e) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: e.toString()
      });
    }

  } else if (cmdName === "SUBMIT_PROMPT") {
    const targetTab = await getFlowTab();
    if (!targetTab) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: "Flow tab not found"
      });
      return;
    }

    try {
      const response = await chrome.tabs.sendMessage(targetTab.id, {
        action: "SUBMIT_PROMPT",
        payload: { promptText: cmd.promptText }
      });
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: response ? response.success : false,
        message: response ? response.message : "",
        error: response ? response.error : "No response from tab"
      });
    } catch (e) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: e.toString()
      });
    }

  } else if (cmdName === "TRIGGER_GENERATION") {
    const targetTab = await getFlowTab();
    if (!targetTab) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: "Flow tab not found"
      });
      return;
    }

    try {
      const response = await chrome.tabs.sendMessage(targetTab.id, { action: "TRIGGER_GENERATION" });
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: response ? response.success : false,
        message: response ? response.message : "",
        error: response ? response.error : "No response from tab"
      });
    } catch (e) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: e.toString()
      });
    }

  } else if (cmdName === "CHECK_GENERATION_STATUS") {
    const targetTab = await getFlowTab();
    if (!targetTab) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        status: "ERROR",
        error: "Flow tab not found"
      });
      return;
    }

    try {
      const response = await chrome.tabs.sendMessage(targetTab.id, { action: "CHECK_GENERATION_STATUS" });
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        status: response ? response.status : "IDLE",
        videoUrl: response ? response.videoUrl : "",
        error: response ? response.error : ""
      });
    } catch (e) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        status: "ERROR",
        error: e.toString()
      });
    }

  } else if (cmdName === "DOWNLOAD_VIDEO") {
    const targetTab = await getFlowTab();
    if (!targetTab) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: "Flow tab not found"
      });
      return;
    }

    try {
      const response = await chrome.tabs.sendMessage(targetTab.id, { action: "GET_VIDEO_URL" });
      if (response && response.success && response.url) {
        // Fetch the video content as base64 and return directly to desktop app
        const vidResp = await fetch(response.url);
        const vidBlob = await vidResp.blob();
        const reader = new FileReader();
        reader.onloadend = async () => {
          await reportStatus({
            profileName: currentProfileName,
            command: cmdName,
            success: true,
            videoDataUri: reader.result,
            url: response.url
          });
        };
        reader.readAsDataURL(vidBlob);
      } else {
        await reportStatus({
          profileName: currentProfileName,
          command: cmdName,
          success: false,
          error: response ? response.error : "Failed to locate video stream"
        });
      }
    } catch (e) {
      await reportStatus({
        profileName: currentProfileName,
        command: cmdName,
        success: false,
        error: e.toString()
      });
    }

  } else if (cmdName === "GET_PROFILE") {
    await reportStatus({
      profileName: currentProfileName,
      command: cmdName,
      status: "CONNECTED"
    });
  }
}

// Send reports back to desktop app
async function reportStatus(payload) {
  try {
    await fetch(`${BRIDGE_URL}/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (err) {
    console.error("[Bridge] Failed to send report to desktop app:", err);
  }
}

// Start polling
pollBridge();
