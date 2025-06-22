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
Once Webots is installed, run:
```cmd
cd c:/workspaces/chasebot/sim
python setup_jetbot_world.py
```

This will create the initial JetBot world and controller files.
