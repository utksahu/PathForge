# PathForge — Algorithm Visualization Studio

PathForge is an interactive pathfinding and maze-generation studio built with Python and Pygame. It combines a tested, benchmarkable algorithm library with a visual frontend for exploring how graph-search algorithms behave on the same grid.

![PathForge demo](assets/pathforge_demo.gif)

## Highlights

- **7 pathfinding algorithms:** BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS, and Jump Point Search (JPS)
- **4 maze generators:** Recursive Backtracker, Prim's, Kruskal's, and Recursive Division
- Weighted terrain with configurable movement rules
- 4-direction and 8-direction movement, with JPS support for diagonal uniform-cost grids
- Event-driven search replay with pause/resume, single-step execution, and 0.25×–4× playback speed
- Interactive wall/terrain painting and start/goal placement
- Undo/redo map history, random maps, and live search telemetry
- Standalone correctness tests and a reproducible benchmark harness

## Architecture

The project deliberately separates the algorithm engine from the UI:

```text
pathforge/
├── app.py                       # Pygame UI, input, rendering, visualization
├── pathforge_core/
│   ├── grid.py                  # Grid representation and movement/cost rules
│   ├── algorithms.py            # 7 pathfinding algorithms + SearchResult
│   ├── maze_generation.py       # 4 maze-generation algorithms
│   └── benchmark.py             # Reproducible algorithm benchmark harness
├── tests/
│   ├── test_algorithms.py       # Search correctness and optimality tests
│   └── test_maze_generation.py  # Maze connectivity/tree-property tests
├── assets/
│   └── pathforge_demo.gif       # Short UI demonstration
├── benchmark_results.json       # Recorded benchmark output
├── requirements.txt
└── LICENSE
```

`pathforge_core/` has **no Pygame dependency**. Algorithms operate on a grid and return a common `SearchResult` containing the path, cost, expansion count, timing, and an ordered event trace. `app.py` consumes that trace to animate the search without embedding algorithm logic in the UI.

## Algorithms

### Pathfinding

| Algorithm | Optimality | Weighted terrain | Diagonal movement |
|---|---|---|---|
| BFS | Yes, unweighted | No | Supported |
| DFS | No | No | Supported |
| Dijkstra | Yes | Yes | Supported |
| A* | Yes, with admissible heuristic | Yes | Supported |
| Greedy Best-First | No | Yes | Supported |
| Bidirectional BFS | Yes, unweighted | No | Supported |
| JPS | Yes, uniform-cost | No | Required |

### Maze generation

| Generator | Technique | Property |
|---|---|---|
| Recursive Backtracker | Randomized DFS | Spanning-tree / perfect maze |
| Prim's | Randomized frontier growth | Spanning-tree / perfect maze |
| Kruskal's | Randomized edges + union-find | Spanning-tree / perfect maze |
| Recursive Division | Recursive wall placement | Fully connected, may contain loops |

## Correctness

The core is tested independently from the Pygame UI.

```bash
pytest -q
```

Current test suite result:

```text
83 passed, 7 skipped
```

The suite covers randomized optimality cross-checks, JPS vs A* path-cost agreement, weighted-terrain behavior, unreachable goals, path validity, maze connectivity, spanning-tree properties, deterministic seeds, and different-seed variation.

The skipped cases are intentionally degenerate random-board cases where generated obstacles can invalidate the intended test setup (for example, a wall landing directly on an endpoint).

## Benchmarking

Run the standalone benchmark harness:

```bash
python -m pathforge_core.benchmark
```

The harness compares algorithms on reproducible boards using nodes expanded, wall-clock time, path cost, and success rate. Results are also stored in `benchmark_results.json`.

One useful result from the included benchmark is that JPS expands substantially fewer nodes than A* on open diagonal boards, while taking longer in this Python implementation because recursive scan-ahead overhead dominates at the tested board size. This is intentionally reported rather than hiding an unfavorable metric.

## Run the visualizer

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd pathforge
```

### 2. Create an environment (recommended)

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Launch

```bash
python app.py
```

## Controls

| Control | Action |
|---|---|
| Left click / drag | Paint selected mode |
| Right click / drag | Erase |
| Space | Run / pause |
| R | Reset search visualization |
| Mouse wheel | Adjust playback speed |
| STEP | Advance one recorded search event |

JPS requires diagonal movement and uniform-cost terrain.

## Design notes

### Event-driven visualization

The core algorithms do not draw anything. They record ordered `visit` and `frontier` events while solving. The UI replays those events at a user-controlled rate. This keeps visualization concerns out of the algorithm implementation and makes the core straightforward to test and benchmark.

### Weighted terrain

Dijkstra, A*, and Greedy Best-First use terrain costs. BFS and DFS intentionally treat the grid as unweighted because their search guarantees are defined around edge count rather than weighted path cost.

### Maze verification

The maze tests validate graph properties rather than only checking that a maze "looks right." The perfect-maze generators are checked for connectivity and exactly `rooms - 1` passages; Recursive Division is checked for full connectivity.

## License

MIT
