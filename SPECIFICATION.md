# tidl-3d: 3D Coastal Flyover Visualization

## Overview

A web-based 3D visualization tool that renders overhead flyover views of NOAA tide station locations, using real topography data and animated tidal water levels.

**Stack:**
- **Backend:** Python 3.13, FastAPI, uv
- **Frontend:** Vanilla JS + Three.js (minimal, ~300 lines)
- **Data Sources:** USGS 3DEP (elevation), NOAA CO-OPS (tides/stations)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Python Backend (FastAPI)                                       │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │ /api/stations │  │ /api/terrain/ │  │ /api/tides/{id}     │  │
│  │ List all tide │  │ {station_id}  │  │ Current + forecast  │  │
│  │ stations      │  │ Returns mesh  │  │ tide predictions    │  │
│  └───────────────┘  └───────────────┘  └─────────────────────┘  │
│           │                 │                     │             │
│           ▼                 ▼                     ▼             │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │ noaa.py       │  │ terrain.py    │  │ noaa.py             │  │
│  │ Station list  │  │ DEM fetch +   │  │ Tide predictions    │  │
│  │ from MDAPI    │  │ mesh gen      │  │ from Data API       │  │
│  └───────────────┘  └───────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌───────────┐   ┌───────────┐   ┌───────────┐
       │ NOAA      │   │ USGS 3DEP │   │ Local     │
       │ CO-OPS    │   │ API       │   │ Mesh      │
       │ APIs      │   │           │   │ Cache     │
       └───────────┘   └───────────┘   └───────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Browser (Three.js)                                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ • Fetch terrain mesh from /api/terrain/{station_id}        ││
│  │ • Fetch tide data from /api/tides/{station_id}             ││
│  │ • Render terrain as BufferGeometry                          ││
│  │ • Render water plane, animate Y position to tide height     ││
│  │ • Animate camera along pre-computed flyover path            ││
│  │ • Station picker dropdown to switch locations               ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

### NOAA CO-OPS APIs

**Metadata API (MDAPI)** — Station information
- Base: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi`
- Endpoints:
  - `GET /stations.json?type=tidepredictions` — List all tide prediction stations
  - `GET /stations/{id}.json` — Single station details

**Data API** — Tide predictions
- Base: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`
- Parameters:
  - `station` — Station ID (e.g., "8631044")
  - `product=predictions`
  - `datum=MLLW` (Mean Lower Low Water)
  - `interval=hilo` or `interval=6` (minutes)
  - `begin_date`, `end_date` — YYYYMMDD format
  - `units=english` or `units=metric`
  - `time_zone=lst_ldt`
  - `format=json`

### USGS 3DEP Elevation API

**National Map API** — Digital Elevation Models
- Base: `https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer`
- We'll use the `exportImage` endpoint to get elevation data as a GeoTIFF
- Parameters:
  - `bbox` — Bounding box in format `xmin,ymin,xmax,ymax`
  - `bboxSR=4326` — Coordinate system (WGS84)
  - `size=width,height` — Output image dimensions
  - `format=tiff`
  - `f=image`

**Coverage:** Continental US, ~1/3 arc-second (~10m) resolution nationally, higher in some areas.

## Mesh Specification

### Terrain Mesh Format

The backend generates meshes in a JSON format optimized for Three.js BufferGeometry:

```json
{
  "station_id": "8631044",
  "station_name": "Wachapreague, VA",
  "bounds": {
    "north": 37.62,
    "south": 37.58,
    "east": -75.66,
    "west": -75.70
  },
  "terrain": {
    "vertices": [x1, y1, z1, x2, y2, z2, ...],
    "normals": [nx1, ny1, nz1, nx2, ny2, nz2, ...],
    "indices": [i1, i2, i3, ...],
    "uvs": [u1, v1, u2, v2, ...]
  },
  "water": {
    "base_level": 0.0,
    "vertices": [x1, y1, z1, x2, y2, z2, ...],
    "indices": [i1, i2, i3, ...]
  },
  "camera_path": {
    "type": "orbit",
    "center": [x, y, z],
    "radius": 500,
    "height": 200,
    "duration_seconds": 60
  },
  "metadata": {
    "grid_resolution": 256,
    "area_km2": 16,
    "vertex_count": 65536,
    "triangle_count": 131072,
    "elevation_range": [-5.0, 45.0],
    "generated_at": "2024-01-15T12:00:00Z"
  }
}
```

### Mesh Generation Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Grid resolution | 256 x 256 | ~65k vertices, ~130k triangles |
| Area coverage | ~4km x 4km | Centered on station coordinates |
| Elevation exaggeration | 2x | Makes terrain features more visible |
| Coordinate system | Local meters | Origin at station, Y-up |

### Coordinate Transformations

1. **Station lat/lon** → Define bounding box (±2km)
2. **Fetch DEM** in WGS84 (EPSG:4326)
3. **Project to local meters** using Transverse Mercator centered on station
4. **Build mesh** with Y as vertical (elevation), X/Z as horizontal plane
5. **Apply vertical exaggeration** (2x default)

## API Endpoints

### `GET /api/stations`

Returns list of all NOAA tide prediction stations.

**Response:**
```json
{
  "stations": [
    {
      "id": "8631044",
      "name": "Wachapreague, VA",
      "lat": 37.6078,
      "lon": -75.6858,
      "state": "VA"
    },
    ...
  ]
}
```

### `GET /api/terrain/{station_id}`

Returns pre-generated terrain mesh for a station.

