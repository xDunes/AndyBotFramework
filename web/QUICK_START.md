# Quick Start Guide

## 🚀 Fastest Way to Get Started

### Windows - 3 Steps

1. **Double-click** `start_web_remote.bat`
2. **Open browser** to `http://localhost:5000`
3. **Done!** 🎉

**First Time Setup:**
- If you get errors, run `install_dependencies.bat` first
- This installs Python packages without needing Visual Studio

### Mobile/Tablet Access

1. **Start server** on your computer (see above)
2. **Find your computer's IP**:
   - Run `ipconfig` in Command Prompt
   - Look for IPv4 Address (e.g., 192.168.1.100)
3. **Open browser on phone/tablet** to `http://YOUR-IP:5000`

---

## 📱 Using the Interface

### Device List (Left Side)
- Click any device to view details
- **Green** = Running
- **Orange** = Stale (no recent updates)
- **Red** = Stopped

### Remote Control
- **Current Device Only**: Changes apply to selected device
- **ALL Running Devices**: Changes apply to all active bots

### Screenshot Interaction
- **Click** on screenshot → Sends tap command to device
- **Click + Drag** → Sends swipe command to device

---

## 🛠️ Common Tasks

### Change Refresh Speed
1. Type new interval in "Interval (s)" field (e.g., 1 for 1 second)
2. Click "Set"

### Control Bot Functions
1. Select a device from the list
2. Check/uncheck function boxes (Street, Artists, etc.)
3. Changes are sent automatically

### Adjust Settings
1. Select a device
2. Change Sleep Time or Studio Stop values
3. Click "Set" button next to the field

### Stop Auto-Refresh
- Uncheck "Auto-refresh" at the top
- Good for saving resources when not actively monitoring

---

## 🔧 Troubleshooting

### Installation errors (Visual Studio / compiler)?
1. **Run `install_dependencies.bat`** - This fixes most issues!
2. Or manually: `pip install Flask flask-cors opencv-python numpy`
3. Still failing? Try: `python -m pip install --upgrade pip`

### Can't access from another device?
1. Check Windows Firewall (see full README)
2. Verify both devices are on same WiFi
3. Use correct IP address (not 127.0.0.1 or localhost)

### Server won't start?
1. Install Python 3.8+ from python.org
2. Run `install_dependencies.bat`
3. Try changing port in server.py

### Screenshots not showing?
1. Make sure bot instances are running
2. Check that bots are updating state database
3. Wait for next auto-refresh cycle

---

## 📚 More Help

See **README.md** for:
- Complete hosting options
- Windows Task Scheduler setup
- Internet access methods
- API documentation
- Security considerations

---

## 💡 Pro Tips

- **Bookmark** `http://localhost:5000` for quick access
- Use **Chrome** or **Firefox** for best experience
- **Increase interval** (2-5 seconds) when monitoring many devices
- Create **desktop shortcut** to `start_web_remote.bat`
- For 24/7 operation, use **Task Scheduler** method (see README)
