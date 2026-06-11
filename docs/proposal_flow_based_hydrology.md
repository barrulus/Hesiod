# Proposal: Flow-Based Hydrology for Hesiod

*Prepared by barrulus (b@rry.im) following the Discord discussion of 2026-06-10
(eobet / barrulus / Otto Link) on river generation at large scales, rivers
failing to reach the sea, lake pooling, and Strahler ordering.*

---

## 1. Motivation — the problem the Discord thread surfaced

The conversation exposed a core tension between two paradigms:

- **Hesiod / HighMap today: procedural erosion on a heightfield.**
  `HydraulicSaleve`, `HydraulicStreamLog`, `HydraulicParticle` etc. carve
  plausible-looking valleys by moving sediment around an array. They do not
  know what a *river* is: there is no connected network, no source→mouth
  identity, and no guarantee that water reaches the sea. This is exactly why
  eobet's rivers "fade away before they hit the sea" and look "too wide" —
  the erosion stalls when the slope flattens (the *add slope → erode →
  subtract slope* trick is a workaround for precisely this).

- **Tools like FMG (Fantasy Map Generator): a flow graph laid on top of a
  finished heightmap.** FMG never erodes. It routes precipitation downhill
  over a depression-filled surface, accumulates flux additively at
  confluences, pools into lakes at sinks, spills lake outlets onward, and
  derives river width from accumulated discharge. As noted in the thread:
  *"tools like FMG add the flow on top of the heightmap, so lakes are formed
  there."*

The question this document answers: **how could Hesiod implement and — just
as importantly — visually represent a flow-based hydrology system**, bridging
FMG's graph model into Hesiod's tiled-array node world.

Open questions from the thread that a flow pass answers directly:

| Thread question | Flow-based answer |
|---|---|
| "1000 km coastline, several hundred rivers — possible?" (eobet) | River count becomes a single *minimum-flux threshold* slider on an accumulation map, not seed luck. |
| "Rivers fade before they hit the sea" (eobet) | Depression filling (priority-flood) guarantees a strictly descending path from every land cell to the ocean; accumulation then never strands flow on a flat. |
| "If a river stops, shouldn't it pool into a lake?" (eobet) | Yes — sinks flood to their spill elevation; if inflow exceeds evaporation, the lake spills an outlet river onward. |
| "Build a flow graph like the Strahler number" (Otto) | Strahler is a labelling pass over the flow tree — ideal for width/classification/styling, not for routing. |
| "Hydrology as a higher function: precipitation, wind, elevation; tributary flow becomes additive" (barrulus) | This is precipitation-weighted flow accumulation with additive flux at confluences — FMG's `drainWater()` is a working reference implementation. |

---

## 2. Reference model — what FMG actually does

FMG's river generator (`rivergenerator.ts`, with `lakes.ts` and `biomes.ts`)
is a compact, complete flow model worth restating because every step maps
onto a HighMap primitive that already exists:

1. **`alterHeights()`** — tiny height perturbation so flow is not degenerate
   on flats.

2. **`resolveDepressions()`** — *priority-flood* (Barnes 2014). Every pit is
   raised by an epsilon so **every land cell has a strictly descending path
   to a boundary or the ocean**. This single step is why FMG rivers always
   reach the sea, and it is the step missing from a pure-erosion pipeline.

3. **`drainWater()`** — the heart of the model:
   - each land cell receives flux from precipitation
     (`cells.fl[i] += prec[...]`);
   - cells are processed **high → low**, and flux is pushed to the lowest
     neighbour (`flowDown`). Because of step 2 this always terminates at
     water or the map border;
   - **tributary flow is additive** — `cells.fl[toCell] += fromFlux`;
   - a river only "proclaims" itself once
     `flux > MIN_FLUX_TO_FORM_RIVER` — **this threshold is the river-count
     knob** (hundreds of rivers across 1000 km is just a lower threshold);
   - confluences record `parent` / `basin` relationships → the river set is
     a forest of trees.

4. **Lakes** (`lakes.ts`) — a sink that cannot reach the ocean becomes a
   lake; the lake fills to its lowest shoreline cell, computes evaporation
   (Penman-style) vs. inflow flux, and if `flux > evaporation` it **spills
   an outlet river onward** (`detectCloseLakes` / `defineClimateData`).
   Chain lakes retain river identity through the chain.

