# File Versioning Standards for ChaseBot

## Naming Convention Requirements

### PROHIBITED Terms
**NEVER use these ambiguous descriptors in filenames:**
- `fixed`
- `corrected`
- `proper`
- `updated`
- `new`
- `old`
- `final`
- `latest`
- `improved`
- `better`

### REQUIRED: Semantic Versioning
All files that may have multiple versions MUST use semantic versioning:

#### Format: `filename_vX.Y.Z.extension`
- **X**: Major version (breaking changes)
- **Y**: Minor version (new features, backwards compatible)
- **Z**: Patch version (bug fixes)

#### Examples:
- ✅ `ros2_yolo_to_nav_goal_v1.0.0.py` - Initial implementation
- ✅ `ros2_yolo_to_nav_goal_v1.1.0.py` - Added feature
- ✅ `ros2_yolo_to_nav_goal_v2.0.0.py` - Major rewrite
- ❌ `ros2_yolo_to_nav_goal_fixed.py` - NEVER DO THIS
- ❌ `ros2_yolo_to_nav_goal_corrected.py` - NEVER DO THIS

## Version Documentation

### Each versioned file MUST have:
1. **Version header comment** explaining changes:
```python
#!/usr/bin/env python3
"""
YOLO to Nav2 Goal Bridge - Version 2.0.0
Major changes:
- v2.0.0: Complete rewrite using camera intrinsics for proper coordinate conversion
- v1.1.0: Added confidence filtering
- v1.0.0: Initial implementation with direct position mapping
"""
```

2. **Changelog entry** in relevant documentation
3. **Clear deprecation notice** on older versions

## Launch File Integration

### When creating new versions:
1. Keep the old version for reference/rollback
2. Update launch files to use specific version:
```python
Node(
    package='chasebot_description',
    executable='ros2_yolo_to_nav_goal_v2.0.0.py',  # Explicit version
    name='yolo_to_nav_goal'
)
```

3. Add launch file parameter for version selection:
```python
DeclareLaunchArgument(
    'bridge_version',
    default_value='2.0.0',
    description='Version of YOLO to Nav2 bridge to use'
)
```

## Migration Strategy

### When replacing a non-versioned file:
1. Rename existing file with v1.0.0
2. Create new version with appropriate version number
3. Update all references in launch files and documentation
4. Test both versions remain functional

### Example migration:
```bash
# Before: ros2_yolo_to_nav_goal_corrected.py
# Step 1: Rename to v1.0.0
mv ros2_yolo_to_nav_goal_corrected.py ros2_yolo_to_nav_goal_v1.0.0.py

# Step 2: Create new version
touch ros2_yolo_to_nav_goal_v2.0.0.py

# Step 3: Update launch files to reference specific version
```

## Documentation Requirements

### Version comparison documentation:
Create comparison docs when multiple versions exist:
- `docs/yolo_nav_bridge_versions.md`
- Include performance metrics
- Include known issues for each version
- Include migration guide between versions

## Benefits of Proper Versioning

1. **Clarity**: Instantly know which implementation is newer
2. **Rollback**: Easy to revert to previous working version
3. **Testing**: Can A/B test different versions
4. **History**: Clear evolution of solutions
5. **Debugging**: Know exactly which version is running

## Enforcement

- Code reviews MUST reject PRs with ambiguous file names
- CI/CD should flag files with prohibited terms
- Regular audits to ensure compliance

This versioning standard ensures professional, maintainable code that clearly communicates the evolution and purpose of each implementation.
