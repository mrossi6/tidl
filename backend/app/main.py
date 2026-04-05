"""FastAPI application for tidl-3d."""

import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.models import (
    BoundingBox,
    CameraPath,
    MeshMetadata,
    Station,
    StationsResponse,
    TerrainMesh,
    TerrainResponse,
    WaterMesh,
)

logger = logging.getLogger(__name__)

app = FastAPI(title='tidl-3d', description='3D Coastal Flyover Visualization')

# Hardcoded stations (will be replaced with NOAA API in Phase 3)
STATIONS = {
    '8631044': Station(id='8631044', name='Wachapreague, VA', lat=37.6078, lon=-75.6858, state='VA'),
    '8638863': Station(id='8638863', name='Chesapeake Bay Bridge Tunnel, VA', lat=36.9667, lon=-76.1133, state='VA'),
    '8452660': Station(id='8452660', name='Newport, RI', lat=41.5044, lon=-71.3261, state='RI'),
}

# Path to frontend files
FRONTEND_DIR = Path(__file__).parent.parent.parent / 'frontend'


def generate_plane_mesh(
    width: float = 1000.0,
    depth: float = 1000.0,
    segments: int = 64,
) -> tuple[list[float], list[float], list[int], list[float]]:
    """
    Generate a flat plane mesh for testing.

    Returns (vertices, normals, indices, uvs).
    """
    vertices: list[float] = []
    normals: list[float] = []
    uvs: list[float] = []
    indices: list[int] = []

    # Generate vertices
    for z in range(segments + 1):
        for x in range(segments + 1):
            # Position (centered at origin)
            px = (x / segments - 0.5) * width
            pz = (z / segments - 0.5) * depth

            # Add some gentle hills for visual interest
            py = 20.0 * math.sin(px * 0.01) * math.cos(pz * 0.01)

            vertices.extend([px, py, pz])

            # Normal (pointing up, adjusted for slope)
            normals.extend([0.0, 1.0, 0.0])

            # UV coordinates
            uvs.extend([x / segments, z / segments])

    # Generate triangle indices
    for z in range(segments):
        for x in range(segments):
            top_left = z * (segments + 1) + x
            top_right = top_left + 1
            bottom_left = (z + 1) * (segments + 1) + x
            bottom_right = bottom_left + 1

            # Two triangles per grid cell
            indices.extend([top_left, bottom_left, top_right])
            indices.extend([top_right, bottom_left, bottom_right])

    return vertices, normals, indices, uvs


def generate_water_mesh(
    width: float = 1000.0,
    depth: float = 1000.0,
) -> tuple[list[float], list[int]]:
    """Generate a simple water plane."""
    half_w = width / 2
    half_d = depth / 2

    vertices = [
        -half_w,
        0.0,
        -half_d,
        half_w,
        0.0,
        -half_d,
        half_w,
        0.0,
        half_d,
        -half_w,
        0.0,
        half_d,
    ]

    indices = [0, 2, 1, 0, 3, 2]

    return vertices, indices


@app.get('/api/terrain/{station_id}')
async def get_terrain(station_id: str) -> TerrainResponse:
    """
    Get terrain mesh for a station.

    Fetches real elevation data from USGS 3DEP and generates mesh.
    Falls back to test plane if elevation fetch fails.
    """
    station = STATIONS.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail=f'Station {station_id} not found')

    # Try to fetch real terrain
    try:
        from app.terrain import mesh_for_point

        vertices, normals, indices, uvs, bbox = await mesh_for_point(
            lat=station.lat,
            lon=station.lon,
            resolution=256,
            half_size_m=2000.0,
        )

        # Calculate elevation range from vertices (Y component)
        y_values = vertices[1::3]  # Every 3rd element starting at 1
        elev_min = min(y_values) if y_values else 0.0
        elev_max = max(y_values) if y_values else 0.0

        # Generate water mesh to cover the same area
        water_verts, water_indices = generate_water_mesh(width=4000.0, depth=4000.0)

        return TerrainResponse(
            station_id=station_id,
            station_name=station.name,
            bounds=BoundingBox(north=bbox[3], south=bbox[1], east=bbox[2], west=bbox[0]),
            terrain=TerrainMesh(
                vertices=vertices,
                normals=normals,
                indices=indices,
                uvs=uvs,
            ),
            water=WaterMesh(
                base_level=0.0,
                vertices=water_verts,
                indices=water_indices,
            ),
            camera_path=CameraPath(
                type='orbit',
                center=[0.0, elev_max / 2, 0.0],  # Look at a point above sea level
                radius=600.0,  # Stay well inside the 4km terrain
                height=400.0,  # Nice aerial view height
                duration_seconds=60.0,
            ),
            metadata=MeshMetadata(
                grid_resolution=256,
                area_km2=16.0,
                vertex_count=len(vertices) // 3,
                triangle_count=len(indices) // 3,
                elevation_range=[elev_min, elev_max],
                generated_at=datetime.now(timezone.utc).isoformat(),
            ),
        )

    except Exception as e:
        logger.warning(f'Failed to fetch real terrain for {station_id}: {e}')
        # Fall back to test plane
        vertices, normals, indices, uvs = generate_plane_mesh()
        water_verts, water_indices = generate_water_mesh()

        return TerrainResponse(
            station_id=station_id,
            station_name=f'{station.name} (test data)',
            bounds=BoundingBox(north=37.62, south=37.58, east=-75.66, west=-75.70),
            terrain=TerrainMesh(
                vertices=vertices,
                normals=normals,
                indices=indices,
                uvs=uvs,
            ),
            water=WaterMesh(
                base_level=0.0,
                vertices=water_verts,
                indices=water_indices,
            ),
            camera_path=CameraPath(
                type='orbit',
                center=[0.0, 0.0, 0.0],
                radius=800.0,
                height=400.0,
                duration_seconds=60.0,
            ),
            metadata=MeshMetadata(
                grid_resolution=64,
                area_km2=1.0,
                vertex_count=len(vertices) // 3,
                triangle_count=len(indices) // 3,
                elevation_range=[-20.0, 20.0],
                generated_at=datetime.now(timezone.utc).isoformat(),
            ),
        )


@app.get('/api/stations')
async def get_stations() -> StationsResponse:
    """Get list of available tide stations."""
    return StationsResponse(stations=list(STATIONS.values()))


# Serve frontend static files
if FRONTEND_DIR.exists():
    app.mount('/', StaticFiles(directory=FRONTEND_DIR, html=True), name='frontend')
