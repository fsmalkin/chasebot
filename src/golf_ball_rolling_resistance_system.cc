#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <string>

#include <gz/math/Pose3.hh>
#include <gz/math/Quaternion.hh>
#include <gz/math/Vector3.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Types.hh>
#include <sdf/Element.hh>

namespace chasecar
{
class GolfBallRollingResistance:
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate,
  public gz::sim::ISystemPostUpdate
{
  public: void Configure(
    const gz::sim::Entity &_entity,
    const std::shared_ptr<const sdf::Element> &_sdf,
    gz::sim::EntityComponentManager &,
    gz::sim::EventManager &) override
  {
    this->modelEntity = _entity;
    if (_sdf->HasElement("link_name"))
      this->linkName = _sdf->Get<std::string>("link_name");
    if (_sdf->HasElement("linear_decel_mps2"))
      this->linearDecelMps2 = _sdf->Get<double>("linear_decel_mps2");
    if (_sdf->HasElement("ball_radius_m"))
      this->ballRadiusM = _sdf->Get<double>("ball_radius_m");
    if (_sdf->HasElement("stop_speed_threshold_mps"))
      this->stopSpeedThresholdMps = _sdf->Get<double>("stop_speed_threshold_mps");
  }

  public: void PreUpdate(
    const gz::sim::UpdateInfo &_info,
    gz::sim::EntityComponentManager &_ecm) override
  {
    if (_info.paused || this->linearDecelMps2 <= 0.0)
      return;

    gz::sim::Model model(this->modelEntity);
    const auto linkEntity = model.LinkByName(_ecm, this->linkName);
    if (linkEntity == gz::sim::kNullEntity)
      return;
    if (!this->observedVelocitySeen || this->observedVelocityDt <= 0.0)
      return;

    gz::sim::Link link(linkEntity);
    const double vx = this->observedVelocityVx;
    const double vy = this->observedVelocityVy;
    const double planarSpeed = std::sqrt(vx * vx + vy * vy);
    if (planarSpeed <= this->stopSpeedThresholdMps)
    {
      link.SetLinearVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      link.SetAngularVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      return;
    }

    const double nextSpeed = std::max(0.0, planarSpeed - this->linearDecelMps2 * this->observedVelocityDt);
    if (nextSpeed <= this->stopSpeedThresholdMps)
    {
      link.SetLinearVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      link.SetAngularVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      return;
    }

    const double scale = nextSpeed / planarSpeed;
    const gz::math::Vector3d worldLinear(scale * vx, scale * vy, 0);
    const auto localLinear = this->lastPostPoseRot.Inverse().RotateVector(worldLinear);
    link.SetLinearVelocity(_ecm, localLinear);

    const double radius = std::max(this->ballRadiusM, 1e-9);
    const gz::math::Vector3d worldAngular(-worldLinear.Y() / radius, worldLinear.X() / radius, 0);
    const auto localAngular = this->lastPostPoseRot.Inverse().RotateVector(worldAngular);
    link.SetAngularVelocity(_ecm, localAngular);
  }

  public: void PostUpdate(
    const gz::sim::UpdateInfo &_info,
    const gz::sim::EntityComponentManager &_ecm) override
  {
    gz::sim::Model model(this->modelEntity);
    const auto linkEntity = model.LinkByName(_ecm, this->linkName);
    if (linkEntity == gz::sim::kNullEntity)
      return;

    gz::sim::Link link(linkEntity);
    const auto pose = link.WorldPose(_ecm);
    if (!pose)
      return;

    if (this->lastPostPoseSeen)
    {
      const double dt = std::chrono::duration<double>(_info.simTime - this->lastPostPoseSimTime).count();
      if (dt > 0.0)
      {
        this->observedVelocityVx = (pose->Pos().X() - this->lastPostPoseX) / dt;
        this->observedVelocityVy = (pose->Pos().Y() - this->lastPostPoseY) / dt;
        this->observedVelocityDt = dt;
        this->observedVelocitySeen = true;
      }
    }

    this->lastPostPoseSeen = true;
    this->lastPostPoseSimTime = _info.simTime;
    this->lastPostPoseX = pose->Pos().X();
    this->lastPostPoseY = pose->Pos().Y();
    this->lastPostPoseRot = pose->Rot();
  }

  private: gz::sim::Entity modelEntity{gz::sim::kNullEntity};
  private: std::string linkName{"link"};
  private: double linearDecelMps2{0.72};
  private: double ballRadiusM{0.021336};
  private: double stopSpeedThresholdMps{0.03};
  private: bool lastPostPoseSeen{false};
  private: std::chrono::steady_clock::duration lastPostPoseSimTime{std::chrono::steady_clock::duration::zero()};
  private: double lastPostPoseX{0.0};
  private: double lastPostPoseY{0.0};
  private: gz::math::Quaterniond lastPostPoseRot{1, 0, 0, 0};
  private: bool observedVelocitySeen{false};
  private: double observedVelocityVx{0.0};
  private: double observedVelocityVy{0.0};
  private: double observedVelocityDt{0.0};
};
}

GZ_ADD_PLUGIN(
  chasecar::GolfBallRollingResistance,
  gz::sim::System,
  chasecar::GolfBallRollingResistance::ISystemConfigure,
  chasecar::GolfBallRollingResistance::ISystemPreUpdate,
  chasecar::GolfBallRollingResistance::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(
  chasecar::GolfBallRollingResistance,
  "chasecar::GolfBallRollingResistance")
