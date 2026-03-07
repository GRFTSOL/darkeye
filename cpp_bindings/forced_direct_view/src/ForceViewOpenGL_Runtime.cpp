#include "ForceViewOpenGL.h"
#include "PhysicsState.h"

#include <QVariant>
#include <QVariantMap>
#include <QVariantList>
#include <QHash>
#include <QMetaObject>
#include <QThread>

#include <chrono>
#include <random>
#include <algorithm>
#include <mutex>

namespace {

int addNodeToPhysicsState(PhysicsState& state, float x, float y)
{
    const int newIndex = state.nNodes++;
    state.pos.resize(2 * state.nNodes);
    state.vel.resize(2 * state.nNodes);
    state.mass.push_back(1.0f);
    state.dragging.push_back(0);
    state.renderPosA.resize(2 * state.nNodes);
    state.renderPosB.resize(2 * state.nNodes);
    state.dragPos.resize(2 * state.nNodes);

    state.pos[2 * newIndex] = x;
    state.pos[2 * newIndex + 1] = y;
    state.vel[2 * newIndex] = 0.0f;
    state.vel[2 * newIndex + 1] = 0.0f;
    state.renderPosA[2 * newIndex] = x;
    state.renderPosA[2 * newIndex + 1] = y;
    state.renderPosB[2 * newIndex] = x;
    state.renderPosB[2 * newIndex + 1] = y;
    state.dragPos[2 * newIndex] = x;
    state.dragPos[2 * newIndex + 1] = y;
    return newIndex;
}

bool removeNodeFromPhysicsState(PhysicsState& state, int index)
{
    if (index < 0 || index >= state.nNodes) return false;

    const int last = state.nNodes - 1;
    const bool moved = (index != last);
    if (moved) {
        state.pos[2 * index]         = state.pos[2 * last];
        state.pos[2 * index + 1]     = state.pos[2 * last + 1];
        state.vel[2 * index]         = state.vel[2 * last];
        state.vel[2 * index + 1]     = state.vel[2 * last + 1];
        state.mass[index]            = state.mass[last];
        state.dragging[index]        = state.dragging[last];
        state.renderPosA[2 * index]     = state.renderPosA[2 * last];
        state.renderPosA[2 * index + 1] = state.renderPosA[2 * last + 1];
        state.renderPosB[2 * index]     = state.renderPosB[2 * last];
        state.renderPosB[2 * index + 1] = state.renderPosB[2 * last + 1];
        state.dragPos[2 * index]     = state.dragPos[2 * last];
        state.dragPos[2 * index + 1] = state.dragPos[2 * last + 1];
    }

    state.nNodes--;
    state.pos.resize(2 * state.nNodes);
    state.vel.resize(2 * state.nNodes);
    state.mass.resize(state.nNodes);
    state.dragging.resize(state.nNodes);
    state.renderPosA.resize(2 * state.nNodes);
    state.renderPosB.resize(2 * state.nNodes);
    state.dragPos.resize(2 * state.nNodes);

    std::vector<int> newEdges;
    newEdges.reserve(state.edges.size());
    const int newN = state.nNodes;
    for (size_t i = 0; i + 1 < state.edges.size(); i += 2) {
        int u = state.edges[i];
        int v = state.edges[i + 1];

        if (u == index || v == index) continue;

        if (moved) {
            if (u == last) u = index;
            if (v == last) v = index;
        }

        if (u < 0 || v < 0 || u >= newN || v >= newN || u == v) continue;
        newEdges.push_back(u);
        newEdges.push_back(v);
    }
    state.edges.swap(newEdges);
    return true;
}

bool addEdgeToPhysicsState(PhysicsState& state, int u, int v)
{
    if (u < 0 || u >= state.nNodes || v < 0 || v >= state.nNodes || u == v) return false;

    for (size_t i = 0; i < state.edges.size(); i += 2) {
        if ((state.edges[i] == u && state.edges[i + 1] == v) ||
            (state.edges[i] == v && state.edges[i + 1] == u)) {
            return false;
        }
    }

    state.edges.push_back(u);
    state.edges.push_back(v);
    return true;
}

bool removeEdgeFromPhysicsState(PhysicsState& state, int u, int v)
{
    if (u < 0 || u >= state.nNodes || v < 0 || v >= state.nNodes) return false;

    for (size_t i = 0; i < state.edges.size(); i += 2) {
        if ((state.edges[i] == u && state.edges[i + 1] == v) ||
            (state.edges[i] == v && state.edges[i + 1] == u)) {
            state.edges.erase(state.edges.begin() + i, state.edges.begin() + i + 2);
            return true;
        }
    }

    return false;
}

} // namespace

