/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
 * Public License. The full license is in the file LICENSE, distributed with
 * this software. */
#include <algorithm>
#include <cmath>
#include <numbers>

#include "highmap/filters.hpp"
#include "highmap/hydrology.hpp"
#include "highmap/primitives.hpp"
#include "highmap/virtual_array/virtual_texture.hpp"

#include "hesiod/logger.hpp"
#include "hesiod/model/nodes/attributes.hpp"
#include "hesiod/model/nodes/base_node.hpp"

namespace hesiod
{

// -----------------------------------------------------------------------------
// Ports & Attributes
// -----------------------------------------------------------------------------

constexpr const char *P_ELEVATION  = "elevation";
constexpr const char *P_DEPOSITION = "deposition";
constexpr const char *P_TEXTURE    = "texture";

constexpr const char *A_GRASS    = "grass";
constexpr const char *A_DRY      = "dry_grass";
constexpr const char *A_SOIL     = "soil";
constexpr const char *A_SEDIMENT = "sediment";
constexpr const char *A_ROCK     = "rock";
constexpr const char *A_RIDGE    = "ridge";
constexpr const char *A_SNOW     = "snow";

constexpr const char *A_ROCK_SLOPE    = "rock_slope";
constexpr const char *A_ROCK_EDGE     = "rock_edge";
constexpr const char *A_STRATA        = "strata";
constexpr const char *A_STREAKS       = "streaks";
constexpr const char *A_STREAK_LENGTH = "streak_length";
constexpr const char *A_FLOW          = "flow";
constexpr const char *A_FLOW_WIDTH    = "flow_width";
constexpr const char *A_DEPOSITION    = "deposition_amount";
constexpr const char *A_SNOW_LINE     = "snow_line";
constexpr const char *A_SNOW_AMOUNT   = "snow_amount";
constexpr const char *A_SEED          = "seed";
constexpr const char *A_NOISE_SCALE   = "noise_scale";
constexpr const char *A_COLOR_NOISE   = "color_noise";
constexpr const char *A_DETAIL        = "detail";
constexpr const char *A_CAVITY        = "cavity";

// -----------------------------------------------------------------------------
// Setup
// -----------------------------------------------------------------------------

void setup_colorize_terrain_node(BaseNode &node)
{
  Logger::log()->trace("setup node {}", node.get_label());

  // --- Ports

  node.add_port<hmap::VirtualArray>(gnode::PortType::IN, P_ELEVATION);
  node.add_port<hmap::VirtualArray>(gnode::PortType::IN, P_DEPOSITION);
  node.add_port<hmap::VirtualTexture>(gnode::PortType::OUT, P_TEXTURE, CONFIG_TEX(node));

  // --- Attributes

  node.set_current_category("Materials");
  add_color(node, A_GRASS, "Grass", {0.38f, 0.44f, 0.29f, 1.f});
  add_color(node, A_DRY, "Dry Grass", {0.60f, 0.58f, 0.42f, 1.f});
  add_color(node, A_SOIL, "Soil", {0.64f, 0.55f, 0.43f, 1.f});
  add_color(node, A_SEDIMENT, "Sediment", {0.80f, 0.76f, 0.68f, 1.f});
  add_color(node, A_ROCK, "Rock", {0.53f, 0.50f, 0.46f, 1.f});
  add_color(node, A_RIDGE, "Ridge", {0.71f, 0.70f, 0.68f, 1.f});
  add_color(node, A_SNOW, "Snow", {0.94f, 0.95f, 0.97f, 1.f});

  node.set_current_category("Rock & Ridges");
  add_float(node, A_ROCK_SLOPE, "Rock Slope", 3.f, 0.05f, 8.f);
  add_float(node, A_ROCK_EDGE, "Edge Softness", 0.15f, 0.01f, 1.f);
  add_float(node, A_STRATA, "Strata", 0.35f, 0.f, 1.f);
  add_float(node, A_STREAKS, "Ridge Streaks", 0.8f, 0.f, 1.f);
  add_float(node, A_STREAK_LENGTH, "Streak Length", 0.06f, 0.f, 0.25f);

  node.set_current_category("Water & Snow");
  add_float(node, A_FLOW, "Flow Channels", 0.8f, 0.f, 1.f);
  add_float(node, A_FLOW_WIDTH, "Channel Width", 0.5f, 0.f, 1.f);
  add_float(node, A_DEPOSITION, "Deposition", 0.5f, 0.f, 1.f);
  add_float(node, A_SNOW_LINE, "Snow Line", 0.85f, 0.f, 1.f);
  add_float(node, A_SNOW_AMOUNT, "Snow", 0.f, 0.f, 1.f);

  node.set_current_category("Variation");
  add_seed(node, A_SEED);
  add_float(node, A_NOISE_SCALE, "Noise Scale", 1.f, 0.1f, 8.f);
  add_float(node, A_COLOR_NOISE, "Color Noise", 1.f, 0.f, 2.f);
  add_float(node, A_DETAIL, "Relief Detail", 1.f, 0.f, 2.f);
  add_float(node, A_CAVITY, "Cavity Shading", 0.6f, 0.f, 1.f);
}

// -----------------------------------------------------------------------------
// Compute
// -----------------------------------------------------------------------------

namespace
{

struct Params
{
  glm::vec3 grass, dry, soil, sediment, rock, ridge, snow;
  float     rock_slope, rock_edge, strata, streaks, streak_length;
  float     flow, flow_width, deposition, snow_line, snow_amount;
  uint32_t  seed;
  float     noise_scale, color_noise, detail, cavity;
};

float smoothstep(float a, float b, float x)
{
  const float t = std::clamp((x - a) / (b - a), 0.f, 1.f);
  return t * t * (3.f - 2.f * t);
}

// zero mean, most values in [-1, 1]
void standardize(hmap::Array &a)
{
  double sum = 0.0, sum2 = 0.0;
  for (float v : a.vector)
  {
    sum += v;
    sum2 += (double)v * v;
  }
  const double n    = (double)a.vector.size();
  const double mean = sum / n;
  const double std  = std::sqrt(std::max(sum2 / n - mean * mean, 1e-12));

  for (float &v : a.vector)
    v = std::clamp(float((v - mean) / (2.5 * std)), -1.f, 1.f);
}

// what stands out of the surface at a given scale: > 0 on crests, < 0 in gullies
hmap::Array relief(const hmap::Array &z, int ir)
{
  hmap::Array b = z;
  hmap::smooth_cpulse(b, std::max(1, ir));
  b = z - b;
  standardize(b);
  return b;
}

// a shade of `c`: darker and richer for t < 0, lighter and duller for t > 0
glm::vec3 shade(const glm::vec3 &c, float t)
{
  const float     luma = glm::dot(c, glm::vec3(0.299f, 0.587f, 0.114f));
  const glm::vec3 grey(luma);
  const glm::vec3 lit = c * (1.f + 0.4f * t);
  return glm::mix(grey * (1.f + 0.4f * t), lit, 1.f - 0.3f * t);
}

glm::vec3 rgb(const glm::vec4 &c) { return {c.r, c.g, c.b}; }

void colorize_terrain(const hmap::Array         &z,
                      const hmap::Array         *p_deposition,
                      const Params              &p,
                      const glm::vec4           &bbox,
                      std::vector<hmap::Array *> rgba)
{
  const glm::ivec2 shape = z.shape;
  const int        nx    = shape.x;
  const int        ny    = shape.y;
  const int        n     = nx * ny;
  const auto       px    = [nx](float frac) { return std::max(1, int(frac * nx)); };

  const auto [it_min, it_max] = std::minmax_element(z.vector.begin(), z.vector.end());
  const float zmin            = *it_min;
  const float zrange          = std::max(*it_max - zmin, 1e-6f);

  // --- Terrain analysis

  // slope and fall lines, read from a lightly smoothed surface
  hmap::Array zs = z;
  hmap::smooth_cpulse(zs, px(1.f / 512.f));

  std::vector<float> gx(n), gy(n), slope(n);

#pragma omp parallel for
  for (int j = 0; j < ny; ++j)
    for (int i = 0; i < nx; ++i)
    {
      const int   ip = std::min(i + 1, nx - 1), im = std::max(i - 1, 0);
      const int   jp = std::min(j + 1, ny - 1), jm = std::max(j - 1, 0);
      const float dx = (zs(ip, j) - zs(im, j)) / float(ip - im) * nx;
      const float dy = (zs(i, jp) - zs(i, jm)) / float(jp - jm) * nx;
      const int   k  = j * nx + i;

      gx[k]    = dx;
      gy[k]    = dy;
      slope[k] = std::hypot(dx, dy);
    }

  const hmap::Array fine   = relief(z, px(1.f / 400.f));
  const hmap::Array crest  = relief(z, px(1.f / 100.f));
  const hmap::Array region = relief(z, px(1.f / 20.f));

  // drainage on a log scale: 0 on the ridges, 1 in the main river
  hmap::Array flow = hmap::flow_accumulation_dinf(zs, 0.1f);
  {
    const float lmax = std::log(std::max(flow.max(), 2.f));
    for (float &v : flow.vector)
      v = std::log(std::max(v, 1.f)) / lmax;
  }
  hmap::Array moisture = flow;
  hmap::smooth_cpulse(moisture, px(1.f / 100.f));

  // deposits relative to the thick ones (among the cells that have any), so a
  // few strong spots do not wash out the rest and sparse maps stay sparse
  std::vector<float> deposit(n, 0.f);
  if (p_deposition && p_deposition->shape == shape)
  {
    std::vector<float> positive;
    for (float v : p_deposition->vector)
      if (v > 0.f)
        positive.push_back(v);

    if (!positive.empty())
    {
      auto it = positive.begin() + (size_t)(0.9 * (positive.size() - 1));
      std::nth_element(positive.begin(), it, positive.end());
      const float ref = std::max(*it, 1e-6f);
      for (int k = 0; k < n; ++k)
        deposit[k] = std::clamp(p_deposition->vector[k] / ref, 0.f, 1.f);
    }
  }

  // --- Noise

  const auto noise = [&](float kw, int seed_offset, int octaves)
  {
    const float k = kw * p.noise_scale;
    hmap::Array a = hmap::noise_fbm(hmap::NoiseType::PERLIN,
                                    shape,
                                    {k, k},
                                    p.seed + seed_offset,
                                    octaves,
                                    0.f,
                                    0.5f,
                                    2.f,
                                    nullptr,
                                    nullptr,
                                    nullptr,
                                    bbox);
    standardize(a);
    return a;
  };

  const hmap::Array n_large = noise(3.f, 0, 4);
  const hmap::Array n_mid   = noise(12.f, 1, 5);
  const hmap::Array n_fine  = noise(64.f, 2, 3);
  const hmap::Array n_rill  = noise(160.f, 3, 2);
  const hmap::Array n_grain = noise(320.f, 4, 2);

  // --- Fall lines

  // bare high crests: their colour runs down the slopes below them
  std::vector<float> source(n);
  for (int k = 0; k < n; ++k)
  {
    const float h = (z.vector[k] - zmin) / zrange;
    source[k]     = smoothstep(0.05f,
                           0.35f,
                           0.6f * crest.vector[k] + 0.6f * region.vector[k]) *
                smoothstep(0.3f, 0.75f, h + 0.15f * n_mid.vector[k]) *
                (0.75f + 0.25f * n_fine.vector[k]);
  }

  const float streak_px    = p.streak_length * nx;
  const int   streak_steps = std::clamp(int(streak_px), 0, 64);
  const float streak_step  = streak_steps ? streak_px / streak_steps : 0.f;
  const int   rill_steps   = std::clamp(nx / 96, 3, 24);

  std::vector<float> streak(n), rill(n);

#pragma omp parallel for
  for (int j = 0; j < ny; ++j)
    for (int i = 0; i < nx; ++i)
    {
      // walk up the fall line, one cell per step when step is 1
      const auto walk = [&](int steps, float step, auto &&visit)
      {
        float x = (float)i, y = (float)j;
        for (int s = 1; s <= steps; ++s)
        {
          const int   k = int(y + 0.5f) * nx + int(x + 0.5f);
          const float g = std::hypot(gx[k], gy[k]);
          if (g < 1e-6f)
            return;

          x += step * gx[k] / g;
          y += step * gy[k] / g;
          if (x < 0.f || y < 0.f || x > nx - 1.f || y > ny - 1.f)
            return;

          visit(s, int(y + 0.5f) * nx + int(x + 0.5f));
        }
      };

      const int k = j * nx + i;

      // fine noise averaged along the fall line: rills and gullies
      float sum   = n_rill.vector[k];
      int   count = 1;
      walk(rill_steps,
           1.f,
           [&](int, int kk)
           {
             sum += n_rill.vector[kk];
             ++count;
           });
      rill[k] = std::clamp(sum / std::sqrt((float)count), -1.f, 1.f);

      float best = source[k];
      walk(streak_steps,
           streak_step,
           [&](int s, int kk)
           { best = std::max(best, source[kk] * (1.f - s / (streak_steps + 1.f))); });
      streak[k] = best;
    }

  // --- Colours

  for (hmap::Array *p_channel : rgba)
    *p_channel = hmap::Array(shape);

  const float cn     = p.color_noise;
  const float two_pi = 2.f * std::numbers::pi_v<float>;

#pragma omp parallel for
  for (int k = 0; k < n; ++k)
  {
    const float h  = (z.vector[k] - zmin) / zrange;
    const float s  = slope[k] / p.rock_slope; // 1 where rock takes over
    const float c  = crest.vector[k];
    const float r  = region.vector[k];
    const float nl = n_large.vector[k];
    const float nm = n_mid.vector[k];
    const float nf = n_fine.vector[k];
    const float ng = n_grain.vector[k];
    const float rl = rill[k];

    // grass: lush where water gathers, dry on high convex ground; a narrow,
    // noisy transition keeps the patches crisp
    const float wet = 0.5f + 0.6f * moisture.vector[k] - 0.35f * r - 0.2f * c +
                      0.15f * nl;
    const float dry = smoothstep(0.42f,
                                 0.58f,
                                 1.f - wet + 0.35f * (h - 0.4f) + 0.12f * nm +
                                     0.08f * nf);
    glm::vec3   col = glm::mix(shade(p.grass, cn * (0.3f * nm + 0.3f * nf + 0.2f * ng)),
                             shade(p.dry, cn * (0.3f * nm + 0.3f * nf + 0.2f * ng)),
                             dry);

    // soil on moderate slopes and bare bumps
    const float soil = smoothstep(0.35f,
                                  0.6f,
                                  s + 0.2f * nm + 0.1f * nf + 0.25f * std::max(c, 0.f));
    col = glm::mix(col, shade(p.soil, cn * (0.25f * rl + 0.3f * nm + 0.15f * ng)), soil);

    // sediment along the drainage lines and in crisp deposits
    const float t0  = 0.8f - 0.5f * p.flow_width;
    float       sed = p.flow * smoothstep(t0, t0 + 0.08f, flow.vector[k] + 0.05f * nf);
    sed = std::max(sed, p.deposition * smoothstep(0.4f, 0.8f, deposit[k] + 0.15f * nf));
    sed *= 1.f - smoothstep(0.6f, 1.f, s);
    col = glm::mix(col, shade(p.sediment, cn * (0.4f * nf + 0.2f * nm + 0.2f * ng)), sed);

    // rock on steep ground: ragged edges, strata, a hint of rills
    const float edge = p.rock_edge;
    const float rock = smoothstep(1.f - edge,
                                  1.f + edge,
                                  s + 0.25f * nm + 0.1f * nf +
                                      0.3f * std::max(c, 0.f) * h);
    const float band = std::sin(two_pi * (14.f * h + 0.4f * nl + 0.1f * nm));
    col              = glm::mix(col,
                   shade(p.rock,
                         0.35f * p.strata * band +
                             cn * (0.2f * rl + 0.3f * nf + 0.15f * ng) + 0.25f * c),
                   rock);

    // ridge colour spilling down the slopes
    const float spill = p.streaks *
                        smoothstep(0.25f,
                                   0.65f,
                                   streak[k] * (0.75f + 0.25f * (1.f + nf))) *
                        smoothstep(0.15f, 0.4f, s);
    col = glm::mix(col,
                   shade(p.ridge, cn * (0.3f * nf + 0.15f * rl + 0.15f * ng)),
                   spill);

    // snow on high ground, sliding off the steep parts
    const float snow = p.snow_amount *
                       smoothstep(-0.04f,
                                  0.04f,
                                  h - p.snow_line + 0.08f * nm + 0.04f * nf -
                                      0.15f * std::max(0.f, s - 0.9f) - 0.05f * c);
    col = glm::mix(col, shade(p.snow, 0.15f * nf - 0.3f * std::max(-c, 0.f)), snow);

    // relief: dark gullies, crisp detail, grain, then a slow warm / cool drift
    col *= 1.f - p.cavity * 0.35f * std::clamp(-0.7f * c - 0.4f * r, 0.f, 1.f);
    col *= 1.f + p.detail * 0.22f * fine.vector[k];
    col *= 1.f + cn * (0.05f * nm + 0.06f * nf + 0.05f * ng);
    col += cn * 0.015f * nl * glm::vec3(1.f, 0.6f, 0.1f);

    rgba[0]->vector[k] = std::clamp(col.r, 0.f, 1.f);
    rgba[1]->vector[k] = std::clamp(col.g, 0.f, 1.f);
    rgba[2]->vector[k] = std::clamp(col.b, 0.f, 1.f);
    rgba[3]->vector[k] = 1.f;
  }
}

} // namespace

void compute_colorize_terrain_node(BaseNode &node)
{
  Logger::log()->trace("computing node [{}]/[{}]", node.get_label(), node.get_id());

  // --- Inputs / Outputs

  const auto *p_z   = node.get_value_ref<hmap::VirtualArray>(P_ELEVATION);
  const auto *p_dep = node.get_value_ref<hmap::VirtualArray>(P_DEPOSITION);
  auto       *p_tex = node.get_value_ref<hmap::VirtualTexture>(P_TEXTURE);

  if (!p_z)
    return;

  // --- Params

  const Params p = {
      .grass         = rgb(node.val<glm::vec4>(A_GRASS)),
      .dry           = rgb(node.val<glm::vec4>(A_DRY)),
      .soil          = rgb(node.val<glm::vec4>(A_SOIL)),
      .sediment      = rgb(node.val<glm::vec4>(A_SEDIMENT)),
      .rock          = rgb(node.val<glm::vec4>(A_ROCK)),
      .ridge         = rgb(node.val<glm::vec4>(A_RIDGE)),
      .snow          = rgb(node.val<glm::vec4>(A_SNOW)),
      .rock_slope    = node.val<float>(A_ROCK_SLOPE),
      .rock_edge     = node.val<float>(A_ROCK_EDGE),
      .strata        = node.val<float>(A_STRATA),
      .streaks       = node.val<float>(A_STREAKS),
      .streak_length = node.val<float>(A_STREAK_LENGTH),
      .flow          = node.val<float>(A_FLOW),
      .flow_width    = node.val<float>(A_FLOW_WIDTH),
      .deposition    = node.val<float>(A_DEPOSITION),
      .snow_line     = node.val<float>(A_SNOW_LINE),
      .snow_amount   = node.val<float>(A_SNOW_AMOUNT),
      .seed          = (uint32_t)node.val<int>(A_SEED),
      .noise_scale   = node.val<float>(A_NOISE_SCALE),
      .color_noise   = node.val<float>(A_COLOR_NOISE),
      .detail        = node.val<float>(A_DETAIL),
      .cavity        = node.val<float>(A_CAVITY),
  };

  // --- Compute

  // fall lines and drainage cross tile borders: work on the whole map at once
  hmap::for_each_tile(
      {p_z, p_dep},
      p_tex->channels_ptr(),
      [&p](std::vector<const hmap::Array *> p_arrays_in,
           std::vector<hmap::Array *>       p_arrays_out,
           const hmap::TileRegion          &region)
      {
        auto [pa_z, pa_dep] = unpack<2>(p_arrays_in);
        colorize_terrain(*pa_z, pa_dep, p, region.bbox, p_arrays_out);
      },
      node.cfg().cm_single_array);
}

} // namespace hesiod
