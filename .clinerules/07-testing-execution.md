# Testing and Execution Standards

## Direct Execution Over Documentation

### Core Principle
**Execute tests directly instead of creating UAT documentation**
- Skip creating detailed UAT procedures
- Run tests immediately with direct terminal commands
- Report results in real-time
- Document only critical findings, not procedures

### Implementation Pattern
```bash
# ❌ AVOID: Creating UAT docs
Creating slice15_camera_test_uat.md...

# ✅ DO: Direct execution
wsl -d Ubuntu-22.04 -- bash -c "command to test"
```

## Terminal Diagnostics Over Scripts

### Core Principle
**Use direct terminal commands for diagnostics instead of creating diagnostic scripts**
- Scripts add debugging overhead and complexity
- Direct commands provide immediate feedback
- Easier to iterate and adjust on the fly
- No file sync or permission issues

### Diagnostic Patterns

#### ❌ AVOID: Creating diagnostic scripts
```python
# Creating fix_display_and_test_camera.py
# Writing complex logic to test displays
# Debugging the script itself
```

#### ✅ PREFER: Direct terminal diagnostics
```bash
# Test display directly
wsl -d Ubuntu-22.04 -- bash -c "export DISPLAY=:0.0 && timeout 2 xset q"

# Check camera topics
wsl -d Ubuntu-22.04 -- bash -c "source /opt/ros/humble/setup.bash && ros2 topic list | grep d415"

# Test camera data flow
wsl -d Ubuntu-22.04 -- bash -c "source /opt/ros/humble/setup.bash && ros2 topic hz /d415/image_raw"
```

## Execution Workflow

### 1. Immediate Testing
- Start with simplest possible test
- Build complexity only if needed
- Report results immediately

### 2. Progressive Diagnostics
```bash
# Level 1: Basic connectivity
wsl -d Ubuntu-22.04 -- bash -c "echo 'WSL2 is responsive'"

# Level 2: Service availability  
wsl -d Ubuntu-22.04 -- bash -c "ros2 topic list"

# Level 3: Specific functionality
wsl -d Ubuntu-22.04 -- bash -c "ros2 topic echo /d415/image_raw --once"
```

### 3. Real-time Reporting
- Show command being executed
- Display output immediately
- Interpret results concisely
- Move to next step quickly

## Benefits

1. **Faster Development**: No time wasted on documentation that won't be used
2. **Immediate Feedback**: See what works/fails right away
3. **Less Debugging**: No script bugs to debug
4. **Direct Control**: Adjust commands on the fly based on results

## Exception Cases

Only create scripts when:
- Complex logic is genuinely needed (rare)
- Automation will be reused many times
- User specifically requests a script

Otherwise, always prefer direct terminal execution.
