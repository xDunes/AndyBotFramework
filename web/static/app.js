// Bot Web Remote - Main Application

// Theme handling - load theme before anything else to prevent flash
(function() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
})();

// Configuration
let appConfig = null;

// State
let selectedDevice = null;
let autoRefresh = true;
let refreshInterval = 1000; // milliseconds (1s default - more stable for remote connections)
let refreshTimer = null;
let screenshotDisplaySize = null;
let mouseDownPos = null;
let allBots = []; // Store all bots for mobile navigation
let touchStartX = 0;
let touchEndX = 0;
let touchStartY = 0;
let touchEndY = 0;

// WebSocket state
let socket = null;
let screenshotFPS = 5; // Default 5 FPS for live feed

// Preview screenshots state
let previewScreenshots = {}; // Map of device_name -> screenshot data
let selectedPreviews = new Set(); // Track selected preview devices

// Screenshot timestamp tracking to prevent older images overwriting newer ones
let currentScreenshotTimestamp = null; // Timestamp of currently displayed screenshot
let previewScreenshotTimestamps = {}; // Map of device_name -> timestamp

// Preview polling optimization - poll previews less frequently than main
let previewRefreshCounter = 0;
const PREVIEW_REFRESH_DIVISOR = 4; // Poll previews every 4th refresh cycle (4 seconds at 1000ms)

// Refresh state - prevent overlapping refreshes
let isRefreshing = false;
let consecutiveErrors = 0;
const MAX_CONSECUTIVE_ERRORS = 3;

// Function checkboxes configuration - will be loaded from config
let functionCheckboxes = [];

// Initialize application
async function init() {
    console.log('Bot Web Remote - Initializing...');

    // Initialize theme dropdown to match saved theme
    initializeTheme();

    // Load configuration first
    await loadConfig();

    // Set page title from config
    if (appConfig && appConfig.app_title) {
        document.title = appConfig.app_title;
        document.getElementById('pageTitle').textContent = appConfig.app_title;
    }

    // Initialize apply mode radio buttons to "current"
    initializeApplyMode();

    // Setup event listeners
    setupEventListeners();

    // Create function checkboxes
    createFunctionCheckboxes();

    // Create commands
    createCommands();

    // Create bot settings
    createBotSettings();

    // Setup screenshot canvas
    setupScreenshotCanvas();

    // Setup mobile swipe navigation
    setupMobileSwipeNavigation();

    // Initialize WebSocket connection
    initializeWebSocket();

    // Start auto-refresh
    startAutoRefresh();
}

// Initialize WebSocket connection for live updates
function initializeWebSocket() {
    console.log('Connecting to WebSocket...');

    // Connect to Socket.IO server
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
    });

    socket.on('connection_status', (data) => {
        console.log('Connection status:', data.status);
    });

    socket.on('screenshot_update', (data) => {
        const timestamp = data.timestamp;

        // Update main screenshot if this is the selected device (priority - always update)
        if (data.device_name === selectedDevice) {
            // Only update if this screenshot is newer than what we're displaying
            if (!currentScreenshotTimestamp || timestamp > currentScreenshotTimestamp) {
                currentScreenshotTimestamp = timestamp;
                updateScreenshotFromWebSocket(data.screenshot);
            }
        }

        // Update preview only if preview data is included (server throttles this)
        // Don't fall back to full screenshot - that defeats the bandwidth optimization
        if (data.preview && isAllModeActive() && data.device_name !== selectedDevice) {
            const prevTimestamp = previewScreenshotTimestamps[data.device_name];
            if (!prevTimestamp || timestamp > prevTimestamp) {
                previewScreenshotTimestamps[data.device_name] = timestamp;
                previewScreenshots[data.device_name] = data.preview;
                updatePreviewScreenshot(data.device_name, data.preview);
            }
        }
    });

    socket.on('fps_updated', (data) => {
        console.log(`Screenshot FPS updated to: ${data.fps}`);
        screenshotFPS = data.fps;
    });

    // Listen for real-time log updates
    socket.on('log_update', (data) => {
        // Only update if this log is for the currently selected device
        if (data.device_name === selectedDevice) {
            appendLogEntry(data.entry);
        }
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    // Could add a visual indicator in the UI if desired
    if (connected) {
        console.log('Live feed active');
    } else {
        console.log('Live feed disconnected, using polling fallback');
    }
}

// Check if we're on mobile viewport
function isMobileViewport() {
    return window.innerWidth <= 1024;
}

// Update screenshot from WebSocket data
function updateScreenshotFromWebSocket(screenshotData) {
    const canvas = document.getElementById('screenshotCanvas');
    const container = document.getElementById('screenshotContainer');
    const placeholder = container.querySelector('.screenshot-placeholder');

    const img = new Image();
    img.onload = () => {
        // Calculate display size (maintain 540:960 aspect ratio)
        const targetWidth = 540;
        const targetHeight = 960;
        let maxWidth = 400;
        let maxHeight = 600;

        // Scale down main screenshot when ALL mode is active on mobile
        if (isMobileViewport() && isAllModeActive()) {
            maxWidth = 320;  // 80% of 400
            maxHeight = 480; // 80% of 600
        }

        const scale = Math.min(maxWidth / targetWidth, maxHeight / targetHeight, 1.0);
        const displayWidth = Math.floor(targetWidth * scale);
        const displayHeight = Math.floor(targetHeight * scale);

        // Set canvas size
        canvas.width = displayWidth;
        canvas.height = displayHeight;
        screenshotDisplaySize = { width: displayWidth, height: displayHeight };

        // Draw image
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, displayWidth, displayHeight);

        // Show canvas, hide placeholder
        canvas.style.display = 'block';
        if (placeholder) placeholder.style.display = 'none';
    };
    img.src = screenshotData;
}

// Load configuration from server
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();

        if (data.success && data.config) {
            const config = data.config;
            appConfig = config; // Store full config

            // Build function checkboxes from layout, respecting row structure
            functionCheckboxes = [];

            if (config.function_layout) {
                // Find the maximum row length to ensure consistent grid display
                let maxRowLength = 0;
                for (const row of config.function_layout) {
                    if (row.length > maxRowLength) {
                        maxRowLength = row.length;
                    }
                }

                // Build checkbox list with empty placeholders to maintain row structure
                for (const row of config.function_layout) {
                    for (const funcName of row) {
                        // Create display name by removing "do" prefix
                        let displayName = funcName;
                        if (funcName.startsWith('do')) {
                            displayName = funcName.substring(2); // Remove "do" prefix
                        }
                        functionCheckboxes.push({ name: funcName, label: displayName });
                    }

                    // Add empty placeholders to fill the row to maxRowLength
                    const placeholdersNeeded = maxRowLength - row.length;
                    for (let i = 0; i < placeholdersNeeded; i++) {
                        functionCheckboxes.push({ name: `_placeholder_${functionCheckboxes.length}`, label: '', isPlaceholder: true });
                    }
                }
            }

            // Always add fix_enabled at the end
            functionCheckboxes.push({ name: 'fix_enabled', label: 'Fix/Recover', isSetting: true });

            console.log('Loaded function layout from config:', functionCheckboxes);
        } else {
            console.error('Failed to load config - function layout will be empty');
            functionCheckboxes = [
                { name: 'fix_enabled', label: 'Fix/Recover', isSetting: true }
            ];
        }
    } catch (error) {
        console.error('Error loading config:', error);
        functionCheckboxes = [
            { name: 'fix_enabled', label: 'Fix/Recover', isSetting: true }
        ];
    }
}

