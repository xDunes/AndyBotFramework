"""
Unified Bot Launcher - Start any game bot with a single script

This script dynamically loads game modules from the games/ directory,
eliminating the need for separate bot entry points per game.

Usage:
    python start_bot.py                              # Interactive mode
    python start_bot.py -g <game> -d <device> [options]
    python start_bot.py --game <game> --device <device> [options]

Examples:
    python start_bot.py                               # Interactive selection
    python start_bot.py -g apex_girl -d Gelvil
    python start_bot.py -g apex_girl -d Gelvil --no-auto-start-bot
    python start_bot.py -g apex_girl -d Gelvil --no-auto-start-device
    python start_bot.py --game template --device Device1
    python start_bot.py --list-games

Options:
    -g, --game              Game module name (folder in games/)
    -d, --device            Device name (must exist in master.conf)
    --no-auto-start-bot     Disable auto-starting the bot on launch
    --no-auto-start-device  Disable auto-launching LDPlayer device
    -l, --list-games        List available games and exit
    -h, --help              Show this help message

If no arguments are provided, interactive mode walks you through selection.
"""

import sys
import os
import argparse
import importlib
import tkinter as tk

# Core framework
from core import load_config, load_master_config, BotController, launch_devices_if_needed
from core.utils import build_function_map, build_command_map, set_gui_instance, set_state_manager, set_log_db

# Generic GUI
from gui import BotGUI


def get_available_games():
    """Get list of available game modules in games/ directory

    Returns:
        list: Game folder names that contain functions.py
    """
    games_dir = os.path.join(os.path.dirname(__file__), 'games')
    games = []

    if not os.path.exists(games_dir):
        return games

    for item in os.listdir(games_dir):
        item_path = os.path.join(games_dir, item)
        # Check if it's a directory with functions.py
        if os.path.isdir(item_path):
            functions_file = os.path.join(item_path, 'functions.py')
            if os.path.exists(functions_file):
                games.append(item)

    return sorted(games)


def load_game_modules(game_name):
    """Dynamically load game functions and commands modules

    Args:
        game_name: Name of the game folder in games/

    Returns:
        tuple: (functions_module, commands_module, findimg_path)

    Raises:
        ImportError: If game modules cannot be loaded
    """
    # Import functions module (required)
    functions_module = importlib.import_module(f'games.{game_name}.functions')

    # Import commands module (optional - create empty if not exists)
    try:
        commands_module = importlib.import_module(f'games.{game_name}.commands')
    except ImportError:
        # Create a dummy module with no commands
        import types
        commands_module = types.ModuleType(f'games.{game_name}.commands')

    # Build findimg path
    findimg_path = os.path.join(os.path.dirname(__file__), 'games', game_name, 'findimg')

    return functions_module, commands_module, findimg_path


def format_game_name(game_name):
    """Format game name for display (snake_case to Title Case)

    Args:
        game_name: Game folder name (e.g., "apex_girl")

    Returns:
        str: Formatted name (e.g., "Apex Girl")
    """
    return ' '.join(word.capitalize() for word in game_name.split('_'))


def interactive_select(prompt, options, format_func=None):
    """Interactive selection from a list of options

    Args:
        prompt: Question to ask the user
        options: List of options to choose from
        format_func: Optional function to format display names

    Returns:
        str: Selected option value
    """
    print(f"\n{prompt}")
    print("-" * 40)

    for i, option in enumerate(options, 1):
        display = format_func(option) if format_func else option
        print(f"  {i}. {display}")

    print()

    while True:
        try:
            choice = input("Enter number: ").strip()
            if not choice:
                continue
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)