5. **Width from discharge** (`getWidth` / `getOffset`) — mouth width is a
   function of accumulated flux, not erosion. Rivers are thin at the source
   and fat at the mouth by construction.

6. **Climate loop** (`biomes.ts`) — river flux feeds back into cell moisture
   (`if (riverIds[cellId]) moisture += max(flux/10, 2)`), which drives biome
   selection. Precipitation → flow → moisture → biome closes the
   "higher-function hydrology" loop.

**Strahler ordering** (raised by Otto in the thread) is a labelling of this
same tree: leaf streams (no upstream) are order 1; when two streams of equal
order meet the result is order+1; otherwise the max order continues. It was
invented for exactly this purpose in hydrology (Horton 1945, Strahler 1952)
and is the natural driver for line weight, naming class ("creek" vs.
"river"), and LOD culling.

---

## 3. What Hesiod / HighMap already has

The good news: HighMap already ships almost every primitive needed. They are
simply (a) used mostly for erosion, and (b) **not assembled into a connected,
precipitation-driven network**.

From `highmap/hydrology/hydrology.hpp`:

| HighMap primitive | What it gives | FMG equivalent |
|---|---|---|
| `flow_accumulation_d8` / `flow_accumulation_dinf` | upstream drainage area per cell | the `cells.fl` accumulation in `drainWater()` |
| `flow_direction_d8` / `flow_direction_dinf` | per-cell downhill routing | the "lowest neighbour" step |
| `basin_id(...)` (priority-flood) | drainage basin per cell | `river.basin` |
| `d8_compute_ndip` | in-degree (incoming flow count) per cell | confluence detection — *and the building block for Strahler* |
| `find_flow_sinks` / `find_flow_apex` | endpoints / sources | lake sites / river sources |
| `flow_stream` + `dig_river` (the `FlowStream` node, currently WIP) | trace a descending path from a seed, carve it | river path + meandering |
| `flooding_lake_system` (`FloodingLakeSystem` node) | flood a pit to spill level | `lakes.ts` fill |
| `DepressionFilling` node | priority-flood pit removal | `resolveDepressions()` |

The node UI already has a **Hydrology** category: `FlowStream` (WIP),
`FlowSimulation`, `FlowSimulationViscous`, `FloodingLakeSystem`,
`FloodingFromPoint`, `FloodingFromBoundaries`, `FlatbedCarve`,
`WaterDepthDryOut`, `WaterDepthFromMask`, `WaterElevationFromDepth`,
`WaterMask`, `MergeWaterDepths`, plus `SelectRivers` and `WatershedRidge`.

### The two real gaps

1. **`flow_accumulation_*` is not exposed as a node** — it exists in HighMap
   but no Hesiod node wraps it — and it accumulates a *uniform* unit per
   cell. There is no **precipitation-weighted** accumulation, which is the
   thing that makes flow magnitude physically meaningful.

2. **There is no river-network *object*.** Hesiod nodes pass `VirtualArray`
   tiles via `for_each_tile`; FMG passes a global graph carrying
   `{flux, river, parent, basin, confluence}` per cell plus per-river
   records. Hesiod has no typed graph that survives downstream of the
   heightmap. Notably, `flow_stream` and `flooding_lake_system` already
   force `cm_single_array` ("not tileable") — because **flow is inherently
   non-local and crosses tiles**. That is the central architectural
   constraint for everything below.

---

## 4. Proposed pipeline — algorithm side

In increasing order of effort:

### (a) `FlowAccumulation` node — expose + weight accumulation

Wrap `flow_accumulation_dinf` (D8 as an option) as a node, with an optional
`precipitation` input port that weights each cell's contribution. Small and
immediately useful:

- output **is** a discharge / moisture proxy map;
- thresholding it gives a river mask with controllable density (the
  "hundreds of rivers" knob);
- log-scaled, it is the input for river width and map tinting.

### (b) Always-route-to-the-sea pre-step

Make depression filling (priority-flood — already available via
`DepressionFilling` / the machinery in `basin_id`) the standard pre-step of
the flow pipeline. Guarantees a monotone descent from every interior cell to
the ocean/boundary, so accumulation never strands flow on a flat. This is
the array-world version of FMG's `resolveDepressions()` and is what fixes
"rivers fade before the sea" *deterministically* rather than by seed luck.

