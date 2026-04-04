# tidl-3d

3D coastal flyover visualization with real tides and terrain.

## Quick Start

```bash
# Install dependencies
cd backend
uv sync

# Run development server
uv run fastapi dev app/main.py

# Open browser
open http://localhost:8000
```

## Project Structure

```
tidl-3d/
├── backend/           # Python FastAPI server
│   ├── app/
│   │   ├── main.py    # API endpoints
│   │   └── models.py  # Pydantic schemas
│   └── pyproject.toml
├── frontend/          # Three.js browser app
│   ├── index.html
│   ├── main.js
│   └── style.css
└── SPECIFICATION.md   # Detailed project spec
```

## Development Phases

- [x] Phase 1: Scaffolding & proof of concept
- [ ] Phase 2: Real terrain from USGS 3DEP
- [ ] Phase 3: Tides & animated water
- [ ] Phase 4: Camera flyover paths
- [ ] Phase 5: Station picker & polish

See [SPECIFICATION.md](./SPECIFICATION.md) for full details.
