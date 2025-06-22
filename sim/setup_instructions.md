# Webots Installation and Setup Instructions

## Manual Webots Installation

Since automated installation failed, please follow these manual steps:

### Step 1: Download Webots
1. Visit: https://cyberbotics.com
2. Click "Download" in the navigation
3. Select "Windows Installer (.exe)" from the dropdown
4. Download the installer (approximately 250MB)

### Step 2: Install Webots
1. Run the downloaded installer as Administrator
2. Follow the installation wizard
3. Accept the license agreement
4. Choose installation directory (default is recommended)
5. Complete the installation

### Step 3: Verify Installation
After installation, verify Webots is working:
```cmd
webots --version
```

### Step 4: Environment Setup
Add Webots to your PATH if not done automatically:
1. Open System Properties > Environment Variables
2. Add Webots installation directory to PATH
3. Restart VS Code to reload environment

## Next Steps After Installation
Once Webots is installed, the simulation environment is ready to use with our pre-configured world files.

## Testing Movement System

### Quick Movement Test
```cmd
cd c:/workspaces/chasebot/sim
python auto_run_with_controller.py test_manual_movement.py
```

### High-Speed Visible Movement Test
```cmd
cd c:/workspaces/chasebot/sim
python auto_run_with_controller.py test_high_speed_movement.py
```

### Position Tracking Test (for debugging)
```cmd
cd c:/workspaces/chasebot/sim
python auto_run_with_controller.py test_movement_supervisor.py
```

## Important Configuration Notes

### Motor Device Names
- Left motor: `"left_wheel_hinge"`
- Right motor: `"right_wheel_hinge"`
- **NOT** "left wheel motor" or "right wheel motor"

### Motor Velocity Scaling
- Low velocities (1.0 rad/s): Barely visible movement (~0.1mm)
- Practical velocities: 10-50 rad/s for visible movement
- High-speed test uses 50 rad/s for demonstration

### Physics Configuration
The ChaseBot world file includes proper physics configuration:
- Mass: 2.5kg
- Inertia matrix properly configured
- Contact friction: 8.0 (high traction)

## Available Test Scripts

1. **test_manual_movement.py** - Basic movement sequence test
2. **test_movement_supervisor.py** - Movement with position tracking
3. **test_high_speed_movement.py** - High-speed visible movement test
4. **discover_devices.py** - Device discovery and enumeration
5. **diagnose_physics.py** - Physics configuration diagnostics

## World Files

1. **chasebot_world.wbt** - Full environment with golf balls
2. **simple_test_world.wbt** - Minimal test environment

## Running Custom Controllers

Use the flexible launcher to test any controller:
```cmd
python auto_run_with_controller.py [controller_script.py]
```

## Troubleshooting

### No Movement Visible
- Check motor velocities (increase to 10-50 for visible movement)
- Verify physics is enabled in world file
- Use position tracking test to verify actual movement

### Motor Not Found Errors
- Ensure using correct device names: "left_wheel_hinge", "right_wheel_hinge"
- Run device discovery script to enumerate available devices

### Physics Issues
- Run physics diagnostic script to check configuration
- Verify robot has physics field with proper mass and inertia
