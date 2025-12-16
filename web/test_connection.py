"""
Test script to verify the web server can access the state database
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path (same as server.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*60)
print("Testing State Database Connection")
print("="*60)
print()

try:
    from core.state_manager import StateManager
    print("[OK] StateManager imported successfully")

    # Test getting stats
    stats = StateManager.get_database_stats()
    print(f"[OK] Database stats retrieved:")
    print(f"  - Total bots: {stats['total_bots']}")
    print(f"  - Running: {stats['running_bots']}")
    print(f"  - Stopped: {stats['stopped_bots']}")
    print(f"  - Database: {stats['db_path']}")
    print(f"  - Size: {stats['db_size_mb']} MB")
    print()

    # Test getting all bots
    all_bots = StateManager.get_all_bots()
    print(f"[OK] Found {len(all_bots)} bot instances:")

    for bot in all_bots:
        status = "RUNNING" if bot['is_running'] else "STOPPED"
        print(f"  - {bot['device_name']}: {status}")

    print()
    print("="*60)
    print("[SUCCESS] All tests passed! The server should work correctly.")
    print("="*60)

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
    print()
    print("="*60)
    print("[FAILED] Test failed. Check the error above.")
    print("="*60)
