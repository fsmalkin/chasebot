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
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)

# Install ROS 2 URDF files
install(DIRECTORY ros2_config/urdf
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)

# Install ROS 2 world files
install(DIRECTORY ros2_config/worlds
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)

# Install ROS 2 params files
install(DIRECTORY ros2_config/params
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)

# Install ROS 2 behavior trees
install(DIRECTORY ros2_config/behavior_trees
  DESTINATION share/${PROJECT_NAME}/ros2_config/
)

# Install Python scripts as executables
install(PROGRAMS
  ros2_scripts/shutdown_manager.py
  ros2_scripts/cleanup_before_launch.py
  ros2_scripts/ros2_yolo_detector.py
  ros2_scripts/ros2_yolo_detector_quiet.py
  ros2_scripts/ros2_yolo_detector_silent.py
  ros2_scripts/ros2_yolo_to_nav_goal.py
  ros2_scripts/ros2_yolo_to_nav_goal_fixed.py
  ros2_scripts/ros2_yolo_to_nav_goal_corrected.py
  ros2_scripts/ros2_yolo_to_nav_goal_v1.0.0.py
  ros2_scripts/ros2_yolo_to_nav_goal_v1.1.0.py
  ros2_scripts/ros2_yolo_to_nav_goal_v1.2.0.py
  ros2_scripts/ros2_yolo_to_nav_goal_v2.0.0.py
  ros2_scripts/blank_map_publisher.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
