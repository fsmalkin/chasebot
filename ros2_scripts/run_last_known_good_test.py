#!/usr/bin/env python3
"""
Run Last Known Good Test
Based on: test_3d_position_extraction.py
Purpose: Verify YOLO + 3D extraction works with known good parameters
"""

import subprocess
import time

def main():
    print("=" * 80)
    print("🔍 RUNNING LAST KNOWN GOOD TEST")
    print("=" * 80)
    print("\n📋 Configuration:")
    print("  - YOLO confidence threshold: 0.3")
    print("  - 3D extractor confidence threshold: 0.1")
    print("  - Input topic: /d415/color/image_raw")
    print("  - Known working test: test_3d_position_extraction.py")
    print("=" * 80)
    
    # Simply run the last known good test
    print("\nExecuting test_3d_position_extraction.py...")
    subprocess.run(['python3', 'ros2_scripts/test_3d_position_extraction.py'])

if __name__ == '__main__':
    main()
