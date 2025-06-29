#!/bin/bash
# ChaseBot GUI Stability Testing Script
# File: ~/bin/test_gui_stability.sh

echo "🧪 Testing GUI stability for ChaseBot UAT..."

# Source display setup
if [ -f ~/bin/setup_display.sh ]; then
    source ~/bin/setup_display.sh
else
    echo "❌ Display setup script not found!"
    exit 1
fi

PASS_COUNT=0
FAIL_COUNT=0
TOTAL_TESTS=5

echo "🔄 Running $TOTAL_TESTS Gazebo stability tests..."

for i in $(seq 1 $TOTAL_TESTS); do
    echo ""
    echo "📋 Test $i/$TOTAL_TESTS: Starting Gazebo..."
    
    # Start Gazebo in background with timeout
    timeout 30s gazebo --verbose &>/dev/null &
    GAZEBO_PID=$!
    
    # Wait for startup
    sleep 8
    
    # Check if Gazebo is still running
    if ps -p $GAZEBO_PID > /dev/null; then
        echo "✅ Test $i: Gazebo started successfully"
        PASS_COUNT=$((PASS_COUNT + 1))
        
        # Clean shutdown
        kill $GAZEBO_PID 2>/dev/null
        wait $GAZEBO_PID 2>/dev/null
    else
        echo "❌ Test $i: Gazebo failed to start or crashed"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # Wait between tests
    sleep 3
    
    # Kill any remaining Gazebo processes
    pkill -f gazebo 2>/dev/null
    sleep 1
done

echo ""
echo "📊 GUI Stability Test Results:"
echo "✅ Successful starts: $PASS_COUNT/$TOTAL_TESTS"
echo "❌ Failed starts: $FAIL_COUNT/$TOTAL_TESTS"

SUCCESS_RATE=$((PASS_COUNT * 100 / TOTAL_TESTS))
echo "📈 Success rate: $SUCCESS_RATE%"

if [ $SUCCESS_RATE -ge 80 ]; then
    echo "🎯 GUI environment is STABLE (≥80% success rate)"
    exit 0
elif [ $SUCCESS_RATE -ge 60 ]; then
    echo "⚠️  GUI environment is UNSTABLE (60-79% success rate)"
    echo "💡 Consider implementing backup solutions"
    exit 1
else
    echo "🚫 GUI environment is UNRELIABLE (<60% success rate)"
    echo "💡 Immediate action required - use alternative solutions"
    exit 2
fi