// Initialize apply mode to "current"
function initializeApplyMode() {
    // Get both sets of radio buttons
    const headerRadios = document.getElementsByName('applyModeHeader');
    const panelRadios = document.getElementsByName('applyModePanel');

    // Set current as default for both
    for (const radio of headerRadios) {
        if (radio.value === 'current') {
            radio.checked = true;
        }
    }
    for (const radio of panelRadios) {
        if (radio.value === 'current') {
            radio.checked = true;
        }
    }

    // Add event listeners to keep them in sync
    for (const radio of headerRadios) {
        radio.addEventListener('change', () => {
            if (radio.checked) {
                syncApplyMode('header', radio.value);
                updatePreviewsVisibility();
            }
        });
    }
    for (const radio of panelRadios) {
        radio.addEventListener('change', () => {
            if (radio.checked) {
                syncApplyMode('panel', radio.value);
                updatePreviewsVisibility();
            }
        });
    }
}

// Sync apply mode between header and panel
function syncApplyMode(source, value) {
    if (source === 'header') {
        const panelRadios = document.getElementsByName('applyModePanel');
        for (const radio of panelRadios) {
            if (radio.value === value) {
                radio.checked = true;
            }
        }
    } else {
        const headerRadios = document.getElementsByName('applyModeHeader');
        for (const radio of headerRadios) {
            if (radio.value === value) {
                radio.checked = true;
            }
        }
    }
}

// Check if ALL mode is active
function isAllModeActive() {
    const applyMode = getApplyMode();
    return applyMode === 'all';
}

// Update preview screenshots visibility based on apply mode
function updatePreviewsVisibility() {
    const previewsContainer = document.getElementById('screenshotPreviews');
    if (!previewsContainer) return;

    const wasVisible = previewsContainer.style.display !== 'none';

    if (isAllModeActive() && selectedDevice) {
        // Use grid for desktop (3 columns), flex for mobile (single row with horizontal scroll)
        previewsContainer.style.display = isMobileViewport() ? 'flex' : 'grid';

        // Only auto-select all previews when first activating ALL mode (not on every refresh)
        if (!wasVisible) {
            // Select all devices except the currently active one
            selectedPreviews.clear();
            allBots.forEach(bot => {
                if (bot.device_name !== selectedDevice) {
                    selectedPreviews.add(bot.device_name);
                }
            });
        }

        updatePreviewScreenshots();
    } else {
        previewsContainer.style.display = 'none';
        selectedPreviews.clear();
    }

    // Refresh main screenshot to apply scaling on mobile
    if (isMobileViewport() && selectedDevice) {
        updateScreenshot();
    }
}

// Update all preview screenshots
// Optional forceRefresh parameter to bypass the throttling (used when rebuilding)
function updatePreviewScreenshots(forceRefresh = false) {
    const previewsContainer = document.getElementById('screenshotPreviews');
    if (!previewsContainer || !selectedDevice) return;

    // Get ALL devices (include selected device for consistent positioning)
    const allDevices = allBots;

    // Get existing preview items
    const existingPreviews = Array.from(previewsContainer.children);
    const existingDeviceNames = existingPreviews.map(item => item.dataset.deviceName);
    const newDeviceNames = allDevices.map(bot => bot.device_name);

    // Check if the device list has changed
    const devicesChanged =
        existingDeviceNames.length !== newDeviceNames.length ||
        existingDeviceNames.some(name => !newDeviceNames.includes(name)) ||
        newDeviceNames.some(name => !existingDeviceNames.includes(name));

    if (devicesChanged) {
        // Device list changed - rebuild previews
        previewsContainer.innerHTML = '';

        allDevices.forEach(bot => {
            const previewItem = createPreviewItem(bot.device_name);
            previewsContainer.appendChild(previewItem);
            // Only load screenshot for non-selected devices
            if (bot.device_name !== selectedDevice) {
                loadPreviewScreenshot(bot.device_name);
            }
        });
    } else {
        // Update selected state for all previews (positions stay the same)
        updatePreviewSelectedStates();

        if (forceRefresh) {
            // Only fetch previews via HTTP when forced (throttled in refreshData)
            // WebSocket updates handle real-time preview updates
            allDevices.forEach(bot => {
                // Only load screenshot for non-selected devices
                if (bot.device_name !== selectedDevice) {
                    loadPreviewScreenshot(bot.device_name);
                }
            });
        }
    }
    // When not forced and no device changes, rely on WebSocket for updates
}

// Update the selected/active state of all preview items
function updatePreviewSelectedStates() {
    allBots.forEach(bot => {
        const previewItem = document.getElementById(`preview-${bot.device_name}`);
        if (!previewItem) return;

        const canvas = previewItem.querySelector('.screenshot-preview-canvas');
        const placeholder = previewItem.querySelector('.screenshot-preview-placeholder');

        if (bot.device_name === selectedDevice) {
            // Currently selected device - show as active/blank
            previewItem.classList.add('active-device');
            previewItem.classList.remove('selected');
            if (canvas) canvas.style.display = 'none';
            if (placeholder) {
                placeholder.textContent = 'Active';
                placeholder.style.display = 'block';
            }
        } else {
            // Other devices - show screenshot
            previewItem.classList.remove('active-device');
            // Update selected state based on selectedPreviews set
            if (selectedPreviews.has(bot.device_name)) {
                previewItem.classList.add('selected');
            } else {
                previewItem.classList.remove('selected');
            }
            // Restore screenshot if we have cached data
            if (previewScreenshots[bot.device_name]) {
                if (canvas) canvas.style.display = 'block';
                if (placeholder) placeholder.style.display = 'none';
            }
        }
    });
}

