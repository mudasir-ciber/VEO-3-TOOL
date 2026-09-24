// Background Service Worker for Chained Evolution Studio Bridge
const BRIDGE_URL = "http://127.0.0.1:18999";
let currentProfileName = "Default";

// Load configured profile name from extension storage
chrome.storage.local.get(["profileName"], (res) => {
  if (res.profileName) {
    currentProfileName = res.profileName;
  }
});

// Polling loop to communicate with Chained Evolution Studio
async function pollBridge() {
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
    // Desktop app may be closed or polling idle
  }

  // Next poll
  setTimeout(pollBridge, 1000);
}

// Handle desktop commands
async function handleCommand(cmd) {
  console.log("[Bridge] Received command:", cmd);

  if (cmd.command === "OPEN_FLOW_PROJECT") {
    const targetUrl = cmd.url || "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4";
    const expectedProfile = cmd.targetProfile || "";

    // If expectedProfile specified and matches or set
    if (expectedProfile) {
      currentProfileName = expectedProfile;
      chrome.storage.local.set({ profileName: expectedProfile });
    }

    const tabs = await chrome.tabs.query({});
    let targetTab = null;

    // 1. Check if exact project tab already exists
    const exactTab = tabs.find(t => t.url && t.url.includes("aa6e6e2c-c62d-43c6-88fe-56d75dff99e4"));
    if (exactTab) {
      console.log("[Bridge] Exact Flow project tab found:", exactTab.id);
      await chrome.tabs.update(exactTab.id, { active: true });
      if (exactTab.windowId) {
        await chrome.windows.update(exactTab.windowId, { focused: true });
      }
      targetTab = exactTab;
    } else {
      // 2. Check if another Flow tab exists
      const flowTab = tabs.find(t => t.url && (t.url.includes("flow.google") || t.url.includes("labs.google/flow")));
      if (flowTab) {
        console.log("[Bridge] Navigating existing Flow tab to project:", flowTab.id);
        await chrome.tabs.update(flowTab.id, { url: targetUrl, active: true });
        if (flowTab.windowId) {
          await chrome.windows.update(flowTab.windowId, { focused: true });
        }
        targetTab = flowTab;
      } else {
        // 3. Create normal tab in the SAME Chrome profile
        console.log("[Bridge] Creating new tab for Flow project in current profile");
        targetTab = await chrome.tabs.create({ url: targetUrl, active: true });
      }
    }

    // Report back to desktop app
    await reportStatus({
      profileName: currentProfileName,
      flowProjectOpened: true,
      tabId: targetTab ? targetTab.id : null,
      url: targetUrl,
      status: "NAVIGATING"
    });
  } else if (cmd.command === "VERIFY_FLOW_PROJECT") {
    const expectedProjectId = "aa6e6e2c-c62d-43c6-88fe-56d75dff99e4";
    const tabs = await chrome.tabs.query({});
    const projectTab = tabs.find(t => t.url && t.url.includes(expectedProjectId));

    if (!projectTab) {
      await reportStatus({
        profileName: currentProfileName,
        verified: false,
        reason: "FLOW_PROJECT_TAB_NOT_FOUND"
      });
      return;
    }

    // Check tab readiness via message to content script
    try {
      const response = await chrome.tabs.sendMessage(projectTab.id, { action: "CHECK_READY" });
      await reportStatus({
        profileName: currentProfileName,
        verified: response ? response.isReady : false,
        authenticated: response ? response.authenticated : false,
        url: projectTab.url,
        status: response && response.isReady ? "READY" : "LOADING"
      });
    } catch (e) {
      // Content script may still be loading
      await reportStatus({
        profileName: currentProfileName,
        verified: false,
        url: projectTab.url,
        status: "LOADING"
      });
    }
  } else if (cmd.command === "GET_PROFILE") {
    await reportStatus({
      profileName: currentProfileName,
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
