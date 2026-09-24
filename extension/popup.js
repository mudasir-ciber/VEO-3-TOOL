// Popup controller for Chained Evolution Studio
document.addEventListener("DOMContentLoaded", () => {
  const btnOpenStudio = document.getElementById("btnOpenStudio");
  const btnOpenSidePanel = document.getElementById("btnOpenSidePanel");
  const btnOpenFlow = document.getElementById("btnOpenFlow");
  const btnRefresh = document.getElementById("btnRefresh");

  const elFlowStatus = document.getElementById("flowStatus");
  const elProjectStatus = document.getElementById("projectStatus");
  const elTabId = document.getElementById("tabId");
  const elProfileName = document.getElementById("profileName");

  // Open Studio Dashboard Tab
  btnOpenStudio.addEventListener("click", async () => {
    const studioUrl = chrome.runtime.getURL("studio.html");
    const tabs = await chrome.tabs.query({ url: studioUrl });
    if (tabs.length > 0) {
      await chrome.tabs.update(tabs[0].id, { active: true });
      const win = await chrome.windows.get(tabs[0].windowId);
      if (win) await chrome.windows.update(tabs[0].windowId, { focused: true });
    } else {
      await chrome.tabs.create({ url: studioUrl });
    }
    window.close();
  });

  // Open Side Panel
  btnOpenSidePanel.addEventListener("click", async () => {
    try {
      const win = await chrome.windows.getCurrent();
      await chrome.sidePanel.open({ windowId: win.id });
      window.close();
    } catch (e) {
      // Fallback to tab
      chrome.tabs.create({ url: chrome.runtime.getURL("studio.html") });
      window.close();
    }
  });

  // Open Flow
  btnOpenFlow.addEventListener("click", async () => {
    chrome.tabs.create({ url: "https://flow.google.com/project/aa6e6e2c-c62d-43c6-88fe-56d75dff99e4" });
    window.close();
  });

  btnRefresh.addEventListener("click", checkStatus);

  // Check Profile
  chrome.storage.local.get(["profileName"], (res) => {
    if (res.profileName) {
      elProfileName.textContent = res.profileName;
    }
  });

  checkStatus();

  async function checkStatus() {
    elFlowStatus.textContent = "CHECKING...";
    elFlowStatus.className = "val";

    try {
      const tabs = await chrome.tabs.query({});
      let foundTab = null;
      let mismatchTab = null;

      for (const tab of tabs) {
        if (!tab.url) continue;
        const u = tab.url.toLowerCase();
        if (u.includes("flow.google.com") || u.includes("labs.google.com/flow")) {
          if (u.includes("aa6e6e2c-c62d-43c6-88fe-56d75dff99e4")) {
            foundTab = tab;
            break;
          } else {
            mismatchTab = tab;
          }
        }
      }

      if (foundTab) {
        elFlowStatus.textContent = "CONNECTED ✓";
        elFlowStatus.className = "val green";
        elProjectStatus.textContent = "aa6e6e2c-c62d... ✓";
        elProjectStatus.className = "val green";
        elTabId.textContent = String(foundTab.id);
      } else if (mismatchTab) {
        elFlowStatus.textContent = "MISMATCH ⚠️";
        elFlowStatus.className = "val red";
        elProjectStatus.textContent = "Wrong Project ID";
        elProjectStatus.className = "val red";
        elTabId.textContent = String(mismatchTab.id);
      } else {
        elFlowStatus.textContent = "NOT OPEN ✗";
        elFlowStatus.className = "val red";
        elProjectStatus.textContent = "No Flow Tab";
        elProjectStatus.className = "val";
        elTabId.textContent = "None";
      }
    } catch (e) {
      elFlowStatus.textContent = "ERROR";
      elFlowStatus.className = "val red";
    }
  }
});
