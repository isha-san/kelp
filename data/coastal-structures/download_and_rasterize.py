"""
Download CSMW Coastal Structures and Barriers from the California CNRA ArcGIS
MapServer and rasterize the polygon layer to a GeoTIFF.

Source:
  https://gis.cnra.ca.gov/arcgis/rest/services/Ocean/CSMW_Coastal_Structures_and_Barriers/MapServer/0

Output:
  coastal_structures.geojson   — raw download (all features)
  coastal_structures.tif       — rasterized binary mask (1 = structure present)

Resolution: ~10 m (expressed in degrees, same convention as the kelp rasters).
CRS: EPSG:4326 (WGS-84 lat/lon), matching the rest of the project.
"""

import json
import math
from pathlib import Path

import requests
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = (
    "https://gis.cnra.ca.gov/arcgis/rest/services"
    "/Ocean/CSMW_Coastal_Structures_and_Barriers/MapServer/0/query"
)
OUT_DIR = Path(__file__).parent
GEOJSON_PATH = OUT_DIR / "coastal_structures.geojson"
RASTER_PATH  = OUT_DIR / "coastal_structures.tif"

# ~10 m in degrees (latitude-based approximation, valid for California)
TARGET_RES_DEG = 10.0 / 111_320.0  # ≈ 8.983e-5 °

# California coast bounding box in WGS-84 (lon_min, lat_min, lon_max, lat_max)
# Generous bounds — rasterize will only burn what's actually in the features.
CA_BOUNDS = (-124.5, 32.5, -117.1, 42.0)


# ---------------------------------------------------------------------------
# Step 1: Download all features from the ArcGIS REST API
# ---------------------------------------------------------------------------
def download_features() -> dict:
    """Page through the query endpoint and return a single GeoJSON FeatureCollection."""
    all_features = []
    offset = 0
    page_size = 1000  # server max is 2000; 1000 is safe

    print("Downloading features from ArcGIS REST API...")
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": "4326",       # ask server to return WGS-84 directly
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        page = resp.json()

        features = page.get("features", [])
        all_features.extend(features)
        print(f"  fetched {len(all_features)} features so far...")

        # Stop when the server signals there are no more records
        if not page.get("exceededTransferLimit", False) or len(features) == 0:
            break
        offset += page_size

    print(f"  total features downloaded: {len(all_features)}\n")
    return {
        "type": "FeatureCollection",
        "features": all_features,
    }


# ---------------------------------------------------------------------------
# Step 2: Rasterize polygons to GeoTIFF
# ---------------------------------------------------------------------------
def rasterize_features(geojson: dict) -> None:
    lon_min, lat_min, lon_max, lat_max = CA_BOUNDS

    width  = int(math.ceil((lon_max - lon_min) / TARGET_RES_DEG))
    height = int(math.ceil((lat_max - lat_min) / TARGET_RES_DEG))

    transform = from_bounds(lon_min, lat_min, lon_max, lat_max, width, height)

    print(f"Rasterizing to {height:,} rows × {width:,} cols "
          f"(~{TARGET_RES_DEG*111320:.0f} m resolution)...")

    # Build (geometry, value) pairs for rasterize
    shapes = []
    for feat in geojson["features"]:
        geom = feat.get("geometry")
        if geom is None:
            continue
        shapes.append((geom, 1))

    if not shapes:
        print("WARNING: no valid geometries found — output will be empty.")

    burned = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=True,   # include pixels the polygon edge merely touches
    )

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": width,
        "height": height,
        "count": 1,
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "nodata": 255,
    }

    with rasterio.open(RASTER_PATH, "w", **profile) as dst:
        dst.write(burned, 1)

    n_pixels = int(burned.sum())
    print(f"  pixels burned (structure present): {n_pixels:,}")
    print(f"  saved → {RASTER_PATH}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Download
    geojson = download_features()
    GEOJSON_PATH.write_text(json.dumps(geojson, indent=2))
    print(f"GeoJSON saved → {GEOJSON_PATH}\n")

    # Rasterize
    rasterize_features(geojson)

    print("Done.")
