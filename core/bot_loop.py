"""
Bot Loop - Generic bot execution loop

This module provides the main execution loop for game bots.
The loop is game-agnostic and receives the function map as a parameter.
"""

import time

from .bot import BOT, BotStoppedException
from .android import Android, AndroidStoppedException
from .config_loader import get_serial, format_cooldown_time


def run_bot_loop(gui, function_map, config, command_handlers=None, fix_recover_func=None, findimg_path=None):
    """Main bot execution loop with GUI integration

    This is the core bot loop that runs continuously while the bot is active.
    It executes enabled functions in sequence, handles commands, manages cooldowns,
    and processes remote commands.

    Loop behavior:
    1. Execute all enabled functions in sequence
    2. Check and execute any pending command triggers
    3. Run Fix/Recover function if enabled
    4. Sleep for configured duration
    5. Repeat

    Args:
        gui: BotGUI instance containing configuration and state
        function_map: Dict mapping function names to callables
                     e.g., {"doConcert": do_concert, "doRally": do_rally}
        config: Configuration dictionary with cooldowns, auto_uncheck, etc.
        command_handlers: Optional dict mapping command IDs to handler functions
                          e.g., {"min_fans": handle_min_fans, "max_fans": handle_max_fans}
        fix_recover_func: Optional function to call for fix/recover operations
                         Signature: fix_recover_func(bot, device)
        findimg_path: Path to the findimg folder containing needle images
                     e.g., "games/apex_girl/findimg"

    Note:
        - Pressing Ctrl key during loop skips remaining functions for that iteration
        - BotStoppedException is raised when Stop button is clicked
        - Cooldowns prevent functions from running too frequently
    """
    # Import here to avoid circular imports and make keyboard optional
    try:
        import keyboard
        has_keyboard = True
    except ImportError:
        has_keyboard = False

    # Get device from GUI (set by start_bot.py)
    device = gui.device_name

    # Initialize Android and Bot
    try:
        andy = Android(get_serial(device), device_name=device)
        andy.set_gui(gui)

        gui.root.after(0, gui._on_settings_change)

    except AndroidStoppedException:
        # Error already logged by android.py with available serials
        _cleanup_on_error(gui)
        return
    except Exception as error:
        gui.update_status("Error", f"Error: {error}")
        gui.log(f"ERROR: {error}")
        _cleanup_on_error(gui)
        return

    bot = BOT(andy, findimg_path=findimg_path)
    bot.set_gui(gui)
    bot.should_stop = False

    # Store bot and android references on GUI for access by functions
    gui.bot = bot
    gui.andy = andy
    gui.device = device

    # Get configuration for loop behavior
    auto_uncheck = set(config.get('auto_uncheck', []))
    function_cooldowns = config.get('cooldowns', {})

    # Track last run time for each function (float timestamps)
    gui.last_run_times = {func_name: 0.0 for func_name in function_map.keys()}

    # Main loop
    while gui.is_running:
        try:
            # Get sleep time from GUI settings
            sleep_time = _get_sleep_time(gui)

            # Track if any function executed this iteration
            any_function_executed = False

            # Priority 1: Execute enabled functions
            for func_name, func in function_map.items():
                # Check if Control key is held down before each function
                if has_keyboard and keyboard.is_pressed('ctrl'):
                    if gui.function_states.get(func_name) and gui.function_states[func_name].get():
                        gui.update_status("Running", f"CTRL held - skipping {func_name}")
                    break

                # Update cooldown display for this function
                cooldown = function_cooldowns.get(func_name, 0)
                if cooldown > 0 and func_name in gui.cooldown_labels:
                    _update_cooldown_display(gui, func_name, cooldown)

                # Check if function is enabled
                if func_name not in gui.function_states:
                    continue
                if not gui.function_states[func_name].get():
                    continue

                # Check cooldown
                if cooldown > 0:
                    current_time = time.time()
                    time_since_last_run = current_time - gui.last_run_times.get(func_name, 0)
                    if time_since_last_run < cooldown:
                        continue

                gui.update_status("Running", func_name)

                try:
                    # Call function
                    result = _execute_function(func, bot, device, gui, func_name)
                    any_function_executed = True

                    # Update last run time only if function didn't explicitly fail
                    # Functions return False to indicate failure/abort - cooldown should NOT start
                    # Functions return None (no return) or truthy value - cooldown starts normally
                    if result is not False:
                        gui.last_run_times[func_name] = time.time()

                    # Auto-uncheck if function returns True (signals completion)
                    # Functions in auto_uncheck list will uncheck when they return truthy
                    if result and (result is True or func_name in auto_uncheck):
                        gui.function_states[func_name].set(False)
                        gui.log(f"{func_name} completed - unchecked")

                except BotStoppedException:
                    gui.log(f"Stopped during {func_name}")
                    raise
                except AndroidStoppedException:
                    gui.log(f"Android connection lost during {func_name}")
                    raise
                except Exception as e:
                    gui.log(f"ERROR in {func_name}: {e}")
                    gui.update_status("Running", f"Error in {func_name}")
                    time.sleep(1)

            # If no functions executed, take a screenshot to keep web feed updated
            if not any_function_executed:
                try:
                    bot.screenshot()
                except Exception:
                    pass  # Ignore screenshot errors when idle

            # Priority 2: Check for command triggers
            if command_handlers:
                _handle_commands(gui, bot, command_handlers)

            # Priority 3: Run Fix/Recover if enabled
            if has_keyboard and keyboard.is_pressed('ctrl'):
                gui.update_status("Running", "CTRL held - skipping Fix")
            elif hasattr(gui, 'fix_enabled') and gui.fix_enabled.get():
                _run_fix_recover(gui, bot, device, fix_recover_func)

            # Sleep if configured
            if sleep_time > 0:
                if has_keyboard and keyboard.is_pressed('ctrl'):
                    gui.update_status("Running", "CTRL held - override active")
                else:
                    gui.update_status("Running", f"Sleeping {sleep_time}s")
                time.sleep(sleep_time)

        except BotStoppedException:
            gui.log("Bot stopped by user")
            break
        except AndroidStoppedException as e:
            gui.log(f"Android connection stopped: {e}")
            break
        except Exception as e:
            if not gui.is_running:
                gui.log(f"ERROR during shutdown: {e}")
                break
            gui.update_status("Error", str(e))
            gui.log(f"ERROR: {e}")
            time.sleep(1)

    # Cleanup
    _cleanup_on_stop(gui)


