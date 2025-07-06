# JetBot URDF vs SDF Configuration Comparison

**Date**: 2025-07-06  
**Purpose**: Verify configuration consistency after wheel axis fix

## Configuration Comparison

### ✅ Matching Elements

#### Dimensions
- **Base**: 0.15 x 0.12 x 0.08m (identical)
- **Wheels**: radius 0.032m, length 0.02m (identical)
- **Casters**: radius 0.015m (identical)
- **Wheel separation**: 0.16m (0.08m each side)

#### Masses
- **Base**: 2.5kg (identical)
- **Wheels**: 0.1kg each (identical)
- **Casters**: 0.05kg each (identical)

#### Inertias
- All inertia values match between URDF and SDF

#### Positions
- **Base**: Z=0.05m (identical)
- **Wheels**: Y=±0.08m, Z=0.032m (identical)
- **Front caster**: X=0.06m, Z=0.015m (identical)
- **Back caster**: X=-0.06m, Z=0.015m (identical)

#### Friction
- **Wheels**: mu=100.0, mu2=100.0 (identical)
- **Casters**: mu=0.0, mu2=0.0 (frictionless, identical)

### 🔧 Fixed Issues

#### Wheel Joint Axes
- **Old URDF**: `<axis xyz="0 1 0"/>` (Y-axis)
- **Fixed SDF**: `<axis><xyz>0 0 1</xyz></axis>` (Z-axis)
- **Reason**: Ignition Gazebo requires Z-axis for wheels rotated 90° around X

### 📝 Intentional Differences

#### Control System
- **Old URDF**: `libgazebo_ros_diff_drive.so` plugin
- **New SDF**: `gz_ros2_control` with velocity controllers
- **Status**: Keeping gz_ros2_control per user preference

#### Camera
- **Old URDF**: Has camera link, joint, and sensor plugin
- **New SDF**: No camera (deferred to next slice)
- **Next step**: Add camera after movement validation

### ✅ Validation Complete

All critical mechanical configurations match between the old working URDF and the new SDF:
- Robot dimensions ✓
- Mass properties ✓
- Joint positions ✓
- Friction parameters ✓
- Wheel axes (now fixed) ✓

The only missing element is the camera, which will be added in the next development slice after movement is validated.
