#!/usr/bin/env python3
"""
Reliable file synchronization between Windows and WSL2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Dict, List, Tuple


class SyncManager:
    def __init__(
        self,
        wsl_distro: str = "Ubuntu-22.04",
        windows_base: str | None = None,
        wsl_base: str | None = None,
        sync_log_file: str | None = None,
    ) -> None:
        self.wsl_distro = wsl_distro
        self.repo_root = Path(__file__).resolve().parents[1]

        base_from_env = os.environ.get("CHASECAR_WINDOWS_BASE")
        self.windows_base = Path(windows_base or base_from_env or self.repo_root).resolve()

        wsl_base_from_env = os.environ.get("CHASECAR_WSL_BASE")
        self.wsl_base = wsl_base or wsl_base_from_env or self._detect_wsl_base()

        self.sync_log_file = Path(sync_log_file or (self.repo_root / "SYNC_STATUS.json"))
        self.sync_status: Dict[str, object] = {"files": {}, "last_sync": None}
        self.load_sync_status()

    def load_sync_status(self) -> None:
        if self.sync_log_file.exists():
            with self.sync_log_file.open("r", encoding="utf-8") as handle:
                self.sync_status = json.load(handle)

    def save_sync_status(self) -> None:
        with self.sync_log_file.open("w", encoding="utf-8") as handle:
            json.dump(self.sync_status, handle, indent=2)

    def run_wsl_command(self, command: str) -> Tuple[bool, str]:
        cmd = ["wsl", "-d", self.wsl_distro, "--", "bash", "-lc", command]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, result.stdout.strip()
        except FileNotFoundError:
            return False, "wsl executable not found on PATH"
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else ""
            stdout = exc.stdout.strip() if exc.stdout else ""
            details = stderr or stdout or f"exit code {exc.returncode}"
            return False, details

    def _detect_wsl_base(self) -> str:
        detect_cmd = (
            "if [ -d ~/ros2_ws/src/chasecar ]; then echo ~/ros2_ws/src/chasecar; "
            "elif [ -d ~/ros2_ws/src/chasebot_description ]; then echo ~/ros2_ws/src/chasebot_description; "
            "else echo ~/ros2_ws/src/chasecar; fi"
        )
        success, output = self.run_wsl_command(detect_cmd)
        if success and output:
            return output.strip()
        return "~/ros2_ws/src/chasecar"

    @staticmethod
    def windows_to_wsl_path(path: Path) -> str:
        text = str(path).replace("\\", "/")
        if len(text) >= 3 and text[1] == ":" and text[2] == "/":
            drive = text[0].lower()
            return f"/mnt/{drive}{text[2:]}"
        return text

    @staticmethod
    def get_file_hash(windows_path: Path) -> str | None:
        try:
            with windows_path.open("rb") as handle:
                return hashlib.md5(handle.read()).hexdigest()
        except OSError:
            return None

    def verify_file_exists_in_wsl(self, relative_path: str) -> bool:
        normalized = relative_path.replace("\\", "/")
        wsl_path = f"{self.wsl_base}/{normalized}"
        success, output = self.run_wsl_command(
            f"test -f '{wsl_path}' && echo EXISTS || echo NOT_FOUND"
        )
        return success and output == "EXISTS"

    def sync_file(self, relative_path: str, verify: bool = True) -> Tuple[bool, str]:
        normalized = relative_path.replace("\\", "/")
        windows_path = (self.windows_base / normalized).resolve()

        if not windows_path.exists():
            return False, f"File not found: {windows_path}"

        windows_path_for_wsl = self.windows_to_wsl_path(windows_path)
        wsl_dest = f"{self.wsl_base}/{normalized}"
        wsl_dir = os.path.dirname(wsl_dest)

        success, output = self.run_wsl_command(f"mkdir -p '{wsl_dir}'")
        if not success:
            return False, f"Failed to create directory in WSL: {output}"

        success, output = self.run_wsl_command(f"cp '{windows_path_for_wsl}' '{wsl_dest}'")
        if not success:
            return False, f"Failed to copy file: {output}"

        if verify:
            if not self.verify_file_exists_in_wsl(normalized):
                return False, "File copied but verification failed"

            success, size_output = self.run_wsl_command(f"stat -c%s '{wsl_dest}'")
            if success:
                wsl_size = int(size_output)
                windows_size = windows_path.stat().st_size
                if windows_size != wsl_size:
                    return (
                        False,
                        f"Size mismatch after copy (Windows={windows_size}, WSL={wsl_size})",
                    )

        file_hash = self.get_file_hash(windows_path)
        tracked_files = self.sync_status.setdefault("files", {})
        if isinstance(tracked_files, dict):
            tracked_files[normalized] = {
                "last_sync": datetime.now().isoformat(),
                "hash": file_hash,
                "size": windows_path.stat().st_size,
            }

        return True, "Synced successfully"

    def sync_directory(
        self, directory: str = "ros2_scripts", pattern: str = "*.py", verify: bool = True
    ) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        directory_path = (self.windows_base / directory).resolve()

        if not directory_path.exists():
            return results

        pattern_path = str(directory_path / pattern)
        for file_path in glob(pattern_path):
            rel = Path(file_path).resolve().relative_to(self.windows_base)
            relative_path = rel.as_posix()

            print(f"Syncing {relative_path} ...")
            success, message = self.sync_file(relative_path, verify=verify)
            results.append({"file": relative_path, "success": success, "message": message})

            if success:
                print(f"  [OK] {message}")
            else:
                print(f"  [ERR] {message}")

        self.sync_status["last_sync"] = datetime.now().isoformat()
        self.save_sync_status()
        return results

    def sync_critical_files(self) -> List[Dict[str, object]]:
        critical_files = [
            "ros2_scripts/ros2_yolo_detector_frisbee.py",
            "ros2_scripts/ros2_yolo_detector_frisbee_quiet.py",
            "ros2_scripts/yolo_3d_position_extractor.py",
            "ros2_scripts/d415_3d_debug_viewer.py",
            "ros2_scripts/test_3d_position_extraction.py",
            "ros2_scripts/test_sports_ball_detection_uat.py",
            "ros2_scripts/test_camera_topic.py",
            "ros2_scripts/kill_chasebot_processes.py",
            "ros2_scripts/cleanup_before_launch.py",
        ]

        results: List[Dict[str, object]] = []
        for relative_path in critical_files:
            print(f"Syncing {relative_path} ...")
            success, message = self.sync_file(relative_path, verify=True)
            results.append({"file": relative_path, "success": success, "message": message})
            if success:
                print(f"  [OK] {message}")
            else:
                print(f"  [ERR] {message}")

        self.sync_status["last_sync"] = datetime.now().isoformat()
        self.save_sync_status()
        return results

    def check_sync_status(self) -> List[Dict[str, str]]:
        needs_sync: List[Dict[str, str]] = []
        tracked_files = self.sync_status.get("files", {})
        if not isinstance(tracked_files, dict):
            return needs_sync

        for file_path, info in tracked_files.items():
            windows_path = (self.windows_base / file_path).resolve()
            if not windows_path.exists():
                needs_sync.append({"file": file_path, "reason": "Missing in Windows repo"})
                continue

            current_hash = self.get_file_hash(windows_path)
            saved_hash = info.get("hash") if isinstance(info, dict) else None
            if current_hash != saved_hash:
                needs_sync.append({"file": file_path, "reason": "Modified in Windows repo"})
                continue

            if not self.verify_file_exists_in_wsl(file_path):
                needs_sync.append({"file": file_path, "reason": "Missing in WSL workspace"})

        return needs_sync


def summarize(results: List[Dict[str, object]], label: str) -> None:
    success_count = sum(1 for item in results if item.get("success"))
    print(f"{label}: {success_count}/{len(results)} succeeded")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync files from Windows repo to WSL workspace."
    )
    parser.add_argument(
        "action",
        choices=["sync", "sync-all", "sync-critical", "status", "verify"],
        help="Action to run",
    )
    parser.add_argument(
        "--directory",
        default="ros2_scripts",
        help="Directory to sync for 'sync' action",
    )
    parser.add_argument(
        "--pattern",
        default="*.py",
        help="Glob pattern used for 'sync' action",
    )
    parser.add_argument(
        "--distro",
        default="Ubuntu-22.04",
        help="WSL distro name",
    )
    parser.add_argument(
        "--windows-base",
        default=None,
        help="Windows repo root override",
    )
    parser.add_argument(
        "--wsl-base",
        default=None,
        help="WSL package path override (example: ~/ros2_ws/src/chasecar)",
    )
    args = parser.parse_args()

    manager = SyncManager(
        wsl_distro=args.distro,
        windows_base=args.windows_base,
        wsl_base=args.wsl_base,
    )

    if args.action == "sync":
        results = manager.sync_directory(args.directory, args.pattern)
        summarize(results, "Sync result")
        return

    if args.action == "sync-all":
        results = manager.sync_directory("ros2_scripts", "*.py")
        summarize(results, "Sync-all result")
        return

    if args.action == "sync-critical":
        results = manager.sync_critical_files()
        summarize(results, "Sync-critical result")
        return

    if args.action == "status":
        needs_sync = manager.check_sync_status()
        if needs_sync:
            print("Files that need sync:")
            for item in needs_sync:
                print(f"  - {item['file']}: {item['reason']}")
        else:
            print("All tracked files are in sync.")
        if manager.sync_status.get("last_sync"):
            print(f"Last sync: {manager.sync_status['last_sync']}")
        return

    if args.action == "verify":
        tracked_files = manager.sync_status.get("files", {})
        if not isinstance(tracked_files, dict) or not tracked_files:
            print("No tracked files found in sync log.")
            return

        missing = []
        for file_path in tracked_files:
            if manager.verify_file_exists_in_wsl(file_path):
                print(f"[OK] {file_path}")
            else:
                print(f"[ERR] {file_path}")
                missing.append(file_path)

        if missing:
            print(f"Missing from WSL: {len(missing)}")
        else:
            print("All tracked files verified in WSL.")


if __name__ == "__main__":
    main()
