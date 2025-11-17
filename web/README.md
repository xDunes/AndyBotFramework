# ApexGirl Bot Web Remote

A web-based remote monitoring and control interface for ApexGirl Bot instances with full desktop and mobile support.

## Features

- **Real-time Monitoring**: View all running bot instances with live status updates
- **Remote Control**: Control bot settings, checkboxes, and interact with device screenshots
- **Desktop & Mobile Friendly**: Responsive design that works seamlessly on all devices
- **Multi-Device Control**: Apply changes to a single device or all running devices at once
- **Screenshot Interaction**: Click or drag on screenshots to send tap/swipe commands to devices
- **Auto-refresh**: Configurable auto-refresh interval for real-time updates

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Pip (Python package manager)

### Installation

1. Navigate to the `web` folder:
   ```bash
   cd web
   ```

2. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

   **Troubleshooting Installation Issues:**

   If you get errors about missing Visual Studio or compiler tools:
   ```bash
   # Try upgrading pip first
   python -m pip install --upgrade pip

   # Then install with pre-built binaries
   pip install --only-binary :all: -r requirements.txt
   ```

   Or install packages individually:
   ```bash
   pip install Flask flask-cors
   pip install opencv-python
   pip install numpy
   ```

### Running the Server

1. Start the server:
   ```bash
   python server.py
   ```

2. Open your web browser and navigate to:
   - **Local access**: `http://localhost:5000`
   - **Network access**: `http://<your-computer-ip>:5000`

3. The server will display your network IP address in the console when it starts.

## Hosting on Windows

### Method 1: Simple Local Hosting (Easiest)

This method is best for quick testing and local network access.

1. **Open Command Prompt or PowerShell**
2. **Navigate to the web folder**:
   ```cmd
   cd e:\VSC\ApexGirl\Apex-Girl\web
   ```
3. **Run the server**:
   ```cmd
   python server.py
   ```
4. **Access the interface**:
   - On the same computer: `http://localhost:5000`
   - From other devices on your network: `http://<your-computer-ip>:5000`

**To find your computer's IP address:**
- Open Command Prompt and run: `ipconfig`
- Look for "IPv4 Address" under your active network adapter (usually starts with 192.168.x.x)

**Note**: Keep the Command Prompt window open while using the web interface.

---

### Method 2: Run as Background Process

To run the server in the background without keeping a window open:

1. **Create a batch file** (`start_web_remote.bat` in the `web` folder):
   ```batch
   @echo off
   cd /d "%~dp0"
   start /min pythonw server.py
   ```

2. **Double-click the batch file** to start the server in the background

3. **To stop the server**:
   - Open Task Manager (Ctrl+Shift+Esc)
   - Find "pythonw.exe" process
   - End the task

---

### Method 3: Windows Task Scheduler (Auto-start on boot)

To automatically start the web server when Windows starts:

1. **Create a VBS script** (`start_web_remote.vbs` in the `web` folder):
   ```vbscript
   Set WshShell = CreateObject("WScript.Shell")
   WshShell.CurrentDirectory = "E:\VSC\ApexGirl\Apex-Girl\web"
   WshShell.Run "pythonw server.py", 0, False
   Set WshShell = Nothing
   ```

2. **Open Task Scheduler**:
   - Press `Win+R`, type `taskschd.msc`, press Enter

3. **Create a new task**:
   - Click "Create Basic Task..."
   - Name: "ApexGirl Web Remote"
   - Trigger: "When I log on"
   - Action: "Start a program"
   - Program/script: `wscript.exe`
   - Add arguments: `"E:\VSC\ApexGirl\Apex-Girl\web\start_web_remote.vbs"`
   - Finish

4. **Test the task**:
   - Right-click the task → "Run"
   - Open browser to `http://localhost:5000` to verify it's working

---

### Method 4: Using Windows Firewall for Network Access

If you can't access the server from other devices on your network:

1. **Open Windows Defender Firewall**:
   - Search for "Windows Defender Firewall" in Start menu
   - Click "Advanced settings"

2. **Create an Inbound Rule**:
   - Click "Inbound Rules" → "New Rule..."
   - Rule Type: "Port"
   - Protocol: TCP, Port: 5000
   - Action: "Allow the connection"
   - Profile: Check all (Domain, Private, Public)
   - Name: "ApexGirl Web Remote"

3. **Test access** from another device on your network

---

### Method 5: Expose to Internet (Advanced)

**⚠️ Warning**: Only do this if you understand the security implications!

To access the web interface from outside your local network:

#### Option A: Port Forwarding (Router Configuration)

1. **Set a static local IP** for your computer (in Windows Network Settings)

2. **Access your router's admin panel**:
   - Common addresses: `192.168.1.1`, `192.168.0.1`, `10.0.0.1`
   - Login with your router credentials

3. **Setup port forwarding**:
   - Forward external port 5000 → internal IP:5000
   - Protocol: TCP

4. **Find your public IP**:
   - Visit `https://whatismyipaddress.com/`

5. **Access remotely**:
   - `http://<your-public-ip>:5000`

**Security Recommendation**: Use a VPN instead of exposing directly to the internet.

#### Option B: ngrok (Easy Internet Access)

1. **Download ngrok**: `https://ngrok.com/download`