bool ForceViewOpenGL::removeNodeInternal(int indexToRemove)
{
    const int lastNodeIndex = m_physicsState->nNodes - 1;
    if (!removeNodeFromPhysicsState(*m_physicsState, indexToRemove)) return false;

    if (indexToRemove != lastNodeIndex && lastNodeIndex >= 0 && lastNodeIndex < m_ids.size()) {
        m_ids[indexToRemove] = m_ids[lastNodeIndex];
        if (lastNodeIndex < m_labels.size()) m_labels[indexToRemove] = m_labels[lastNodeIndex];
        if (lastNodeIndex < m_showRadiiBase.size()) m_showRadiiBase[indexToRemove] = m_showRadiiBase[lastNodeIndex];
        if (lastNodeIndex < m_nodeColors.size()) m_nodeColors[indexToRemove] = m_nodeColors[lastNodeIndex];
    }
    if (lastNodeIndex >= 0 && lastNodeIndex < m_ids.size()) {
        m_ids.removeAt(lastNodeIndex);
        if (lastNodeIndex < m_labels.size()) m_labels.removeAt(lastNodeIndex);
        if (lastNodeIndex < m_showRadiiBase.size()) m_showRadiiBase.removeAt(lastNodeIndex);
        if (lastNodeIndex < m_nodeColors.size()) m_nodeColors.removeAt(lastNodeIndex);
    }
    return true;
}

void ForceViewOpenGL::add_node_runtime(const QString& nodeId, float x, float y,
                                         const QString& label, float radius,
                                         const QColor& color)
{
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, nodeId, x, y, label, radius, color]() {
            add_node_runtime(nodeId, x, y, label, radius, color);
        }, Qt::QueuedConnection);
        return;
    }

    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    for (const QString& existingId : m_ids) {
        if (existingId == nodeId) return;
    }

    addNodeToPhysicsState(*m_physicsState, x, y);

    m_ids.append(nodeId);
    m_labels.append(label.isEmpty() ? nodeId : label);
    m_showRadiiBase.append(radius);
    m_nodeColors.append(color.isValid() ? color : m_baseColor);

    m_neighbors.push_back({});

    m_neighborMask.push_back(0);
    m_lastNeighborMask.push_back(0);

    updateFactor();

    m_labelLayoutCache.clear();
    m_labelLayoutByIndex.clear();
    startMsdfAtlasBuildAsync();

    m_physicsState->syncDragPosFromPos();

    if (m_simulation) {
        m_simulation->stop();
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
}

void ForceViewOpenGL::remove_node_runtime(const QString& nodeId)
{
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, nodeId]() {
            remove_node_runtime(nodeId);
        }, Qt::QueuedConnection);
        return;
    }

    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    int indexToRemove = -1;
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == nodeId) {
            indexToRemove = i;
            break;
        }
    }

    if (indexToRemove == -1) return;

    const int oldLastIndex = m_physicsState->nNodes - 1;
    if (!removeNodeInternal(indexToRemove)) return;

    auto fixIdx = [&](int& idx) {
        if (idx == indexToRemove) idx = -1;
        else if (idx == oldLastIndex) idx = indexToRemove;
    };
    fixIdx(m_hoverIndex);
    fixIdx(m_lastHoverIndex);
    fixIdx(m_selectedIndex);

    const int newN = m_physicsState->nNodes;
    if (m_hoverIndex < 0 || m_hoverIndex >= newN) m_hoverIndex = -1;
    if (m_lastHoverIndex < 0 || m_lastHoverIndex >= newN) m_lastHoverIndex = -1;
    if (m_selectedIndex < 0 || m_selectedIndex >= newN) m_selectedIndex = -1;

    rebuildNeighborsFromEdges();
    m_neighborMask.assign(std::max(0, newN), 0);
    m_lastNeighborMask.assign(std::max(0, newN), 0);
    if (m_hoverIndex >= 0) updateNeighborMaskForHover(m_hoverIndex);

    updateFactor();

    m_labelLayoutCache.clear();
    m_labelLayoutByIndex.clear();
    startMsdfAtlasBuildAsync();

    if (m_simulation) {
        m_simulation->stop();
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
}