// Create a preview item element
function createPreviewItem(deviceName) {
    const previewItem = document.createElement('div');
    previewItem.className = 'screenshot-preview-item';
    previewItem.dataset.deviceName = deviceName;
    previewItem.id = `preview-${deviceName}`;

    // Add selected class if this device is in selectedPreviews
    if (selectedPreviews.has(deviceName)) {
        previewItem.classList.add('selected');
    }

    // Check if this is the currently active/selected device
    const isActiveDevice = deviceName === selectedDevice;
    if (isActiveDevice) {
        previewItem.classList.add('active-device');
    }

    // Add label
    const label = document.createElement('div');
    label.className = 'screenshot-preview-label';
    label.textContent = deviceName;
    previewItem.appendChild(label);

    // Add canvas
    const canvas = document.createElement('canvas');
    canvas.className = 'screenshot-preview-canvas';
    canvas.id = `preview-canvas-${deviceName}`;
    // Hide canvas for active device
    if (isActiveDevice) {
        canvas.style.display = 'none';
    }
    previewItem.appendChild(canvas);

    // Add placeholder
    const placeholder = document.createElement('div');
    placeholder.className = 'screenshot-preview-placeholder';
    placeholder.textContent = isActiveDevice ? 'Active' : 'Loading...';
    placeholder.style.display = 'block';
    previewItem.appendChild(placeholder);

    // Add click handler to toggle selection (desktop)
    previewItem.addEventListener('click', (e) => {
        e.stopPropagation();
        togglePreviewSelection(deviceName);
    });

    // Add touch handler for mobile
    previewItem.addEventListener('touchend', (e) => {
        e.preventDefault();
        e.stopPropagation();
        togglePreviewSelection(deviceName);
    });

    return previewItem;
}

// Toggle preview selection
function togglePreviewSelection(deviceName) {
    // Don't allow toggling the active device
    if (deviceName === selectedDevice) return;

    const previewItem = document.getElementById(`preview-${deviceName}`);
    if (!previewItem) return;

    if (selectedPreviews.has(deviceName)) {
        // Deselect
        selectedPreviews.delete(deviceName);
        previewItem.classList.remove('selected');
        console.log(`Deselected preview: ${deviceName}. Selected count: ${selectedPreviews.size}`);
    } else {
        // Select
        selectedPreviews.add(deviceName);
        previewItem.classList.add('selected');
        console.log(`Selected preview: ${deviceName}. Selected count: ${selectedPreviews.size}`);
    }
}

// Load screenshot for a preview device
async function loadPreviewScreenshot(deviceName) {
    try {
        // Use size=preview for smaller, compressed thumbnails (85x150 JPEG)
        const response = await fetch(`/api/bots/${deviceName}/screenshot?size=preview`);
        const data = await response.json();

        if (data.success && data.screenshot) {
            const timestamp = data.timestamp;

            // Only update if this screenshot is newer than what we have
            const prevTimestamp = previewScreenshotTimestamps[deviceName];
            if (prevTimestamp && timestamp && timestamp <= prevTimestamp) {
                // Skip - we already have a newer screenshot
                return;
            }

            if (timestamp) {
                previewScreenshotTimestamps[deviceName] = timestamp;
            }
            previewScreenshots[deviceName] = data.screenshot;
            updatePreviewScreenshot(deviceName, data.screenshot);
        }
    } catch (error) {
        console.error(`Error loading preview screenshot for ${deviceName}:`, error);
    }
}

// Update a single preview screenshot
function updatePreviewScreenshot(deviceName, screenshotData) {
    const canvas = document.getElementById(`preview-canvas-${deviceName}`);
    const previewItem = document.getElementById(`preview-${deviceName}`);

    if (!canvas || !previewItem) return;

    const placeholder = previewItem.querySelector('.screenshot-preview-placeholder');

    const img = new Image();
    img.onload = () => {
        // Calculate scaled size for preview (maintain 540:960 aspect ratio)
        const targetWidth = 540;
        const targetHeight = 960;
        let maxWidth = 85;
        let maxHeight = 150;

        // Smaller previews on mobile for single row layout
        if (isMobileViewport()) {
            maxWidth = 50;
            maxHeight = 89;
        }

        const scale = Math.min(maxWidth / targetWidth, maxHeight / targetHeight);
        const displayWidth = Math.floor(targetWidth * scale);
        const displayHeight = Math.floor(targetHeight * scale);

        // Set canvas size
        canvas.width = displayWidth;
        canvas.height = displayHeight;

        // Draw image
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, displayWidth, displayHeight);

        // Show canvas, hide placeholder
        canvas.style.display = 'block';
        if (placeholder) placeholder.style.display = 'none';
    };
    img.src = screenshotData;
}

// Setup event listeners
function setupEventListeners() {
    // Settings toggle button
    document.getElementById('settingsToggle').addEventListener('click', () => {
        const panel = document.getElementById('settingsPanel');
        const toggle = document.getElementById('settingsToggle');
        if (panel.style.display === 'none') {
            panel.style.display = 'flex';
            toggle.classList.add('active');
        } else {
            panel.style.display = 'none';
            toggle.classList.remove('active');
        }
    });

    // Auto-refresh toggle
    document.getElementById('autoRefresh').addEventListener('change', (e) => {
        autoRefresh = e.target.checked;
        if (autoRefresh) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });

    // Set interval button
    document.getElementById('setInterval').addEventListener('click', () => {
        const value = parseFloat(document.getElementById('refreshInterval').value);
        if (value > 0) {
            refreshInterval = value * 1000; // Convert to milliseconds
            console.log(`Refresh interval set to ${value}s (${refreshInterval}ms)`);
            if (autoRefresh) {
                stopAutoRefresh();
                startAutoRefresh();
            }
        }
    });

    // Handle window resize to update preview layout
    window.addEventListener('resize', () => {
        if (isAllModeActive() && selectedDevice) {
            updatePreviewsVisibility();
        }
    });
}

// Create commands dynamically from config
function createCommands() {
    const container = document.getElementById('commandsGrid');
    if (!container || !appConfig || !appConfig.commands) return;

    container.innerHTML = ''; // Clear existing

    appConfig.commands.forEach(command => {
        // Skip start_stop - it's now in the Bot section
        if (command.id === 'start_stop') {
            return;
        }

        const button = document.createElement('button');
        button.className = 'btn btn-sm command-btn';
        button.textContent = command.label;

        button.onclick = () => sendCommand(command.id);
        container.appendChild(button);
    });
}

// Create bot settings dynamically from config
function createBotSettings() {
    const container = document.getElementById('botSettings');
    if (!container || !appConfig || !appConfig.bot_settings) return;

    // Find the debug checkbox and keep it
    const debugCheckbox = container.querySelector('.setting-row');
    container.innerHTML = ''; // Clear existing

    // Add configured settings
    appConfig.bot_settings.forEach(setting => {
        const row = document.createElement('div');
        row.className = 'setting-row';

        const label = document.createElement('label');
        label.setAttribute('for', setting.id);
        label.textContent = setting.label + ':';
        row.appendChild(label);

        const input = document.createElement('input');
        input.type = setting.type;
        input.id = setting.id;
        input.value = setting.default;

        if (setting.min !== undefined) input.min = setting.min;
        if (setting.step !== undefined) input.step = setting.step;

        row.appendChild(input);

        const button = document.createElement('button');
        button.className = 'btn btn-sm';
        button.textContent = 'Set';
        button.onclick = () => sendSetting(setting.id);
        row.appendChild(button);

        container.appendChild(row);
    });

    // Re-add debug checkbox at the end
    if (debugCheckbox) {
        container.appendChild(debugCheckbox);
    }
}

