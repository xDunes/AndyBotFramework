import os
import pygetwindow as gw
import sys
import json
from screeninfo import get_monitors
import ctypes
import time

def force_window_to_front(window):
    """Force a window to the foreground even when competing with persistent full-screen windows.

    Uses a combination of techniques:
    1. Temporarily set window as topmost (always-on-top)
    2. Minimize/restore cycle to force Z-order refresh
    3. Remove topmost flag so it behaves normally afterwards
    """
    try:
        hwnd = window._hWnd

        # Validate window handle
        if not ctypes.windll.user32.IsWindow(hwnd):
            return

        # Define Windows API constants
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040

        # Step 1: Set as topmost (always-on-top) - this beats full-screen windows
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        )

        # Step 2: Minimize and restore to force refresh
        window.minimize()
        time.sleep(0.05)  # Small delay to ensure minimize completes
        window.restore()

        # Step 3: Remove topmost flag so window behaves normally
        # (we don't want it to stay always-on-top permanently)
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        )

    except Exception:
        # Fallback to just minimize/restore if API calls fail
        try:
            window.minimize()
            window.restore()
        except:
            pass

monitorWidth=0
xStart=0
yStart=0
monitor=1
try:
    newMonitor=sys.argv[1]
    if not newMonitor is None:
        monitor=newMonitor
except IndexError:
    print("NO ARGUMENT - using default monitor 4")

monitor_found = False
for m in get_monitors():
    print(m)
    #if m.is_primary:
    if m.name==f'\\\\.\\DISPLAY{monitor}':
        monitorWidth=m.width
        xStart=m.x
        yStart=m.y
        monitor_found = True
        break

if not monitor_found:
    print(f"Error: Monitor DISPLAY{monitor} not found")
    sys.exit(1)

if monitorWidth == 0:
    print(f"Error: Invalid monitor width (0) for DISPLAY{monitor}")
    sys.exit(1)

# Load window titles from master.conf (at project root)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(project_root, 'master.conf')
try:
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
        windowsTitles = [device['window'] for device in config['devices'].values()]
except FileNotFoundError:
    print(f"Error: master.conf file not found at {config_path}")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: master.conf is not valid JSON")
    sys.exit(1)
except KeyError as e:
    print(f"Error: Missing expected key in master.conf: {e}")
    sys.exit(1)

print(windowsTitles)

windows=[]

#width=int(480*1.3)
#height=int(810*1.3)

for windowTitle in windowsTitles:
    try:
        # Filter for exact match only
        allMatches = gw.getWindowsWithTitle(windowTitle)
        matchingWindows = [w for w in allMatches if w.title == windowTitle]
        if matchingWindows:
            window = matchingWindows[0]
            windows.append(window)
        else:
            print(f"Didn't find exact match for '{windowTitle}'")
    except IndexError:
        print(f"Didn't find {windowTitle}")

if len(windows) == 0:
    print("Error: No windows found to arrange. Please check window titles in master.conf")
    sys.exit(1)

width=int(monitorWidth/len(windows))
#height=int(width*1.6875)
#height=int(width*2.16666666) 540x1170
height=int(width*1.8)   #540x960

counter=0
for window in windows:
    try:
        window.resizeTo(width,height)
        window.moveTo(xStart+(width*counter),yStart)
        # Bring window to front after positioning
        force_window_to_front(window)
        counter=counter+1
    except Exception as e:
        print(f"Error positioning window '{window.title}': {e}")
        counter=counter+1  # Still increment counter to maintain spacing for remaining windows
