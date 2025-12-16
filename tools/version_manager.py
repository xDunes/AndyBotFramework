#!/usr/bin/env python3
"""
Version Manager for Apex-Girl Bot Framework

Handles automatic version tracking and changelog management.

Usage:
    python version_manager.py build              # Auto-increment build version
    python version_manager.py minor              # Increment minor version (summarizes builds)
    python version_manager.py major              # Increment major version
    python version_manager.py add "Change text"  # Add a change to current build
    python version_manager.py show               # Show current version
"""

import sys
import re
from datetime import datetime
from pathlib import Path


class VersionManager:
    def __init__(self):
        self.version_file = Path(__file__).parent / "version.py"
        self.changelog_file = Path(__file__).parent / "CHANGELOG.md"
        self.load_version()

    def load_version(self):
        """Load current version from version.py"""
        with open(self.version_file, 'r') as f:
            content = f.read()

        # Extract version info
        match = re.search(r"__version__ = ['\"](\d+)\.(\d+)\.(\d+)['\"]", content)
        if match:
            self.major = int(match.group(1))
            self.minor = int(match.group(2))
            self.build = int(match.group(3))
        else:
            raise ValueError("Could not parse version from version.py")

    def save_version(self):
        """Save version to version.py"""
        version_string = f"{self.major}.{self.minor}.{self.build}"

        content = f'''"""
Version information for Apex-Girl Bot Framework
Auto-managed by version_manager.py
"""

__version__ = "{version_string}"
__version_info__ = {{
    'major': {self.major},
    'minor': {self.minor},
    'build': {self.build}
}}

def get_version():
    """Get the current version string"""
    return __version__

def get_version_info():
    """Get version information as a dictionary"""
    return __version_info__.copy()

def get_version_tuple():
    """Get version as a tuple (major, minor, build)"""
    return (__version_info__['major'], __version_info__['minor'], __version_info__['build'])
'''

        with open(self.version_file, 'w') as f:
            f.write(content)

        print(f"✓ Updated version to {version_string}")

    def read_changelog(self):
        """Read changelog file"""
        with open(self.changelog_file, 'r', encoding='utf-8') as f:
            return f.read()

    def write_changelog(self, content):
        """Write changelog file"""
        with open(self.changelog_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_unreleased_changes(self):
        """Extract unreleased build changes from changelog"""
        content = self.read_changelog()

        # Find the [Unreleased] section
        pattern = r'\[Unreleased\]\s*\n\s*### Build Changes\s*\n(.*?)(?=\n---|\Z)'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            return []

        changes_text = match.group(1).strip()

        # Skip the comment line
        if '<!-- Automatically tracked changes' in changes_text:
            changes_text = re.sub(r'<!--.*?-->', '', changes_text, flags=re.DOTALL).strip()

        if not changes_text:
            return []

        # Parse individual changes (lines starting with -)
        changes = []
        for line in changes_text.split('\n'):
            line = line.strip()
            if line.startswith('-'):
                changes.append(line[1:].strip())

        return changes

    def increment_build(self):
        """Increment build version"""
        self.build += 1
        self.save_version()

    def increment_minor(self):
        """Increment minor version and summarize build changes"""
        # Get unreleased changes
        changes = self.get_unreleased_changes()

        if not changes:
            print("⚠ Warning: No build changes to summarize")
            response = input("Continue with minor version bump? (y/n): ")
            if response.lower() != 'y':
                print("Cancelled")
                return

        # Increment version
        self.minor += 1
        self.build = 0
        self.save_version()

        # Update changelog
        self.add_minor_release(changes)

    def increment_major(self):
        """Increment major version"""
        # Increment version
        self.major += 1
        self.minor = 0
        self.build = 0
        self.save_version()

        # Update changelog
        self.add_major_release()

    def add_change(self, change_text):
        """Add a change entry to unreleased section"""
        content = self.read_changelog()

        # Auto-increment build version
        old_version = f"{self.major}.{self.minor}.{self.build}"
        self.increment_build()
        new_version = f"{self.major}.{self.minor}.{self.build}"

        # Find the [Unreleased] section
        pattern = r'(\[Unreleased\]\s*\n\s*### Build Changes\s*\n)(.*?)((?=\n---)|(?=\Z))'

        def replacer(match):
            header = match.group(1)
            existing = match.group(2)
            footer = match.group(3)

            # Remove the comment if it exists
            existing = re.sub(r'<!--.*?-->\s*\n?', '', existing, flags=re.DOTALL)

            # Add new change
            date = datetime.now().strftime("%Y-%m-%d")
            new_entry = f"- [{new_version}] {date} - {change_text}\n"

            return header + new_entry + existing + footer

        content = re.sub(pattern, replacer, content, flags=re.DOTALL)
        self.write_changelog(content)

        print(f"✓ Added change (version bumped: {old_version} → {new_version})")
        print(f"  {change_text}")

    def add_minor_release(self, changes):
        """Add a new minor release section with summarized changes"""
        content = self.read_changelog()
        version = f"{self.major}.{self.minor}.{self.build}"
        date = datetime.now().strftime("%Y-%m-%d")

        # Create release section
        release_section = f"\n## [{version}] - {date}\n\n"
        release_section += "### Changes\n\n"

        if changes:
            for change in changes:
                # Extract just the description (remove build version prefix if present)
                change_text = re.sub(r'^\[\d+\.\d+\.\d+\]\s+\d{4}-\d{2}-\d{2}\s+-\s+', '', change)
                release_section += f"- {change_text}\n"
        else:
            release_section += "- Minor improvements and bug fixes\n"

        release_section += "\n"

        # Clear unreleased section
        unreleased_section = "\n## [Unreleased]\n\n### Build Changes\n<!-- Automatically tracked changes go here. Will be summarized when MINOR version is bumped. -->\n\n"

        # Find where to insert (after the first ## [Unreleased] section)
        pattern = r'(\[Unreleased\].*?### Build Changes.*?(?=\n---|\n## \[))'
        content = re.sub(pattern, f"[Unreleased]\n\n### Build Changes\n<!-- Automatically tracked changes go here. Will be summarized when MINOR version is bumped. -->\n\n---\n{release_section.strip()}", content, count=1, flags=re.DOTALL)

        # Update version history
        history_pattern = r'(## Version History\s*\n)'
        history_entry = f"- **{version}** - {date}\n"
        content = re.sub(history_pattern, f"\\1\n{history_entry}", content)

        self.write_changelog(content)
        print(f"✓ Created minor release {version}")
        print(f"  Summarized {len(changes)} build change(s)")

    def add_major_release(self):
        """Add a new major release section"""
        content = self.read_changelog()
        version = f"{self.major}.{self.minor}.{self.build}"
        date = datetime.now().strftime("%Y-%m-%d")

        # Get list of minor versions since last major
        minor_versions = self.extract_minor_versions(content)

        # Create release section
        release_section = f"\n## [{version}] - {date}\n\n"
        release_section += "### Major Release\n\n"

        if minor_versions:
            release_section += "#### Minor Versions Included:\n"
            for v in minor_versions:
                release_section += f"- {v}\n"
            release_section += "\n"
            release_section += "*See individual minor versions above for detailed changes.*\n"
        else:
            release_section += "- Major version release\n"

        release_section += "\n"

        # Clear unreleased section
        pattern = r'(\[Unreleased\].*?### Build Changes.*?(?=\n---|\n## \[))'
        content = re.sub(pattern, f"[Unreleased]\n\n### Build Changes\n<!-- Automatically tracked changes go here. Will be summarized when MINOR version is bumped. -->\n\n---\n{release_section.strip()}", content, count=1, flags=re.DOTALL)

        # Update version history
        history_pattern = r'(## Version History\s*\n)'
        history_entry = f"- **{version}** - {date} (Major Release)\n"
        content = re.sub(history_pattern, f"\\1\n{history_entry}", content)

        self.write_changelog(content)
        print(f"✓ Created major release {version}")

    def extract_minor_versions(self, content):
        """Extract minor version numbers from recent releases"""
        # Find all version headers between current position and previous major
        pattern = r'## \[(\d+\.\d+\.\d+)\]'
        matches = re.findall(pattern, content)

        minor_versions = []
        for v in matches:
            parts = v.split('.')
            major = int(parts[0])
            if major == self.major - 1:  # Previous major version's minors
                minor_versions.append(v)

        return minor_versions

    def show_version(self):
        """Display current version"""
        print(f"Current version: {self.major}.{self.minor}.{self.build}")

        # Show unreleased changes if any
        changes = self.get_unreleased_changes()
        if changes:
            print(f"\nUnreleased changes ({len(changes)}):")
            for change in changes:
                print(f"  - {change}")
        else:
            print("\nNo unreleased changes")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    manager = VersionManager()
    command = sys.argv[1].lower()

    if command == 'build':
        manager.increment_build()

    elif command == 'minor':
        manager.increment_minor()

    elif command == 'major':
        manager.increment_major()

    elif command == 'add':
        if len(sys.argv) < 3:
            print("Error: Please provide change description")
            print("Usage: python version_manager.py add \"Your change description\"")
            sys.exit(1)
        change_text = sys.argv[2]
        manager.add_change(change_text)

    elif command == 'show':
        manager.show_version()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
