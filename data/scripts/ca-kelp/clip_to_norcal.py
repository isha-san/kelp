"""
Clip California kelp raster files to Northern California
(everything north of 37.813179° latitude, i.e., down to Marin County).

Uses row-by-row chunked I/O to avoid loading huge arrays into memory.
"""

import rasterio
from rasterio.windows import from_bounds, Window
from pathlib import Path

INPUT_DIR = Path(__file__).parent
OUTPUT_DIR = INPUT_DIR / "norcal"
OUTPUT_DIR.mkdir(exist_ok=True)

MIN_LAT = 37.813179   # southern clip edge — top of Marin County
CHUNK_ROWS = 1024     # rows to process at a time

tifs = sorted(INPUT_DIR.glob("*.tif"))
print(f"Found {len(tifs)} raster(s) to clip.\n")

for src_path in tifs:
    out_path = OUTPUT_DIR / src_path.name.replace("California", "NorCal")
    print(f"Clipping: {src_path.name}")
    print(f"      → : {out_path.name}")

    with rasterio.open(src_path) as src:
        bounds = src.bounds

        clip_bounds = (bounds.left, MIN_LAT, bounds.right, bounds.top)
        clip_window = from_bounds(*clip_bounds, transform=src.transform)

        # Snap to integer pixel grid
        col_off = max(0, int(clip_window.col_off))
        row_off = max(0, int(clip_window.row_off))
        width   = min(src.width  - col_off, int(clip_window.width))
        height  = min(src.height - row_off, int(clip_window.height))

        out_transform = src.window_transform(
            Window(col_off, row_off, width, height)
        )

        profile = src.profile.copy()
        profile.update(
            height=height,
            width=width,
            transform=out_transform,
            tiled=True,
            compress="lzw",
            blockxsize=512,
            blockysize=512,
        )

        print(f"  Original : {src.shape[0]} rows × {src.shape[1]} cols")
        print(f"  Clipped  : {height} rows × {width} cols")

        with rasterio.open(out_path, "w", **profile) as dst:
            rows_done = 0
            while rows_done < height:
                chunk = min(CHUNK_ROWS, height - rows_done)
                window = Window(col_off, row_off + rows_done, width, chunk)
                data = src.read(window=window)
                dst.write(data, window=Window(0, rows_done, width, chunk))
                rows_done += chunk
                pct = rows_done / height * 100
                print(f"  {pct:5.1f}%", end="\r", flush=True)

        print(f"  100.0% — saved {out_path}\n")

print("Done. Clipped files saved to:", OUTPUT_DIR)