// Create function checkboxes dynamically
function createFunctionCheckboxes() {
    const container = document.getElementById('functionControls');
    container.innerHTML = ''; // Clear existing

    if (!appConfig || !appConfig.function_layout) return;

    // Create rows based on function_layout from config
    appConfig.function_layout.forEach(rowFunctions => {
        const row = document.createElement('div');
        row.className = 'checkbox-grid-row';

        rowFunctions.forEach(funcName => {
            const label = document.createElement('label');
            label.className = 'checkbox-label';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.id = funcName;
            input.addEventListener('change', () => sendCheckboxCommand(funcName));

            const span = document.createElement('span');
            // Create display name by removing "do" prefix
            let displayName = funcName;
            if (funcName.startsWith('do')) {
                displayName = funcName.substring(2); // Remove "do" prefix
            }
            span.textContent = displayName;

            label.appendChild(input);
            label.appendChild(span);
            row.appendChild(label);
        });

        container.appendChild(row);
    });

    // Add fix_enabled checkbox at the end (if it exists in functionCheckboxes)
    const fixCheckbox = functionCheckboxes.find(cb => cb.isSetting && cb.name === 'fix_enabled');
    if (fixCheckbox) {
        const row = document.createElement('div');
        row.className = 'checkbox-grid-row';

        const label = document.createElement('label');
        label.className = 'checkbox-label';

        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = 'fix_enabled';
        input.addEventListener('change', () => sendSetting('fix_enabled'));

        const span = document.createElement('span');
        span.textContent = fixCheckbox.label;

        label.appendChild(input);
        label.appendChild(span);
        row.appendChild(label);

        container.appendChild(row);
    }
}

// Auto-refresh control
function startAutoRefresh() {
    refreshData();
    refreshTimer = setInterval(refreshData, refreshInterval);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Format elapsed time
function formatElapsedTime(seconds) {
    if (seconds < 60) {
        return `${Math.floor(seconds)}s`;
    } else if (seconds < 3600) {
        return `${Math.floor(seconds / 60)}m`;
    } else {
        return `${Math.floor(seconds / 3600)}h`;
    }
}

// Helper function to fetch with timeout
async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        throw error;
    }
}

// Refresh all data
async function refreshData() {
    // Prevent overlapping refreshes
    if (isRefreshing) {
        return;
    }
    isRefreshing = true;

    try {
        // Increment preview refresh counter
        previewRefreshCounter++;

        // Fetch stats and bots in parallel with timeout
        const [statsResponse, botsResponse] = await Promise.all([
            fetchWithTimeout('/api/stats', {}, 8000),
            fetchWithTimeout('/api/bots', {}, 8000)
        ]);

        const [statsData, botsData] = await Promise.all([
            statsResponse.json(),
            botsResponse.json()
        ]);

        // Reset error counter on success
        consecutiveErrors = 0;

        if (statsData.success) {
            updateStats(statsData.stats);
        } else {
            console.error('Stats API error:', statsData.error);
        }

        if (botsData.success) {
            updateDeviceList(botsData.bots);

            // Update function tooltips with device info
            updateFunctionTooltips();

            // Auto-select first device if none selected
            if (!selectedDevice && botsData.bots.length > 0) {
                selectDevice(botsData.bots[0].device_name);
            }
        } else {
            console.error('Bots API error:', botsData.error);
        }

        // Refresh selected device details
        if (selectedDevice) {
            // Determine if we should force refresh previews this cycle
            // Previews are polled less frequently to save bandwidth
            const shouldRefreshPreviews = (previewRefreshCounter % PREVIEW_REFRESH_DIVISOR) === 0;
            await refreshDeviceDetails(shouldRefreshPreviews);
        }
    } catch (error) {
        consecutiveErrors++;
        console.error(`Error refreshing data (${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}):`, error.message);

        // Only show error in UI after multiple consecutive failures
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            const deviceList = document.getElementById('deviceList');
            if (deviceList && allBots.length === 0) {
                deviceList.innerHTML = `<div class="loading" style="color: orange;">Connection unstable - retrying...</div>`;
            }
        }
    } finally {
        isRefreshing = false;
    }
}

// Update stats display
function updateStats(stats) {
    const statsText = document.getElementById('statsText');
    statsText.innerHTML = `
        <strong>Total Bots:</strong> ${stats.total_bots}<br>
        <strong>Running:</strong> ${stats.running_bots}<br>
        <strong>Stopped:</strong> ${stats.stopped_bots}<br>
        <strong>Database Size:</strong> ${stats.db_size_mb} MB
    `;
}

// Update device list
function updateDeviceList(bots) {
    const deviceList = document.getElementById('deviceList');

    // Store bots for mobile navigation
    allBots = bots;

    if (bots.length === 0) {
        deviceList.innerHTML = '<div class="loading">No bot instances found</div>';
        return;
    }

    // Get existing device items
    const existingItems = {};
    Array.from(deviceList.children).forEach(item => {
        const deviceName = item.querySelector('.device-name')?.textContent;
        if (deviceName) {
            existingItems[deviceName] = item;
        }
    });

    // Create a map of bot names for quick lookup
    const botMap = {};
    bots.forEach(bot => {
        botMap[bot.device_name] = bot;
    });

    // Check if the device list structure has changed
    const currentDeviceNames = Object.keys(existingItems);
    const newDeviceNames = bots.map(b => b.device_name);
    const hasStructureChanged =
        currentDeviceNames.length !== newDeviceNames.length ||
        currentDeviceNames.some(name => !botMap[name]) ||
        newDeviceNames.some(name => !existingItems[name]);

    if (hasStructureChanged) {
        // Rebuild the list only if devices were added/removed
        deviceList.innerHTML = '';
        bots.forEach(bot => {
            const deviceItem = document.createElement('div');
            deviceItem.className = 'device-item';

            const deviceName = document.createElement('span');
            deviceName.className = 'device-name';
            deviceName.textContent = bot.device_name;

            const deviceStatus = document.createElement('div');
            deviceStatus.className = 'device-status';

            deviceItem.appendChild(deviceName);
            deviceItem.appendChild(deviceStatus);
            deviceItem.addEventListener('click', () => selectDevice(bot.device_name));

            deviceList.appendChild(deviceItem);
        });
    }

    // Update only the content and classes of existing items
    Array.from(deviceList.children).forEach((deviceItem, index) => {
        const bot = bots[index];
        if (!bot) return;

        // Build the class list
        const classes = ['device-item'];
        if (bot.is_running) {
            if (bot.elapsed_seconds && bot.elapsed_seconds > 30) {
                classes.push('stale');
            } else {
                classes.push('running');
            }
        } else {
            classes.push('stopped');
        }
        if (selectedDevice === bot.device_name) {
            classes.push('selected');
        }

        // Only update className if it changed
        const newClassName = classes.join(' ');
        if (deviceItem.className !== newClassName) {
            deviceItem.className = newClassName;
        }

        // Update status text - just show elapsed time
        const deviceStatus = deviceItem.querySelector('.device-status');
        const timeStr = bot.elapsed_seconds !== null ? formatElapsedTime(bot.elapsed_seconds) : '?';
        if (deviceStatus.textContent !== timeStr) {
            deviceStatus.textContent = timeStr;
        }
    });
}

