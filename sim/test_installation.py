#!/usr/bin/env python3
"""
ChaseBot Installation Validation Script
Tests that Webots is properly installed and our simulation files work
"""

import os
import sys
import subprocess

def test_webots_installation():
    """Test if Webots is properly installed and accessible"""
    print("Testing Webots installation...")
    
    # Common Webots installation paths
    webots_paths = [
        r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe",
        r"C:\Program Files\Webots\webots.exe",
        "webots"  # If in PATH
    ]
    
    for path in webots_paths:
        try:
            result = subprocess.run([path, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ Webots found at: {path}")
                print(f"✅ Version: {result.stdout.strip()}")
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            continue
    
    print("❌ Webots not found or not responding")
    print("   Make sure Webots is installed and added to PATH")
    return None

def test_simulation_files():
    """Test that all simulation files exist and are properly formatted"""
    print("\nTesting simulation files...")
    
    required_files = [
        "worlds/chasebot_world.wbt",
        "controllers/jetbot_controller/jetbot_controller.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ Found: {file_path}")
        else:
            print(f"❌ Missing: {file_path}")
            all_exist = False
    
    return all_exist

def test_python_dependencies():
    """Test that required Python packages are available"""
    print("\nTesting Python dependencies...")
    
    dependencies = [
        ("opencv-python", "cv2"),
        ("numpy", "numpy")
    ]
    
    all_available = True
    for package_name, import_name in dependencies:
        try:
            __import__(import_name)
            print(f"✅ {package_name} available")
        except ImportError:
            print(f"❌ {package_name} missing - install with: pip install {package_name}")
            all_available = False
    
    return all_available

def launch_simulation(webots_path):
    """Attempt to launch the simulation"""
    print(f"\nLaunching simulation with Webots at: {webots_path}")
    
    world_file = os.path.abspath("worlds/chasebot_world.wbt")
    
    if not os.path.exists(world_file):
        print(f"❌ World file not found: {world_file}")
        return False
    
    try:
        print(f"🚀 Starting: {webots_path} {world_file}")
        print("   (This will open Webots with our ChaseBot simulation)")
        print("   Close Webots window when done testing")
        
        # Launch Webots with our world file
        subprocess.run([webots_path, world_file])
        return True
        
    except Exception as e:
        print(f"❌ Failed to launch simulation: {e}")
        return False

def main():
    """Main validation function"""
    print("ChaseBot Installation Validation")
    print("=" * 50)
    
    # Test Webots installation
    webots_path = test_webots_installation()
    
    # Test simulation files
    files_ok = test_simulation_files()
    
    # Test Python dependencies
    deps_ok = test_python_dependencies()
    
    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    
    if webots_path and files_ok and deps_ok:
        print("✅ All tests passed! Ready to run simulation.")
        
        response = input("\nWould you like to launch the simulation now? (y/n): ")
        if response.lower().startswith('y'):
            launch_simulation(webots_path)
        else:
            print(f"\nTo launch manually:")
            print(f"1. Open Webots")
            print(f"2. File > Open World...")
            print(f"3. Select: {os.path.abspath('worlds/chasebot_world.wbt')}")
            print(f"4. Click Play button")
    else:
        print("❌ Some tests failed. Please address the issues above.")
        
        if not webots_path:
            print("\n🔧 Webots Installation Issues:")
            print("   - Ensure Webots is fully installed")
            print("   - Add Webots to your system PATH")
            print("   - Try restarting your terminal/VS Code")
        
        if not files_ok:
            print("\n🔧 Missing Files:")
            print("   - Run: python setup_jetbot_world.py")
        
        if not deps_ok:
            print("\n🔧 Python Dependencies:")
            print("   - Run: pip install opencv-python numpy")

if __name__ == "__main__":
    main()
