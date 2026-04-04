"""
Terrain data fetching and mesh generation for tidl-3d.

Fetches elevation GeoTIFF from USGS 3DEP and converts to
3D mesh suitable for Three.js BufferGeometry.
"""

import httpx
import numpy as np
from pyproj import Transformer
from rasterio.io import MemoryFile
from rasterio.transform import Affine

# USGS 3DEP exportImage endpoint
USGS_URL = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'

# Default grid resolution
DEFAULT_RESOLUTION = 256
# Vertical exaggeration factor
VERTICAL_EXAGGERATION = 2.0
# No-data or invalid elevation values will be clamped to this level (sea level)
NO_DATA_FILL = 0.0


async def fetch_elevation(
    bbox: tuple[float, float, float, float],
    size: tuple[int, int] = (DEFAULT_RESOLUTION, DEFAULT_RESOLUTION),
) -> tuple[np.ndarray, Affine, str]:
    """
    Fetch elevation GeoTIFF for given bbox (xmin, ymin, xmax, ymax in EPSG:4326).

    Returns:
      - 2D numpy array of elevation values (meters), shape = size
      - Affine transform for pixel to dataset CRS coordinates
      - Dataset CRS as string (e.g. "EPSG:3857")

    """
    params = {
        'bbox': f'{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}',
        'bboxSR': 4326,
        'size': f'{size[0]},{size[1]}',
        'format': 'tiff',
        'f': 'image',
    }
    # NOTE: SSL verification disabled due to ZScaler proxy certificate issues.
    # The ZScaler certs have a malformed "Basic Constraints" extension that
    # Python 3.13's stricter SSL validation rejects. This is acceptable for
    # a local development tool fetching public elevation data.
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get(USGS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data_bytes = resp.content

    # Read GeoTIFF from memory
    with MemoryFile(data_bytes) as mem:
        with mem.open() as dataset:
            arr = dataset.read(1, masked=True)
            transform = dataset.transform
            crs = dataset.crs.to_string() if dataset.crs else 'EPSG:4326'

    # Convert masked values (no-data) to sea level
    elev = arr.filled(np.nan)
    elev = np.where(np.isfinite(elev), elev, NO_DATA_FILL)
    return elev, transform, crs


def bbox_for_point(lat: float, lon: float, half_size_m: float = 2000.0) -> tuple[float, float, float, float]:
    """
    Create a bounding box ~2km (half_size_m) around a lat/lon point.

    Returns (xmin, ymin, xmax, ymax) in degrees (EPSG:4326).
    """
    # Approximate meters per degree at this latitude
    m_per_deg_lat = 111319.9
    m_per_deg_lon = 111319.9 * np.cos(np.deg2rad(lat))
    lat_delta = half_size_m / m_per_deg_lat
    lon_delta = half_size_m / m_per_deg_lon
    return (lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta)


def generate_mesh(
    elev: np.ndarray,
    transform: Affine,
    center_lat: float,
    center_lon: float,
    resolution: int = DEFAULT_RESOLUTION,
    vertical_exagg: float = VERTICAL_EXAGGERATION,
    source_crs: str = 'EPSG:4326',
) -> tuple[list[float], list[float], list[int], list[float]]:
    """
    Convert elevation array to mesh vertices, normals, indices, and uvs.

    Coordinate system: local meters (Transverse Mercator centered on station), Y up.
    """
    h, w = elev.shape
    # Setup projection to local Transverse Mercator
    local_crs = f'+proj=tmerc +lat_0={center_lat} +lon_0={center_lon} +units=m +ellps=WGS84'
    transformer_to_local = Transformer.from_crs('EPSG:4326', local_crs, always_xy=True)
    transformer_src_to_wgs84 = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
    # Origin in projected meters (station center)
    origin_x, origin_y = transformer_to_local.transform(center_lon, center_lat)

    # Precompute projected grid positions and vertices
    vertices = np.zeros((h, w, 3), dtype=np.float64)
    for i in range(h):  # row (y index)
        for j in range(w):  # col (x index)
            src_xy = transform * (j, i)
            src_x, src_y = float(src_xy[0]), float(src_xy[1])

            try:
                lon, lat = transformer_src_to_wgs84.transform(src_x, src_y)
            except Exception:
                lon, lat = center_lon, center_lat

            if not (np.isfinite(lon) and np.isfinite(lat)):
                lon, lat = center_lon, center_lat

            try:
                x_proj, y_proj = transformer_to_local.transform(lon, lat)
            except Exception:
                x_proj, y_proj = origin_x, origin_y

            if not (np.isfinite(x_proj) and np.isfinite(y_proj)):
                x_proj, y_proj = origin_x, origin_y

            local_x = x_proj - origin_x
            local_z = y_proj - origin_y
            height = float(elev[i, j]) * vertical_exagg
            vertices[i, j, :] = (local_x, height, local_z)

    # Compute grid spacing (assume roughly uniform)
    if w > 1 and h > 1:
        dx = np.linalg.norm(vertices[0, 1, :] - vertices[0, 0, :])
        dz = np.linalg.norm(vertices[1, 0, :] - vertices[0, 0, :])
    else:
        dx = dz = 1.0

    # Compute normals via central differences
    normals = np.zeros_like(vertices)
    for i in range(h):
        for j in range(w):
            if 0 < i < h - 1 and 0 < j < w - 1:
                # height differences
                dh_dx = (elev[i, j + 1] - elev[i, j - 1]) * vertical_exagg / (2 * dx)
                dh_dz = (elev[i + 1, j] - elev[i - 1, j]) * vertical_exagg / (2 * dz)
                # normal vector
                n = np.array([-dh_dx, 1.0, -dh_dz], dtype=np.float64)
                n /= np.linalg.norm(n)
                normals[i, j, :] = n
            else:
                normals[i, j, :] = (0.0, 1.0, 0.0)

    # Build indices and uvs
    vertices_flat: list[float] = []
    normals_flat: list[float] = []
    uvs_flat: list[float] = []
    for i in range(h):
        v = i / (h - 1) if h > 1 else 0.0
        for j in range(w):
            uv_u = j / (w - 1) if w > 1 else 0.0
            uv_v = v
            # append vertex
            vx, vy, vz = vertices[i, j, :]
            vertices_flat.extend([vx, vy, vz])
            # append normal
            nx, ny, nz = normals[i, j, :]
            normals_flat.extend([nx, ny, nz])
            # append uv
            uvs_flat.extend([uv_u, uv_v])

    # Triangle indices (two triangles per cell)
    indices: list[int] = []
    for i in range(h - 1):
        for j in range(w - 1):
            idx0 = i * w + j
            idx1 = idx0 + 1
            idx2 = (i + 1) * w + j
            idx3 = idx2 + 1
            # triangle one
            indices.extend([idx0, idx2, idx1])
            # triangle two
            indices.extend([idx1, idx2, idx3])

    return vertices_flat, normals_flat, indices, uvs_flat


def find_land_center_offset(
    elev: np.ndarray,
    search_radius_cells: int = 64,
) -> tuple[int, int]:
    """
    Analyze elevation grid to find offset toward land mass center.

    The goal is to shift the view so the coastline crosses the terrain
    in an interesting way, rather than having the tide station (which is
    at the water's edge) centered.

    Returns (row_offset, col_offset) in grid cells to shift toward land.
    """
    h, w = elev.shape
    center_row, center_col = h // 2, w // 2

    # Find cells that are above sea level (land)
    land_mask = elev > 0.5  # Small threshold to avoid noise

    if not np.any(land_mask):
        # No land found, no offset
        return (0, 0)

    # Find centroid of land mass
    land_rows, land_cols = np.where(land_mask)
    if len(land_rows) == 0:
        return (0, 0)

    land_centroid_row = int(np.mean(land_rows))
    land_centroid_col = int(np.mean(land_cols))

    # Calculate offset from center toward land centroid
    # We don't want to go all the way - just shift partway toward land
    row_offset = (land_centroid_row - center_row) // 2
    col_offset = (land_centroid_col - center_col) // 2

    # Clamp to search radius
    row_offset = max(-search_radius_cells, min(search_radius_cells, row_offset))
    col_offset = max(-search_radius_cells, min(search_radius_cells, col_offset))

    return (row_offset, col_offset)


async def mesh_for_point(
    lat: float,
    lon: float,
    resolution: int = DEFAULT_RESOLUTION,
    half_size_m: float = 2000.0,
) -> tuple[list[float], list[float], list[int], list[float], tuple[float, float, float, float]]:
    """
    High-level helper: fetch elevation and generate mesh for a station point.

    This function fetches a larger area first, analyzes the land/water distribution,
    then offsets the center toward land to get a better coastline view.

    Returns vertices, normals, indices, uvs, bbox
    """
    # First, fetch a larger area to analyze land/water distribution
    # We fetch 50% larger to have room to shift the center
    scout_half_size = half_size_m * 1.5
    scout_bbox = bbox_for_point(lat, lon, half_size_m=scout_half_size)
    scout_elev, scout_transform, source_crs = await fetch_elevation(scout_bbox, size=(resolution, resolution))

    # Find offset toward land
    row_offset, col_offset = find_land_center_offset(scout_elev)

    # Convert cell offset to lat/lon offset
    # Each cell represents (scout_half_size * 2) / resolution meters
    meters_per_cell = (scout_half_size * 2) / resolution

    # Approximate conversion to degrees
    m_per_deg_lat = 111319.9
    m_per_deg_lon = 111319.9 * np.cos(np.deg2rad(lat))

    lat_offset = (row_offset * meters_per_cell) / m_per_deg_lat
    lon_offset = (col_offset * meters_per_cell) / m_per_deg_lon

    # New center shifted toward land
    adjusted_lat = lat + lat_offset
    adjusted_lon = lon + lon_offset

    # Now fetch the actual terrain at the adjusted center
    bbox = bbox_for_point(adjusted_lat, adjusted_lon, half_size_m=half_size_m)
    elev, transform, source_crs = await fetch_elevation(bbox, size=(resolution, resolution))

    # Generate mesh centered on the adjusted point
    verts, norms, inds, uvs = generate_mesh(
        elev, transform, adjusted_lat, adjusted_lon, resolution, source_crs=source_crs
    )
    return verts, norms, inds, uvs, bbox