### (c) Lakes at endpoints, with spill

Wire together two primitives that already exist:

1. `find_flow_sinks` locates interior endpoints;
2. `flooding_lake_system` floods each to its spill elevation;
3. estimate evaporation from lake area (and temperature, if a climate input
   exists); if accumulated inflow exceeds it, re-inject the residual flux at
   the spill cell and continue accumulation downstream — a direct port of
   FMG's lake outlet / chain-lake logic.

Output: a `water_depth` raster for the lakes plus the continued river
network. This natively answers "shouldn't it pool into a lake?".

### (d) `StreamOrder` (Strahler) node

With `flow_direction_d8` (parent pointer per cell) and `d8_compute_ndip`
(in-degree per cell), a reverse-topological pass (Kahn's algorithm seeded
from the apexes) assigns Strahler order:

- order 1 at sources;
- at a confluence, `order = max(children)`, or `max + 1` if the maximum is
  shared by two or more children.

Output an integer field driving width, colour, classification, and LOD —
replacing length-based heuristics with something physically grounded.

### (e) `RiverNetwork` data type — the real prize

A typed object (sibling to `Path` / `Cloud`) holding:

- per-reach polyline geometry (meanderable);
- per-reach attributes: `{flux, strahler_order, parent, basin, width,
  source, mouth}`;
- lake records with `{shoreline, height, inlets, outlet}`.

Produced once on a single full-resolution array and carried between nodes.
This is what enables FMG-quality output — named rivers, meanders,
width-from-discharge, vector export (e.g. to Azgaar's FMG, which is already
being done by hand via heightmap round-trips). It is the biggest lift
because it cuts against the tile/GPU array model, but `flow_stream` and
`flooding_lake_system` already accept being single-array, so there is
precedent.

### Resulting node graph

```
Heightmap → DepressionFilling → FlowDirection ┐
Precipitation ────────────────────────────────┼→ FlowAccumulation → StreamOrder → FlowStream(dig) → erosion/width
                                              └→ FloodingLakeSystem (sinks) → MergeWaterDepths
```

---

## 5. Fresh input — runevision's "Fast and Gorgeous Erosion Filter" (March 2026)