// Select a device
function selectDevice(deviceName) {
    selectedDevice = deviceName;
    // Reset timestamp when switching devices so we accept the first screenshot
    currentScreenshotTimestamp = null;

    // Immediately update visual selection (don't wait for next refresh cycle)
    const deviceList = document.getElementById('deviceList');
    if (deviceList) {
        Array.from(deviceList.children).forEach(item => {
            const nameEl = item.querySelector('.device-name');
            if (nameEl) {
                if (nameEl.textContent === deviceName) {
                    item.classList.add('selected');
                } else {
                    item.classList.remove('selected');
                }
            }
        });
    }

    updateCurrentDeviceDisplay();

    // If ALL mode is active, update preview states (keep positions, just update active indicator)
    if (isAllModeActive()) {
        // Remove selected device from selectedPreviews, add it back to others
        selectedPreviews.delete(deviceName);
        // Add all other devices that aren't already selected
        allBots.forEach(bot => {
            if (bot.device_name !== deviceName && !selectedPreviews.has(bot.device_name)) {
                selectedPreviews.add(bot.device_name);
            }
        });
        console.log(`Active device changed to ${deviceName}. Selected count: ${selectedPreviews.size}`);
        // Update visual states without rebuilding
        updatePreviewSelectedStates();
    }

    updatePreviewsVisibility();

    // Fetch device details async (don't block selection)
    refreshDeviceDetails();
}

// Update current device display in header
function updateCurrentDeviceDisplay() {
    const currentDeviceNameEl = document.getElementById('currentDeviceName');
    const statusIndicator = document.getElementById('statusIndicator');

    // Find the bot in allBots to get its status
    const bot = allBots.find(b => b.device_name === selectedDevice);
    if (bot) {
        // Show device name with LD/Bot status indicators
        const ldIndicator = bot.ld_running ? '🟢' : '🔴';
        const botIndicator = bot.is_running ? '🟢' : '🔴';
        currentDeviceNameEl.innerHTML = `${selectedDevice} <span style="font-size: 0.8em;">LD${ldIndicator} Bot${botIndicator}</span>`;

        // Main status indicator shows bot running state (for backward compatibility)
        statusIndicator.className = 'status-indicator';
        if (bot.is_running) {
            if (bot.elapsed_seconds && bot.elapsed_seconds > 30) {
                statusIndicator.classList.add('stale');
            } else {
                statusIndicator.classList.add('running');
            }
        } else {
            statusIndicator.classList.add('stopped');
        }
    } else {
        currentDeviceNameEl.textContent = selectedDevice || 'Loading...';
    }
}

// Refresh device details
// refreshPreviews: if true, also refresh preview screenshots via HTTP (throttled)
async function refreshDeviceDetails(refreshPreviews = false) {
    if (!selectedDevice) return;

    try {
        // Fetch device state
        const response = await fetch(`/api/bots/${selectedDevice}`);
        const data = await response.json();

        if (!data.success) {
            console.error('Failed to fetch device state:', data.error);
            return;
        }

        const state = data.state;

        // Update status info
        updateStatusInfo(state);

        // Update control panel
        updateControlPanel(state);

        // Log updates are now handled via WebSocket in real-time
        // Only use REST API log on initial load (when log is empty/placeholder)
        const logElement = document.getElementById('logText');
        if (logElement && (logElement.textContent === 'No log entries' || logElement.textContent === '')) {
            updateLog(state.current_log);
        }

        // Update main screenshot (always at full rate)
        await updateScreenshot();

        // Update preview screenshots only when requested (throttled)
        // WebSocket handles real-time updates; HTTP polling is a fallback
        if (refreshPreviews && isAllModeActive()) {
            updatePreviewScreenshots(true);
        }

    } catch (error) {
        console.error('Error refreshing device details:', error);
    }
}

// Update status info
function updateStatusInfo(state) {
    const headerStatusInfo = document.getElementById('headerStatusInfo');

    const ldStatus = state.ld_running ? '<span style="color: green;">Running</span>' : '<span style="color: red;">Stopped</span>';
    const botStatus = state.is_running ? '<span style="color: green;">Running</span>' : '<span style="color: red;">Stopped</span>';
    const startTime = state.start_time;
    const lastUpdate = state.last_update;
    const endTime = state.end_time || 'N/A';
    const uptime = state.uptime_seconds ? formatElapsedTime(state.uptime_seconds) : 'N/A';

    headerStatusInfo.innerHTML = `
        <strong>Device:</strong> ${state.device_name}<br>
        <strong>LDPlayer:</strong> ${ldStatus}<br>
        <strong>Bot:</strong> ${botStatus}<br>
        <strong>Started:</strong> ${startTime}<br>
        <strong>Last Update:</strong> ${lastUpdate}<br>
        <strong>Stopped:</strong> ${endTime}<br>
        <strong>Uptime:</strong> ${uptime}
    `;

    // Update header device display
    updateCurrentDeviceDisplay();
}

// Update control panel
function updateControlPanel(state) {
    // Update function checkboxes based on function_layout
    if (appConfig && appConfig.function_layout) {
        appConfig.function_layout.forEach(rowFunctions => {
            rowFunctions.forEach(funcName => {
                const input = document.getElementById(funcName);
                if (input && funcName in state) {
                    input.checked = Boolean(state[funcName]);
                }
            });
        });
    }

    // Update fix_enabled if it exists
    const fixEnabledInput = document.getElementById('fix_enabled');
    if (fixEnabledInput && 'fix_enabled' in state) {
        fixEnabledInput.checked = Boolean(state.fix_enabled);
    }

    // Update dynamic bot settings
    if (appConfig && appConfig.bot_settings) {
        appConfig.bot_settings.forEach(setting => {
            const element = document.getElementById(setting.id);
            if (element && setting.id in state) {
                element.value = state[setting.id] || setting.default;
            }
        });
    }

    // Update debug checkboxes (both in Settings and Bot section)
    const debugElement = document.getElementById('debugEnabled');
    if (debugElement) {
        debugElement.checked = Boolean(state.debug_enabled);
    }
    const botDebugElement = document.getElementById('botDebugEnabled');
    if (botDebugElement) {
        botDebugElement.checked = Boolean(state.debug_enabled);
    }

}

