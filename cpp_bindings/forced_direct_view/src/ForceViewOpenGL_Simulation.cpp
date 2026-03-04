#include "ForceViewOpenGL.h"
#include "PhysicsState.h"
#include "Simulation.h"
#include "Forces.h"

#include <QMetaObject>
#include <QThread>
#include <QTimer>

#include <cmath>
#include <chrono>
#include <random>
#include <mutex>

// =====================================================================
// setGraph
// =====================================================================

void ForceViewOpenGL::setGraph(int nNodes,
                               const QVector<int>&   edges,
                               const QVector<float>& pos,
                               const QStringList&    id,
                               const QStringList&    labels,
                               const QVector<float>& radii,
                               const QVector<QColor>& nodeColors)
{
    // 确保在 GUI 线程执行，避免与 paintGL 竞态导致崩溃
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, nNodes, edges, pos, id, labels, radii, nodeColors]() {
            setGraph(nNodes, edges, pos, id, labels, radii, nodeColors);
        }, Qt::QueuedConnection);
        return;
    }

    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) m_simulation->stop();
    }

    m_physicsState = std::make_unique<PhysicsState>();
    std::vector<int> edgeVec(edges.begin(), edges.end());
    m_physicsState->init(nNodes, edgeVec);


    const float L = std::sqrt(static_cast<float>(nNodes)) * kInitialLayoutScaleFactor + kInitialLayoutBaseOffset;
    std::mt19937 rng(static_cast<unsigned>(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::uniform_real_distribution<float> dist(-L, L);
    for (int i = 0; i < nNodes; ++i) {
        m_physicsState->pos[2 * i]     = dist(rng);
        m_physicsState->pos[2 * i + 1] = dist(rng);
    }
    m_physicsState->syncRenderPosFromPos();
    m_physicsState->syncDragPosFromPos();

    m_ids = id;


    m_neighbors.assign(nNodes, {});
    int E = static_cast<int>(edgeVec.size()) / 2;
    for (int e = 0; e < E; ++e) {
        int s = edgeVec[2 * e], d = edgeVec[2 * e + 1];
        if (s >= 0 && s < nNodes && d >= 0 && d < nNodes) {
            m_neighbors[s].push_back(d);
            m_neighbors[d].push_back(s);
        }
    }

    m_showRadiiBase = radii;
    m_labels = labels;
    m_nodeColors = nodeColors;
    m_neighborMask.assign(nNodes, 0);
    m_lastNeighborMask.clear();
    m_hoverIndex = -1; //悬浮的节点index，pos[index]可以取到这个节点的pos，
    m_lastHoverIndex = -1;
    m_selectedIndex = -1;
    m_dragging = false;
    m_hoverGlobal = 0.0f;
    m_lastDimEdges.clear();
    m_lastHighlightEdges.clear();
    updateFactor();
    // 图变更后立即清空布局缓存，避免使用旧图的布局数据导致崩溃
    m_labelLayoutCache.clear();
    m_labelLayoutByIndex.clear();
    {
        std::lock_guard<std::mutex> lock(m_msdfAtlasMutex);
        m_msdfAtlasResultReady = false;
    }
    m_msdfAtlasBuildId++;
    // 图变更后触发一次异步 MSDF atlas 构建（若需要显示文字时会自动应用）
    startMsdfAtlasBuildAsync();

    m_allowWarmup.store(true, std::memory_order_release);
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    startSimThread();
    requestRenderActivity();

    QTimer::singleShot(kFitViewDelayMs, this, [this]() {//一定延迟后缩放，但是还是有点突兀
        fitViewToContent();
    });
}

void ForceViewOpenGL::rebuildSimulation()
{
    m_simulation = std::make_unique<Simulation>(m_physicsState.get());

    auto many = std::make_unique<ManyBodyForce>(m_manyBodyStrength, kManyBodyDistanceLimitSq);
    m_simulation->addForce("manybody", std::move(many));
    auto link = std::make_unique<LinkForce>(m_linkStrength, m_linkDistance);
    m_simulation->addForce("link", std::move(link));
    auto center = std::make_unique<CenterForce>(0.0f, 0.0f, m_centerStrength);
    m_simulation->addForce("center", std::move(center));

    auto collision = std::make_unique<CollisionForce>(m_collisionRadius, m_collisionStrength);
    m_simulation->addForce("collision", std::move(collision));
}

void ForceViewOpenGL::rebuildNeighborsFromEdges()
{
    const int N = m_physicsState ? m_physicsState->nNodes : 0;
    m_neighbors.assign(std::max(0, N), {});
    if (!m_physicsState || N <= 0) return;
    const int E = m_physicsState->edgeCount();
    const int* edges = m_physicsState->edges.data();
    for (int e = 0; e < E; ++e) {
        int s = edges[2 * e];
        int d = edges[2 * e + 1];
        if (s >= 0 && s < N && d >= 0 && d < N && s != d) {
            m_neighbors[static_cast<size_t>(s)].push_back(d);
            m_neighbors[static_cast<size_t>(d)].push_back(s);
        }
    }
}

// =====================================================================
// Simulation control & force params
// =====================================================================

void ForceViewOpenGL::pauseSimulation()
{
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) m_simulation->pause(); }
    m_simActive.store(false, std::memory_order_release);
    emit simulationStopped();
}

