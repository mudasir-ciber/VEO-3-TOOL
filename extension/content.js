// Content Script for Google Flow page monitoring
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "CHECK_READY") {
    const isReady = checkFlowReady();
    const isAuthenticated = checkAuthenticated();
    sendResponse({
      isReady: isReady,
      authenticated: isAuthenticated,
      url: window.location.href
    });
  }
  return true;
});

function checkFlowReady() {
  // Check if Angular prompt box is rendered and visible
  const promptBox = document.querySelector(".prompt-box-container");
  const loadingPage = document.querySelector("flow-loading-page");

  // Loading page must not be actively displaying
  const isLoading = loadingPage && window.getComputedStyle(loadingPage).display !== "none" && window.getComputedStyle(loadingPage).opacity !== "0";

  if (promptBox && !isLoading) {
    return true;
  }

  // Alternative check: tile-view-header or content-container present
  const header = document.querySelector("flow-tile-view-header");
  const content = document.querySelector(".aisandbox-content");
  return Boolean(header && content && !isLoading);
}

function checkAuthenticated() {
  // If sign in button is present, not authenticated
  const signInBtn = document.querySelector('button:has-text("Sign in"), a[href*="accounts.google.com"]');
  if (signInBtn) return false;

  // If user profile picture or account panel exists
  const accountMeta = document.querySelector('meta[name="og-profile-acct"]');
  const userPic = document.querySelector('img[src*="googleusercontent.com"]');
  return Boolean(accountMeta || userPic || window.location.href.includes("flow.google.com"));
}
