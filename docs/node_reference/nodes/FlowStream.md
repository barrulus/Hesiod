
FlowStream Node
===============


TODO



![img](../../images/nodes/FlowStream_settings.png)


## Category


WIP
## Inputs

|Name|Type|Description|
| :--- | :--- | :--- |
|input|VirtualArray|Input heightmap terrain.|
|sources|Cloud|Cloud of source coordinates from which flow streams originate.|
|noise_r|VirtualArray|Optional noise array to perturb trench width.|

## Outputs

|Name|Type|Description|
| :--- | :--- | :--- |
|output|VirtualArray|Output heightmap with carved river channels.|
|water_depth|VirtualArray|Water depth computed as the difference between input and output terrain.|

## Parameters

|Name|Type|Description|
| :--- | :--- | :--- |
|control_points_count|Integer|Number of control points sampled for the triangulation mesh.|
|depth|Float|Maximum depth of the carved riverbed.|
|distance_exponent|Float|Exponent applied to distance/elevation terms when evaluating path costs.|
|elevation_ratio|Float|Weight given to elevation difference versus distance in the cost function.|
|enable_width_curvature_scaling|Bool|Modulates trench width based on path curvature.|
|enable_width_distance_scaling|Bool|Modulates trench width along the distance and depth of the path.|
|favor_domain_center|Bool|Biases flow paths toward passing through the center of the domain.|
|radial_profile|Enum|Profile shape used across the trench cross-section.|
|radial_profile_parameter|Float|Sharpness or shape exponent for the radial profile.|
|Seed|Random seed number|Random seed number. The random seed is an offset to the randomized process. A different seed will produce a new result.|
|upward_penalization|Float|Penalty factor applied to uphill elevation changes during pathfinding.|
|width|Float|Width of the carved river trench.|

## Example


!!! note "No example yet"
    No example available for this node.
