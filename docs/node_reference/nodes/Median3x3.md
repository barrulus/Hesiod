
Median3x3 Node
==============


Median3x3 filter is a median filter with a 3x3 kernel used to reduce noise while preserving edges in an image. This process removes outliers and smooths the image without noise reduction and feature preservation in digital images.



![img](../../images/nodes/Median3x3_settings.png)


# Category


Filter/Smoothing
# Inputs

|Name|Type|Description|
| :--- | :--- | :--- |
|input|Heightmap|Input heightmap.|
|mask|Heightmap|Mask defining the filtering intensity (expected in [0, 1]).|

# Outputs

|Name|Type|Description|
| :--- | :--- | :--- |
|output|Heightmap|Filtered heightmap.|

# Parameters

|Name|Type|Description|
| :--- | :--- | :--- |
|GPU|Bool|Toogle GPU acceleration on or off.|

# Example


No example available.