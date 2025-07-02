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

# Install Python scripts as executables
install(PROGRAMS
  ros2_scripts/shutdown_manager.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
