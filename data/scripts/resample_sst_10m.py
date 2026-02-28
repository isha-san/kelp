"""
Clip NorCal SST from .nc4 to a GeoTIFF at native ~1km resolution.

Keeps the original 0.01° (~1 km) pixel size — no upsampling.
Alignment to the 10 m grid happens at data-loading time.
"""

import os
import h5py
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from pathlib import Path

INPUT_FILE  = Path(__file__).parent.parent / "preprocessed" / "JPLMUR_2023001_ANNUAL_L4ANALYSIS_SST_NorCal_1KM.nc4"
OUTPUT_FILE = Path(__file__).parent.parent / "preprocessed" / "JPLMUR_2023001_ANNUAL_L4ANALYSIS_SST_NorCal_1KM.tif"

# NorCal bounding box — matches kelp canopy / coastal structures extent
NORCAL_LEFT, NORCAL_BOTTOM, NORCAL_RIGHT, NORCAL_TOP = -124.5, 37.813179, -117.1, 42.0

CRS = "EPSG:4326"

print(f"Reading {INPUT_FILE.name} ...")

with h5py.File(INPUT_FILE, "r") as f:
    lat = f["lat"][:]   # (1419,) ascending: 37.82 → 52.0
    lon = f["lon"][:]   # (7001,) ascending: -132.0 → -62.0

    lat_mask = (lat >= NORCAL_BOTTOM) & (lat <= NORCAL_TOP)
    lon_mask = (lon >= NORCAL_LEFT)   & (lon <= NORCAL_RIGHT)

    lat_idx = np.where(lat_mask)[0]
    lon_idx = np.where(lon_mask)[0]
    lat_clip = lat[lat_idx[0] : lat_idx[-1] + 1]
    lon_clip = lon[lon_idx[0] : lon_idx[-1] + 1]

    sst = f["sst"][0, 0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1].astype("float32")

# NetCDF lat is south→north; flip to north→south for rasterio
sst = sst[::-1, :].copy()
lat_clip = lat_clip[::-1]

src_h, src_w = sst.shape
src_res = float(abs(lat[1] - lat[0]))  # 0.01°

transform = from_bounds(
    float(lon_clip[0])  - src_res / 2,   # left
    float(lat_clip[-1]) - src_res / 2,   # bottom
    float(lon_clip[-1]) + src_res / 2,   # right
    float(lat_clip[0])  + src_res / 2,   # top
    src_w, src_h,
)

print(f"  Clipped shape : {src_h} × {src_w}  (~1 km pixels)")
print(f"  Writing {OUTPUT_FILE.name} ...")

profile = {
    "driver": "GTiff",
    "dtype": "float32",
    "nodata": float("nan"),
    "width": src_w,
    "height": src_h,
    "count": 1,
    "crs": CRS,
    "transform": transform,
    "compress": "lzw",
    "tiled": True,
    "blockxsize": 256,
    "blockysize": 256,
}

with rasterio.open(OUTPUT_FILE, "w", **profile) as dst:
    dst.write(sst[np.newaxis, :, :])

out_mb = os.path.getsize(OUTPUT_FILE) / 1e6
print(f"  Done. {out_mb:.1f} MB  →  {OUTPUT_FILE}")
