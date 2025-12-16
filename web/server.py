"""
Web Remote Server - Flask API backend for web-based bot monitoring

Provides RESTful API endpoints for the web interface to interact with
the bot state database.

Usage:
    python server.py

    Then open browser to http://localhost:5000
"""

import sys
import os

# Add parent directory to path so we can import from core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from core.state_manager import StateManager
import base64
import cv2 as cv
import numpy as np
from datetime import datetime
from PIL import Image
import io
import json
import threading
import time

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # Enable CORS for all routes
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# =============================================================================
# STATIC FILE ROUTES
# =============================================================================

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory('static', path)

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get configuration from config_loader"""
    try:
        from core.config_loader import load_config
        config = load_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        stats = StateManager.get_database_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bots', methods=['GET'])
def get_all_bots():
    """Get all bot instances"""
    try:
        all_bots = StateManager.get_all_bots()

        # Sort alphabetically by device name
        all_bots.sort(key=lambda x: x['device_name'].lower())

        # Calculate time since last update for each bot
        # Also remove binary data (screenshot blobs) that can't be JSON serialized
        for bot in all_bots:
            # Remove screenshot blob (we have a separate endpoint for screenshots)
            if 'latest_screenshot' in bot:
                del bot['latest_screenshot']

            # Convert SQLite integers (0/1) to Python booleans
            bot['is_running'] = bool(bot.get('is_running', 0))
            bot['ld_running'] = bool(bot.get('ld_running', 0))

            # Calculate elapsed time
            try:
                last_dt = datetime.fromisoformat(bot['last_update'])
                elapsed = (datetime.now() - last_dt).total_seconds()
                bot['elapsed_seconds'] = elapsed
            except:
                bot['elapsed_seconds'] = None

        return jsonify({
            'success': True,
            'bots': all_bots
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bots/<device_name>', methods=['GET'])
def get_device_state(device_name):
    """Get state for a specific device"""
    try:
        state = StateManager.get_device_state(device_name)

        if not state:
            return jsonify({
                'success': False,
                'error': 'Device not found'
            }), 404

        # Convert SQLite integers (0/1) to Python booleans
        state['is_running'] = bool(state.get('is_running', 0))
        state['ld_running'] = bool(state.get('ld_running', 0))

        # Calculate uptime
        try:
            start_dt = datetime.fromisoformat(state['start_time'])
            if state['is_running']:
                uptime = (datetime.now() - start_dt).total_seconds()
            elif state['end_time']:
                end_dt = datetime.fromisoformat(state['end_time'])
                uptime = (end_dt - start_dt).total_seconds()
            else:
                uptime = 0
            state['uptime_seconds'] = uptime
        except:
            state['uptime_seconds'] = 0

        # Calculate elapsed time since last update
        try:
            last_dt = datetime.fromisoformat(state['last_update'])
            elapsed = (datetime.now() - last_dt).total_seconds()
            state['elapsed_seconds'] = elapsed
        except:
            state['elapsed_seconds'] = None

        # Remove screenshot blob (we have a separate endpoint for screenshots)
        if 'latest_screenshot' in state:
            del state['latest_screenshot']

        return jsonify({
            'success': True,
            'state': state
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bots/<device_name>/screenshot', methods=['GET'])
def get_device_screenshot(device_name):
    """Get screenshot for a specific device (as base64 PNG or JPEG)

    Query params:
        size: 'preview' for small thumbnail (85x150), 'full' for original (default)
        format: 'jpeg' or 'png' (default: jpeg for preview, png for full)
    """
    try:
        # Get screenshot and timestamp together
        screenshot, timestamp = StateManager.get_device_screenshot_with_timestamp(device_name)

        if screenshot is None:
            return jsonify({
                'success': False,
                'error': 'No screenshot available'
            }), 404

        # OpenCV stores images as BGR, need to convert to RGB for web display
        if len(screenshot.shape) == 3:
            if screenshot.shape[2] == 4:
                # BGRA to RGBA
                screenshot = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGBA)
            elif screenshot.shape[2] == 3:
                # BGR to RGB
                screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

        # Check for size parameter
        size = request.args.get('size', 'full')
        img = Image.fromarray(screenshot)
        original_width, original_height = img.size

        if size == 'preview':
            # Resize for preview - 85x150 matches the CSS max dimensions
            # Maintain aspect ratio based on 540:960
            preview_width = 85
            preview_height = 150
            img = img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)

            # Use JPEG with lower quality for previews - much smaller file size
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=60, optimize=True)
            buffer.seek(0)
            base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            mime_type = 'image/jpeg'
        else:
            # Full size - use PNG for quality
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            mime_type = 'image/png'

        return jsonify({
            'success': True,
            'screenshot': f'data:{mime_type};base64,{base64_data}',
            'timestamp': str(timestamp) if timestamp else None,
            'width': original_width,
            'height': original_height
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/checkbox', methods=['POST'])
def send_checkbox_command():
    """Send checkbox command to device(s)"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        apply_mode = data.get('apply_mode', 'current')
        checkbox_name = data.get('name')
        enabled = data.get('enabled')

        if not checkbox_name or enabled is None:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        if apply_mode == 'all':
            # Apply to all running devices
            running_bots = StateManager.get_all_running_bots()
            for bot in running_bots:
                StateManager.send_command(
                    bot['device_name'],
                    'checkbox',
                    {'name': checkbox_name, 'enabled': enabled}
                )
        else:
            # Apply to specific device
            if not device_name:
                return jsonify({
                    'success': False,
                    'error': 'device_name required for current mode'
                }), 400

            StateManager.send_command(
                device_name,
                'checkbox',
                {'name': checkbox_name, 'enabled': enabled}
            )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/setting', methods=['POST'])