// Update function checkbox tooltips to show which devices have each function enabled
function updateFunctionTooltips() {
    if (!appConfig || !appConfig.function_layout) return;

    appConfig.function_layout.forEach(rowFunctions => {
        rowFunctions.forEach(funcName => {
            const label = document.querySelector(`label[for="${funcName}"]`) ||
                          document.querySelector(`label:has(#${funcName})`);
            if (!label) return;

            // Find all devices that have this function enabled
            const enabledDevices = allBots
                .filter(bot => bot[funcName] === 1 || bot[funcName] === true)
                .map(bot => bot.device_name);

            if (enabledDevices.length > 0) {
                label.title = `Enabled on: ${enabledDevices.join(', ')}`;
            } else {
                label.title = 'Not enabled on any device';
            }
        });
    });
}

// Update log (full replacement from API)
function updateLog(logText) {
    const logElement = document.getElementById('logText');
    const logContainer = document.getElementById('logContainer');
    logElement.textContent = logText || 'No log entries';
    // Auto-scroll to bottom (scroll the container, not the pre element)
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

// Append a single log entry (from WebSocket)
function appendLogEntry(entry) {
    const logElement = document.getElementById('logText');
    const logContainer = document.getElementById('logContainer');
    if (!logElement) return;

    const MAX_LOG_LINES = 100;

    // If log is empty or just placeholder, replace it
    if (logElement.textContent === 'No log entries' || logElement.textContent === '') {
        logElement.textContent = entry;
    } else {
        // Append new entry
        logElement.textContent += '\n' + entry;

        // Trim old lines if exceeding max
        const lines = logElement.textContent.split('\n');
        if (lines.length > MAX_LOG_LINES) {
            logElement.textContent = lines.slice(-MAX_LOG_LINES).join('\n');
        }
    }

    // Auto-scroll to bottom (scroll the container, not the pre element)
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

// Update screenshot
async function updateScreenshot() {
    if (!selectedDevice) return;

    try {
        const response = await fetch(`/api/bots/${selectedDevice}/screenshot`);
        const data = await response.json();

        const canvas = document.getElementById('screenshotCanvas');
        const container = document.getElementById('screenshotContainer');
        const placeholder = container.querySelector('.screenshot-placeholder');

        if (data.success && data.screenshot) {
            const timestamp = data.timestamp;

            // Only update if this screenshot is newer than what we're displaying
            // This prevents older HTTP responses from overwriting newer WebSocket updates
            if (currentScreenshotTimestamp && timestamp && timestamp <= currentScreenshotTimestamp) {
                // Skip this update - we already have a newer screenshot
                return;
            }

            // Update the timestamp tracker
            if (timestamp) {
                currentScreenshotTimestamp = timestamp;
            }

            const img = new Image();
            img.onload = () => {
                // Calculate display size (maintain 540:960 aspect ratio)
                const targetWidth = 540;
                const targetHeight = 960;
                let maxWidth = 400;
                let maxHeight = 600;

                // Scale down main screenshot when ALL mode is active on mobile
                if (isMobileViewport() && isAllModeActive()) {
                    maxWidth = 320;  // 80% of 400
                    maxHeight = 480; // 80% of 600
                }

                const scale = Math.min(maxWidth / targetWidth, maxHeight / targetHeight, 1.0);
                const displayWidth = Math.floor(targetWidth * scale);
                const displayHeight = Math.floor(targetHeight * scale);

                // Set canvas size
                canvas.width = displayWidth;
                canvas.height = displayHeight;
                screenshotDisplaySize = { width: displayWidth, height: displayHeight };

                // Draw image
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, displayWidth, displayHeight);

                // Show canvas, hide placeholder
                canvas.style.display = 'block';
                if (placeholder) placeholder.style.display = 'none';
            };
            img.src = data.screenshot;
        } else {
            // Show placeholder, hide canvas
            canvas.style.display = 'none';
            if (placeholder) {
                placeholder.style.display = 'block';
                placeholder.textContent = 'No screenshot available';
            }
        }
    } catch (error) {
        console.error('Error updating screenshot:', error);
    }
}

// Setup screenshot canvas for click/drag
function setupScreenshotCanvas() {
    const canvas = document.getElementById('screenshotCanvas');

    canvas.addEventListener('mousedown', (e) => {
        const rect = canvas.getBoundingClientRect();
        mouseDownPos = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
            timestamp: Date.now()
        };
    });

    canvas.addEventListener('mouseup', (e) => {
        if (!mouseDownPos || !screenshotDisplaySize) return;

        const rect = canvas.getBoundingClientRect();
        const mouseUpPos = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
            timestamp: Date.now()
        };

        handleScreenshotInteraction(mouseDownPos, mouseUpPos);
        mouseDownPos = null;
    });

    // Touch support for mobile
    canvas.addEventListener('touchstart', (e) => {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const touch = e.touches[0];
        mouseDownPos = {
            x: touch.clientX - rect.left,
            y: touch.clientY - rect.top,
            timestamp: Date.now()
        };
    });

    canvas.addEventListener('touchend', (e) => {
        e.preventDefault();
        if (!mouseDownPos || !screenshotDisplaySize) return;

        const rect = canvas.getBoundingClientRect();
        const touch = e.changedTouches[0];
        const mouseUpPos = {
            x: touch.clientX - rect.left,
            y: touch.clientY - rect.top,
            timestamp: Date.now()
        };

        handleScreenshotInteraction(mouseDownPos, mouseUpPos);
        mouseDownPos = null;
    });
}

// Handle screenshot click/drag interaction
function handleScreenshotInteraction(downPos, upPos) {
    // Device resolution (always 540x960)
    const deviceWidth = 540;
    const deviceHeight = 960;

    // Calculate scale
    const scaleX = deviceWidth / screenshotDisplaySize.width;
    const scaleY = deviceHeight / screenshotDisplaySize.height;

    // Convert to device coordinates
    const pressX = Math.floor(downPos.x * scaleX);
    const pressY = Math.floor(downPos.y * scaleY);
    const releaseX = Math.floor(upPos.x * scaleX);
    const releaseY = Math.floor(upPos.y * scaleY);

    // Clamp to device bounds
    const clampedPressX = Math.max(0, Math.min(pressX, deviceWidth - 1));
    const clampedPressY = Math.max(0, Math.min(pressY, deviceHeight - 1));
    const clampedReleaseX = Math.max(0, Math.min(releaseX, deviceWidth - 1));
    const clampedReleaseY = Math.max(0, Math.min(releaseY, deviceHeight - 1));

    // Calculate distance
    const distance = Math.sqrt(
        Math.pow(clampedReleaseX - clampedPressX, 2) +
        Math.pow(clampedReleaseY - clampedPressY, 2)
    );

    // Calculate duration (time between press and release)
    const duration = upPos.timestamp - downPos.timestamp;

    console.log(`Screenshot interaction: (${clampedPressX}, ${clampedPressY}) -> (${clampedReleaseX}, ${clampedReleaseY}), distance: ${distance}, duration: ${duration}ms`);

    // Determine tap vs swipe (threshold: 10 pixels)
    if (distance < 10) {
        sendTapCommand(clampedPressX, clampedPressY);
    } else {
        sendSwipeCommand(clampedPressX, clampedPressY, clampedReleaseX, clampedReleaseY, duration);
    }
}

