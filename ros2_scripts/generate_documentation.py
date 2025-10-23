#!/usr/bin/env python3
"""
File: generate_documentation.py
Status: ACTIVE
Version: 1.0.0
Last Updated: 2025-01-09
Purpose: Auto-generate README and status documentation from FILE_REGISTRY.yaml
Dependencies: PyYAML
"""

import yaml
import os
from datetime import datetime
from collections import defaultdict

def load_registry(file_path='FILE_REGISTRY.yaml'):
    """Load the file registry YAML"""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def generate_status_table(files):
    """Generate a markdown table of file statuses"""
    status_groups = defaultdict(list)
    
    for filename, metadata in files.items():
        status = metadata.get('status', 'UNKNOWN')
        status_groups[status].append((filename, metadata))
    
    # Create table for each status
    tables = []
    
    # Active files first
    if 'ACTIVE' in status_groups:
        tables.append("### ✅ ACTIVE FILES\n")
        tables.append("| File | Purpose | Version | Last Updated | Working Status |")
        tables.append("|------|---------|---------|--------------|----------------|")
        
        for filename, meta in sorted(status_groups['ACTIVE']):
            purpose = meta.get('purpose', 'N/A')[:50] + '...' if len(meta.get('purpose', '')) > 50 else meta.get('purpose', 'N/A')
            version = meta.get('version', 'N/A')
            last_updated = meta.get('last_updated', 'N/A')
            working = meta.get('working_status', 'N/A')
            tables.append(f"| {filename} | {purpose} | {version} | {last_updated} | {working} |")
        tables.append("")
    
    # Deprecated files
    if 'DEPRECATED' in status_groups:
        tables.append("### ❌ DEPRECATED FILES\n")
        tables.append("| File | Purpose | Replaced By | Issue |")
        tables.append("|------|---------|-------------|-------|")
        
        for filename, meta in sorted(status_groups['DEPRECATED']):
            purpose = meta.get('purpose', 'N/A')[:40] + '...' if len(meta.get('purpose', '')) > 40 else meta.get('purpose', 'N/A')
            replaced_by = meta.get('replaced_by', 'N/A')
            issue = meta.get('issue', meta.get('archive_reason', 'N/A'))[:40] + '...' if len(meta.get('issue', meta.get('archive_reason', ''))) > 40 else meta.get('issue', meta.get('archive_reason', 'N/A'))
            tables.append(f"| {filename} | {purpose} | {replaced_by} | {issue} |")
        tables.append("")
    
    # Experimental files
    if 'EXPERIMENTAL' in status_groups:
        tables.append("### 🧪 EXPERIMENTAL FILES\n")
        tables.append("| File | Purpose | Version |")
        tables.append("|------|---------|---------|")
        
        for filename, meta in sorted(status_groups['EXPERIMENTAL']):
            purpose = meta.get('purpose', 'N/A')[:60] + '...' if len(meta.get('purpose', '')) > 60 else meta.get('purpose', 'N/A')
            version = meta.get('version', 'N/A')
            tables.append(f"| {filename} | {purpose} | {version} |")
        tables.append("")
    
    return '\n'.join(tables)

def generate_quick_reference(registry):
    """Generate quick reference section"""
    lines = ["## 🚀 Quick Reference\n"]
    
    # Working detectors
    if 'working_detectors' in registry:
        lines.append("### Working YOLO Detectors")
        for detector in registry['working_detectors']:
            lines.append(f"- `{detector}`")
        lines.append("")
    
    # Working tests
    if 'working_tests' in registry:
        lines.append("### Working Test Scripts")
        for test in registry['working_tests']:
            lines.append(f"- `{test}`")
        lines.append("")
    
    # Essential tools
    if 'essential_tools' in registry:
        lines.append("### Essential Tools")
        for tool in registry['essential_tools']:
            lines.append(f"- `{tool}`")
        lines.append("")
    
    return '\n'.join(lines)

def generate_topic_reference(files):
    """Generate topic subscription/publication reference"""
    publishers = defaultdict(list)
    subscribers = defaultdict(list)
    
    for filename, metadata in files.items():
        if metadata.get('status') == 'ACTIVE' and 'topics' in metadata:
            topics = metadata['topics']
            
            for topic in topics.get('publishes', []):
                publishers[topic].append(filename)
            
            for topic in topics.get('subscribes', []):
                subscribers[topic].append(filename)
    
    lines = ["## 📡 Topic Reference\n"]
    
    if publishers:
        lines.append("### Publishers")
        for topic, files in sorted(publishers.items()):
            lines.append(f"- **{topic}**: {', '.join(files)}")
        lines.append("")
    
    if subscribers:
        lines.append("### Subscribers")
        for topic, files in sorted(subscribers.items()):
            lines.append(f"- **{topic}**: {', '.join(files)}")
        lines.append("")
    
    return '\n'.join(lines)

