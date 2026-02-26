cmake_minimum_required(VERSION 3.8)
project(chasebot_description)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Install ROS 2 launch files
install(DIRECTORY ros2_config/launch
  DESTINATION share/${PROJECT_NAME}/
)

# Install ROS 2 URDF files
install(DIRECTORY ros2_config/urdf
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)
install(DIRECTORY ros2_config/urdf
  DESTINATION share/${PROJECT_NAME}/
)

# Install ROS 2 world files
install(DIRECTORY ros2_config/worlds
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)
install(DIRECTORY ros2_config/worlds
  DESTINATION share/${PROJECT_NAME}/
)

# Install ROS 2 params files
install(DIRECTORY ros2_config/params
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)
install(DIRECTORY ros2_config/params
  DESTINATION share/${PROJECT_NAME}/
)

# Install ROS 2 config files  
install(DIRECTORY ros2_config/config
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)
install(DIRECTORY ros2_config/config
  DESTINATION share/${PROJECT_NAME}/
)

# Install ROS 2 behavior trees
install(DIRECTORY ros2_config/behavior_trees
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)
install(DIRECTORY ros2_config/behavior_trees
  DESTINATION share/${PROJECT_NAME}/
)

# Install Python scripts as executables
install(PROGRAMS
  ros2_scripts/shutdown_manager.py
  ros2_scripts/cleanup_before_launch.py
  ros2_scripts/blank_map_publisher.py
  ros2_scripts/blank_map_publisher_quiet.py
  ros2_scripts/ros2_yolo_detector.py
  ros2_scripts/ros2_yolo_detector_quiet.py
  ros2_scripts/ros2_yolo_detector_silent.py
  ros2_scripts/ros2_yolo_detector_frisbee.py
  ros2_scripts/ros2_yolo_detector_frisbee_quiet.py
  ros2_scripts/ros2_yolo_detector_headless.py
  ros2_scripts/ros2_vision_to_laserscan_hsv.py
  ros2_scripts/ros2_ball_to_nav_goal.py
  ros2_scripts/ros2_yolo_to_nav_goal_v3.0.0.py
  ros2_scripts/yolo_3d_position_extractor.py
  ros2_scripts/yolo_3d_to_nav2_bridge.py
  ros2_scripts/yolo_3d_direct_follower.py
  ros2_scripts/yolo_3d_direct_follower_v2.py
  scripts/coordinate_uat_runner.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install workflow helper scripts (Windows + Python utilities)
install(DIRECTORY scripts
  DESTINATION share/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.ps1" PATTERN "*.py"
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
