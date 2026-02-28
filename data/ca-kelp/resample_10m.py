"""
Resample NorCal kelp rasters to ~10 m resolution using max pooling.

Uses rasterio.warp.reproject which handles large files without loading
everything into memory at once.
"""

import math
import os
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from pathlib import Path

INPUT_DIR  = Path(__file__).parent / "norcal"
OUTPUT_DIR = Path(__file__).parent / "norcal_10m"
OUTPUT_DIR.mkdir(exist_ok=True)

# 10 m expressed in degrees (latitude-based; valid approximation for NorCal)
TARGET_RES_DEG = 10.0 / 111320.0   # ≈ 0.00008983°

tifs = sorted(INPUT_DIR.glob("*.tif"))
print(f"Found {len(tifs)} raster(s) to resample.\n")

for src_path in tifs:
    out_name = src_path.name.replace("NorCal", "NorCal_10m")
    out_path = OUTPUT_DIR / out_name
    print(f"Resampling: {src_path.name}")
    print(f"       → : {out_name}")

    with rasterio.open(src_path) as src:
        b = src.bounds

        dst_width  = int(math.ceil((b.right - b.left) / TARGET_RES_DEG))
        dst_height = int(math.ceil((b.top   - b.bottom) / TARGET_RES_DEG))

        dst_transform = from_bounds(
            b.left, b.bottom, b.right, b.top,
            dst_width, dst_height
        )

        profile = src.profile.copy()
        profile.update(
            height=dst_height,
            width=dst_width,
            transform=dst_transform,
            tiled=True,
            compress="lzw",
            blockxsize=512,
            blockysize=512,
        )

        src_pixels  = src.height * src.width
        dst_pixels  = dst_height * dst_width
        approx_scale = src.height / dst_height

        print(f"  Original  : {src.height:,} × {src.width:,}  ({src_pixels/1e6:.1f} Mpx)")
        print(f"  Target    : {dst_height:,} × {dst_width:,}  ({dst_pixels/1e6:.1f} Mpx)  "
              f"[~{approx_scale:.1f}× downscale]")

        with rasterio.open(out_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                resampling=Resampling.max,
            )

        in_mb  = os.path.getsize(src_path) / 1e6
        out_mb = os.path.getsize(out_path) / 1e6
        print(f"  File size : {in_mb:.1f} MB → {out_mb:.1f} MB  "
              f"({100*(1-out_mb/in_mb):.0f}% smaller)\n")

print("Done. Files saved to:", OUTPUT_DIR)
