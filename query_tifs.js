/**
 * query_tifs.js
 *
 * Given a lat/lon coordinate, reads the nearest-neighbor pixel value
 * from one or more GeoTIFF files (WGS84/EPSG:4326).
 *
 * Dependencies: geotiff.js (https://geotiffjs.github.io/)
 *   <script src="https://cdn.jsdelivr.net/npm/geotiff@2/dist-browser/geotiff.js"></script>
 *   or: import { fromUrl, fromArrayBuffer } from 'geotiff';
 */

/**
 * Compute the pixel [col, row] for a lat/lon using nearest-neighbor.
 *
 * @param {number} lat  - Latitude (degrees)
 * @param {number} lon  - Longitude (degrees)
 * @param {object} image - GeoTIFF image object from geotiff.js
 * @returns {{ col: number, row: number } | null} Pixel coords, or null if out of bounds
 */
function latLonToPixel(lat, lon, image) {
  // origin = [x (lon), y (lat), z] of the top-left corner of the top-left pixel
  const [originLon, originLat] = image.getOrigin();
  // resolution = [xRes, yRes, zRes]; yRes is negative (north-up rasters)
  const [xRes, yRes] = image.getResolution();

  const col = Math.round((lon - originLon) / xRes);
  const row = Math.round((lat - originLat) / yRes);

  const width = image.getWidth();
  const height = image.getHeight();

  if (col < 0 || col >= width || row < 0 || row >= height) {
    return null; // coordinate is outside this raster's extent
  }

  return { col, row };
}

/**
 * Read the value of a single pixel from a GeoTIFF image.
 * Uses a 1×1 window read so only that tile/strip is fetched — efficient
 * even for very large files if served over HTTP with range-request support.
 *
 * @param {object} image   - GeoTIFF image from geotiff.js
 * @param {number} col     - Pixel column (0-indexed)
 * @param {number} row     - Pixel row (0-indexed)
 * @param {number} [band]  - 1-indexed band number (default: 1)
 * @returns {Promise<number|null>} The pixel value, or null on error
 */
async function readPixel(image, col, row, band = 1) {
  const samples = [band - 1]; // geotiff.js uses 0-indexed samples
  const window = [col, row, col + 1, row + 1]; // [left, top, right, bottom]

  const rasters = await image.readRasters({ window, samples });
  // rasters[0] is a TypedArray with the sample data; window is 1×1 so index 0
  return rasters[0][0];
}

/**
 * Query a list of GeoTIFF files for the nearest-neighbor value at a lat/lon.
 *
 * @param {Array<string>}  tifPaths  - URLs or paths to .tif files
 * @param {number}         lat       - Query latitude
 * @param {number}         lon       - Query longitude
 * @param {object}         [options]
 * @param {number}         [options.band=1]      - Raster band to read (1-indexed)
 * @param {function}       [options.onProgress]  - Called with (index, total, path) as each file is read
 * @returns {Promise<Array<{ file: string, value: number|null, outOfBounds: boolean }>>}
 */
async function queryTifs(tifPaths, lat, lon, options = {}) {
  const { band = 1, onProgress } = options;
  const { fromUrl } = GeoTIFF; // global from CDN; or: import { fromUrl } from 'geotiff'

  const results = [];

  for (let i = 0; i < tifPaths.length; i++) {
    const path = tifPaths[i];
    if (onProgress) onProgress(i, tifPaths.length, path);

    try {
      const tif = await fromUrl(path);
      const image = await tif.getImage();
      const pixel = latLonToPixel(lat, lon, image);

      if (pixel === null) {
        results.push({ file: path, value: null, outOfBounds: true });
      } else {
        const value = await readPixel(image, pixel.col, pixel.row, band);
        results.push({ file: path, value, outOfBounds: false });
      }
    } catch (err) {
      results.push({ file: path, value: null, outOfBounds: false, error: err.message });
    }
  }

  return results;
}

/**
 * Same as queryTifs but loads from an ArrayBuffer instead of a URL.
 * Useful when files are uploaded via <input type="file"> or fetched manually.
 *
 * @param {Array<{ name: string, buffer: ArrayBuffer }>} tifBuffers
 * @param {number} lat
 * @param {number} lon
 * @param {object} [options]
 * @returns {Promise<Array<{ file: string, value: number|null, outOfBounds: boolean }>>}
 */
async function queryTifsFromBuffers(tifBuffers, lat, lon, options = {}) {
  const { band = 1, onProgress } = options;
  const { fromArrayBuffer } = GeoTIFF;

  const results = [];

  for (let i = 0; i < tifBuffers.length; i++) {
    const { name, buffer } = tifBuffers[i];
    if (onProgress) onProgress(i, tifBuffers.length, name);

    try {
      const tif = await fromArrayBuffer(buffer);
      const image = await tif.getImage();
      const pixel = latLonToPixel(lat, lon, image);

      if (pixel === null) {
        results.push({ file: name, value: null, outOfBounds: true });
      } else {
        const value = await readPixel(image, pixel.col, pixel.row, band);
        results.push({ file: name, value, outOfBounds: false });
      }
    } catch (err) {
      results.push({ file: name, value: null, outOfBounds: false, error: err.message });
    }
  }

  return results;
}
