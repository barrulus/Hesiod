/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
 * Public License. The full license is in the file LICENSE, distributed with
 * this software. */
#include "highmap/flora/forest.hpp"
#include "highmap/scatter/scatter_field.hpp"
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

  add_float(node, A_SCALE_RADIUS, "Scale Radius", 1.0f, 0.0001f, 100.0f, "{:.2e}", true);
  add_bool(node, A_PRUNE_COLLISIONS, "Prune Collisions", false);
  add_float(node, A_PRUNE_DENSITY, "Prune Density", 1.0f, 0.0f, 1.0f);
  add_seed(node, A_SEED, "Seed");
}

void compute_forest_process_node(BaseNode &node)
{
  Logger::log()->trace("computing node [{}]/[{}]", node.get_label(), node.get_id());

  hmap::Forest *p_in_forest  = node.get_value_ref<hmap::Forest>(P_INPUT);
  hmap::Forest *p_out_forest = node.get_value_ref<hmap::Forest>(P_OUTPUT);

  if (!p_in_forest)
    return;

  *p_out_forest = *p_in_forest;

  // --- 1. Set elevation from heightmap (optional input)

  hmap::VirtualArray *p_elevation = node.get_value_ref<hmap::VirtualArray>(P_ELEVATION);

  if (p_elevation)
  {
    hmap::for_each_tile(
        {p_elevation},
        {},
        [&](const std::vector<const hmap::Array *> &p_arrays_in,
            std::vector<hmap::Array *> &,
            const hmap::TileRegion &region)
        {
          const auto [p_elev_tile] = unpack<1>(p_arrays_in);
          p_out_forest->set_elevation_from_terrain(*p_elev_tile, region.bbox);
        },
        node.cfg().cm_cpu);
  }

  // --- 2. Scale radius (default 1.0, nothing)

  const float scale_radius = node.val<float>(A_SCALE_RADIUS);
  if (std::abs(scale_radius - 1.0f) > 1e-6f)
  {
    for (auto &item : *p_out_forest)
      item.radius *= scale_radius;
  }

  // --- 3. Prune density per tile using for_each_tile wrapper

  const float prune_density_ratio = node.val<float>(A_PRUNE_DENSITY);
  if (prune_density_ratio < 1.0f - 1e-6f && !p_out_forest->empty())
  {
    hmap::VirtualArray *p_density_mask = node.get_value_ref<hmap::VirtualArray>(
        P_DENSITY_MASK);

    hmap::VirtualArray  dummy_mask;
    hmap::VirtualArray *p_mask_va = p_density_mask ? p_density_mask : &dummy_mask;

    if (!p_density_mask)
    {
      dummy_mask = hmap::VirtualArray(CONFIG(node));
      dummy_mask.fill(1.0f, node.cfg().cm_cpu);
    }

    glm::ivec2 num_tiles   = p_mask_va->get_max_tiles();
    int        total_tiles = num_tiles.x * num_tiles.y;

    std::vector<hmap::ScatterField> tile_fields(total_tiles);
    std::vector<glm::vec4>          tile_bboxs(total_tiles);

    const auto base_seed = static_cast<uint32_t>(node.val<int>(A_SEED));

    auto is_in_bbox = [](const glm::vec3 &position, const glm::vec4 &bbox) -> bool
    {
      return position.x >= bbox.x && position.x <= bbox.y && position.y >= bbox.z &&
             position.y <= bbox.w;
    };

    hmap::for_each_tile(
        {p_mask_va},
        {},
        [&](const std::vector<const hmap::Array *> &p_arrays_in,
            std::vector<hmap::Array *> &,
            const hmap::TileRegion &region)
        {
          const auto [p_mask_tile] = unpack<1>(p_arrays_in);

          int tile_index = region.key.ty * num_tiles.x + region.key.tx;

          tile_bboxs[tile_index] = region.bbox;

          hmap::Forest tile_forest;
          for (const auto &item : *p_out_forest)
          {
            if (is_in_bbox(item.position, region.bbox))
              tile_forest.push_back(item);
          }

          if (tile_forest.empty())
            return;

          uint32_t tile_seed = base_seed + static_cast<uint32_t>(tile_index) * 1999u +
                               17u;
          tile_forest.prune_density(*p_mask_tile,
                                    prune_density_ratio,
                                    tile_seed,
                                    region.bbox);

          tile_fields[tile_index] = std::move(tile_forest);
        },
        node.cfg().cm_cpu);

    hmap::ScatterField merged = hmap::merge_scatter_fields(tile_fields, tile_bboxs, true);
    *p_out_forest             = hmap::Forest(std::move(merged));
  }

  // --- 4. Prune collisions (outside tile loop)

  if (node.val<bool>(A_PRUNE_COLLISIONS) && !p_out_forest->empty())
  {
    p_out_forest->prune_collisions();
  }
}

} // namespace hesiod