def generate_readme_content(registry):
    """Generate complete README content"""
    files = registry['files']
    summary = registry.get('summary', {})
    
    content = [
        "# ROS2 Scripts Directory",
        f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} from FILE_REGISTRY.yaml*\n",
        "## 📊 Summary",
        f"- **Total Files**: {summary.get('total_files', len(files))}",
        f"- **Active**: {summary.get('active', 0)}",
        f"- **Deprecated**: {summary.get('deprecated', 0)}",
        f"- **Experimental**: {summary.get('experimental', 0)}",
        f"- **Unknown/Needs Review**: {summary.get('unknown', 0)}\n",
        generate_quick_reference(registry),
        "## 📁 File Status Overview\n",
        generate_status_table(files),
        generate_topic_reference(files),
        "## 🔧 How to Use\n",
        "### Running YOLO Detection",
        "```bash",
        "# For verbose output (debugging)",
        "python3 ros2_yolo_detector_frisbee.py --ros-args -p use_sim_time:=true",
        "",
        "# For quiet output (production)",
        "python3 ros2_yolo_detector_frisbee_quiet.py --ros-args -p use_sim_time:=true",
        "```\n",
        "### Running Tests",
        "```bash",
        "# Full system demo",
        "python ros2_scripts/test_sports_ball_detection_uat.py",
        "",
        "# 3D vision test (run from Windows)",
        "python ros2_scripts/test_3d_position_extraction.py",
        "```\n",
        "### Diagnostics",
        "```bash",
        "# Check camera topics",
        "python3 test_camera_topic.py",
        "",
        "# Monitor YOLO output",
        "python3 monitor_yolo_detections.py",
        "```\n",
        "---",
        "*To update this documentation, modify FILE_REGISTRY.yaml and run:*",
        "```bash",
        "python3 generate_documentation.py",
        "```"
    ]
    
    return '\n'.join(content)

def update_readme():
    """Update the README.md file"""
    registry = load_registry()
    new_content = generate_readme_content(registry)
    
    # Backup existing README
    if os.path.exists('README.md'):
        backup_name = f'README.md.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        os.rename('README.md', backup_name)
        print(f"Backed up existing README to {backup_name}")
    
    # Write new README
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Generated new README.md")

def generate_status_report():
    """Generate a quick status report for session handoff"""
    registry = load_registry()
    files = registry['files']
    
    report = [
        "# ChaseBot ROS2 Scripts Status Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "## 🟢 WORKING & VERIFIED",
        "### YOLO Detectors"
    ]
    
    # Find working detectors
    for filename, meta in files.items():
        if 'yolo_detector' in filename and meta.get('working_status') == 'VERIFIED':
            report.append(f"- **{filename}**: {meta['purpose']}")
            if 'test_command' in meta:
                report.append(f"  - Test with: `{meta['test_command']}`")
    
    report.extend([
        "\n### 3D Vision Pipeline",
        "- **yolo_3d_position_extractor.py**: Extracts 3D positions",
        "- **d415_3d_debug_viewer.py**: Visual debugging",
        "\n### Test Scripts"
    ])
    
    # Find working tests
    for filename, meta in files.items():
        if filename.startswith('test_') and meta.get('working_status') == 'VERIFIED':
            report.append(f"- **{filename}**: {meta['purpose']}")
    
    report.extend([
        "\n## 🔴 KNOWN ISSUES",
        "- YOLO detects simulated balls as 'frisbee' (class 29) - this is handled",
        "- Display configuration required for GUI scripts (see README)",
        "- Some test scripts must be run from Windows, not WSL",
        "\n## 🎯 QUICK COMMANDS",
        "```bash",
        "# Check what's working",
        "python3 test_camera_topic.py",
        "",
        "# Run full demo",
        "python ros2_scripts/test_sports_ball_detection_uat.py",
        "",
        "# Test 3D vision (from Windows)",
        "python ros2_scripts/test_3d_position_extraction.py",
        "```"
    ])
    
    return '\n'.join(report)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        # Generate quick status report
        print(generate_status_report())
    else:
        # Update README
        update_readme()
        print("\nQuick status report:")
        print(generate_status_report())