def _cleanup_on_error(gui):
    """Clean up GUI state after connection error"""
    gui.is_running = False
    gui.root.after(0, lambda: gui.toggle_button.config(text="Start"))
    gui.root.after(0, gui._update_status_label)
    gui.root.after(0, gui._on_settings_change)
    if hasattr(gui, 'stop_live_screenshot_updater'):
        gui.stop_live_screenshot_updater()


def _cleanup_on_stop(gui):
    """Clean up GUI state when bot stops"""
    gui.update_status("Stopped", "")
    gui.is_running = False
    gui.root.after(0, lambda: gui.toggle_button.config(text="Start"))
    gui.root.after(0, gui._update_status_label)
    try:
        gui.root.after(0, gui._update_full_state)
    except Exception as e:
        gui.log(f"[System] Error updating state on stop: {e}")


def _handle_commands(gui, bot, command_handlers):
    """Handle triggered commands"""
    for command_id, handler in command_handlers.items():
        trigger_key = f'{command_id}'
        if hasattr(gui, 'command_triggers') and gui.command_triggers.get(trigger_key):
            gui.command_triggers[trigger_key] = False
            gui.update_status("Running", f"{command_id} (command)")
            try:
                handler(bot, gui)
            except BotStoppedException:
                gui.log(f"Stopped during {command_id} command")
                raise
            except Exception as e:
                gui.log(f"ERROR in {command_id} command: {e}")


def _get_sleep_time(gui):
    """Get sleep time from GUI settings"""
    try:
        if hasattr(gui, 'sleep_time'):
            return float(gui.sleep_time.get())
    except (ValueError, AttributeError):
        pass
    return 0


def _update_cooldown_display(gui, func_name, cooldown):
    """Update cooldown label display for a function"""
    current_time = time.time()
    time_since_last_run = current_time - gui.last_run_times.get(func_name, 0)
    remaining = int(cooldown - time_since_last_run)

    if remaining > 0:
        gui.cooldown_labels[func_name].config(text=f"({format_cooldown_time(remaining)})")
    else:
        gui.cooldown_labels[func_name].config(text="")


def _execute_function(func, bot, device, gui, func_name):
    """Execute a function with appropriate parameters"""
    import inspect
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Build kwargs based on what the function accepts
    kwargs = {}
    if 'bot' in params:
        kwargs['bot'] = bot
    if 'device' in params:
        kwargs['device'] = device
    if 'gui' in params:
        kwargs['gui'] = gui

    # Handle special parameters for specific functions
    if 'stop' in params and hasattr(gui, 'studio_stop'):
        try:
            kwargs['stop'] = int(gui.studio_stop.get())
        except (ValueError, AttributeError):
            kwargs['stop'] = 6

    return func(**kwargs)


def _run_fix_recover(gui, bot, device, fix_recover_func):
    """Run the fix/recover function if provided

    Args:
        gui: BotGUI instance
        bot: BOT instance
        device: Device name string
        fix_recover_func: Function to call, signature: func(bot, device)
    """
    if fix_recover_func is None:
        return

    try:
        gui.update_status("Running", "Fix/Recover")
        fix_recover_func(bot, device)
    except BotStoppedException:
        gui.log("Stopped during Fix/Recover")
        raise
    except AndroidStoppedException:
        gui.log("Android connection lost during Fix/Recover")
        raise
    except Exception as e:
        gui.log(f"ERROR in Fix/Recover: {e}")
