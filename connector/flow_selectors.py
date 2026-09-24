"""Selector definitions and semantic locators for Google Flow web interface."""

# Top level Google Flow navigation & login
URLS = [
    "https://flow.google",
    "https://labs.google/fx/tools/flow",
    "https://labs.google/flow"
]

# Selectors to detect sign-in status
LOGIN_BUTTON_SELECTORS = [
    'a[href*="accounts.google.com"]',
    'button:has-text("Sign in")',
    'button:has-text("Log in")',
    'a:has-text("Sign in")',
    'a:has-text("Get started")',
    'button[aria-label*="Sign in" i]'
]

AUTHENTICATED_SELECTORS = [
    'meta[name="og-profile-acct"]',
    '.flow-account-panel-overlay',
    'flow-tile-view-header',
    '.aisandbox-content',
    '.prompt-box-container',
    'img[src*="googleusercontent.com"]',
    'button[aria-label*="Google Account" i]',
    'button[aria-label*="Account Information" i]',
    'div[aria-label*="profile" i]',
    'header button[aria-haspopup="menu"]'
]

# Reference Image Upload Selectors
REFERENCE_UPLOAD_SELECTORS = [
    'input[type="file"][accept*="image"]',
    'input[type="file"]',
    '.prompt-box-container button:has(mat-icon:has-text("add"))',
    '.prompt-box-container button:has(mat-icon:has-text("image"))',
    '.prompt-box-container button.flow-icon-button-primary',
    'button[aria-label*="reference" i]',
    'button[aria-label*="add image" i]',
    'button[aria-label*="first frame" i]',
    'button:has-text("Add Reference")',
    'button:has-text("Upload Image")',
    '.flow-media-picker-dialog-panel input[type="file"]',
    '.drop-images-overlay',
    '[data-testid*="reference-upload"]'
]

# Reference Upload Confirmation Selectors (indicating image is loaded)
REFERENCE_PREVIEW_SELECTORS = [
    '.prompt-box-container img',
    'img[alt*="reference" i]',
    'img[alt*="uploaded" i]',
    '[data-testid*="reference-preview"]',
    '.reference-thumbnail',
    '.reference-preview',
    'div[aria-label*="reference image" i]'
]

# Prompt Input Field Selectors
PROMPT_INPUT_SELECTORS = [
    '.prompt-box-container textarea',
    '.prompt-box-container [contenteditable="true"]',
    '.prompt-box-container div[role="textbox"]',
    'textarea[placeholder*="prompt" i]',
    'textarea[placeholder*="Describe" i]',
    'textarea[aria-label*="prompt" i]',
    'div[contenteditable="true"][role="textbox"]',
    'textarea',
    'input[type="text"][placeholder*="prompt" i]'
]

# Generate Button Selectors
GENERATE_BUTTON_SELECTORS = [
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
]

# Generation In-Progress Indicators
GENERATING_INDICATORS = [
    'flow-loading-page',
    '.loading-page-fade-in',
    'flow-loading-page .text-container',
    '.tiles-container flow-loading-page',
    '.batch-container [role="progressbar"]',
    '[role="progressbar"]',
    'div:has-text("Generating...")',
    'div:has-text("Rendering...")',
    'div:has-text("Creating...")',
    'div:has-text("In queue")',
    '.generating-spinner',
    'svg[aria-label*="loading" i]'
]

# Video Result & Download Selectors
DOWNLOAD_BUTTON_SELECTORS = [
    'button.flow-icon-button-transparent:has(mat-icon:has-text("download"))',
    'button:has(mat-icon:has-text("download"))',
    '.batch-tiles-section button:has(mat-icon:has-text("download"))',
    '.tiles-container button:has(mat-icon:has-text("download"))',
    'button[aria-label*="Download" i]',
    'a[aria-label*="Download" i]',
    'button:has-text("Download")',
    'a[download]',
    'button[title*="Download" i]',
    '[data-testid*="download-button"]'
]

VIDEO_PLAYER_SELECTORS = [
    '.batch-tiles-section video',
    '.tiles-container video',
    'flow-video-player video',
    'video',
    'video[src]',
    '[data-testid*="video-player"]'
]

# Error or alert indicators
ERROR_INDICATORS = [
    '.error-tile',
    '.banner.error',
    '.banner.warning',
    'div[role="alert"]',
    '.flow-snackbar-panel:has-text("error")',
    '.flow-snackbar-panel:has-text("failed")'
]

