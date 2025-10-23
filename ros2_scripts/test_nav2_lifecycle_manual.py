#!/usr/bin/env python3
"""
Manual Lifecycle Transition Script for Nav2
Allows step-by-step lifecycle transitions to debug issues
"""

import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import GetState, ChangeState
from lifecycle_msgs.msg import Transition
import time
import sys

class LifecycleDebugger(Node):
    def __init__(self):
        super().__init__('lifecycle_debugger')
        self.get_logger().info('Lifecycle Debugger started')
        
        # Define lifecycle transitions
        self.TRANSITION_CONFIGURE = Transition.TRANSITION_CONFIGURE
        self.TRANSITION_CLEANUP = Transition.TRANSITION_CLEANUP
        self.TRANSITION_ACTIVATE = Transition.TRANSITION_ACTIVATE
        self.TRANSITION_DEACTIVATE = Transition.TRANSITION_DEACTIVATE
        self.TRANSITION_SHUTDOWN = Transition.TRANSITION_SHUTDOWN
        
        # State names for display
        self.state_names = {
            1: "unconfigured",
            2: "inactive",
            3: "active",
            4: "finalized"
        }
        
    def get_state(self, node_name):
        """Get current lifecycle state of a node"""
        client = self.create_client(GetState, f'/{node_name}/get_state')
        
        if not client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error(f'Service /{node_name}/get_state not available')
            return None
            
        request = GetState.Request()
        future = client.call_async(request)
        
        # Wait for response
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        
        if future.result() is not None:
            state_id = future.result().current_state.id
            state_name = self.state_names.get(state_id, f"unknown({state_id})")
            self.get_logger().info(f'{node_name} is in state: {state_name}')
            return state_id
        else:
            self.get_logger().error(f'Failed to get state for {node_name}')
            return None
            
    def change_state(self, node_name, transition):
        """Change lifecycle state of a node"""
        client = self.create_client(ChangeState, f'/{node_name}/change_state')
        
        if not client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error(f'Service /{node_name}/change_state not available')
            return False
            
        request = ChangeState.Request()
        request.transition.id = transition
        
        self.get_logger().info(f'Requesting transition {transition} for {node_name}...')
        future = client.call_async(request)
        
        # Wait for response
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        
        if future.result() is not None:
            success = future.result().success
            if success:
                self.get_logger().info(f'Transition successful for {node_name}')
            else:
                self.get_logger().error(f'Transition failed for {node_name}')
            return success
        else:
            self.get_logger().error(f'Transition request timed out for {node_name}')
            return False
            
    def debug_node(self, node_name):
        """Debug lifecycle transitions for a single node"""
        self.get_logger().info(f'\n=== Debugging {node_name} ===')
        
        # Get initial state
        state = self.get_state(node_name)
        if state is None:
            return False
            
        # If unconfigured, try to configure
        if state == 1:  # unconfigured
            self.get_logger().info(f'Attempting to configure {node_name}...')
            if self.change_state(node_name, self.TRANSITION_CONFIGURE):
                time.sleep(2)
                state = self.get_state(node_name)
            else:
                self.get_logger().error(f'Failed to configure {node_name}')
                return False
                
        # If inactive, try to activate
        if state == 2:  # inactive
            self.get_logger().info(f'Attempting to activate {node_name}...')
            if self.change_state(node_name, self.TRANSITION_ACTIVATE):
                time.sleep(2)
                state = self.get_state(node_name)
            else:
                self.get_logger().error(f'Failed to activate {node_name}')
                return False
                
        # Check final state
        if state == 3:  # active
            self.get_logger().info(f'{node_name} is now ACTIVE!')
            return True
        else:
            self.get_logger().error(f'{node_name} is not active (state: {state})')
            return False
            
    def run_debug_sequence(self):
        """Run debugging sequence for Nav2 nodes"""
        nodes_to_debug = ['controller_server', 'planner_server']
        
        self.get_logger().info('Starting Nav2 lifecycle debugging...')
        self.get_logger().info('Make sure Nav2 nodes are running but not managed by lifecycle_manager!')
        
        # Check if nodes are available
        for node_name in nodes_to_debug:
            self.get_logger().info(f'\nChecking {node_name}...')
            state = self.get_state(node_name)
            if state is None:
                self.get_logger().error(f'{node_name} not found. Make sure it is running.')
                return
                
        # Debug each node
        input("\nPress Enter to start debugging sequence...")
        
        for node_name in nodes_to_debug:
            input(f"\nPress Enter to debug {node_name}...")
            success = self.debug_node(node_name)
            if not success:
                self.get_logger().error(f'Failed to activate {node_name}. Check terminal output for errors.')
                break
                
        # Final status
        self.get_logger().info('\n=== Final Status ===')
        for node_name in nodes_to_debug:
            self.get_state(node_name)
            
def main():
    rclpy.init()
    
    debugger = LifecycleDebugger()
    
    try:
        debugger.run_debug_sequence()
    except KeyboardInterrupt:
        debugger.get_logger().info('Debugging interrupted')
    finally:
        debugger.destroy_node()
        rclpy.shutdown()
        
if __name__ == '__main__':
    main()
