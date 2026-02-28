"""
Clip SST NetCDF4 files to Northern California
(everything north of 37.813179° latitude, i.e., down to Marin County).

Uses chunked row I/O to avoid loading the full array into memory.
"""

import h5py
import numpy as np
from pathlib import Path

INPUT_DIR  = Path(__file__).parent
OUTPUT_DIR = INPUT_DIR / "norcal"
OUTPUT_DIR.mkdir(exist_ok=True)

MIN_LAT    = 37.813179   # southern clip edge — top of Marin County
CHUNK_ROWS = 256         # lat rows to process at a time

nc4s = sorted(INPUT_DIR.glob("*.nc4"))
print(f"Found {len(nc4s)} file(s) to clip.\n")

for src_path in nc4s:
    out_path = OUTPUT_DIR / src_path.name.replace("CONUS", "NorCal")
    print(f"Clipping : {src_path.name}")
    print(f"       → : {out_path.name}")

    with h5py.File(src_path, "r") as src, h5py.File(out_path, "w") as dst:
        lat = src["lat"][:]
        lon = src["lon"][:]

        # Find the first lat index at or above MIN_LAT (lat is ascending)
        lat_start = int(np.searchsorted(lat, MIN_LAT))
        clipped_lat = lat[lat_start:]
        n_lat_out = len(clipped_lat)

        print(f"  Original : {len(lat)} lat rows × {len(lon)} lon cols")
        print(f"  Clipped  : {n_lat_out} lat rows × {len(lon)} lon cols")
        print(f"  Lat range: {clipped_lat[0]:.6f} – {clipped_lat[-1]:.6f}")

        # ── Copy scalar / 1-D / non-SST datasets verbatim ──────────────────
        for name in src:
            if name == "sst":
                continue  # handled separately below
            if name == "lat":
                ds = dst.create_dataset("lat", data=clipped_lat)
            else:
                ds = dst.create_dataset(name, data=src[name][()])  # [()] works for scalar and array

            # Copy attributes
            for k, v in src[name].attrs.items():
                try:
                    ds.attrs[k] = v
                except Exception:
                    pass  # skip unwritable attrs (e.g. DIMENSION_LIST refs)

        # ── Copy file-level attributes ──────────────────────────────────────
        for k, v in src.attrs.items():
            try:
                dst.attrs[k] = v
            except Exception:
                pass

        # ── Create clipped SST dataset and fill row by row ──────────────────
        src_sst = src["sst"]                      # (time, level, lat, lon)
        t, lv, _, nl = src_sst.shape
        chunks = src_sst.chunks                   # use original chunk shape if set

        dst_sst = dst.create_dataset(
            "sst",
            shape=(t, lv, n_lat_out, nl),
            dtype=src_sst.dtype,
            chunks=chunks,
            compression="gzip",
            compression_opts=4,
        )
        for k, v in src_sst.attrs.items():
            try:
                dst_sst.attrs[k] = v
            except Exception:
                pass

        rows_done = 0
        while rows_done < n_lat_out:
            chunk = min(CHUNK_ROWS, n_lat_out - rows_done)
            src_row = lat_start + rows_done
            data = src_sst[:, :, src_row : src_row + chunk, :]
            dst_sst[:, :, rows_done : rows_done + chunk, :] = data
            rows_done += chunk
            pct = rows_done / n_lat_out * 100
            print(f"  {pct:5.1f}%", end="\r", flush=True)

    print(f"  100.0% — saved {out_path}\n")

print("Done. Clipped files saved to:", OUTPUT_DIR)