// Get apply mode
function getApplyMode() {
    // Try header radios first (for mobile), then panel radios (for desktop)
    const headerRadios = document.getElementsByName('applyModeHeader');
    for (const radio of headerRadios) {
        if (radio.checked) {
            return radio.value;
        }
    }
    const panelRadios = document.getElementsByName('applyModePanel');
    for (const radio of panelRadios) {
        if (radio.checked) {
            return radio.value;
        }
    }
    return 'current';
}

// Get target devices based on apply mode and selected previews
function getTargetDevices() {
    const applyMode = getApplyMode();

    if (applyMode === 'current') {
        // Only current device
        return selectedDevice ? [selectedDevice] : [];
    } else {
        // ALL mode - return selected device + selected previews
        const targets = new Set();

        // Always include the main selected device
        if (selectedDevice) {
            targets.add(selectedDevice);
        }

        // Add all selected preview devices
        selectedPreviews.forEach(device => targets.add(device));

        const targetArray = Array.from(targets);
        console.log(`Target devices (ALL mode): ${targetArray.join(', ')} (${targetArray.length} total)`);
        return targetArray;
    }
}

// Send checkbox command
async function sendCheckboxCommand(checkboxName) {
    if (!selectedDevice) return;

    const enabled = document.getElementById(checkboxName).checked;
    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetchWithTimeout('/api/command/checkbox', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current',
                    name: checkboxName,
                    enabled: enabled
                })
            }, 5000);
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Checkbox command failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Checkbox command sent to ${successCount}/${targetDevices.length} devices: ${checkboxName} = ${enabled}`);

    if (successCount < targetDevices.length) {
        console.error('Some checkbox commands failed');
    }
}

// Send debug setting command (handles both Debug checkboxes and syncs them)
async function sendDebugSetting(checkbox) {
    if (!selectedDevice) return;

    const value = checkbox.checked;

    // Sync both debug checkboxes
    const debugEnabled = document.getElementById('debugEnabled');
    const botDebugEnabled = document.getElementById('botDebugEnabled');
    if (debugEnabled) debugEnabled.checked = value;
    if (botDebugEnabled) botDebugEnabled.checked = value;

    const targetDevices = getTargetDevices();
    if (targetDevices.length === 0) return;

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetch('/api/command/setting', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current',
                    name: 'debug_enabled',
                    value: value
                })
            });
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Debug setting failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Debug setting sent to ${successCount}/${targetDevices.length} devices: debug_enabled = ${value}`);
}

// Send setting command
async function sendSetting(settingName) {
    if (!selectedDevice) return;

    let value;

    // Check if this is a boolean setting (checkbox)
    if (settingName === 'fix_enabled') {
        const element = document.getElementById('fix_enabled');
        if (element) {
            value = element.checked;
        } else {
            return;
        }
    } else {
        // It's a number/text input - get from element with matching ID
        const element = document.getElementById(settingName);
        if (element) {
            // Parse based on input type
            if (element.type === 'number') {
                value = element.value.includes('.') ? parseFloat(element.value) : parseInt(element.value);
            } else {
                value = element.value;
            }
        } else {
            return;
        }
    }

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetch('/api/command/setting', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current',
                    name: settingName,
                    value: value
                })
            });
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Setting command failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Setting command sent to ${successCount}/${targetDevices.length} devices: ${settingName} = ${value}`);

    if (successCount < targetDevices.length) {
        console.error('Some setting commands failed');
    }
}

// Send tap command
async function sendTapCommand(x, y) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetchWithTimeout('/api/command/tap', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current',
                    x: x,
                    y: y
                })
            }, 5000);
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Tap command failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Tap command sent to ${successCount}/${targetDevices.length} devices: (${x}, ${y})`);

    if (successCount < targetDevices.length) {
        console.error('Some tap commands failed');
    }
}

// Send swipe command
async function sendSwipeCommand(x1, y1, x2, y2, duration) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    // Ensure duration is at least 100ms for reliable swipes
    const swipeDuration = Math.max(100, duration || 500);

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetchWithTimeout('/api/command/swipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current',
                    x1: x1,
                    y1: y1,
                    x2: x2,
                    y2: y2,
                    duration: swipeDuration
                })
            }, 5000);
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Swipe command failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Swipe command sent to ${successCount}/${targetDevices.length} devices: (${x1}, ${y1}) -> (${x2}, ${y2}), duration: ${swipeDuration}ms`);

    if (successCount < targetDevices.length) {
        console.error('Some swipe commands failed');
    }
}

// Helper function to delay execution
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Send bot command (start/stop)
async function sendBotCommand(action) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    // Confirm if ALL mode is active
    if (isAllModeActive() && targetDevices.length > 1) {
        const confirmed = confirm(`Are you sure you want to ${action.toUpperCase()} the bot on ALL ${targetDevices.length} devices?`);
        if (!confirmed) return;
    }

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetch('/api/command/bot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    action: action
                })
            });
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Bot ${action} command failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Bot ${action} command sent to ${successCount}/${targetDevices.length} devices`);

    if (successCount < targetDevices.length) {
        console.error('Some bot commands failed');
    }

    // Refresh device state after a short delay to allow bot to process command
    setTimeout(() => {
        refreshDeviceDetails();
    }, 1000);
}

// Take screenshot and open in MS Paint on server
async function sendScreenshotCommand() {
    if (!selectedDevice) return;

    try {
        const response = await fetch('/api/command/screenshot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device_name: selectedDevice
            })
        });

        const result = await response.json();
        if (result.success) {
            console.log(`Screenshot opened in MS Paint: ${result.file}`);
        } else {
            console.error('Screenshot failed:', result.error);
            alert('Screenshot failed: ' + result.error);
        }
    } catch (error) {
        console.error('Error taking screenshot:', error);
        alert('Error taking screenshot: ' + error.message);
    }
}

// Send command trigger
async function sendCommand(commandName) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    let successCount = 0;

    // Execute sequentially to ensure all commands are processed reliably
    for (const deviceName of targetDevices) {
        try {
            const response = await fetch('/api/command/trigger', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current',
                    command: commandName
                })
            });
            const result = await response.json();
            if (result.success) successCount++;
        } catch (err) {
            console.error(`Command ${commandName} failed for ${deviceName}:`, err.message);
        }
    }

    console.log(`Command sent to ${successCount}/${targetDevices.length} devices: ${commandName}`);

    if (successCount < targetDevices.length) {
        console.error('Some commands failed');
    }

    // Refresh device state after a short delay to allow bot to process command
    // This updates button states like Start/Stop and LDStop/LDStart
    setTimeout(() => {
        refreshDeviceDetails();
    }, 1000);
}

