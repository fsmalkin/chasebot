#!/usr/bin/env python3
"""
Kill all ChaseBot-related processes for clean restart.
Ensures no lingering processes interfere with testing.
"""

import subprocess
import signal
import os
import sys
import time

def find_and_kill_processes():
    """Find and kill all ChaseBot-related processes."""
    
    # Process patterns to search for
    patterns = [
        'gazebo',
        'gzserver',
        'gzclient',
        'ros2',
        'nav2',
        'yolo',
        'rviz2',
        'rqt',
        'robot_state_publisher',
        'joint_state_publisher',
        'controller_server',
        'planner_server',
        'bt_navigator',
        'lifecycle_manager',
        'map_server',
        'amcl',
        'python3.*chasebot',
        'python3.*yolo_to_nav',
        'python3.*monitor'
    ]
    
    print("=" * 60)
    print("ChaseBot Process Killer")
    print("=" * 60)
    
    processes_found = False
    killed_pids = []
    
    for pattern in patterns:
        try:
            # Find processes matching pattern
            cmd = f"ps aux | grep -E '{pattern}' | grep -v grep | grep -v kill_chasebot"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = int(parts[1])
                        process_name = ' '.join(parts[10:])  # Command and args
                        
                        # Skip this script itself
                        if 'kill_chasebot_processes' in process_name:
                            continue
                            
                        print(f"Found: PID {pid} - {process_name[:80]}...")
                        
                        try:
                            os.kill(pid, signal.SIGKILL)
                            killed_pids.append(pid)
                            processes_found = True
                        except ProcessLookupError:
                            print(f"  Already terminated")
                        except PermissionError:
                            print(f"  Permission denied (may be system process)")
                        except Exception as e:
                            print(f"  Error: {e}")
                            
        except Exception as e:
            print(f"Error searching for {pattern}: {e}")
    
    if processes_found:
        print("\n" + "=" * 60)
        print(f"Killed {len(killed_pids)} processes")
        print("Waiting 2 seconds for cleanup...")
        time.sleep(2)
        
        # Verify processes are gone
        print("\nVerifying termination...")
        still_running = []
        for pid in killed_pids:
            try:
                os.kill(pid, 0)  # Check if process exists
                still_running.append(pid)
            except ProcessLookupError:
                pass  # Good, process is gone
                
        if still_running:
            print(f"WARNING: {len(still_running)} processes may still be running: {still_running}")
        else:
            print("✓ All processes successfully terminated")
    else:
        print("\n✓ No ChaseBot processes found - system is clean")
    
    print("=" * 60)
    return not processes_found


def main():
    """Main entry point."""
    is_clean = find_and_kill_processes()
    
    if is_clean:
        sys.exit(0)
    else:
        # Return non-zero to indicate we killed processes
        sys.exit(1)


if __name__ == '__main__':
    main()
