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
monitor=4
try:
    newMonitor=sys.argv[1]
    if not newMonitor is None:
        monitor=newMonitor
except Exception as error:
    print("NO ARGUMENT")

for m in get_monitors():
    print(m)
    #if m.is_primary:
    if m.name==f'\\\\.\\DISPLAY{monitor}':
        monitorWidth=m.width
        xStart=m.x
        yStart=m.y

# Load window titles from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    windowsTitles = [device['window'] for device in config['devices'].values()]

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

width=int(monitorWidth/len(windows))
#height=int(width*1.6875)
#height=int(width*2.16666666) 540x1170
height=int(width*1.8)   #540x960

counter=0
for window in windows:
    window.resizeTo(width,height)
    window.moveTo(xStart+(width*counter),yStart)
    # Bring window to front after positioning
    force_window_to_front(window)
    counter=counter+1