2. **Extract and run**:
   ```bash
   ngrok http 5000
   ```

3. **Use the provided URL** (e.g., `https://abc123.ngrok.io`)

**Note**: Free ngrok URLs change each time you restart ngrok.

---

## Accessing from Mobile Devices

### Same Network (WiFi)

1. **Ensure your phone/tablet is on the same WiFi network** as the computer running the server

2. **Find your computer's IP address** (see Method 1)

3. **Open browser on mobile device** and navigate to:
   ```
   http://<your-computer-ip>:5000
   ```

### Over Internet

Use Method 5 (ngrok or port forwarding) and access via the public URL.

---

## Configuration

### Changing the Port

If port 5000 is already in use, you can change it:

1. Open `server.py`
2. Find the last line: `app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)`
3. Change `port=5000` to your desired port (e.g., `port=8080`)
4. Update firewall rules accordingly

### Auto-Refresh Settings

You can adjust the default auto-refresh interval in the web interface:

- Default: 0.5 seconds (500ms)
- Adjust the "Interval" field and click "Set"
- Toggle "Auto-refresh" to enable/disable

---

## Troubleshooting

### Installation fails with compiler/Visual Studio errors

**Issue**: `numpy` or `opencv-python` installation fails with "Failed to activate VS environment" or compiler errors
- **Solution 1**: Upgrade pip and use pre-built binaries:
  ```bash
  python -m pip install --upgrade pip
  pip install --only-binary :all: -r requirements.txt
  ```
- **Solution 2**: Install packages individually (they'll auto-download compatible versions):
  ```bash
  pip install Flask flask-cors opencv-python numpy
  ```
- **Solution 3**: Use a specific numpy version known to have Windows wheels:
  ```bash
  pip install numpy==1.24.3
  pip install -r requirements.txt
  ```

### Server won't start

**Issue**: Port already in use
- **Solution**: Change the port in `server.py` or close the application using port 5000

**Issue**: Module not found errors
- **Solution**: Install requirements: `pip install -r requirements.txt`

### Can't access from network

**Issue**: Connection refused from other devices
- **Solution**: Check Windows Firewall settings (see Method 4)
- **Solution**: Verify you're using the correct IP address (`ipconfig` in Command Prompt)
- **Solution**: Ensure the server is running with `host='0.0.0.0'` (not `127.0.0.1`)

### Screenshots not loading

**Issue**: No screenshot displayed
- **Solution**: Ensure bot instances are running and updating screenshots
- **Solution**: Check that the state database (`state/state_monitor.db`) exists

### Controls not working

**Issue**: Checkbox/setting changes not applied
- **Solution**: Verify bot instances are actively polling for remote commands
- **Solution**: Check that the bot's state manager is properly integrated

---

## API Endpoints

The server provides the following RESTful API endpoints:

### GET `/api/stats`
Get database statistics (total bots, running bots, etc.)

### GET `/api/bots`
Get all bot instances with their states

### GET `/api/bots/<device_name>`
Get state for a specific device

### GET `/api/bots/<device_name>/screenshot`
Get screenshot for a specific device (base64 encoded PNG)

### POST `/api/command/checkbox`
Send checkbox command to device(s)
```json
{
  "device_name": "Gelvil",
  "apply_mode": "current",
  "name": "doStreet",
  "enabled": true
}
```

### POST `/api/command/setting`
Send setting command to device(s)
```json
{
  "device_name": "Gelvil",
  "apply_mode": "current",
  "name": "sleep_time",
  "value": 1.5
}
```

### POST `/api/command/tap`
Send tap command to device(s)
```json
{
  "device_name": "Gelvil",
  "apply_mode": "current",
  "x": 270,
  "y": 480
}
```

### POST `/api/command/swipe`
Send swipe command to device(s)
```json
{
  "device_name": "Gelvil",
  "apply_mode": "current",
  "x1": 270,
  "y1": 800,
  "x2": 270,
  "y2": 200
}
```

---

## File Structure

```
web/
├── server.py              # Flask backend API server
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── static/
    ├── index.html        # Main HTML page
    ├── styles.css        # Responsive CSS styles
    └── app.js            # JavaScript application logic
```

---

## Performance Tips

1. **Adjust refresh interval**: Increase the interval (e.g., 1-2 seconds) if monitoring many devices
2. **Disable auto-refresh**: Turn off auto-refresh when not actively monitoring to reduce load
3. **Close unused browser tabs**: Each open tab will consume resources
4. **Use a modern browser**: Chrome, Firefox, or Edge for best performance

---

## Browser Compatibility

- ✅ Google Chrome (recommended)
- ✅ Mozilla Firefox
- ✅ Microsoft Edge
- ✅ Safari (macOS/iOS)
- ✅ Chrome Mobile (Android)
- ✅ Safari Mobile (iOS)

---

## Security Notes

- The server runs without authentication by default
- Only expose to trusted networks
- For internet access, consider adding authentication
- Use HTTPS for production deployments (requires SSL certificate)
- The server is designed for local/private network use

---

## Support

For issues or questions:
- Check the ApexGirl Bot main documentation
- Review the console output for error messages
- Verify all dependencies are installed correctly

---

## License

This web interface is part of the ApexGirl Bot project and follows the same license.
