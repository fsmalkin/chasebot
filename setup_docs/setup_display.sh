#!/bin/bash
# ChaseBot GUI Environment Stabilization Script
# File: ~/bin/setup_display.sh

echo '🔧 Setting up stable X11 display environment...'

# Method 1: Use WSL2 default gateway (most reliable)
DISPLAY_IP=$(ip route show default | awk '{print $3}')
export DISPLAY=${DISPLAY_IP}:0

echo "📡 Using DISPLAY: $DISPLAY"

# Set OpenGL compatibility for WSL2
export LIBGL_ALWAYS_INDIRECT=1
export MESA_GL_VERSION_OVERRIDE=3.3

# Test X11 connection
echo '🧪 Testing X11 connection...'
if command -v xset &> /dev/null; then
    if xset q >/dev/null 2>&1; then
        echo '✅ X11 connection successful!'
        echo "📊 Display server info: $(xset q | head -2 | tail -1)"
    else
        echo '❌ X11 connection failed!'
        echo '💡 Troubleshooting steps:'
        echo '   1. Ensure VcXsrv is running'
        echo '   2. Check Windows Firewall allows VcXsrv'
        echo '   3. Verify VcXsrv launched with -ac parameter'
        exit 1
    fi
else
    echo '⚠️  xset not found, installing x11-utils...'
    sudo apt update && sudo apt install -y x11-utils
fi

# Add to current session
export DISPLAY LIBGL_ALWAYS_INDIRECT MESA_GL_VERSION_OVERRIDE

echo '🎯 GUI environment ready for ROS 2 + Gazebo'
echo "📋 Environment variables set:"
echo "   DISPLAY=$DISPLAY"
echo "   LIBGL_ALWAYS_INDIRECT=$LIBGL_ALWAYS_INDIRECT"
echo "   MESA_GL_VERSION_OVERRIDE=$MESA_GL_VERSION_OVERRIDE"
