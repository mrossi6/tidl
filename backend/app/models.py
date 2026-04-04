"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel


class TerrainMesh(BaseModel):
    """Terrain geometry data for Three.js BufferGeometry."""

    vertices: list[float]  # [x1, y1, z1, x2, y2, z2, ...]
    normals: list[float]  # [nx1, ny1, nz1, ...]
    indices: list[int]  # Triangle indices
    uvs: list[float]  # [u1, v1, u2, v2, ...]


class WaterMesh(BaseModel):
    """Water plane geometry."""

    base_level: float
    vertices: list[float]
    indices: list[int]


class CameraPath(BaseModel):
    """Pre-computed camera flyover path."""

    type: str  # "orbit", "figure8", etc.
    center: list[float]  # [x, y, z]
    radius: float
    height: float
    duration_seconds: float


class BoundingBox(BaseModel):
    """Geographic bounding box."""

    north: float
    south: float
    east: float
    west: float


class MeshMetadata(BaseModel):
    """Metadata about the generated mesh."""

    grid_resolution: int
    area_km2: float
    vertex_count: int
    triangle_count: int
    elevation_range: list[float]  # [min, max]
    generated_at: str


class TerrainResponse(BaseModel):
    """Complete terrain response for a station."""

    station_id: str
    station_name: str
    bounds: BoundingBox
    terrain: TerrainMesh
    water: WaterMesh
    camera_path: CameraPath
    metadata: MeshMetadata


class Station(BaseModel):
    """NOAA tide prediction station."""

    id: str
    name: str
    lat: float
    lon: float
    state: str | None = None


class StationsResponse(BaseModel):
    """List of stations."""

    stations: list[Station]


class TidePrediction(BaseModel):
    """Single tide prediction (high or low)."""

    time: str
    height_ft: float
    type: str  # "H" or "L"


class CurrentTide(BaseModel):
    """Current tide conditions."""

    height_ft: float
    height_m: float
    trend: str  # "rising", "falling", "slack"
    timestamp: str


class TidesResponse(BaseModel):
    """Tide data response."""

    station_id: str
    current: CurrentTide
    predictions: list[TidePrediction]