void ForceViewOpenGL::resumeSimulation()
{
    bool active = false;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { m_simulation->resume(); active = m_simulation->isActive(); } }
    m_simActive.store(active, std::memory_order_release);
    if (active) { requestRenderActivity(); emit simulationStarted(); }
}

void ForceViewOpenGL::restartSimulation()
{
    m_allowWarmup.store(false, std::memory_order_release);
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) m_simulation->restart(); }
    m_simActive.store(true, std::memory_order_release);
    emit alphaUpdated(1.0f);  // restart 将 alpha 置为 1.0
    requestRenderActivity();
    emit simulationStarted();
}

void ForceViewOpenGL::setManyBodyStrength(float value)
{
    m_manyBodyStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<ManyBodyForce*>(m_simulation->getForce("manybody")); if (f) f->setStrength(value); } }
    restartSimulation();
}

void ForceViewOpenGL::setCenterStrength(float value)
{
    m_centerStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<CenterForce*>(m_simulation->getForce("center")); if (f) f->setStrength(value); } }
    restartSimulation();
}

void ForceViewOpenGL::setLinkStrength(float value)
{
    m_linkStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<LinkForce*>(m_simulation->getForce("link")); if (f) f->setK(value); } }
    restartSimulation();
}

void ForceViewOpenGL::setLinkDistance(float value)
{
    m_linkDistance = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<LinkForce*>(m_simulation->getForce("link")); if (f) f->setDistance(value); } }
    restartSimulation();
}

void ForceViewOpenGL::setCollisionRadius(float value)
{
    m_collisionRadius = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<CollisionForce*>(m_simulation->getForce("collision")); if (f) f->setRadius(value); } }
    restartSimulation();
}

void ForceViewOpenGL::setCollisionStrength(float value)
{
    m_collisionStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<CollisionForce*>(m_simulation->getForce("collision")); if (f) f->setStrength(value); } }
    restartSimulation();
}

// =====================================================================
// Visual parameters
// =====================================================================

void ForceViewOpenGL::setRadiusFactor(float f)      { m_radiusFactor = f; updateFactor(); update(); }
void ForceViewOpenGL::setSideWidthFactor(float f)   { m_sideWidthFactor = f; updateFactor(); update(); }
void ForceViewOpenGL::setTextThresholdFactor(float f) { m_textThresholdFactor = f; updateFactor(); update(); }