void ForceViewOpenGL::add_edge_runtime(const QString& uNodeId, const QString& vNodeId)
{
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, uNodeId, vNodeId]() {
            add_edge_runtime(uNodeId, vNodeId);
        }, Qt::QueuedConnection);
        return;
    }

    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    int u = -1, v = -1;
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == uNodeId) u = i;
        if (m_ids[i] == vNodeId) v = i;
        if (u >= 0 && v >= 0) break;
    }

    if (u < 0 || v < 0 || u == v) return;

    bool added = addEdgeToPhysicsState(*m_physicsState, u, v);
    if (!added) return;

    m_neighbors[u].push_back(v);
    m_neighbors[v].push_back(u);

    if (m_simulation) {
        m_simulation->stop();
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
}

void ForceViewOpenGL::remove_edge_runtime(const QString& uNodeId, const QString& vNodeId)
{
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, uNodeId, vNodeId]() {
            remove_edge_runtime(uNodeId, vNodeId);
        }, Qt::QueuedConnection);
        return;
    }

    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    int u = -1, v = -1;
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == uNodeId) u = i;
        if (m_ids[i] == vNodeId) v = i;
        if (u >= 0 && v >= 0) break;
    }

    if (u < 0 || v < 0) return;

    bool removed = removeEdgeFromPhysicsState(*m_physicsState, u, v);
    if (!removed) return;

    auto removeFromNeighbors = [&](int node, int neighbor) {
        auto& neighbors = m_neighbors[node];
        neighbors.erase(std::remove(neighbors.begin(), neighbors.end(), neighbor),
                       neighbors.end());
    };
    removeFromNeighbors(u, v);
    removeFromNeighbors(v, u);

    if (m_simulation) {
        m_simulation->stop();
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
}