def interactive_mode(master_config):
    """Run interactive selection for game and device

    Args:
        master_config: Master configuration dictionary (from master.conf)

    Returns:
        tuple: (game_name, device_name)
    """
    print("\n" + "=" * 50)
    print("       Andy Bot Framework - Interactive Mode")
    print("=" * 50)

    # Select game
    games = get_available_games()
    if not games:
        print("\nERROR: No games found in games/ directory")
        print("Create a game folder with functions.py to get started.")
        sys.exit(1)

    game_name = interactive_select(
        "Select a game:",
        games,
        format_func=format_game_name
    )
    print(f"  → Selected: {format_game_name(game_name)}")

    # Select device (from master.conf)
    devices = list(master_config.get('devices', {}).keys())
    if not devices:
        print("\nERROR: No devices found in master.conf")
        print("Add devices to master.conf to continue.")
        sys.exit(1)

    device_name = interactive_select(
        "Select a device:",
        devices
    )
    print(f"  → Selected: {device_name}")

    print("\n" + "-" * 50)
    print(f"Starting {format_game_name(game_name)} Bot for {device_name}...")
    print("-" * 50 + "\n")

    return game_name, device_name


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Unified Bot Launcher - Start any game bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_bot.py -g apex_girl -d Gelvil
  python start_bot.py -g apex_girl -d Gelvil --no-auto-start-bot
  python start_bot.py -g apex_girl -d Gelvil --no-auto-start-device
  python start_bot.py --game template --device Device1
  python start_bot.py --list-games
        """
    )

    parser.add_argument('-g', '--game', type=str,
                        help='Game module name (folder in games/)')
    parser.add_argument('-d', '--device', type=str,
                        help='Device name (must exist in master.conf)')
    parser.add_argument('--no-auto-start-bot', action='store_true',
                        help='Disable auto-starting the bot on launch')
    parser.add_argument('--no-auto-start-device', action='store_true',
                        help='Disable auto-launching LDPlayer device')
    parser.add_argument('-l', '--list-games', action='store_true',
                        help='List available games and exit')

    args = parser.parse_args()

    # Handle --list-games
    if args.list_games:
        games = get_available_games()
        if games:
            print("Available games:")
            for game in games:
                print(f"  - {game}")
        else:
            print("No games found in games/ directory")
        sys.exit(0)

    # Load master config early (needed for device list in interactive mode)
    master_config = load_master_config()

    # Interactive mode if no game/device specified
    if not args.game or not args.device:
        game_name, device_name = interactive_mode(master_config)
        auto_start_bot = not args.no_auto_start_bot
    else:
        game_name = args.game
        device_name = args.device
        auto_start_bot = not args.no_auto_start_bot

        # Validate game exists
        available_games = get_available_games()
        if game_name not in available_games:
            print(f"ERROR: Game '{game_name}' not found")
            print(f"Available games: {', '.join(available_games)}")
            sys.exit(1)

        # Validate device exists in master config
        if device_name not in master_config.get('devices', {}):
            print(f"ERROR: Device '{device_name}' not found in master.conf")
            print(f"Available devices: {', '.join(master_config.get('devices', {}).keys())}")
            sys.exit(1)

    # Auto-launch LDPlayer device (default behavior, disabled with --no-auto-start-device)
    if not args.no_auto_start_device:
        print(f"Checking if device '{device_name}' needs to be launched...")
        launch_devices_if_needed(
            device_names=[device_name],
            master_config=master_config,
            stagger_delay=5.0,
            boot_wait=45.0,
            log_func=print
        )

    # Load merged config (master + game-specific)
    config = load_config(game_name)

    # Load game modules dynamically
    try:
        game_functions, game_commands, findimg_path = load_game_modules(game_name)
    except ImportError as e:
        print(f"ERROR: Failed to load game modules for '{game_name}': {e}")
        sys.exit(1)

    # Build function and command maps dynamically from config
    function_map = build_function_map(config, game_functions)
    command_handlers = build_command_map(config, game_commands)

    # Get do_recover function if it exists
    do_recover_func = getattr(game_functions, 'do_recover', None)

    # Create bot controller (handles bot lifecycle)
    controller = BotController(
        device_name=device_name,
        config=config,
        function_map=function_map,
        command_handlers=command_handlers,
        do_recover_func=do_recover_func,
        findimg_path=findimg_path
    )

    # Create GUI (handles display only)
    root = tk.Tk()
    gui = BotGUI(root, device_name, config=config, enable_remote=False)
    gui.set_controller(controller)
    controller.set_gui(gui)

    # Set window title
    display_name = format_game_name(game_name)
    root.title(f"{display_name} Bot - {device_name}")

    # Register logging components with core
    set_gui_instance(gui)
    if gui.state_manager:
        set_state_manager(gui.state_manager)
    if gui.log_db:
        set_log_db(gui.log_db, gui.debug.get)

    # Log startup message
    gui.log(f"{display_name} Bot started for device: {device_name}")
    if auto_start_bot:
        gui.log("Auto-starting bot...")
    else:
        gui.log("Use checkboxes to enable functions, then click Start")

    # Auto-start bot if requested (default behavior)
    if auto_start_bot:
        root.after(100, gui.start_bot)

    # Start the GUI main loop (no remote monitoring in local mode)
    root.mainloop()


if __name__ == "__main__":
    main()
