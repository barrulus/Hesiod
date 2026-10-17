/* Copyright (c) 2023 Otto Link. Distributed under the terms of the GNU General
 * Public License. The full license is in the file LICENSE, distributed with
 * this software. */
#include "highmap/carving.hpp"
#include "highmap/hydrology/hydrology.hpp"

#include "hesiod/model/nodes/attributes.hpp"

#include "hesiod/app/enum_mappings.hpp"
#include "hesiod/logger.hpp"
#include "hesiod/model/nodes/base_node.hpp"

namespace hesiod
{

// -----------------------------------------------------------------------------
// Ports & Attributes
// -----------------------------------------------------------------------------

constexpr const char *P_IN          = "input";
constexpr const char *P_NOISE_R     = "noise_r";
constexpr const char *P_OUT         = "output";
constexpr const char *P_SOURCES     = "sources";
constexpr const char *P_WATER_DEPTH = "water_depth";

constexpr const char *A_CONTROL_POINTS_COUNT          = "control_points_count";
constexpr const char *A_DEPTH                         = "depth";
constexpr const char *A_DISTANCE_EXPONENT             = "distance_exponent";
constexpr const char *A_ELEVATION_RATIO               = "elevation_ratio";
constexpr const char *A_ENABLE_WIDTH_DISTANCE_SCALING = "enable_width_distance_scaling";
constexpr const char *A_FAVOR_DOMAIN_CENTER           = "favor_domain_center";
constexpr const char *A_RADIAL_PROFILE                = "radial_profile";
constexpr const char *A_RADIAL_PROFILE_PARAMETER      = "radial_profile_parameter";
constexpr const char *A_SEED                          = "seed";
constexpr const char *A_UPWARD_PENALIZATION           = "upward_penalization";
constexpr const char *A_WIDTH                         = "width";

// -----------------------------------------------------------------------------
// Setup
// -----------------------------------------------------------------------------

void setup_flow_stream_node(BaseNode &node)
{
  Logger::log()->trace("setup node {}", node.get_label());

  // --- Ports

  node.add_port<hmap::VirtualArray>(gnode::PortType::IN, P_IN);
  node.add_port<hmap::Cloud>(gnode::PortType::IN, P_SOURCES);
  node.add_port<hmap::VirtualArray>(gnode::PortType::IN, P_NOISE_R);
  node.add_port<hmap::VirtualArray>(gnode::PortType::OUT, P_OUT, CONFIG(node));
  node.add_port<hmap::VirtualArray>(gnode::PortType::OUT, P_WATER_DEPTH, CONFIG(node));

  // --- Attributes

  // clang-format off
  node.set_current_category("Pathfinding");
  add_seed(node, A_SEED, "Seed");
  add_int(node, A_CONTROL_POINTS_COUNT, "Control Points Count", 20000, 100, 50000);
  add_float(node, A_ELEVATION_RATIO, "Elevation vs Slope Weight", 0.5f, 0.f, 0.99f);
  add_float(node, A_DISTANCE_EXPONENT, "Distance Exponent", 2.f, 0.1f, 4.f);
  add_float(node, A_UPWARD_PENALIZATION, "Upward Penalization", 100.f, 0.f, 1000.f);
  add_bool(node, A_FAVOR_DOMAIN_CENTER, "Favor Domain Center", true);

  node.set_current_category("Riverbed");
  add_float(node, A_DEPTH, "Depth", 0.02f, 0.f, 0.2f);

  node.set_current_category("Carving");
  add_float(node, A_WIDTH, "Width", 0.02f, 0.001f, 0.2f);
  add_enum(node, A_RADIAL_PROFILE, "Radial Profile", enum_mappings.radial_profile_map, "Smoothstep Upper");
  add_float(node, A_RADIAL_PROFILE_PARAMETER, "Profile Sharpness", 2.f, 0.f, 8.f);
  add_bool(node, A_ENABLE_WIDTH_DISTANCE_SCALING, "Width Distance Scaling", false);
  // clang-format on
}

// -----------------------------------------------------------------------------
// Compute
// -----------------------------------------------------------------------------

void compute_flow_stream_node(BaseNode &node)
{
  Logger::log()->trace("computing node [{}]/[{}]", node.get_label(), node.get_id());

  const auto *p_in          = node.get_value_ref<hmap::VirtualArray>(P_IN);
  const auto *p_cloud       = node.get_value_ref<hmap::Cloud>(P_SOURCES);
  const auto *p_noise_r     = node.get_value_ref<hmap::VirtualArray>(P_NOISE_R);
  auto       *p_out         = node.get_value_ref<hmap::VirtualArray>(P_OUT);
  auto       *p_water_depth = node.get_value_ref<hmap::VirtualArray>(P_WATER_DEPTH);

  if (!p_in)
    return;

  if (!p_cloud || p_cloud->empty())
  {
    p_out->copy_from(*p_in, node.cfg().cm_cpu);
    p_water_depth->fill(0.f, node.cfg().cm_cpu);
    p_out->sync_overlap_buffers();
    p_water_depth->sync_overlap_buffers();
    return;
  }

  // --- Parameters

  // clang-format off
  const auto seed                 = static_cast<std::uint32_t>(node.val<int>(A_SEED));
  const auto control_points_count = static_cast<size_t>(node.val<int>(A_CONTROL_POINTS_COUNT));
  const auto elevation_ratio      = node.val<float>(A_ELEVATION_RATIO);
  const auto distance_exponent    = node.val<float>(A_DISTANCE_EXPONENT);
  const auto upward_penalization  = node.val<float>(A_UPWARD_PENALIZATION);
  const auto favor_domain_center  = node.val<bool>(A_FAVOR_DOMAIN_CENTER);

  const auto depth                          = node.val<float>(A_DEPTH);
  const auto width                          = node.val<float>(A_WIDTH);
  const auto radial_profile                 = node.val_enum<hmap::RadialProfile>(A_RADIAL_PROFILE);
  const auto radial_profile_parameter       = node.val<float>(A_RADIAL_PROFILE_PARAMETER);
  const auto enable_width_distance_scaling  = node.val<bool>(A_ENABLE_WIDTH_DISTANCE_SCALING);
  // clang-format on

  // --- Flow stream paths

  std::vector<hmap::Path> path_list;
  path_list.reserve(p_cloud->size());

  for (const auto &p : *p_cloud)
  {
    hmap::Path path = hmap::va::flow_stream(node.cfg().cm_cpu,
                                            *p_in,
                                            glm::vec2(p.x, p.y),
                                            seed,
                                            control_points_count,
                                            elevation_ratio,
                                            distance_exponent,
                                            upward_penalization,
                                            favor_domain_center);

    if (path.size() > 1)
      path_list.push_back(std::move(path));
  }

  // --- Carve river trench

  hmap::for_each_tile(
      {p_in, p_noise_r},
      {p_out, p_water_depth},
      [&](std::vector<const hmap::Array *> p_arrays_in,
          std::vector<hmap::Array *>       p_arrays_out,
          const hmap::TileRegion          &region)
      {
        auto [pa_in, pa_noise_r]      = unpack<2>(p_arrays_in);
        auto [pa_out, pa_water_depth] = unpack<2>(p_arrays_out);

        *pa_out = *pa_in;

        if (path_list.empty())
        {
          *pa_water_depth = 0.f;
          return;
        }

        hmap::trench(*pa_out,
                     path_list,
                     width,
                     /* enable_width_depth_scaling */ enable_width_distance_scaling,
                     /* enable_width_distance_scaling */ enable_width_distance_scaling,
                     /* enable_width_curvature_scaling */ false,
                     /* curvature_radius_min */ 1.f,
                     /* curv_width_ratio_min */ 0.5f,
                     /* curv_width_ratio_max */ 2.f,
                     radial_profile,
                     radial_profile_parameter,
                     hmap::ElevationLongitudinalProfile::ELP_DECREASING,
                     /* elevation_shift */ -depth,
                     /* shift_ramp_start_ratio */ 0.f,
                     /* shift_ramp_end_ratio */ 0.f,
                     /* min_slope */ 0.001f,
                     /* k_neighbors */ 8,
                     /* p_noise_r */ pa_noise_r,
                     /* p_bending_mask */ nullptr,
                     /* tile_size */ 32,
                     /* bbox */ region.bbox);

        *pa_water_depth = *pa_in - *pa_out;
      },
      node.cfg().cm_single_array);

  p_out->sync_overlap_buffers();
  p_water_depth->sync_overlap_buffers();
}

} // namespace hesiod