def send_setting_command():
    """Send setting command to device(s)"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        apply_mode = data.get('apply_mode', 'current')
        setting_name = data.get('name')
        value = data.get('value')

        if not setting_name or value is None:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        if apply_mode == 'all':
            # Apply to all running devices
            running_bots = StateManager.get_all_running_bots()
            for bot in running_bots:
                StateManager.send_command(
                    bot['device_name'],
                    'setting',
                    {'name': setting_name, 'value': value}
                )
        else:
            # Apply to specific device
            if not device_name:
                return jsonify({
                    'success': False,
                    'error': 'device_name required for current mode'
                }), 400

            StateManager.send_command(
                device_name,
                'setting',
                {'name': setting_name, 'value': value}
            )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/tap', methods=['POST'])
def send_tap_command():
    """Send tap command to device(s)"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        apply_mode = data.get('apply_mode', 'current')
        x = data.get('x')
        y = data.get('y')

        if x is None or y is None:
            return jsonify({
                'success': False,
                'error': 'Missing x or y coordinates'
            }), 400

        if apply_mode == 'all':
            # Apply to all running devices
            running_bots = StateManager.get_all_running_bots()
            for bot in running_bots:
                StateManager.send_command(
                    bot['device_name'],
                    'tap',
                    {'x': int(x), 'y': int(y)}
                )
        else:
            # Apply to specific device
            if not device_name:
                return jsonify({
                    'success': False,
                    'error': 'device_name required for current mode'
                }), 400

            StateManager.send_command(
                device_name,
                'tap',
                {'x': int(x), 'y': int(y)}
            )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/swipe', methods=['POST'])