void ForceViewOpenGL::apply_diff_runtime(const QVariantList& diffList)
{
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, diffList]() {
            apply_diff_runtime(diffList);
        }, Qt::QueuedConnection);
        return;
    }

    if (!m_physicsState) return;
    if (diffList.isEmpty()) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    QVector<QVariantMap> delEdges;
    QVector<QVariantMap> delNodes;
    QVector<QVariantMap> addNodes;
    QVector<QVariantMap> addEdges;
    delEdges.reserve(diffList.size());
    delNodes.reserve(diffList.size());
    addNodes.reserve(diffList.size());
    addEdges.reserve(diffList.size());

    for (const QVariant& v : diffList) {
        const QVariantMap m = v.toMap();
        const QString op = m.value(QStringLiteral("op")).toString();
        if (op == QStringLiteral("del_edge")) delEdges.push_back(m);
        else if (op == QStringLiteral("del_node")) delNodes.push_back(m);
        else if (op == QStringLiteral("add_node")) addNodes.push_back(m);
        else if (op == QStringLiteral("add_edge")) addEdges.push_back(m);
    }

    auto buildIdToIndex = [&]() {
        QHash<QString, int> map;
        map.reserve(m_ids.size());
        for (int i = 0; i < m_ids.size(); ++i) map.insert(m_ids[i], i);
        return map;
    };

    auto parseColor = [&](const QVariant& var) -> QColor {
        QColor c;
        if (var.canConvert<QColor>()) {
            c = qvariant_cast<QColor>(var);
        } else {
            const QString s = var.toString();
            if (!s.isEmpty()) c = QColor(s);
        }
        if (!c.isValid()) c = m_baseColor;
        return c;
    };

    auto getAttr = [&](const QVariantMap& m, const QString& key) -> QVariant {
        if (m.contains(key)) return m.value(key);
        const QVariantMap attr = m.value(QStringLiteral("attr")).toMap();
        return attr.value(key);
    };

    // 1) 删除边
    {
        const auto idToIndex = buildIdToIndex();
        for (const QVariantMap& m : delEdges) {
            const QString uId = m.value(QStringLiteral("u")).toString();
            const QString vId = m.value(QStringLiteral("v")).toString();
            if (uId.isEmpty() || vId.isEmpty()) continue;
            const int u = idToIndex.value(uId, -1);
            const int v = idToIndex.value(vId, -1);
            if (u < 0 || v < 0) continue;
            removeEdgeFromPhysicsState(*m_physicsState, u, v);
        }
    }

    // 2) 删除节点
    if (!delNodes.isEmpty()) {
        m_hoverIndex = -1;
        m_lastHoverIndex = -1;
        m_selectedIndex = -1;
    }
    for (const QVariantMap& m : delNodes) {
        const QString nodeId = m.value(QStringLiteral("id")).toString();
        if (nodeId.isEmpty()) continue;

        int indexToRemove = -1;
        for (int i = 0; i < m_ids.size(); ++i) {
            if (m_ids[i] == nodeId) { indexToRemove = i; break; }
        }
        if (indexToRemove < 0) continue;

        removeNodeInternal(indexToRemove);
    }

    // 3) 添加节点
    const int nodesAfterAdd = m_physicsState->nNodes + addNodes.size();
    const float addLayoutL = std::sqrt(static_cast<float>(nodesAfterAdd)) * kInitialLayoutScaleFactor + kInitialLayoutBaseOffset;
    std::mt19937 addRng(static_cast<unsigned>(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::uniform_real_distribution<float> addDist(-addLayoutL, addLayoutL);

    for (const QVariantMap& m : addNodes) {
        QString nodeId = m.value(QStringLiteral("id")).toString();
        if (nodeId.isEmpty()) nodeId = m.value(QStringLiteral("nodeId")).toString();
        if (nodeId.isEmpty()) continue;

        bool exists = false;
        for (const QString& id : m_ids) {
            if (id == nodeId) { exists = true; break; }
        }
        if (exists) continue;

        double x, y;
        if (m.contains(QStringLiteral("x")) && m.contains(QStringLiteral("y"))) {
            x = m.value(QStringLiteral("x")).toDouble();
            y = m.value(QStringLiteral("y")).toDouble();
        } else {
            x = static_cast<double>(addDist(addRng));
            y = static_cast<double>(addDist(addRng));
        }

        const QVariant labelVar = getAttr(m, QStringLiteral("label"));
        const QString label = (labelVar.isValid() && !labelVar.toString().isEmpty()) ? labelVar.toString() : nodeId;

        const QVariant radiusVar = getAttr(m, QStringLiteral("radius"));
        double radiusD = radiusVar.isValid() ? radiusVar.toDouble() : 7.0;
        if (!(radiusD > 0.0)) radiusD = 7.0;

        const QVariant colorVar = getAttr(m, QStringLiteral("color"));
        const QColor color = parseColor(colorVar);

        addNodeToPhysicsState(*m_physicsState, static_cast<float>(x), static_cast<float>(y));
        m_ids.append(nodeId);
        m_labels.append(label);
        m_showRadiiBase.append(static_cast<float>(radiusD));
        m_nodeColors.append(color);
    }

    // 4) 添加边
    {
        const auto idToIndex = buildIdToIndex();
        for (const QVariantMap& m : addEdges) {
            const QString uId = m.value(QStringLiteral("u")).toString();
            const QString vId = m.value(QStringLiteral("v")).toString();
            if (uId.isEmpty() || vId.isEmpty() || uId == vId) continue;
            const int u = idToIndex.value(uId, -1);
            const int v = idToIndex.value(vId, -1);
            if (u < 0 || v < 0) continue;
            addEdgeToPhysicsState(*m_physicsState, u, v);
        }
    }

    rebuildNeighborsFromEdges();
    const int newN = m_physicsState->nNodes;
    if (m_hoverIndex < 0 || m_hoverIndex >= newN) m_hoverIndex = -1;
    if (m_lastHoverIndex < 0 || m_lastHoverIndex >= newN) m_lastHoverIndex = -1;
    if (m_selectedIndex < 0 || m_selectedIndex >= newN) m_selectedIndex = -1;

    m_neighborMask.assign(std::max(0, newN), 0);
    m_lastNeighborMask.assign(std::max(0, newN), 0);
    if (m_hoverIndex >= 0) updateNeighborMaskForHover(m_hoverIndex);

    updateFactor();
    startMsdfAtlasBuildAsync();
    m_physicsState->syncDragPosFromPos();

    if (m_simulation) {
        m_simulation->stop();
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
}
