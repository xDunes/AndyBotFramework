// Bot Web Remote - Main Application

// Configuration
let appConfig = null;

// State
let selectedDevice = null;
let autoRefresh = true;
let refreshInterval = 500; // milliseconds (500ms = 0.5s for near-live updates)
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

// Function checkboxes configuration - will be loaded from config
let functionCheckboxes = [];

// Initialize application
async function init() {
    console.log('Bot Web Remote - Initializing...');

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

    // Create shortcuts
    createShortcuts();

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
        // Update main screenshot if this is the selected device
        if (data.device_name === selectedDevice) {
            updateScreenshotFromWebSocket(data.screenshot);
        }

        // Store screenshot for preview updates (if ALL mode is active)
        previewScreenshots[data.device_name] = data.screenshot;

        // Update preview if ALL mode is active and this device is in the preview list
        if (isAllModeActive()) {
            updatePreviewScreenshot(data.device_name, data.screenshot);
        }
    });

    socket.on('fps_updated', (data) => {
        console.log(`Screenshot FPS updated to: ${data.fps}`);
        screenshotFPS = data.fps;
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
            console.error('Failed to load config, using defaults');
            // Fallback to default layout
            functionCheckboxes = [
                { name: 'doStreet', label: 'Street' },
                { name: 'doStudio', label: 'Studio' },
                { name: 'doGroup', label: 'Group' },
                { name: '_placeholder_0', label: '', isPlaceholder: true },
                { name: 'doHelp', label: 'Help' },
                { name: 'doCoin', label: 'Coin' },
                { name: 'doHeal', label: 'Heal' },
                { name: '_placeholder_1', label: '', isPlaceholder: true },
                { name: 'doRally', label: 'Rally' },
                { name: 'doConcert', label: 'Concert' },
                { name: 'doParking', label: 'Parking' },
                { name: '_placeholder_2', label: '', isPlaceholder: true },
                { name: 'fix_enabled', label: 'Fix/Recover', isSetting: true }
            ];
        }
    } catch (error) {
        console.error('Error loading config:', error);
        // Use default layout on error
        functionCheckboxes = [
            { name: 'doStreet', label: 'Street' },
            { name: 'doStudio', label: 'Studio' },
            { name: 'doGroup', label: 'Group' },
            { name: '_placeholder_0', label: '', isPlaceholder: true },
            { name: 'doHelp', label: 'Help' },
            { name: 'doCoin', label: 'Coin' },
            { name: 'doHeal', label: 'Heal' },
            { name: '_placeholder_1', label: '', isPlaceholder: true },
            { name: 'doRally', label: 'Rally' },
            { name: 'doConcert', label: 'Concert' },
            { name: 'doParking', label: 'Parking' },
            { name: '_placeholder_2', label: '', isPlaceholder: true },
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
            const otherDevices = allBots.filter(bot => bot.device_name !== selectedDevice);
            selectedPreviews.clear();
            otherDevices.forEach(bot => selectedPreviews.add(bot.device_name));
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
function updatePreviewScreenshots() {
    const previewsContainer = document.getElementById('screenshotPreviews');
    if (!previewsContainer || !selectedDevice) return;

    // Get list of other devices (exclude selected device)
    const otherDevices = allBots.filter(bot => bot.device_name !== selectedDevice);

    // Get existing preview items
    const existingPreviews = Array.from(previewsContainer.children);
    const existingDeviceNames = existingPreviews.map(item => item.dataset.deviceName);
    const newDeviceNames = otherDevices.map(bot => bot.device_name);

    // Check if the device list has changed
    const devicesChanged =
        existingDeviceNames.length !== newDeviceNames.length ||
        existingDeviceNames.some(name => !newDeviceNames.includes(name)) ||
        newDeviceNames.some(name => !existingDeviceNames.includes(name));

    if (devicesChanged) {
        // Device list changed - rebuild previews
        previewsContainer.innerHTML = '';

        otherDevices.forEach(bot => {
            const previewItem = createPreviewItem(bot.device_name);
            previewsContainer.appendChild(previewItem);
            loadPreviewScreenshot(bot.device_name);
        });
    } else {
        // Device list unchanged - just update screenshots
        otherDevices.forEach(bot => {
            loadPreviewScreenshot(bot.device_name);
        });
    }
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

    // Add label
    const label = document.createElement('div');
    label.className = 'screenshot-preview-label';
    label.textContent = deviceName;
    previewItem.appendChild(label);

    // Add canvas
    const canvas = document.createElement('canvas');
    canvas.className = 'screenshot-preview-canvas';
    canvas.id = `preview-canvas-${deviceName}`;
    previewItem.appendChild(canvas);

    // Add placeholder
    const placeholder = document.createElement('div');
    placeholder.className = 'screenshot-preview-placeholder';
    placeholder.textContent = 'Loading...';
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
        const response = await fetch(`/api/bots/${deviceName}/screenshot`);
        const data = await response.json();

        if (data.success && data.screenshot) {
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

// Create shortcuts dynamically from config
function createShortcuts() {
    const container = document.getElementById('shortcutsGrid');
    if (!container || !appConfig || !appConfig.shortcuts) return;

    container.innerHTML = ''; // Clear existing

    appConfig.shortcuts.forEach(shortcut => {
        const button = document.createElement('button');
        button.className = 'btn shortcut-btn';
        button.textContent = shortcut.label;

        // Handle start_stop button specially - it needs the ID
        if (shortcut.id === 'start_stop') {
            button.id = 'startStopBtn';
        }

        button.onclick = () => sendShortcut(shortcut.id);
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

// Refresh all data
async function refreshData() {
    try {
        // Fetch stats
        const statsResponse = await fetch('/api/stats');
        const statsData = await statsResponse.json();

        if (statsData.success) {
            updateStats(statsData.stats);
        } else {
            console.error('Stats API error:', statsData.error);
        }

        // Fetch all bots
        const botsResponse = await fetch('/api/bots');
        const botsData = await botsResponse.json();

        if (botsData.success) {
            updateDeviceList(botsData.bots);

            // Auto-select first device if none selected
            if (!selectedDevice && botsData.bots.length > 0) {
                selectDevice(botsData.bots[0].device_name);
            }
        } else {
            console.error('Bots API error:', botsData.error);
            const deviceList = document.getElementById('deviceList');
            deviceList.innerHTML = `<div class="loading" style="color: red;">Error: ${botsData.error}</div>`;
        }

        // Refresh selected device details
        if (selectedDevice) {
            await refreshDeviceDetails();
        }
    } catch (error) {
        console.error('Error refreshing data:', error);
        const deviceList = document.getElementById('deviceList');
        deviceList.innerHTML = `<div class="loading" style="color: red;">Connection error: ${error.message}</div>`;
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

        // Update status text only if changed (just time, status shown by color)
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
    updateCurrentDeviceDisplay();
    refreshDeviceDetails();

    // If ALL mode is active, auto-select all remaining devices (except the new active device)
    if (isAllModeActive()) {
        const otherDevices = allBots.filter(bot => bot.device_name !== selectedDevice);
        selectedPreviews.clear();
        otherDevices.forEach(bot => selectedPreviews.add(bot.device_name));
        console.log(`Active device changed to ${deviceName}. Auto-selected ${selectedPreviews.size} preview devices.`);
    }

    updatePreviewsVisibility();
}

// Update current device display in header
function updateCurrentDeviceDisplay() {
    const currentDeviceNameEl = document.getElementById('currentDeviceName');
    const statusIndicator = document.getElementById('statusIndicator');

    if (!selectedDevice) {
        currentDeviceNameEl.textContent = 'No device selected';
        statusIndicator.className = 'status-indicator';
        return;
    }

    currentDeviceNameEl.textContent = selectedDevice;

    // Find the bot in allBots to get its status
    const bot = allBots.find(b => b.device_name === selectedDevice);
    if (bot) {
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
    }
}

// Refresh device details
async function refreshDeviceDetails() {
    if (!selectedDevice) return;

    try {
        // Show device content
        document.getElementById('deviceDetails').querySelector('.no-selection').style.display = 'none';
        document.getElementById('deviceContent').style.display = 'grid';

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

        // Update log
        updateLog(state.current_log);

        // Update screenshot
        await updateScreenshot();

    } catch (error) {
        console.error('Error refreshing device details:', error);
    }
}

// Update status info
function updateStatusInfo(state) {
    const headerStatusInfo = document.getElementById('headerStatusInfo');

    const status = state.is_running ? 'RUNNING' : 'STOPPED';
    const startTime = state.start_time;
    const lastUpdate = state.last_update;
    const endTime = state.end_time || 'N/A';
    const uptime = state.uptime_seconds ? formatElapsedTime(state.uptime_seconds) : 'N/A';

    headerStatusInfo.innerHTML = `
        <strong>Device:</strong> ${state.device_name}<br>
        <strong>Status:</strong> ${status}<br>
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

    // Update debug checkbox
    const debugElement = document.getElementById('debugEnabled');
    if (debugElement) {
        debugElement.checked = Boolean(state.debug_enabled);
    }

    // Update Start/Stop button text
    const startStopBtn = document.getElementById('startStopBtn');
    if (startStopBtn) {
        startStopBtn.textContent = state.is_running ? 'Stop' : 'Start';
    }
}

// Update log
function updateLog(logText) {
    const logElement = document.getElementById('logText');
    logElement.textContent = logText || 'No log entries';
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
            y: e.clientY - rect.top
        };
    });

    canvas.addEventListener('mouseup', (e) => {
        if (!mouseDownPos || !screenshotDisplaySize) return;

        const rect = canvas.getBoundingClientRect();
        const mouseUpPos = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
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
            y: touch.clientY - rect.top
        };
    });

    canvas.addEventListener('touchend', (e) => {
        e.preventDefault();
        if (!mouseDownPos || !screenshotDisplaySize) return;

        const rect = canvas.getBoundingClientRect();
        const touch = e.changedTouches[0];
        const mouseUpPos = {
            x: touch.clientX - rect.left,
            y: touch.clientY - rect.top
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

    console.log(`Screenshot interaction: (${clampedPressX}, ${clampedPressY}) -> (${clampedReleaseX}, ${clampedReleaseY}), distance: ${distance}`);

    // Determine tap vs swipe (threshold: 10 pixels)
    if (distance < 10) {
        sendTapCommand(clampedPressX, clampedPressY);
    } else {
        sendSwipeCommand(clampedPressX, clampedPressY, clampedReleaseX, clampedReleaseY);
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
        // ALL mode - return current device + selected preview devices
        const targets = [];
        if (selectedDevice) {
            targets.push(selectedDevice);
        }
        selectedPreviews.forEach(deviceName => {
            if (deviceName !== selectedDevice) {
                targets.push(deviceName);
            }
        });
        console.log(`Target devices (ALL mode): ${targets.join(', ')} (${targets.length} total)`);
        return targets;
    }
}

// Send checkbox command
async function sendCheckboxCommand(checkboxName) {
    if (!selectedDevice) return;

    const enabled = document.getElementById(checkboxName).checked;
    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    try {
        // Send command to each target device
        const promises = targetDevices.map(deviceName =>
            fetch('/api/command/checkbox', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current', // Always use 'current' since we're targeting specific devices
                    name: checkboxName,
                    enabled: enabled
                })
            })
        );

        const responses = await Promise.all(promises);
        const results = await Promise.all(responses.map(r => r.json()));

        const successCount = results.filter(r => r.success).length;
        console.log(`Checkbox command sent to ${successCount}/${targetDevices.length} devices: ${checkboxName} = ${enabled}`);

        if (successCount < targetDevices.length) {
            console.error('Some checkbox commands failed');
        }
    } catch (error) {
        console.error('Error sending checkbox command:', error);
    }
}

// Send setting command
async function sendSetting(settingName) {
    if (!selectedDevice) return;

    let value;

    // Check if this is a boolean setting (checkbox)
    if (settingName === 'fix_enabled' || settingName === 'debug_enabled') {
        const element = document.getElementById(settingName === 'debug_enabled' ? 'debugEnabled' : 'fix_enabled');
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

    try {
        // Send command to each target device
        const promises = targetDevices.map(deviceName =>
            fetch('/api/command/setting', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current', // Always use 'current' since we're targeting specific devices
                    name: settingName,
                    value: value
                })
            })
        );

        const responses = await Promise.all(promises);
        const results = await Promise.all(responses.map(r => r.json()));

        const successCount = results.filter(r => r.success).length;
        console.log(`Setting command sent to ${successCount}/${targetDevices.length} devices: ${settingName} = ${value}`);

        if (successCount < targetDevices.length) {
            console.error('Some setting commands failed');
        }
    } catch (error) {
        console.error('Error sending setting command:', error);
    }
}

// Send tap command
async function sendTapCommand(x, y) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    try {
        // Send command to each target device
        const promises = targetDevices.map(deviceName =>
            fetch('/api/command/tap', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current', // Always use 'current' since we're targeting specific devices
                    x: x,
                    y: y
                })
            })
        );

        const responses = await Promise.all(promises);
        const results = await Promise.all(responses.map(r => r.json()));

        const successCount = results.filter(r => r.success).length;
        console.log(`Tap command sent to ${successCount}/${targetDevices.length} devices: (${x}, ${y})`);

        if (successCount < targetDevices.length) {
            console.error('Some tap commands failed');
        }
    } catch (error) {
        console.error('Error sending tap command:', error);
    }
}

// Send swipe command
async function sendSwipeCommand(x1, y1, x2, y2) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    try {
        // Send command to each target device
        const promises = targetDevices.map(deviceName =>
            fetch('/api/command/swipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current', // Always use 'current' since we're targeting specific devices
                    x1: x1,
                    y1: y1,
                    x2: x2,
                    y2: y2
                })
            })
        );

        const responses = await Promise.all(promises);
        const results = await Promise.all(responses.map(r => r.json()));

        const successCount = results.filter(r => r.success).length;
        console.log(`Swipe command sent to ${successCount}/${targetDevices.length} devices: (${x1}, ${y1}) -> (${x2}, ${y2})`);

        if (successCount < targetDevices.length) {
            console.error('Some swipe commands failed');
        }
    } catch (error) {
        console.error('Error sending swipe command:', error);
    }
}

// Send shortcut command
async function sendShortcut(shortcutName) {
    if (!selectedDevice) return;

    const targetDevices = getTargetDevices();

    if (targetDevices.length === 0) return;

    try {
        // Send command to each target device
        const promises = targetDevices.map(deviceName =>
            fetch('/api/command/shortcut', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_name: deviceName,
                    apply_mode: 'current', // Always use 'current' since we're targeting specific devices
                    shortcut: shortcutName
                })
            })
        );

        const responses = await Promise.all(promises);
        const results = await Promise.all(responses.map(r => r.json()));

        const successCount = results.filter(r => r.success).length;
        console.log(`Shortcut command sent to ${successCount}/${targetDevices.length} devices: ${shortcutName}`);

        if (successCount < targetDevices.length) {
            console.error('Some shortcut commands failed');
        }
    } catch (error) {
        console.error('Error sending shortcut command:', error);
    }
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