Rune Skovbo Johansen (runevision) published a detailed write-up of a new
erosion technique — blog post
([blog.runevision.com](https://blog.runevision.com/2026/03/fast-and-gorgeous-erosion-filter.html))
plus a companion video — building on Clay John's 2018 *Eroded Terrain Noise*
and Felix Westin's (Fewes) 2023 Shadertoys. It is worth folding into this
proposal because it sits at the exact intersection of the two paradigms in
§1, and one of its outputs is directly useful to the hydrology pipeline.

### 5.1 What it is

> *"It's essentially a special kind of noise which produces gorgeous
> branching gullies and ridges, while still allowing every point to be
> evaluated in isolation, which means it's fast, GPU-friendly, and trivial
> to generate in chunks. Furthermore, rather than defining the landscape
> entirely, it can be applied on top of any height function, essentially
> applying erosion on top as a filter."*

The mechanism, compactly:

- **Gradient-aligned stripe noise.** Stripes (cosine wave for height offset,
  sine wave for slope) are oriented along the negative gradient of the input
  height function — the direction water would flow. Each octave's gullies
  modify the combined gradient, so the next (smaller) octave's gullies
  branch off at an angle: a *dendritic pattern without any simulation*.
- **Per-cell pivots, Worley-style.** To rotate stripes without large
  distortion, the domain is divided into grid cells each with a random pivot
  point; neighbouring cells' stripes are blended (blending unaligned sine
  waves just yields a smaller-amplitude sine wave, so the blend is seamless).
- **The "fade approach".** Where the slope approaches zero (peaks, valleys),
  stripes are faded towards a user-supplied **fade target** in [-1, 1]
  (−1 at valleys, +1 at peaks, typically derived from altitude). This gives
  crisp pointy peaks *and* crisp V-shaped valleys simultaneously — fixing
  the valley-bulge artifact of the original "frequency approach".
- **Slope shaping function.** Erosion magnitude uses
  `1 − (1 − slope)²` (an ease-out) instead of `slope^0.5` — the square-root
  curve's vertical start caused visible discontinuities at peaks/valleys.
  (Directly relevant to the thread: this is the same lever as the "drainage
  exponent" tuning Otto suggested for `HydraulicSaleve`.)
- **Stacked fading.** After each octave, the mask and fade target are
  updated so subsequent smaller gullies are faded out *on the ridges and
  creases of larger ones* — this is what keeps large-scale ridgelines crisp
  and unbroken, with a single `detail` parameter
  (`combiMask = pow_inv(combiMask, detail) * newMask`) controlling how far
  high-frequency gullies are confined to steep slopes.
- **Normalized gullies** (released separately as *Phacelle Noise*): the
  interpolated cosine/sine pair is treated as a point on a unit circle and
  re-normalized (above a 0.5-length threshold, scale ×2 then clamp) for
  consistent gully magnitude without loop/spike artifacts.
- **Straight gullies:** for direction computation, the gully slope uses the
  *sign* of the sine wave (as if gullies were extruded triangle waves), so
  tributary gullies branch off cleanly instead of curling along their
  parents.
- Extras: a *gully weight* factor for pointy peaks, separate **ridge and
  crease rounding** (sediment-filled valley bottoms vs. weathered ridges),
  and approximate analytical derivatives as a secondary output.

### 5.2 Why it matters to this proposal

**1. It is the tileable half of the equation.** The whole point of the
technique is point-in-isolation evaluation: it fits Hesiod's
`for_each_tile` + GPU compute model *perfectly*, including chunked
generation of world-scale maps (the equirectangular wrap-around use case
from the thread). This is the exact opposite of flow accumulation, which is
global and forces `cm_single_array`. The two paradigms slot together rather
than compete:

> **flow graph = global connectivity and topology** (rivers guaranteed to
> reach the sea, lakes with spill, Strahler order, discharge);
> **runevision filter = local, fast, crisp gully/ridge detail** at
> resolutions and chunk sizes where a global pass is impractical.

**2. Its admitted limitation is precisely the thread's complaint.** From the
post, on drawing drainage streaks from the technique alone:

> *"It's not a perfect solution, since the interpolated stripes we use for
> the gullies cannot consistently produce unbroken lines. So sometimes a
> gully, and the drawn water drainage at its bottom, just stops halfway
> down a mountainside rather than following through all the way down to the
> lowest reachable point."*

That is the "rivers fade away before they hit the sea" problem, stated as a
structural property of *any* purely local technique. It is independent
confirmation that connectivity must come from a global flow pass (§4 b),
while appearance can come from local filtering.

**3. The ridge map is a free drainage visualization.** The technique's
internal *fade target*, after all octaves (with the last octave faded to
neutral), is what Rune calls a **ridge map**: ridges in white, creases in
black — effectively an analytical map of every gully bottom. He uses it to
draw bright dendritic drainage streaks on the textured terrain at zero
simulation cost. For Hesiod this is a ready-made texture channel (see
Channel B below) and could also serve as a *prior* for the flow pass — e.g.
blended into the precipitation input, or used to seed `FlowStream` sources
at detected creases.

**4. A hybrid pipeline becomes the natural architecture.**

```
                    ┌─ global, single-array, coarse-to-mid res ─────────────┐
Heightmap ─────────→│ DepressionFilling → FlowAccumulation(precip) →        │→ trunk rivers, lakes,
                    │ StreamOrder → lake fill & spill                       │  discharge, water_depth
                    └───────────────────────────────────────────────────────┘
                    ┌─ local, tiled, GPU, full res ─────────────────────────┐
        + ─────────→│ runevision-style erosion filter                       │→ crisp gullies/ridges,
                    │ (strength & fade target modulated by discharge map)   │  ridge map (drainage streaks)
                    └───────────────────────────────────────────────────────┘
```

Modulating the filter's erosion strength / fade target / detail by the
discharge map means gully density and depth *correlate with actual
drainage* — the local detail visually agrees with the global network. This
is also a more principled take on what `HydraulicStreamUpscaleAmplification`
gestures at today: global structure at low resolution, amplified locally.

**5. Implementation is realistic.** The code is released under **MPL-2.0**
(compatible with Hesiod's GPLv3), with reference Shadertoys (*Advanced
Terrain Erosion Filter*, *Mouse-Paint Eroded Mountains*, *Phacelle Noise*),
and has already been ported to Unity (Burst and Shadergraph), Unreal, Godot,
Blender geometry nodes, Houdini, and the Leveller heightmap tool. Notably,
when a commenter asked for *"an application where I can apply this filter to
a heightmap and export the new heightmap"*, Rune replied that none exists
yet — *"maybe as plugins to existing applications"*. Hesiod is arguably the
most natural home for exactly that: a node (working title
`HydraulicGully` / `ErosionFilter`) alongside `HydraulicProcedural`, with
`fade_target`, `mask`, and `detail` as input ports — the technique's
parameter design (user-supplied fade target map, per-point evaluation) maps
one-to-one onto Hesiod's port model.

---

## 6. Visual representation — the main subject

Visualization turns out to be the *easy* half: Hesiod already moves and
renders every data channel a flow-hydrology system needs. Everything that
flows between nodes is one of four types, and each already renders:

| Type | Node thumbnail (`DataPreview`) | 2D/3D viewer |
|---|---|---|
| `VirtualArray` | grayscale, histogram, slope-height heatmap, TERRAIN/TURBO/HOT/MAGMA colormaps | terrain mesh, **or water surface** |
| `VirtualTexture` (RGBA) | the coloured image | albedo on the terrain |
| `Path` (polylines) | drawn as lines | — (thumbnail only today) |
| `Cloud` (points) | drawn as dots | — (thumbnail only today) |

This yields four complementary visual channels.

### Channel A — real 3D water surface *(already built; highest impact)*

`Viewer3D` already accepts a **`water_depth`** input alongside `elevation`,
`color`, and `normal_map`, and `QTerrainRenderer` builds a *separate water
mesh*:

```
water elevation = terrain elevation + water_depth    (wet cells only)
```

It is toggled by the "waves" icon, dilates one cell at the shoreline to
avoid truncated cells at the water/ground interface, and culls dry cells
(`viewer_3d.cpp`, water block). `FlowSimulation` and `FloodingLakeSystem`
already feed it.

**What flow-based hydrology buys here:** if the river generator emits a
`water_depth` raster where depth is driven by accumulated discharge, then:

- **rivers appear as actual 3D water ribbons** inset into their channels —
  thin at the source, fat at the mouth, *for free*, because width/depth is a
  function of accumulated flux rather than erosion;
- **lakes at sinks render as flat pools** automatically (a pit filled to
  spill level is just a `water_depth` blob);
- the "fades before the sea" symptom disappears visually: depression-filled
  accumulation produces a continuous wet ribbon to the coast.

**No new rendering code is required for the headline result.** The work is
generating a discharge-derived `water_depth`, i.e. nodes (a)–(c) above.

### Channel B — map-view tint (albedo texture)

For the top-down cartographic look (the FMG/AFMG aesthetic): map discharge
(log-scaled) or Strahler order through a blue ramp via the existing
`colorize` machinery (40 gradient presets ship in `data/color_gradients/`,
plus the built-in colormaps) and blend the river mask over a relief or biome
texture:

- pale hairline blue for creeks → saturated wide blue for major rivers;
- lakes and ocean as solid water colour;
- composites cleanly with existing biome/relief texturing into the `color`
  port of the 3D viewer or a texture export.

Needs only a small "colorize + blend by mask" node chain — all primitives
exist.

If a runevision-style erosion filter node is added (§5), its **ridge map**
output slots straight into this channel: bright dendritic drainage streaks
at every gully bottom, analytically derived at full tiled resolution. The
flow-derived discharge tint provides the *connected* trunk network; the
ridge-map streaks provide the fine capillary texture between them — the two
composite naturally because the filter's gullies are slope-aligned with the
same terrain the flow pass routed over.

### Channel C — vector overlay *(the Strahler payoff; the one new piece)*

A river *network as a graph* is naturally a `Path` (one polyline per reach)
plus a `Cloud` (sources, confluences, lake outlets). Both types already
render as lines and dots in node thumbnails — so a `RiverNetwork →
Path/Cloud` extraction node is visible immediately with **zero** new
rendering code.

The genuinely new rendering work is **overlaying `Path`/`Cloud` in the 2D
and 3D viewers** (today they are thumbnail-only). This is where Strahler
order earns its keep visually:

- **line weight = stream order** — order-1 brooks draw hairline, an order-5+
  trunk draws bold: exactly the Horton–Strahler picture;
- markers from the `Cloud`: sources, confluences, lake inlets/outlets,
  mouths;
- in the 3D viewer, the polylines can be draped a small epsilon above the
  terrain mesh;
- this channel is also the export path: polylines + attributes map directly
  to SVG/GeoJSON-style vector output for external map tools.

This is the only channel that requires touching viewer code.

### Channel D — per-node debug previews *(free; useful while building)*

The intermediate rasters are self-visualizing with the existing thumbnail
modes:

- **flow accumulation** → `colorize_histogram` or the slope-height heatmap
  preview — log-scaled drainage lights up the branching tree immediately;
- **stream order** → a discrete colormap thumbnail;
- **basins** → `basin_id` through a categorical TURBO map — instantly shows
  watershed partitioning (and pairs with the existing `WatershedRidge`
  node).

### Putting it together

```
Heightmap ─┬─→ FlowAccumulation ─→ discharge raster ──┐
Precip ────┘         │                                ├─→ water_depth ─→ [3D viewer: water surface]   ← Channel A
                     ├─→ StreamOrder ─→ RiverNetwork ─┤
                     │                                ├─→ Path/Cloud ──→ [overlay, line-weight=order] ← Channel C
                     └─→ colorize(blue ramp) ─────────┴─→ color ───────→ [3D albedo / map tint]       ← Channel B
```

---

## 7. Suggested order of implementation

| Step | Effort | New rendering? | Payoff |
|---|---|---|---|
| 1. `FlowAccumulation` node (precip-weighted, D8/D∞) | small | no (Channel D free) | river density knob; discharge map |
| 2. Depression-fill pre-step convention | trivial | no | rivers always reach the sea |
| 3. Discharge → `water_depth` (+ lake fill & spill via existing flooding nodes) | medium | **no** (Channel A exists) | rivers & lakes as real 3D water |
| 4. `StreamOrder` (Strahler) node | small | no | physically grounded width/classification |
| 5. Blue-ramp colorize/blend chain | trivial | no | cartographic map view (Channel B) |
| 6. `RiverNetwork` type + `Path`/`Cloud` extraction | large | thumbnails free | named rivers, meanders, vector export |
| 7. `Path`/`Cloud` overlay in 2D/3D viewers | medium | **yes** (the only new viewer work) | Strahler-weighted vector map (Channel C) |
| 8. Runevision-style erosion filter node (§5) — fully independent of 1–7, can proceed in parallel | medium | no (ridge map feeds Channel B) | tiled/GPU gully detail; drainage-streak ridge map; hybrid with discharge modulation |

Steps 1–3 alone resolve every visual complaint raised in the Discord thread,
using rendering that already ships. Steps 4–7 add the cartographic and
vector layers that close the gap with FMG-class output. Step 8 is
orthogonal — a tileable appearance layer that the flow pass can modulate —
and is the only step that could be picked up independently of all the
others.

---

## 8. References

- Horton, R. E. (1945) — *Erosional development of streams and their
  drainage basins.*
- Strahler, A. N. (1952, 1957) — *Hypsometric analysis* / *Quantitative
  analysis of watershed geomorphology.* (Strahler stream order)
- Barnes, Lehman, Mulla (2014) — *Priority-flood: an optimal
  depression-filling and watershed-labeling algorithm.*
- Azgaar's Fantasy Map Generator — `rivergenerator.ts`, `lakes.ts`,
  `biomes.ts` (reference implementation of the on-top flow-graph model).
- HighMap — `highmap/hydrology/hydrology.hpp` (existing flow primitives).
- Rune Skovbo Johansen (2026) — *Fast and Gorgeous Erosion Filter*,
  https://blog.runevision.com/2026/03/fast-and-gorgeous-erosion-filter.html
  (point-evaluated, tileable erosion-as-noise filter; ridge map; MPL-2.0
  reference Shadertoys: *Advanced Terrain Erosion Filter*, *Mouse-Paint
  Eroded Mountains*, *Phacelle Noise*).
- Clay John (2018) — *Eroded Terrain Noise* (Shadertoy; original version of
  the technique); Felix Westin / Fewes (2023) — *Terrain Erosion Noise*
  (Shadertoy refinement).
