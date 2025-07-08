# Documentation Structure Standards

## Core Principles

### 1. NO Floating Documentation Files
- **PROHIBITED**: Creating standalone doc files like "YOLO_DETECTION_FIX_BREAKTHROUGH.md"
- **REQUIRED**: All documentation must be in README.md files at directory level
- **REASON**: Prevents scattered, disconnected documentation

### 2. Hierarchical Documentation Structure
```
chasebot/
├── README.md                    # Project overview
├── docs/
│   └── README.md               # Master project plan & status tracker
├── [directory]/
│   └── README.md               # Directory-specific documentation
└── memory-bank/                # Session-specific context
```

### 3. Master Project Plan (docs/README.md)
The `docs/README.md` file serves as:
- **Project Plan**: High-level goals and milestones
- **Status Tracker**: Current state of all components
- **Work Classification**:
  - ✅ COMPLETED: Finished and working
  - ❌ ABANDONED: No longer pursued (with reason)
  - 🚧 IN PROGRESS: Currently being worked on
  - ⏳ PENDING: Planned but not started
- **Navigation Hub**: Links to all directory READMEs

### 4. Directory-Level READMEs
Each directory's README.md must include:
- **File Inventory**: List of all files in the directory
- **Purpose**: What each file does
- **Status**: Active, deprecated, experimental
- **Dependencies**: What each file needs to run
- **Changelog**: Version history for the directory

### 5. Session Details Go to Memory Bank
- Breakthrough discoveries → `memory-bank/activeContext.md`
- Implementation details → `memory-bank/progress.md`
- Technical decisions → `memory-bank/systemPatterns.md`
- NOT in floating doc files

## Documentation Updates Required

When making changes:
1. Update the relevant directory's README.md
2. Update docs/README.md project status
3. Update memory bank for session context
4. NEVER create standalone documentation files

## Example Directory README Structure

```markdown
# Directory Name

## Overview
Brief description of what this directory contains

## File Inventory

### Active Files
- **filename.py** - Purpose, dependencies, usage
  - Status: Active
  - Version: 1.0.0
  - Dependencies: ROS2 Humble, OpenCV

### Deprecated Files
- **old_file.py** - What it did, why deprecated
  - Status: Deprecated (replaced by new_file.py)
  - Reason: Topic mismatch issue

## Changelog
- 2025-01-07: Fixed YOLO detector topic subscription
- 2025-01-06: Initial YOLO integration
```

## Benefits
1. **Single Source of Truth**: Each directory owns its documentation
2. **Clear Navigation**: Easy to find what you need
3. **Historical Context**: Changes tracked in appropriate places
4. **No Orphaned Docs**: Everything has a clear home
