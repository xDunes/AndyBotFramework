"""
Version information for Apex-Girl Bot Framework
Auto-managed by version_manager.py
"""

__version__ = "0.1.0"
__version_info__ = {
    'major': 0,
    'minor': 1,
    'build': 0
}

def get_version():
    """Get the current version string"""
    return __version__

def get_version_info():
    """Get version information as a dictionary"""
    return __version_info__.copy()

def get_version_tuple():
    """Get version as a tuple (major, minor, build)"""
    return (__version_info__['major'], __version_info__['minor'], __version_info__['build'])