// Set screenshot FPS
function setScreenshotFPS() {
    const fpsSelect = document.getElementById('screenshotFPS');
    const fps = parseInt(fpsSelect.value);

    screenshotFPS = fps;

    // Send to server via WebSocket
    if (socket && socket.connected) {
        socket.emit('set_fps', { fps: fps });
        console.log(`Screenshot FPS set to: ${fps}`);
    } else {
        console.warn('WebSocket not connected, FPS change not sent to server');
    }
}

// Set theme (dark/light)
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    console.log(`Theme set to: ${theme}`);
}

// Initialize theme dropdown to match current theme
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
        themeSelect.value = savedTheme;
    }
}

// Send LDPlayer command
async function sendLDCommand(commandName) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();
    console.log(`sendLDCommand: command=${commandName}, targetDevices=${targetDevices.length}, devices=${targetDevices.join(',')}`);

    if (targetDevices.length === 0) return;

    // Commands that require confirmation in ALL mode
    const dangerousCommands = ['ld_start', 'ld_stop', 'ld_reboot'];
    // Commands that require 5-second delay between devices (start/reboot only, not stop)
    const delayedCommands = ['ld_start', 'ld_reboot'];

    // Confirm if ALL mode is active and this is a dangerous command
    if (isAllModeActive() && targetDevices.length > 1 && dangerousCommands.includes(commandName)) {
        const actionName = commandName.replace('ld_', '').toUpperCase();
        const confirmed = confirm(`Are you sure you want to ${actionName} LDPlayer on ALL ${targetDevices.length} devices?`);
        if (!confirmed) return;
    }

    try {
        let successCount = 0;

        // Send commands with 5 second delay between each when in ALL mode for start/reboot only
        if (isAllModeActive() && targetDevices.length > 1 && delayedCommands.includes(commandName)) {
            for (let i = 0; i < targetDevices.length; i++) {
                const deviceName = targetDevices[i];
                const startTime = Date.now();
                console.log(`[${new Date().toLocaleTimeString()}] Sending LDPlayer ${commandName} to ${deviceName} (${i + 1}/${targetDevices.length})...`);

                const response = await fetch('/api/command/ldplayer', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        device_name: deviceName,
                        apply_mode: 'current',
                        command: commandName
                    })
                });

                const result = await response.json();
                const fetchTime = Date.now() - startTime;
                console.log(`[${new Date().toLocaleTimeString()}] Response for ${deviceName}: ${result.success ? 'OK' : 'FAIL'} (${fetchTime}ms)`);
                if (result.success) successCount++;

                // Wait 5 seconds before next device (except for the last one)
                if (i < targetDevices.length - 1) {
                    console.log(`[${new Date().toLocaleTimeString()}] Waiting 5 seconds before next device...`);
                    await delay(5000);
                    console.log(`[${new Date().toLocaleTimeString()}] Delay complete, proceeding to next device`);
                }
            }
        } else {
            // Single device or non-dangerous command - execute sequentially for reliability
            for (const deviceName of targetDevices) {
                try {
                    const response = await fetch('/api/command/ldplayer', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            device_name: deviceName,
                            apply_mode: 'current',
                            command: commandName
                        })
                    });
                    const result = await response.json();
                    if (result.success) successCount++;
                } catch (err) {
                    console.error(`LDPlayer ${commandName} failed for ${deviceName}:`, err.message);
                }
            }
        }

        console.log(`LDPlayer command sent to ${successCount}/${targetDevices.length} devices: ${commandName}`);

        if (successCount < targetDevices.length) {
            console.error('Some LDPlayer commands failed');
        }
    } catch (error) {
        console.error('Error sending LDPlayer command:', error);
    }
}

// Toggle collapsible section
function toggleSection(sectionName) {
    const content = document.getElementById(`${sectionName}Content`);
    const icon = document.getElementById(`${sectionName}Icon`);

    if (content && icon) {
        content.classList.toggle('collapsed');
        icon.classList.toggle('collapsed');
    }
}

// Setup mobile swipe navigation
function setupMobileSwipeNavigation() {
    // Listen for swipes only in the header area (for device navigation)
    const header = document.querySelector('.header');

    if (!header) return;

    header.addEventListener('touchstart', (e) => {
        // Only process swipes on the header, not on interactive elements
        if (e.target.closest('button') || e.target.closest('input') || e.target.closest('select')) {
            return;
        }

        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    header.addEventListener('touchend', (e) => {
        // Only process swipes on the header, not on interactive elements
        if (e.target.closest('button') || e.target.closest('input') || e.target.closest('select')) {
            return;
        }

        touchEndX = e.changedTouches[0].clientX;
        touchEndY = e.changedTouches[0].clientY;

        handleSwipeGesture();
    }, { passive: true });
}

// Handle swipe gesture for device navigation
function handleSwipeGesture() {
    const swipeDistanceX = touchEndX - touchStartX;
    const swipeDistanceY = touchEndY - touchStartY;

    // Minimum swipe distance (in pixels)
    const minSwipeDistance = 50;

    // Make sure horizontal swipe is dominant (not vertical scroll)
    if (Math.abs(swipeDistanceX) > minSwipeDistance && Math.abs(swipeDistanceX) > Math.abs(swipeDistanceY) * 2) {
        if (swipeDistanceX > 0) {
            // Swipe right - go to previous device
            navigateToPreviousDevice();
        } else {
            // Swipe left - go to next device
            navigateToNextDevice();
        }
    }
}

// Navigate to previous device
function navigateToPreviousDevice() {
    if (allBots.length === 0) return;

    // Find current device index
    const currentIndex = allBots.findIndex(bot => bot.device_name === selectedDevice);

    if (currentIndex > 0) {
        // Go to previous device
        selectDevice(allBots[currentIndex - 1].device_name);
        console.log('Swiped to previous device:', allBots[currentIndex - 1].device_name);
    } else if (currentIndex === 0) {
        // Wrap around to last device
        selectDevice(allBots[allBots.length - 1].device_name);
        console.log('Wrapped to last device:', allBots[allBots.length - 1].device_name);
    }
}

// Navigate to next device
function navigateToNextDevice() {
    if (allBots.length === 0) return;

    // Find current device index
    const currentIndex = allBots.findIndex(bot => bot.device_name === selectedDevice);

    if (currentIndex >= 0 && currentIndex < allBots.length - 1) {
        // Go to next device
        selectDevice(allBots[currentIndex + 1].device_name);
        console.log('Swiped to next device:', allBots[currentIndex + 1].device_name);
    } else if (currentIndex === allBots.length - 1) {
        // Wrap around to first device
        selectDevice(allBots[0].device_name);
        console.log('Wrapped to first device:', allBots[0].device_name);
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
