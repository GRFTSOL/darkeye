# ForceView — C++ Force-Directed Graph

C++ implementation of the force-directed graph simulation and rendering engine, exposed to Python via Shiboken6 as `PyForceView`.

## Architecture

- **PhysicsState**: Flat arrays (pos, vel, mass, dragging, edges)
- **Forces**: CenterForce, LinkForce, ManyBodyForce (block-tiled O(N²))
- **Simulation**: Tick loop with alpha cooling, velocity integration
- **NodeLayer**: QGraphicsObject — edge/node/text rendering, hover animation, mouse interaction
- **ForceView**: QGraphicsView — owns Simulation + NodeLayer, driven by QTimer (no IPC, no child process)

## Prerequisites

- Qt 6 (Desktop, MSVC 2022 64-bit)
- CMake 3.26+
- C++17 compiler
- Python 3 + PySide6 + shiboken6-generator (for bindings)

## Build

```powershell
# Configure
cmake -B build

# Build (Release)
cmake --build build --config Release

# Install (copies .dll/.pyd to source dir for Python import)
cmake --install build --config Release
```

## Test (standalone)

```powershell
build\Release\forceview_test.exe
```

## Python Usage

```python
from PyForceView import ForceView

view = ForceView()
view.setGraph(n_nodes, edges_flat, pos_flat, labels, radii)
view.nodeLeftClicked.connect(lambda idx: print(f"Clicked {idx}"))
view.show()
```

## File Layout

```
├── CMakeLists.txt          — Build config (lib + test exe + Shiboken binding)
├── bindings.h / .xml       — Shiboken typesystem (exposes ForceView)
├── include/
│   ├── PhysicsState.h      — Flat arrays for physics state
│   ├── Forces.h            — Force base + CenterForce/LinkForce/ManyBodyForce
│   ├── Simulation.h        — Simulation engine
│   ├── NodeLayer.h         — QGraphicsObject renderer
│   └── ForceView.h         — QGraphicsView (public API)
└── src/
    ├── main.cpp            — Standalone test
    ├── Forces.cpp
    ├── Simulation.cpp
    ├── NodeLayer.cpp
    └── ForceView.cpp
```
