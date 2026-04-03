# Graph System Architecture Review and Recommendations

This document reviews the current architecture under `core/graph` and proposes a practical refactor roadmap.

## Review Scope

- Reviewed modules:
  - `core/graph/graph.py`
  - `core/graph/graph_manager.py`
  - `core/graph/graph_session.py`
  - `core/graph/graph_filter.py`
  - `core/graph/force_directed_view_widget.py`
  - `core/graph/force_view_settings_panel.py`
  - `core/graph/async_image_loader.py`
  - `core/graph/image_overlay_widget.py`
  - `core/graph/text_parser.py`
- Related tests:
  - `tests/test_text_parser.py`
- Not deep-dived in this file:
  - C++ rendering internals in `cpp_bindings/forced_direct_view` (already discussed in `docs/力导向图架构.md`)

## Current Architecture (As-Is)

1. Data construction layer
   - `graph.py` builds base graph from DB and also contains random graph/test graph and similarity graph generation logic.

2. Global graph lifecycle layer
   - `GraphManager` owns global `networkx.Graph`, async initialization, story-link augmentation, and partial update entry (`update_recent_changes`).
   - Emits `graph_diff_signal` for downstream consumers.

3. View session / projection layer
   - `GraphViewSession` holds one filter per view and materializes `sub_G`.
   - Recomputes filtered graph and emits UI diffs.

4. UI adapter layer
   - `ForceDirectedViewWidget` connects panel, session, C++ OpenGL view, node click routing, theme sync, and graph serialization (`networkx -> arrays`).

5. Overlay/media sidecar
   - `ImageOverlayWidget` + `AsyncImageLoader` provide hover image loading and following behavior.

Data flow today:

`DB -> graph.py -> GraphManager (global G) -> GraphViewSession (subgraph/diff) -> ForceDirectedViewWidget -> ForceViewOpenGL`

## Main Architecture Risks

### 1. Responsibility concentration in core classes

- `GraphManager` currently mixes multiple concerns:
  - graph build
  - graph mutation
  - threading lifecycle
  - Qt signal wiring
  - incremental patch assembly
- `ForceDirectedViewWidget` currently mixes:
  - UI composition
  - domain routing (`node click -> page jump`)
  - graph marshaling
  - test/demo behavior

Impact:

- Hard to test in isolation.
- Changes in one concern can regress unrelated behavior.
- Code ownership boundaries are unclear.

### 2. Incremental pipeline is conceptually present but practically underused

- `GraphManager.graph_diff_signal` emits incremental ops, but `GraphViewSession._on_global_diff` does a recompute of filtered graph and compares old/new subgraphs.
- `fast_calc_diff` still calls `apply_filter` again at the end to refresh state.

Impact:

- Costs drift toward full-recompute complexity as graph grows.
- Diff path and full-load path become harder to reason about and optimize.

### 3. Concurrency model is fragile

- `GraphManager` initializes in background thread and mutates shared `self.G`.
- Only part of update path is guarded by lock; read/write discipline is not unified for all graph accesses.
- `AsyncImageLoader` accesses `cache` and `loading` from UI and worker threads without explicit lock.

Impact:

- Race conditions may appear under frequent updates, fast tab switching, or overlay-heavy usage.
- Failures are timing-dependent and hard to reproduce.

### 4. Delta contract is weakly typed and inconsistent

- Multiple ad-hoc dict payload shapes.
- Op naming is not globally normalized (`remove_edge` vs `del_edge` style split across layers).
- Node type is inferred from string prefixes (`a...` and `w...`) in many places.

Impact:

- Contract drift risk between producer and consumer.
- Refactor cost remains high because behavior is encoded in conventions, not explicit schema.

### 5. Production code still carries test/demo branch logic

- Hardcoded center id in graph mode switching.
- Runtime add/remove node/edge test hooks are in UI class.
- `graph.py` mixes random/test generation and production build logic.

Impact:

- Increases accidental complexity.
- Encourages coupling between debug behavior and runtime behavior.