**Response:** See Mesh Specification above.

**Errors:**
- `404` — Station not found or mesh not generated
- `503` — Elevation data unavailable

### `GET /api/tides/{station_id}`

Returns current conditions and tide predictions.

**Query Parameters:**
- `hours` (optional, default=24) — Forecast duration

**Response:**
```json
{
  "station_id": "8631044",
  "current": {
    "height_ft": 2.34,
    "height_m": 0.71,
    "trend": "rising",
    "timestamp": "2024-01-15T14:30:00-05:00"
  },
  "predictions": [
    {
      "time": "2024-01-15T18:42:00-05:00",
      "height_ft": 3.8,
      "type": "H"
    },
    {
      "time": "2024-01-16T00:18:00-05:00",
      "height_ft": -0.2,
      "type": "L"
    },
    ...
  ]
}
```

### `GET /` (Static files)

Serves the frontend (index.html, main.js, style.css).

---

## Implementation Phases

### Phase 1: Scaffolding & Proof of Concept

**Goal:** Confirm end-to-end data flow from Python to WebGL rendering.

**Deliverables:**
1. Project structure with `uv` + `pyproject.toml`
2. FastAPI app with static file serving
3. `/api/terrain/test` endpoint returning hardcoded plane mesh
4. Three.js frontend that fetches and renders the plane
5. Basic orbit controls for camera

**Acceptance Criteria:**
- `uv run fastapi dev` starts server
- Browser shows rotating 3D plane
- No errors in console

**Files:**
```
backend/
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── models.py
frontend/
├── index.html
├── main.js
└── style.css
```

---

### Phase 2: Real Terrain Data

**Goal:** Fetch actual elevation data and render real coastal terrain.

**Deliverables:**
1. `terrain.py` module with:
   - USGS 3DEP API client
   - GeoTIFF parsing (using `rasterio`)
   - Heightmap → mesh conversion
   - Coordinate projection (using `pyproj`)
2. `/api/terrain/{station_id}` endpoint with real data
3. Terrain rendering with:
   - Elevation-based coloring (green → brown → white)
   - Proper normals for lighting
   - Vertical exaggeration

**Acceptance Criteria:**
- Can fetch elevation for any US coastal station
- Terrain mesh renders with recognizable coastal features
- Performance: mesh generation < 5 seconds

**New Dependencies:**
- `rasterio` — GeoTIFF reading
- `numpy` — Array operations
- `pyproj` — Coordinate transforms
- `httpx` — Async HTTP client

---

### Phase 3: Tides & Water

**Goal:** Add animated water that responds to real tide data.

**Deliverables:**
1. `noaa.py` module with:
   - Station list fetching
   - Tide prediction fetching
   - Current tide height interpolation
2. `/api/stations` endpoint
3. `/api/tides/{station_id}` endpoint
4. Water plane in Three.js:
   - Semi-transparent blue material
   - Animated Y position based on tide height
   - Subtle wave animation (vertex shader)

**Acceptance Criteria:**
- Water level animates smoothly between tide heights
- Current tide state displayed in UI
- Next high/low displayed

---

### Phase 4: Camera Flyover

**Goal:** Automated cinematic camera movement around terrain.

**Deliverables:**
1. Camera path generation in `terrain.py`:
   - Circular orbit path
   - Altitude based on terrain height
   - Smooth interpolation
2. Flyover animation in Three.js:
   - Configurable speed
   - Play/pause controls
   - Manual override with orbit controls

**Acceptance Criteria:**
- Camera smoothly orbits terrain
- User can pause and manually control
- Path avoids clipping through terrain

---

### Phase 5: Station Picker & Polish

**Goal:** Complete UI for browsing all stations.

**Deliverables:**
1. Station picker dropdown/search
2. Batch mesh pre-generation script
3. Loading states and error handling
4. Mesh caching (filesystem)
5. Basic styling/polish

**Acceptance Criteria:**
- Can switch between any US tide station
- Meshes load from cache when available
- Graceful handling of missing elevation data

---

## File Structure (Final)

```
tidl-3d/
├── README.md
├── SPECIFICATION.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application
│   │   ├── models.py            # Pydantic schemas
│   │   ├── noaa.py              # NOAA API client
│   │   └── terrain.py           # DEM fetching & mesh generation
│   ├── data/
│   │   └── meshes/              # Cached pre-generated meshes
│   ├── scripts/
│   │   └── generate_meshes.py   # Batch generation script
│   └── tests/
│       ├── test_noaa.py
│       └── test_terrain.py
├── frontend/
│   ├── index.html
│   ├── main.js
│   └── style.css
└── .gitignore
```

## Dependencies

### Python (backend/pyproject.toml)

```toml
[project]
name = "tidl-3d"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "httpx>=0.28",
    "pydantic>=2.10",
    "rasterio>=1.4",
    "numpy>=2.0",
    "pyproj>=3.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]
```

### JavaScript (CDN)

- Three.js r170+ (ES modules via CDN)
- No build step required

## Development Workflow

```bash
# Setup
cd tidl-3d/backend
uv sync

# Run development server
uv run fastapi dev app/main.py

# Run tests
uv run pytest

# Generate meshes for all stations
uv run python scripts/generate_meshes.py
```

## Future Enhancements (Out of Scope)

- Realistic water rendering (reflections, caustics)
- Vegetation/buildings from OpenStreetMap
- Weather overlay
- Time-lapse mode (replay historical tides)
- VR support
- Mobile optimization
- Deploy to cloud hosting