def send_swipe_command():
    """Send swipe command to device(s)"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        apply_mode = data.get('apply_mode', 'current')
        x1 = data.get('x1')
        y1 = data.get('y1')
        x2 = data.get('x2')
        y2 = data.get('y2')
        duration = data.get('duration', 500)  # Default 500ms if not provided

        if any(v is None for v in [x1, y1, x2, y2]):
            return jsonify({
                'success': False,
                'error': 'Missing swipe coordinates'
            }), 400

        swipe_data = {
            'x1': int(x1),
            'y1': int(y1),
            'x2': int(x2),
            'y2': int(y2),
            'duration': int(duration)
        }

        if apply_mode == 'all':
            # Apply to all running devices
            running_bots = StateManager.get_all_running_bots()
            for bot in running_bots:
                StateManager.send_command(
                    bot['device_name'],
                    'swipe',
                    swipe_data
                )
        else:
            # Apply to specific device
            if not device_name:
                return jsonify({
                    'success': False,
                    'error': 'device_name required for current mode'
                }), 400

            StateManager.send_command(
                device_name,
                'swipe',
                swipe_data
            )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/bot', methods=['POST'])
def send_bot_command():
    """Send bot start/stop command to device"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        action = data.get('action')

        if not device_name:
            return jsonify({
                'success': False,
                'error': 'Missing device_name'
            }), 400

        if action not in ['start', 'stop']:
            return jsonify({
                'success': False,
                'error': 'Invalid action. Must be "start" or "stop"'
            }), 400

        # Start always sends start_bot (will restart if already running)
        # Stop always sends stop_bot
        cmd_type = 'start_bot' if action == 'start' else 'stop_bot'
        StateManager.send_command(device_name, cmd_type, {})

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/trigger', methods=['POST'])
def send_trigger_command():
    """Send trigger command to device(s)"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        apply_mode = data.get('apply_mode', 'current')
        command = data.get('command')

        if not command:
            return jsonify({
                'success': False,
                'error': 'Missing command name'
            }), 400

        # Handle start_stop separately - toggle based on current state
        if command == 'start_stop':
            if apply_mode == 'all':
                # Apply to all devices
                all_bots = StateManager.get_all_bots()
                for bot in all_bots:
                    # Send stop to running bots, start to stopped bots
                    cmd_type = 'stop_bot' if bot['is_running'] else 'start_bot'
                    StateManager.send_command(bot['device_name'], cmd_type, {})
            else:
                # Apply to specific device
                if not device_name:
                    return jsonify({
                        'success': False,
                        'error': 'device_name required for current mode'
                    }), 400

                # Get current state to determine start or stop
                state = StateManager.get_device_state(device_name)
                if state:
                    cmd_type = 'stop_bot' if state['is_running'] else 'start_bot'
                    StateManager.send_command(device_name, cmd_type, {})

        else:
            # Handle other commands - load from config
            try:
                from core.config_loader import load_config
                config = load_config()
                commands_config = config.get('commands', [])
            except Exception:
                commands_config = []

            # Find command in config
            command_config = None
            for cmd in commands_config:
                if cmd.get('id') == command:
                    command_config = cmd
                    break

            if not command_config or 'command_type' not in command_config:
                return jsonify({
                    'success': False,
                    'error': f'Unknown command: {command}'
                }), 400

            command_data = {'type': command_config['command_type'], 'name': command}

            if apply_mode == 'all':
                # Apply to all running devices
                running_bots = StateManager.get_all_running_bots()
                for bot in running_bots:
                    StateManager.send_command(
                        bot['device_name'],
                        command_data['type'],
                        {'name': command_data['name']}
                    )
            else:
                # Apply to specific device
                if not device_name:
                    return jsonify({
                        'success': False,
                        'error': 'device_name required for current mode'
                    }), 400

                StateManager.send_command(
                    device_name,
                    command_data['type'],
                    {'name': command_data['name']}
                )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command/ldplayer', methods=['POST'])
def send_ldplayer_command():
    """Send LDPlayer command to device(s)"""
    try:
        data = request.json
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        device_name = data.get('device_name')
        apply_mode = data.get('apply_mode', 'current')
        command = data.get('command')

        if not command:
            return jsonify({
                'success': False,
                'error': 'Missing command name'
            }), 400

        # Map command names to command types
        command_map = {
            'ld_start': 'ld_start',
            'ld_stop': 'ld_stop',
            'ld_reboot': 'ld_reboot',
            'app_start': 'app_start',
            'app_stop': 'app_stop'
        }

        if command not in command_map:
            return jsonify({
                'success': False,
                'error': f'Unknown LDPlayer command: {command}'
            }), 400

        cmd_type = command_map[command]

        if apply_mode == 'all':
            # Apply to all devices (running or not)
            all_bots = StateManager.get_all_bots()
            for bot in all_bots:
                StateManager.send_command(bot['device_name'], cmd_type, {})
        else:
            # Apply to specific device
            if not device_name:
                return jsonify({
                    'success': False,
                    'error': 'device_name required for current mode'
                }), 400

            StateManager.send_command(device_name, cmd_type, {})

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# WEBSOCKET HANDLERS
# =============================================================================

# Global state for screenshot monitoring
screenshot_monitor_running = False
screenshot_fps = 5  # Default 5 FPS

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    sid = getattr(request, 'sid', 'unknown')
    print(f'Client connected: {sid}')
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    sid = getattr(request, 'sid', 'unknown')
    print(f'Client disconnected: {sid}')

@socketio.on('set_fps')
def handle_fps_change(data):
    """Handle FPS setting change from client"""
    global screenshot_fps
    try:
        fps = int(data.get('fps', 5))
        screenshot_fps = max(1, min(fps, 30))  # Clamp between 1-30 FPS
        print(f'Screenshot FPS set to: {screenshot_fps}')
        emit('fps_updated', {'fps': screenshot_fps})
    except Exception as e:
        print(f'Error setting FPS: {e}')

def screenshot_monitor_thread():
    """Background thread to monitor database for screenshot changes and push to clients

    This runs continuously and pushes screenshot updates via WebSocket when they change.
    Provides near-real-time live feed to all connected web clients.

    Optimization: Sends full screenshots at high FPS, previews at reduced rate (1/3 FPS).
    """
    global screenshot_monitor_running, screenshot_fps

    last_screenshots = {}  # {device_name: screenshot_timestamp}
    last_preview_send = {}  # {device_name: time.time()} - throttle preview sends
    preview_interval = 1.0  # Send previews at most once per second

    while screenshot_monitor_running:
        try:
            sleep_interval = 1.0 / screenshot_fps
            current_time = time.time()

            # Get all bots
            all_bots = StateManager.get_all_bots()

            for bot in all_bots:
                device_name = bot['device_name']
                screenshot_timestamp = bot.get('screenshot_timestamp')

                # Check if screenshot changed
                if last_screenshots.get(device_name) != screenshot_timestamp:
                    last_screenshots[device_name] = screenshot_timestamp

                    # Get screenshot and push to clients
                    screenshot = StateManager.get_device_screenshot(device_name)
                    if screenshot is not None:
                        try:
                            # Convert color space for web display
                            if len(screenshot.shape) == 3:
                                if screenshot.shape[2] == 4:
                                    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGB)
                                elif screenshot.shape[2] == 3:
                                    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

                            img = Image.fromarray(screenshot)

                            # Encode full-size as JPEG for main display
                            buffer = io.BytesIO()
                            img.save(buffer, format='JPEG', quality=85, optimize=True)
                            buffer.seek(0)
                            base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

                            # Check if we should include preview (throttled)
                            last_preview = last_preview_send.get(device_name, 0)
                            include_preview = (current_time - last_preview) >= preview_interval

                            message = {
                                'device_name': device_name,
                                'screenshot': f'data:image/jpeg;base64,{base64_data}',
                                'timestamp': str(screenshot_timestamp),
                                'width': screenshot.shape[1],
                                'height': screenshot.shape[0]
                            }

                            if include_preview:
                                # Encode small preview (85x150) for preview panels
                                preview_img = img.resize((85, 150), Image.Resampling.LANCZOS)
                                preview_buffer = io.BytesIO()
                                preview_img.save(preview_buffer, format='JPEG', quality=60, optimize=True)
                                preview_buffer.seek(0)
                                preview_base64 = base64.b64encode(preview_buffer.getvalue()).decode('utf-8')
                                message['preview'] = f'data:image/jpeg;base64,{preview_base64}'
                                last_preview_send[device_name] = current_time

                            # Push to all connected clients
                            socketio.emit('screenshot_update', message)
                        except Exception as e:
                            print(f'Error encoding screenshot for {device_name}: {e}')

            # Sleep based on FPS setting
            time.sleep(sleep_interval)

        except Exception as e:
            print(f'Screenshot monitor error: {e}')
            time.sleep(1)

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Load app name from config
    app_name = "Bot"
    try:
        from core.config_loader import load_config
        config = load_config()
        app_name = config.get('app_name', 'Bot')
    except:
        pass

    print("="*60)
    print(f"{app_name} Web Remote - Starting Server")
    print("="*60)
    print(f"\nServer will be accessible at:")
    print(f"  - Local:   http://localhost:5000")
    print(f"  - Network: http://<your-ip>:5000")
    print(f"\nFeatures:")
    print(f"  - WebSocket live feed at {screenshot_fps} FPS")
    print(f"  - JPEG compression for faster updates")
    print(f"\nPress Ctrl+C to stop the server\n")
    print("="*60)

    # Start screenshot monitor thread
    screenshot_monitor_running = True
    monitor_thread = threading.Thread(
        target=screenshot_monitor_thread,
        daemon=True,
        name="ScreenshotMonitor"
    )
    monitor_thread.start()
    print("Screenshot monitor thread started")

    # Run server with WebSocket support
    # Use socketio.run instead of app.run for WebSocket functionality
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