### 6. Scaling pressure points are explicit

- Similar graph construction in `generate_similar_graph` uses dense matrix and O(N^2) pair scanning.
- Filter application repeatedly scans all nodes/edges for subgraph materialization.

Impact:

- Performance degradation likely when data volume increases.

### 7. Testing coverage is not architecture-protective

- Current automated test in this area only covers `text_parser`.
- No contract tests for graph deltas, threading behavior, or filter correctness under mutation.

Impact:

- Hard to safely evolve architecture.

## Target Architecture (To-Be)

### 1. Clear layered responsibilities

1. `GraphRepository`
   - DB reads only, no graph mutation rules.

2. `GraphBuilder` / `GraphAugmenter`
   - Build base graph and relation augmentation from repository outputs.

3. `GraphStore`
   - Single owner of mutable graph state.
   - Thread-safe read/write API.
   - Versioned snapshots (`graph_version`).

4. `GraphProjectionService`
   - Filtered subgraph and diff generation from `(snapshot, filter_state, last_version)`.

5. `GraphViewAdapter`
   - Converts typed graph snapshot/delta to `ForceViewOpenGL` payloads.

6. UI widgets
   - Only orchestration and presentation.
   - No DB, no domain mutation logic.

### 2. Contract-first model

- Introduce typed contracts (dataclass or pydantic), for example:
  - `GraphNode`
  - `GraphEdge`
  - `GraphDelta`
  - `GraphSnapshot`
- Normalize ops globally:
  - `add_node`
  - `remove_node`
  - `add_edge`
  - `remove_edge`
  - `update_node_attrs`
  - `update_edge_attrs`
- Keep edge type explicit (`cast`, `reference`, `similarity`, etc.) instead of implicit conventions.

### 3. Versioned incremental flow

- `GraphStore` increments `version` after mutation batch.
- `GraphProjectionService` receives only new deltas since last seen version.
- Session applies filter-aware delta transform first, then falls back to full recompute only when required (filter changed, large invalidation, or contract mismatch).

## Refactor Roadmap (Pragmatic)

### Phase 0: Stabilize contracts and observability (low risk, immediate)

1. Add `core/graph/contracts.py` and unify delta op names.
2. Add timing logs around:
   - graph init
   - session projection
   - UI adapter marshaling
3. Move debug-only graph mode/test operations behind debug flag or dedicated debug module.

### Phase 1: Split data concerns from manager (medium risk)

1. Extract DB access and graph build logic from `GraphManager` into:
   - `GraphRepository`
   - `GraphBuilder`
2. Keep `GraphManager` as orchestrator only (lifecycle + signal dispatch).

### Phase 2: Introduce `GraphStore` + projection contract (medium/high gain)

1. Centralize thread-safe graph mutation and snapshot reads.
2. Make `GraphViewSession` consume typed snapshot/delta API, not raw `networkx` and free-form dicts.
3. Implement version-based projection to reduce unnecessary full recomputes.

### Phase 3: Performance-oriented improvements (high scale gain)

1. Optimize similarity graph build:
   - sparse representation
   - batch compute
   - avoid full dense O(N^2) when possible
2. Evaluate moving hot paths to C++ only after Python contract/layer cleanup is complete.

## Suggested Acceptance Metrics

- Functional:
  - No behavior regression in graph load, filter switch, node click routing, and hover overlay.

- Performance:
  - Full graph load latency: track p50/p95.
  - Filter depth change latency in ego mode: track p50/p95.
  - Incremental update latency after recent work change: track p50/p95.

- Quality:
  - Add unit tests for:
    - delta contract compatibility
    - projection correctness
    - filter correctness under graph mutation
  - Add at least one integration test for `GraphManager -> Session -> ViewAdapter` pipeline.

## Recommended Next Step

Start with Phase 0 in a small PR that only introduces typed contracts and unified op names, plus timing instrumentation. This gives immediate clarity and enables safer follow-up refactors.
