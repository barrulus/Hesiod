/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
 * Public License. The full license is in the file LICENSE, distributed with
 * this software. */
#include "highmap/flora/forest.hpp"
#include "highmap/virtual_array/virtual_array.hpp"

#include "hesiod/logger.hpp"
#include "hesiod/model/nodes/attributes.hpp"
#include "hesiod/model/nodes/base_node.hpp"
#include "hesiod/model/nodes/post_process.hpp"

namespace hesiod
{

// -----------------------------------------------------------------------------
// Ports & Attributes
// -----------------------------------------------------------------------------

constexpr const char *P_INPUT        = "input";
constexpr const char *P_OUTPUT       = "output";
constexpr const char *P_ELEVATION    = "elevation";
constexpr const char *P_DENSITY_MASK = "density_mask";

constexpr const char *A_SCALE_RADIUS     = "scale_radius";
constexpr const char *A_PRUNE_COLLISIONS = "prune_collisions";
constexpr const char *A_PRUNE_DENSITY    = "prune_density";
constexpr const char *A_SEED             = "seed";

void setup_forest_process_node(BaseNode &node)
{
  Logger::log()->trace("setup node {}", node.get_label());

  // --- Ports

  node.add_port<hmap::Forest>(gnode::PortType::IN, P_INPUT);
  node.add_port<hmap::VirtualArray>(gnode::PortType::IN, P_ELEVATION);
  node.add_port<hmap::VirtualArray>(gnode::PortType::IN, P_DENSITY_MASK);
  node.add_port<hmap::Forest>(gnode::PortType::OUT, P_OUTPUT);

  // --- Attributes

  add_float(node, A_SCALE_RADIUS, "Scale Radius", 1.0f, 0.0001f, 100.f, "{:.2e}", true);
  add_bool(node, A_PRUNE_COLLISIONS, "Prune Collisions", false);
  add_float(node, A_PRUNE_DENSITY, "Prune Density", 1.0f, 0.0f, 1.0f);
  add_seed(node, A_SEED, "Seed");
}

void compute_forest_process_node(BaseNode &node)
{
  Logger::log()->trace("computing node [{}]/[{}]", node.get_label(), node.get_id());

  hmap::Forest *p_in_forest  = node.get_value_ref<hmap::Forest>(P_INPUT);
  hmap::Forest *p_out_forest = node.get_value_ref<hmap::Forest>(P_OUTPUT);

  if (!p_in_forest || !p_out_forest)
    return;

  *p_out_forest = *p_in_forest;

  // --- 1. Set elevation from heightmap (optional input)

  hmap::VirtualArray *p_elevation = node.get_value_ref<hmap::VirtualArray>(P_ELEVATION);
  if (p_elevation)
  {
    hmap::Array elev_array = p_elevation->to_array(node.cfg().cm_cpu);
    p_out_forest->set_elevation_from_terrain(elev_array);
  }

  // --- 2. Scale radius (default 1.0, nothing)

  const float scale_radius = node.val<float>(A_SCALE_RADIUS);
  if (std::abs(scale_radius - 1.0f) > 1e-6f)
  {
    for (auto &item : *p_out_forest)
      item.radius *= scale_radius;
  }

  // --- 3. Prune collisions (on/off)

  if (node.val<bool>(A_PRUNE_COLLISIONS))
  {
    p_out_forest->prune_collisions();
  }

  // --- 4. Prune density (default 1.0, nothing)

  const float prune_density_ratio = node.val<float>(A_PRUNE_DENSITY);
  if (prune_density_ratio < 1.0f - 1e-6f)
  {
    const auto          seed           = static_cast<uint32_t>(node.val<int>(A_SEED));
    hmap::VirtualArray *p_density_mask = node.get_value_ref<hmap::VirtualArray>(
        P_DENSITY_MASK);

    if (p_density_mask)
    {
      hmap::Array mask_array = p_density_mask->to_array(node.cfg().cm_cpu);
      p_out_forest->prune_density(mask_array, prune_density_ratio, seed);
    }
    else
    {
      hmap::Array uniform_mask(node.cfg().shape, 1.0f);
      p_out_forest->prune_density(uniform_mask, prune_density_ratio, seed);
    }
  }
}

} // namespace hesiod
