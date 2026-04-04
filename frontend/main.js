/**
 * tidl-3d: 3D Coastal Flyover Visualization
 * Main entry point - Three.js rendering
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ============================================================================
// State
// ============================================================================

const state = {
    currentStationId: null,
    isPlaying: true,
    terrainData: null,
    clock: new THREE.Clock(),
    orbitAngle: 0,
};

// ============================================================================
// Three.js Setup
// ============================================================================

const canvas = document.getElementById('canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x1a1a2e);  // Dark purple-grey dev background

const scene = new THREE.Scene();
// Disable fog for development - makes it easier to see terrain
// scene.fog = new THREE.Fog(0x1a1a2e, 1500, 4000);

const camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    1,
    5000
);
camera.position.set(600, 400, 600);
camera.lookAt(0, 0, 0);

// Orbit controls for manual interaction
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.maxPolarAngle = Math.PI / 2.1; // Prevent going below ground
controls.minDistance = 100;
controls.maxDistance = 2000;

// ============================================================================
// Lighting
// ============================================================================

const ambientLight = new THREE.AmbientLight(0x404060, 0.5);
scene.add(ambientLight);

const sunLight = new THREE.DirectionalLight(0xffffee, 1.0);
sunLight.position.set(200, 500, 300);
sunLight.castShadow = false;
scene.add(sunLight);

const hemisphereLight = new THREE.HemisphereLight(0x87ceeb, 0x3d5c5c, 0.4);
scene.add(hemisphereLight);

// ============================================================================
// Development Helpers
// ============================================================================

// Grid helper for visual reference (size=4000 to match terrain, divisions=40)
const gridHelper = new THREE.GridHelper(4000, 40, 0x444466, 0x333344);
gridHelper.position.y = -5; // Slightly below sea level
scene.add(gridHelper);

// Axes helper (R=X, G=Y, B=Z)
const axesHelper = new THREE.AxesHelper(500);
scene.add(axesHelper);

// ============================================================================
// Terrain & Water Meshes
// ============================================================================

let terrainMesh = null;
let waterMesh = null;

function createTerrainMesh(terrainData) {
    // Remove existing terrain
    if (terrainMesh) {
        scene.remove(terrainMesh);
        terrainMesh.geometry.dispose();
        terrainMesh.material.dispose();
    }

    const geometry = new THREE.BufferGeometry();
    
    const vertices = new Float32Array(terrainData.terrain.vertices);
    const normals = new Float32Array(terrainData.terrain.normals);
    const indices = new Uint32Array(terrainData.terrain.indices);
    const uvs = new Float32Array(terrainData.terrain.uvs);

    geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
    geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    geometry.setIndex(new THREE.BufferAttribute(indices, 1));

    // Generate vertex colors based on elevation (Y component)
    // Water level is 0, so below 0 = water, above 0 = land
    const colors = new Float32Array(vertices.length);
    const [elevMin, elevMax] = terrainData.metadata.elevation_range;
    
    for (let i = 0; i < vertices.length; i += 3) {
        const elevation = vertices[i + 1]; // Y is elevation
        
        if (elevation < 0) {
            // Underwater - blue tones (deeper = darker blue)
            const depth = Math.min(1, Math.abs(elevation) / Math.abs(elevMin || 1));
            colors[i] = 0.1 - depth * 0.05;      // R
            colors[i + 1] = 0.3 + depth * 0.2;   // G
            colors[i + 2] = 0.6 + depth * 0.3;   // B
        } else if (elevation < 2) {
            // Beach/marsh - sandy tan
            colors[i] = 0.76;     // R
            colors[i + 1] = 0.70; // G
            colors[i + 2] = 0.50; // B
        } else if (elevation < 20) {
            // Low land - green
            const t = (elevation - 2) / 18;
            colors[i] = 0.2 + t * 0.1;      // R
            colors[i + 1] = 0.5 + t * 0.1;  // G
            colors[i + 2] = 0.2;            // B
        } else {
            // Higher elevation - brown/grey
            const t = Math.min(1, (elevation - 20) / 80);
            colors[i] = 0.4 + t * 0.3;      // R
            colors[i + 1] = 0.35 + t * 0.3; // G
            colors[i + 2] = 0.25 + t * 0.4; // B
        }
    }
    
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Recompute normals for proper lighting
    geometry.computeVertexNormals();

    // Material with elevation-based vertex coloring
    const material = new THREE.MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.8,
        metalness: 0.1,
        flatShading: false,
    });

    terrainMesh = new THREE.Mesh(geometry, material);
    scene.add(terrainMesh);
}

function createWaterMesh(waterData) {
    // Remove existing water
    if (waterMesh) {
        scene.remove(waterMesh);
        waterMesh.geometry.dispose();
        waterMesh.material.dispose();
    }

    const geometry = new THREE.BufferGeometry();
    
    const vertices = new Float32Array(waterData.vertices);
    const indices = new Uint32Array(waterData.indices);

    geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    geometry.setIndex(new THREE.BufferAttribute(indices, 1));
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
        color: 0x1e90ff,
        roughness: 0.1,
        metalness: 0.3,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
    });

    waterMesh = new THREE.Mesh(geometry, material);
    waterMesh.position.y = waterData.base_level;
    scene.add(waterMesh);
}

// ============================================================================
// Camera Animation
// ============================================================================

function updateCameraOrbit(deltaTime) {
    if (!state.isPlaying || !state.terrainData) return;

    const path = state.terrainData.camera_path;
    const speed = (2 * Math.PI) / path.duration_seconds;
    
    state.orbitAngle += speed * deltaTime;
    if (state.orbitAngle > 2 * Math.PI) {
        state.orbitAngle -= 2 * Math.PI;
    }

    const x = path.center[0] + path.radius * Math.cos(state.orbitAngle);
    const z = path.center[2] + path.radius * Math.sin(state.orbitAngle);
    const y = path.center[1] + path.height;

    camera.position.set(x, y, z);
    camera.lookAt(path.center[0], path.center[1], path.center[2]);
}

// ============================================================================
// Water Animation
// ============================================================================

function updateWater(time) {
    if (!waterMesh) return;

    // Subtle wave animation
    const baseLevel = state.terrainData?.water.base_level ?? 0;
    waterMesh.position.y = baseLevel + Math.sin(time * 0.5) * 0.5;
}

// ============================================================================
// API Calls
// ============================================================================

async function fetchStations() {
    const response = await fetch('/api/stations');
    const data = await response.json();
    return data.stations;
}

async function fetchTerrain(stationId) {
    const response = await fetch(`/api/terrain/${stationId}`);
    const data = await response.json();
    return data;
}

// ============================================================================
// UI Updates
// ============================================================================

async function populateStationSelect() {
    const select = document.getElementById('station-select');
    const stations = await fetchStations();
    
    select.innerHTML = stations.map(s => 
        `<option value="${s.id}">${s.name}</option>`
    ).join('');
    
    // Load first station
    if (stations.length > 0) {
        await loadStation(stations[0].id);
    }
}

async function loadStation(stationId) {
    const status = document.getElementById('status');
    status.textContent = 'Loading terrain...';
    
    try {
        state.terrainData = await fetchTerrain(stationId);
        state.currentStationId = stationId;
        
        createTerrainMesh(state.terrainData);
        // Water is now shown via vertex colors on terrain, not a separate mesh
        // createWaterMesh(state.terrainData.water);
        
    controls.target.set(
        state.terrainData.camera_path.center[0],
        state.terrainData.camera_path.center[1],
        state.terrainData.camera_path.center[2]
    );
    controls.update();
        
        status.textContent = `${state.terrainData.metadata.vertex_count.toLocaleString()} vertices`;
    } catch (error) {
        console.error('Failed to load terrain:', error);
        status.textContent = 'Error loading terrain';
    }
}

function setupEventListeners() {
    // Station select
    const select = document.getElementById('station-select');
    select.addEventListener('change', (e) => {
        if (e.target.value) {
            loadStation(e.target.value);
        }
    });
    
    // Play/Pause button
    const playPause = document.getElementById('play-pause');
    playPause.addEventListener('click', () => {
        state.isPlaying = !state.isPlaying;
        playPause.textContent = state.isPlaying ? 'Pause' : 'Play';
        
        // Enable/disable orbit controls based on play state
        controls.enabled = !state.isPlaying;
    });
    
    // Window resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}

// ============================================================================
// Animation Loop
// ============================================================================

function animate() {
    requestAnimationFrame(animate);
    
    const deltaTime = state.clock.getDelta();
    const elapsedTime = state.clock.getElapsedTime();
    
    updateCameraOrbit(deltaTime);
    // updateWater(elapsedTime); // Water now shown via terrain vertex colors
    
    if (!state.isPlaying) {
        controls.update();
    }
    
    renderer.render(scene, camera);
}

// ============================================================================
// Initialization
// ============================================================================

// For easy debugging from the console
window.state = state;
window.THREE = THREE;
window.scene = scene;
window.camera = camera;
window.renderer = renderer;
window.controls = controls;

async function init() {
    setupEventListeners();
    await populateStationSelect();
    animate();
}

init().catch(console.error);
