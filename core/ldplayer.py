"""
LDPlayer Console Interface - Wrapper for ldconsole.exe CLI commands

Provides a Python interface to control LDPlayer emulator instances via CLI.
Based on: https://www.ldplayer.net/blog/introduction-to-ldplayer-command-line-interface.html

Usage:
    from ldplayer import LDPlayer

    # Initialize with path to LDPlayer installation
    ld = LDPlayer("D:\\LDPlayer\\LDPlayer9\\")

    # Or initialize from master.conf
    ld = LDPlayer.from_config()

    # Launch instance by index
    ld.launch(index=0)

    # Check if instance is running
    if ld.is_running(index=0):
        print("Instance 0 is running")

    # Quit instance
    ld.quit(index=0)
"""

import subprocess
import os
import json
from typing import Optional, List, Dict, Any, Union


class LDPlayer:
    """Interface for controlling LDPlayer emulator instances via CLI

    Attributes:
        ldplayer_path: Path to LDPlayer installation directory
        ldconsole_path: Full path to ldconsole.exe
    """

    def __init__(self, ldplayer_path: str):
        """Initialize LDPlayer controller

        Args:
            ldplayer_path: Path to LDPlayer installation directory
                          (e.g., "D:\\LDPlayer\\LDPlayer9\\")

        Raises:
            FileNotFoundError: If ldconsole.exe not found at specified path
        """
        self.ldplayer_path = ldplayer_path
        self.ldconsole_path = os.path.join(ldplayer_path, 'ldconsole.exe')

        if not os.path.exists(self.ldconsole_path):
            raise FileNotFoundError(f"ldconsole.exe not found at: {self.ldconsole_path}")

    @classmethod
    def from_config(cls, config_path: Optional[str] = None) -> 'LDPlayer':
        """Create LDPlayer instance from master.conf

        Args:
            config_path: Path to config file (defaults to master.conf)

        Returns:
            LDPlayer instance configured from master.conf

        Raises:
            FileNotFoundError: If config file not found
            KeyError: If LDPlayerPath not in config
        """
        if config_path is None:
            # Config is at project root, not inside core/
            project_root = os.path.dirname(os.path.dirname(__file__))
            config_path = os.path.join(project_root, 'master.conf')

        with open(config_path, 'r') as f:
            config = json.load(f)

        ldplayer_path = config.get('LDPlayerPath')
        if not ldplayer_path:
            raise KeyError("LDPlayerPath not found in config")

        return cls(ldplayer_path)

    def _run_command(self, args: List[str], wait: bool = True,
                     timeout: Optional[float] = None) -> Optional[str]:
        """Execute ldconsole command

        Args:
            args: Command arguments (without ldconsole.exe)
            wait: If True, wait for command to complete and return output
            timeout: Timeout in seconds (only used if wait=True)

        Returns:
            Command output if wait=True, None otherwise

        Raises:
            subprocess.TimeoutExpired: If command times out
            subprocess.CalledProcessError: If command fails
        """
        cmd = [self.ldconsole_path] + args

        if wait:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip()
        else:
            subprocess.Popen(cmd)
            return None

    # ========================================================================
    # Instance Control
    # ========================================================================

    def launch(self, index: Optional[int] = None, name: Optional[str] = None,
               wait: bool = False) -> Optional[str]:
        """Launch LDPlayer instance

        Args:
            index: Instance index (0-based)
            name: Instance name (alternative to index)
            wait: If True, wait for launch to complete

        Returns:
            Command output if wait=True, None otherwise

        Raises:
            ValueError: If neither index nor name provided
        """
        args = ['launch']
        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        return self._run_command(args, wait=wait)

    def quit(self, index: Optional[int] = None, name: Optional[str] = None,
             wait: bool = False) -> Optional[str]:
        """Quit (close) LDPlayer instance

        Args:
            index: Instance index (0-based)
            name: Instance name (alternative to index)
            wait: If True, wait for quit to complete

        Returns:
            Command output if wait=True, None otherwise

        Raises:
            ValueError: If neither index nor name provided
        """
        args = ['quit']
        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        return self._run_command(args, wait=wait)

    def quitall(self, wait: bool = False) -> Optional[str]:
        """Quit all running LDPlayer instances

        Args:
            wait: If True, wait for command to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        return self._run_command(['quitall'], wait=wait)

    def reboot(self, index: Optional[int] = None, name: Optional[str] = None,
               wait: bool = False) -> Optional[str]:
        """Reboot LDPlayer instance

        Args:
            index: Instance index (0-based)
            name: Instance name (alternative to index)
            wait: If True, wait for reboot to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['reboot']
        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        return self._run_command(args, wait=wait)

    # ========================================================================
    # Instance Information
    # ========================================================================

    def list_instances(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """List all LDPlayer instances with their status

        Args:
            timeout: Maximum time to wait for response in seconds (default 5s)

        Returns:
            List of dicts with instance info:
            - index: Instance index
            - name: Instance name
            - top_window_handle: Top window handle
            - bind_window_handle: Bind window handle
            - android_started: Whether Android is started (-1=no, 1=yes)
            - pid: Process ID (-1 if not running)
            - vbox_pid: VirtualBox process ID
        """
        output = self._run_command(['list2'], wait=True, timeout=timeout)

        instances = []
        if output:
            for line in output.split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 7:
                        instances.append({
                            'index': int(parts[0]),
                            'name': parts[1],
                            'top_window_handle': int(parts[2]),
                            'bind_window_handle': int(parts[3]),
                            'android_started': int(parts[4]) == 1,
                            'pid': int(parts[5]),
                            'vbox_pid': int(parts[6])
                        })

        return instances

    def is_running(self, index: Optional[int] = None,
                   name: Optional[str] = None) -> bool:
        """Check if an LDPlayer instance is running

        Args:
            index: Instance index (0-based)
            name: Instance name (alternative to index)

        Returns:
            True if instance is running (Android started), False otherwise

        Raises:
            ValueError: If neither index nor name provided
        """
        if index is None and name is None:
            raise ValueError("Either index or name must be provided")

        instances = self.list_instances()

        for instance in instances:
            if index is not None and instance['index'] == index:
                return instance['android_started'] and instance['pid'] != -1
            if name is not None and instance['name'] == name:
                return instance['android_started'] and instance['pid'] != -1

        return False

    def get_instance_info(self, index: Optional[int] = None,
                          name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get information about a specific instance

        Args:
            index: Instance index (0-based)
            name: Instance name (alternative to index)

        Returns:
            Dict with instance info, or None if not found
        """
        if index is None and name is None:
            raise ValueError("Either index or name must be provided")

        instances = self.list_instances()

        for instance in instances:
            if index is not None and instance['index'] == index:
                return instance
            if name is not None and instance['name'] == name:
                return instance

        return None

    # ========================================================================
    # Instance Management
    # ========================================================================

    def add(self, name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Create a new LDPlayer instance

        Args:
            name: Name for the new instance (optional)
            wait: If True, wait for creation to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['add']
        if name:
            args.extend(['--name', name])

        return self._run_command(args, wait=wait)

    def copy(self, from_index: Optional[int] = None, from_name: Optional[str] = None,
             new_name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Copy an existing LDPlayer instance

        Args:
            from_index: Index of instance to copy
            from_name: Name of instance to copy (alternative to from_index)
            new_name: Name for the new copy (optional)
            wait: If True, wait for copy to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['copy']
        if new_name:
            args.extend(['--name', new_name])

        if from_index is not None:
            args.extend(['--from', str(from_index)])
        elif from_name is not None:
            args.extend(['--from', from_name])
        else:
            raise ValueError("Either from_index or from_name must be provided")

        return self._run_command(args, wait=wait)

    def remove(self, index: Optional[int] = None, name: Optional[str] = None,
               wait: bool = True) -> Optional[str]:
        """Delete an LDPlayer instance

        Args:
            index: Instance index to delete
            name: Instance name to delete (alternative to index)
            wait: If True, wait for deletion to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['remove']
        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        return self._run_command(args, wait=wait)

    def rename(self, new_name: str, index: Optional[int] = None,
               old_name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Rename an LDPlayer instance

        Args:
            new_name: New name for the instance
            index: Instance index to rename
            old_name: Current name of instance (alternative to index)
            wait: If True, wait for rename to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['rename', '--title', new_name]
        if index is not None:
            args.extend(['--index', str(index)])
        elif old_name is not None:
            args.extend(['--name', old_name])
        else:
            raise ValueError("Either index or old_name must be provided")

        return self._run_command(args, wait=wait)

    # ========================================================================
    # Instance Configuration
    # ========================================================================

    def modify(self, index: Optional[int] = None, name: Optional[str] = None,
               resolution: Optional[str] = None, cpu: Optional[int] = None,
               memory: Optional[int] = None, manufacturer: Optional[str] = None,
               model: Optional[str] = None, phone_number: Optional[str] = None,
               imei: Optional[str] = None, imsi: Optional[str] = None,
               sim_serial: Optional[str] = None, android_id: Optional[str] = None,
               mac: Optional[str] = None, auto_rotate: Optional[bool] = None,
               lock_window: Optional[bool] = None,
               wait: bool = True) -> Optional[str]:
        """Modify LDPlayer instance properties

        Args:
            index: Instance index
            name: Instance name (alternative to index)
            resolution: Resolution as "width,height,dpi" (e.g., "1280,720,240")
            cpu: Number of CPU cores (1-4)
            memory: Memory in MB (512-8192)
            manufacturer: Device manufacturer
            model: Device model
            phone_number: Phone number
            imei: IMEI number
            imsi: IMSI number
            sim_serial: SIM serial number
            android_id: Android ID
            mac: MAC address
            auto_rotate: Enable auto-rotate
            lock_window: Lock window size
            wait: If True, wait for modification to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['modify']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        if resolution:
            args.extend(['--resolution', resolution])
        if cpu is not None:
            args.extend(['--cpu', str(cpu)])
        if memory is not None:
            args.extend(['--memory', str(memory)])
        if manufacturer:
            args.extend(['--manufacturer', manufacturer])
        if model:
            args.extend(['--model', model])
        if phone_number:
            args.extend(['--pnumber', phone_number])
        if imei:
            args.extend(['--imei', imei])
        if imsi:
            args.extend(['--imsi', imsi])
        if sim_serial:
            args.extend(['--simserial', sim_serial])
        if android_id:
            args.extend(['--androidid', android_id])
        if mac:
            args.extend(['--mac', mac])
        if auto_rotate is not None:
            args.extend(['--autorotate', '1' if auto_rotate else '0'])
        if lock_window is not None:
            args.extend(['--lockwindow', '1' if lock_window else '0'])

        return self._run_command(args, wait=wait)

    # ========================================================================
    # Application Management
    # ========================================================================

    def install_app(self, apk_path: Optional[str] = None,
                    package_name: Optional[str] = None,
                    index: Optional[int] = None, name: Optional[str] = None,
                    wait: bool = True) -> Optional[str]:
        """Install an application on LDPlayer instance

        Args:
            apk_path: Path to APK file
            package_name: Package name (for Play Store install)
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for install to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['installapp']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        if apk_path:
            args.extend(['--filename', apk_path])
        elif package_name:
            args.extend(['--packagename', package_name])
        else:
            raise ValueError("Either apk_path or package_name must be provided")

        return self._run_command(args, wait=wait)

    def uninstall_app(self, package_name: str, index: Optional[int] = None,
                      name: Optional[str] = None,
                      wait: bool = True) -> Optional[str]:
        """Uninstall an application from LDPlayer instance

        Args:
            package_name: Package name to uninstall
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for uninstall to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['uninstallapp']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--packagename', package_name])

        return self._run_command(args, wait=wait)

    def run_app(self, package_name: str, index: Optional[int] = None,
                name: Optional[str] = None, wait: bool = False) -> Optional[str]:
        """Run an application on LDPlayer instance

        Args:
            package_name: Package name to run
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for app to start

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['runapp']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--packagename', package_name])

        return self._run_command(args, wait=wait)

    def kill_app(self, package_name: str, index: Optional[int] = None,
                 name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Kill (force stop) an application on LDPlayer instance

        Args:
            package_name: Package name to kill
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for app to stop

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['killapp']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--packagename', package_name])

        return self._run_command(args, wait=wait)

    # ========================================================================
    # System Properties
    # ========================================================================

    def setprop(self, key: str, value: str, index: Optional[int] = None,
                name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Set a system property on LDPlayer instance

        Args:
            key: Property key
            value: Property value
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for command to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['setprop']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--key', key, '--value', value])

        return self._run_command(args, wait=wait)

    def getprop(self, key: str, index: Optional[int] = None,
                name: Optional[str] = None) -> Optional[str]:
        """Get a system property from LDPlayer instance

        Args:
            key: Property key
            index: Instance index
            name: Instance name (alternative to index)

        Returns:
            Property value
        """
        args = ['getprop']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--key', key])

        return self._run_command(args, wait=True)

    # ========================================================================
    # ADB Commands
    # ========================================================================

    def adb(self, command: str, index: Optional[int] = None,
            name: Optional[str] = None, wait: bool = True,
            timeout: Optional[float] = None) -> Optional[str]:
        """Execute ADB command on LDPlayer instance

        Args:
            command: ADB command to execute (without 'adb' prefix)
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for command to complete
            timeout: Timeout in seconds

        Returns:
            Command output if wait=True, None otherwise

        Example:
            ld.adb("shell input tap 100 200", index=0)
        """
        args = ['adb']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--command', command])

        return self._run_command(args, wait=wait, timeout=timeout)

    # ========================================================================
    # Input Actions
    # ========================================================================

    def action(self, key: str, index: Optional[int] = None,
               name: Optional[str] = None, wait: bool = False) -> Optional[str]:
        """Execute a predefined action on LDPlayer instance

        Args:
            key: Action key (e.g., "call.shake" for shake)
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for action to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['action']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--key', key])

        return self._run_command(args, wait=wait)

    # ========================================================================
    # Backup and Restore
    # ========================================================================

    def backup(self, file_path: str, index: Optional[int] = None,
               name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Backup LDPlayer instance to file

        Args:
            file_path: Path to save backup file
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for backup to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['backup']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--file', file_path])

        return self._run_command(args, wait=wait)

    def restore(self, file_path: str, index: Optional[int] = None,
                name: Optional[str] = None, wait: bool = True) -> Optional[str]:
        """Restore LDPlayer instance from backup file

        Args:
            file_path: Path to backup file
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for restore to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['restore']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--file', file_path])

        return self._run_command(args, wait=wait)

    # ========================================================================
    # File Operations
    # ========================================================================

    def pull(self, remote_path: str, local_path: str,
             index: Optional[int] = None, name: Optional[str] = None,
             wait: bool = True) -> Optional[str]:
        """Pull file from LDPlayer instance to local machine

        Args:
            remote_path: Path on Android device
            local_path: Local destination path
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for transfer to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['pull']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--remote', remote_path, '--local', local_path])

        return self._run_command(args, wait=wait)

    def push(self, local_path: str, remote_path: str,
             index: Optional[int] = None, name: Optional[str] = None,
             wait: bool = True) -> Optional[str]:
        """Push file from local machine to LDPlayer instance

        Args:
            local_path: Local file path
            remote_path: Destination path on Android device
            index: Instance index
            name: Instance name (alternative to index)
            wait: If True, wait for transfer to complete

        Returns:
            Command output if wait=True, None otherwise
        """
        args = ['push']

        if index is not None:
            args.extend(['--index', str(index)])
        elif name is not None:
            args.extend(['--name', name])
        else:
            raise ValueError("Either index or name must be provided")

        args.extend(['--remote', remote_path, '--local', local_path])

        return self._run_command(args, wait=wait)

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def get_running_instances(self) -> List[Dict[str, Any]]:
        """Get list of all currently running instances

        Returns:
            List of instance info dicts for running instances only
        """
        return [inst for inst in self.list_instances()
                if inst['android_started'] and inst['pid'] != -1]

    def get_stopped_instances(self) -> List[Dict[str, Any]]:
        """Get list of all stopped instances

        Returns:
            List of instance info dicts for stopped instances only
        """
        return [inst for inst in self.list_instances()
                if not inst['android_started'] or inst['pid'] == -1]

    def wait_for_boot(self, index: Optional[int] = None,
                      name: Optional[str] = None,
                      timeout: float = 120.0,
                      poll_interval: float = 2.0) -> bool:
        """Wait for an instance to fully boot

        Args:
            index: Instance index
            name: Instance name (alternative to index)
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds

        Returns:
            True if instance booted successfully, False if timeout
        """
        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running(index=index, name=name):
                return True
            time.sleep(poll_interval)

        return False


# Convenience function for quick access
def get_ldplayer() -> LDPlayer:
    """Get LDPlayer instance configured from config.json

    Returns:
        LDPlayer instance
    """
    return LDPlayer.from_config()
