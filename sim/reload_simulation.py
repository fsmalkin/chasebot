#!/usr/bin/env python3
"""
Quick script to reload the ChaseBot simulation
"""

import subprocess
import os

def reload_simulation():
    webots_path = r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"
    world_file = os.path.abspath("worlds/chasebot_world.wbt")
    
    print("Reloading ChaseBot simulation...")
    print(f"World file: {world_file}")
    
    try:
        subprocess.run([webots_path, world_file])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reload_simulation()