void ForceViewOpenGL::setNodeColors(const QVector<QColor>& colors)
{
    if (!m_physicsState || colors.size() != m_physicsState->nNodes)
        return;
    m_nodeColors = colors;
    requestRenderActivity();
    update();
}

QStringList ForceViewOpenGL::getNodeIds() const
{
    return m_ids;
}

void ForceViewOpenGL::setArrowScale(float f)
{
    float clamped = std::max(0.2f, std::min(f, 5.0f));
    if (std::abs(clamped - m_arrowScale) < 1e-3f)
        return;
    m_arrowScale = clamped;
    requestRenderActivity();
    update();
}

void ForceViewOpenGL::setArrowEnabled(bool enabled)
{
    if (m_arrowEnabled == enabled)
        return;
    m_arrowEnabled = enabled;
    requestRenderActivity();
    update();
}

void ForceViewOpenGL::setEdgeColor(const QColor& c) { m_edgeColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::edgeColor() const { return m_edgeColor; }
void ForceViewOpenGL::setEdgeDimColor(const QColor& c) { m_edgeDimColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::edgeDimColor() const { return m_edgeDimColor; }

void ForceViewOpenGL::setBaseColor(const QColor& c) { m_baseColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::baseColor() const { return m_baseColor; }
void ForceViewOpenGL::setDimColor(const QColor& c) { m_dimColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::dimColor() const { return m_dimColor; }
void ForceViewOpenGL::setHoverColor(const QColor& c) { m_hoverColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::hoverColor() const { return m_hoverColor; }

void ForceViewOpenGL::setTextColor(const QColor& c) { m_textColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::textColor() const { return m_textColor; }
void ForceViewOpenGL::setTextDimColor(const QColor& c) { m_textDimColor = c; requestRenderActivity(); update(); }
QColor ForceViewOpenGL::textDimColor() const { return m_textDimColor; }

// =====================================================================
// Neighbor / hover / dragging
// =====================================================================

void ForceViewOpenGL::updateNeighborMaskForHover(int hoverIndex)
{
    if (!m_physicsState || hoverIndex < 0) return;
    int N = m_physicsState->nNodes;
    m_neighborMask.assign(N, 0);
    if (hoverIndex < (int)m_neighbors.size() && N > 0) {
        std::vector<int> frontier = {hoverIndex};
        std::vector<uint8_t> visited(static_cast<size_t>(N), 0);
        visited[static_cast<size_t>(hoverIndex)] = 1;
        for (int level = 0; level < m_neighborDepth && !frontier.empty(); ++level) {
            std::vector<int> next;
            for (int u : frontier) {
                if (u < 0 || u >= (int)m_neighbors.size()) continue;
                for (int nb : m_neighbors[static_cast<size_t>(u)]) {
                    if (nb >= 0 && nb < N && !visited[static_cast<size_t>(nb)]) {
                        visited[static_cast<size_t>(nb)] = 1;
                        m_neighborMask[static_cast<size_t>(nb)] = 1;
                        next.push_back(nb);
                    }
                }
            }
            frontier = std::move(next);
        }
        m_neighborMask[static_cast<size_t>(hoverIndex)] = 0;
    }
    m_lastNeighborMask = m_neighborMask;
}

void ForceViewOpenGL::setNeighborDepth(int depth)
{
    int d = qBound(1, depth, 5);
    if (d != m_neighborDepth) {
        m_neighborDepth = d;
        if (m_hoverIndex >= 0) {
            updateNeighborMaskForHover(m_hoverIndex);
            requestRenderActivity();
        }
    }
}

void ForceViewOpenGL::setDragging(int index, bool dragging)
{
    if (m_physicsState && index >= 0 && index < m_physicsState->nNodes) {
        m_physicsState->dragging[index] = dragging ? 1 : 0;
        if (dragging) { const float* pos = m_physicsState->renderPosData(); m_physicsState->setDragPos(index, pos[2*index], pos[2*index+1]); }
        if (dragging) restartSimulation();
    }
}
