#!/usr/bin/env python3
"""
File: sync_manager.py
Status: ACTIVE
Version: 1.0.0
Last Updated: 2025-01-09
Purpose: Reliable file synchronization between Windows and WSL2
Dependencies: None (uses standard library)
"""

import subprocess
import os
import time
import json
from datetime import datetime
from pathlib import Path

class SyncManager:
    def __init__(self, wsl_distro="Ubuntu-22.04"):
        self.wsl_distro = wsl_distro
        self.windows_base = "c:/Users/arsen_j7sbcbk/Desktop/chasebot"
        self.wsl_base = "~/ros2_ws/src/chasebot_description"
        self.sync_log_file = "SYNC_STATUS.json"
        self.load_sync_status()
    
    def load_sync_status(self):
        """Load previous sync status"""
        if os.path.exists(self.sync_log_file):
            with open(self.sync_log_file, 'r') as f:
                self.sync_status = json.load(f)
        else:
            self.sync_status = {"files": {}, "last_sync": None}
    
    def save_sync_status(self):
        """Save sync status to file"""
        with open(self.sync_log_file, 'w') as f:
            json.dump(self.sync_status, f, indent=2)
    
    def run_wsl_command(self, command):
        """Run a command in WSL and return output"""
        cmd = ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", command]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, f"Error: {e.stderr}"
    
    def get_file_hash(self, windows_path):
        """Get hash of a Windows file"""
        try:
            import hashlib
            with open(windows_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            return None
    
    def verify_file_exists_in_wsl(self, relative_path):
        """Check if file exists in WSL"""
        wsl_path = f"{self.wsl_base}/{relative_path}"
        success, output = self.run_wsl_command(f"test -f {wsl_path} && echo 'EXISTS' || echo 'NOT_FOUND'")
        return success and output == "EXISTS"
    
    def sync_file(self, relative_path, verify=True):
        """Sync a single file to WSL"""
        windows_path = os.path.join(self.windows_base, relative_path)
        
        # Check if Windows file exists
        if not os.path.exists(windows_path):
            return False, f"File not found: {windows_path}"
        
        # Convert paths
        windows_path_for_wsl = windows_path.replace("\\", "/").replace("c:", "/mnt/c")
        wsl_dest = f"{self.wsl_base}/{relative_path}"
        
        # Create directory if needed
        wsl_dir = os.path.dirname(wsl_dest)
        success, output = self.run_wsl_command(f"mkdir -p {wsl_dir}")
        if not success:
            return False, f"Failed to create directory: {output}"
        
        # Copy file
        copy_cmd = f"cp '{windows_path_for_wsl}' '{wsl_dest}'"
        success, output = self.run_wsl_command(copy_cmd)
        if not success:
            return False, f"Failed to copy: {output}"
        
        # Verify if requested
        if verify:
            if not self.verify_file_exists_in_wsl(relative_path):
                return False, "File copied but verification failed"
            
            # Get file size to double-check
            success, size_output = self.run_wsl_command(f"stat -c%s '{wsl_dest}'")
            if success:
                windows_size = os.path.getsize(windows_path)
                wsl_size = int(size_output)
                if windows_size != wsl_size:
                    return False, f"Size mismatch: Windows={windows_size}, WSL={wsl_size}"
        
        # Update sync status
        file_hash = self.get_file_hash(windows_path)
        self.sync_status["files"][relative_path] = {
            "last_sync": datetime.now().isoformat(),
            "hash": file_hash,
            "size": os.path.getsize(windows_path)
        }
        
        return True, "Successfully synced"
    
    def sync_directory(self, directory="ros2_scripts", pattern="*.py", verify=True):
        """Sync all matching files in a directory"""
        results = []
        directory_path = os.path.join(self.windows_base, directory)
        
        if not os.path.exists(directory_path):
            return results
        
        # Find all matching files
        from glob import glob
        pattern_path = os.path.join(directory_path, pattern)
        files = glob(pattern_path)
        
        for file_path in files:
            relative_path = os.path.relpath(file_path, self.windows_base)
            relative_path = relative_path.replace("\\", "/")
            
            print(f"Syncing {relative_path}...")
            success, message = self.sync_file(relative_path, verify)
            results.append({
                "file": relative_path,
                "success": success,
                "message": message
            })
            
            if success:
                print(f"  ✓ {message}")
            else:
                print(f"  ✗ {message}")
        
        self.sync_status["last_sync"] = datetime.now().isoformat()
        self.save_sync_status()
        
        return results
    
    def sync_critical_files(self):
        """Sync only the critical working files"""
        critical_files = [
            "ros2_scripts/ros2_yolo_detector_frisbee.py",
            "ros2_scripts/ros2_yolo_detector_frisbee_quiet.py",
            "ros2_scripts/yolo_3d_position_extractor.py",
            "ros2_scripts/d415_3d_debug_viewer.py",
            "ros2_scripts/test_3d_position_extraction.py",
            "ros2_scripts/test_sports_ball_detection_uat.py",
            "ros2_scripts/test_camera_topic.py",
            "ros2_scripts/kill_chasebot_processes.py",
            "ros2_scripts/cleanup_before_launch.py"
        ]
        
        results = []
        for file_path in critical_files:
            print(f"Syncing {file_path}...")
            success, message = self.sync_file(file_path, verify=True)
            results.append({
                "file": file_path,
                "success": success,
                "message": message
            })
            
            if success:
                print(f"  ✓ {message}")
            else:
                print(f"  ✗ {message}")
        
        self.sync_status["last_sync"] = datetime.now().isoformat()
        self.save_sync_status()
        
        return results
    
    def check_sync_status(self):
        """Check which files need syncing"""
        needs_sync = []
        
        for file_path, info in self.sync_status.get("files", {}).items():
            windows_path = os.path.join(self.windows_base, file_path)
            
            # Check if file still exists
            if not os.path.exists(windows_path):
                needs_sync.append({
                    "file": file_path,
                    "reason": "File deleted from Windows"
                })
                continue
            
            # Check if file has changed
            current_hash = self.get_file_hash(windows_path)
            if current_hash != info.get("hash"):
                needs_sync.append({
                    "file": file_path,
                    "reason": "File modified"
                })
                continue
            
            # Verify it exists in WSL
            if not self.verify_file_exists_in_wsl(file_path):
                needs_sync.append({
                    "file": file_path,
                    "reason": "Missing from WSL"
                })
        
        return needs_sync

def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync files between Windows and WSL")
    parser.add_argument("action", choices=["sync", "sync-all", "sync-critical", "status", "verify"],
                       help="Action to perform")
    parser.add_argument("--directory", default="ros2_scripts",
                       help="Directory to sync (default: ros2_scripts)")
    parser.add_argument("--pattern", default="*.py",
                       help="File pattern to sync (default: *.py)")
    
    args = parser.parse_args()
    
    manager = SyncManager()
    
    if args.action == "sync":
        # Sync specific directory
        results = manager.sync_directory(args.directory, args.pattern)
        
        # Summary
        success_count = sum(1 for r in results if r["success"])
        print(f"\nSynced {success_count}/{len(results)} files successfully")
        
    elif args.action == "sync-all":
        # Sync all Python files in ros2_scripts
        results = manager.sync_directory("ros2_scripts", "*.py")
        
        # Summary
        success_count = sum(1 for r in results if r["success"])
        print(f"\nSynced {success_count}/{len(results)} files successfully")
        
    elif args.action == "sync-critical":
        # Sync only critical files
        results = manager.sync_critical_files()
        
        # Summary
        success_count = sum(1 for r in results if r["success"])
        print(f"\nSynced {success_count}/{len(results)} critical files successfully")
        
    elif args.action == "status":
        # Check sync status
        needs_sync = manager.check_sync_status()
        
        if needs_sync:
            print("Files needing sync:")
            for item in needs_sync:
                print(f"  - {item['file']}: {item['reason']}")
        else:
            print("All tracked files are in sync")
        
        if manager.sync_status.get("last_sync"):
            print(f"\nLast sync: {manager.sync_status['last_sync']}")
    
    elif args.action == "verify":
        # Verify all tracked files exist in WSL
        print("Verifying files in WSL...")
        missing = []
        
        for file_path in manager.sync_status.get("files", {}).keys():
            if not manager.verify_file_exists_in_wsl(file_path):
                missing.append(file_path)
                print(f"  ✗ {file_path} - MISSING")
            else:
                print(f"  ✓ {file_path} - OK")
        
        if missing:
            print(f"\n{len(missing)} files missing from WSL")
        else:
            print("\nAll files verified in WSL")

if __name__ == "__main__":
    main()
