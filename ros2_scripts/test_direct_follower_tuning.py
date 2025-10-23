#!/usr/bin/env python3
"""
Direct Follower Parameter Tuning Tool
Helps tune the proportional controller gains for smooth ball following
"""

import subprocess
import time
import sys

def test_parameters(linear_gain, angular_gain, max_linear=0.2, max_angular=0.5):
    """Test direct follower with specific parameters"""
    print(f"\n🔧 Testing parameters:")
    print(f"   Linear gain: {linear_gain}")
    print(f"   Angular gain: {angular_gain}")
    print(f"   Max linear speed: {max_linear} m/s")
    print(f"   Max angular speed: {max_angular} rad/s")
    
    # Launch follower with custom parameters
    cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        f'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
        f'timeout 30 python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_direct_follower_v2.py '
        f'--ros-args '
        f'-p linear_gain:={linear_gain} '
        f'-p angular_gain:={angular_gain} '
        f'-p max_linear_speed:={max_linear} '
        f'-p max_angular_speed:={max_angular}'
    ]
    
    print("\nRunning for 30 seconds...")
    subprocess.run(cmd)
    
    return input("\n📊 How was the behavior? (smooth/oscillating/spiral/slow): ").lower()

def main():
    print("=" * 80)
    print("🎯 Direct Follower Parameter Tuning Tool")
    print("=" * 80)
    print("\n📋 This tool helps find optimal control parameters")
    print("Prerequisites:")
    print("  1. Simulation must be running with ball visible")
    print("  2. YOLO detector must be running")
    print("  3. 3D position extractor must be running")
    print("\n🎮 Parameter Effects:")
    print("  - Linear gain: Higher = faster approach, but may overshoot")
    print("  - Angular gain: Higher = faster turning, but may oscillate")
    print("  - Too high gains = oscillation/spiraling")
    print("  - Too low gains = slow response")
    print("=" * 80)
    
    # Check if prerequisites are running
    print("\nChecking prerequisites...")
    check_cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
        'ros2 topic list | grep -E "(yolo|d415)"'
    ]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if "/yolo/ball_position_3d" not in result.stdout:
        print("❌ ERROR: Required topics not found!")
        print("Please run the simulation, YOLO detector, and 3D extractor first.")
        print("\nRun: cd ros2_scripts && python test_direct_follower.py")
        print("Then run this tuning tool in another terminal.")
        return
    
    print("✅ Prerequisites found!")
    
    # Test configurations
    configs = [
        # (linear_gain, angular_gain, description)
        (0.5, 2.0, "Default (may cause spiraling)"),
        (0.3, 1.0, "Conservative (slower but stable)"),
        (0.5, 1.0, "Reduced angular gain"),
        (0.3, 1.5, "Balanced approach"),
        (0.4, 0.8, "Very conservative"),
        (0.6, 1.2, "Slightly aggressive"),
    ]
    
    results = []
    
    print("\n🧪 Testing predefined configurations...")
    for i, (lg, ag, desc) in enumerate(configs):
        print(f"\n--- Configuration {i+1}/{len(configs)}: {desc} ---")
        
        behavior = test_parameters(lg, ag)
        results.append((lg, ag, desc, behavior))
        
        if behavior == "smooth":
            print("✅ Good configuration found!")
            if input("Continue testing? (y/n): ").lower() != 'y':
                break
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 RESULTS SUMMARY")
    print("=" * 80)
    for lg, ag, desc, behavior in results:
        status = "✅" if behavior == "smooth" else "❌"
        print(f"{status} Linear={lg}, Angular={ag} ({desc}): {behavior}")
    
    # Custom testing
    print("\n🔧 Custom Parameter Testing")
    if input("Would you like to test custom parameters? (y/n): ").lower() == 'y':
        while True:
            try:
                lg = float(input("Enter linear gain (0.1-1.0): "))
                ag = float(input("Enter angular gain (0.1-3.0): "))
                ml = float(input("Enter max linear speed (0.1-0.5): "))
                ma = float(input("Enter max angular speed (0.1-1.0): "))
                
                behavior = test_parameters(lg, ag, ml, ma)
                print(f"\nResult: {behavior}")
                
                if input("\nTest another? (y/n): ").lower() != 'y':
                    break
            except ValueError:
                print("Invalid input, please enter numbers only")
    
    # Final recommendation
    smooth_configs = [(lg, ag) for lg, ag, _, b in results if b == "smooth"]
    if smooth_configs:
        best_lg, best_ag = smooth_configs[0]
        print(f"\n✅ RECOMMENDED PARAMETERS:")
        print(f"   Linear gain: {best_lg}")
        print(f"   Angular gain: {best_ag}")
        print("\nTo use these permanently, update yolo_3d_direct_follower_v2.py")
    else:
        print("\n⚠️  No smooth configurations found in predefined set.")
        print("Try custom parameters or check if ball is properly detected.")


if __name__ == '__main__':
    main()
