#include "ForceView.h"

#include <QWheelEvent>
#include <QResizeEvent>
#include <QCloseEvent>
#include <QScrollBar>
#include <QPainter>
#include <QDebug>

#include <cmath>
#include <chrono>
#include <algorithm>
#include <thread>

static double nowSec()
{
    using clock = std::chrono::high_resolution_clock;
    return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

// =====================================================================
// Construction / Destruction
// =====================================================================

ForceView::ForceView(QWidget* parent)
    : QGraphicsView(parent)
{
    setBackgroundBrush(QColor("#FFFFFF"));
    setRenderHint(QPainter::Antialiasing, true);
    setRenderHint(QPainter::TextAntialiasing, true);
    setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setDragMode(QGraphicsView::ScrollHandDrag);
    setTransformationAnchor(QGraphicsView::AnchorUnderMouse);

    m_scene = new QGraphicsScene(this);
    setScene(m_scene);
    m_scene->setSceneRect(-5000, -5000, 10000, 10000);

    setupTimers();
}

ForceView::~ForceView()
{
    stopSimThread();
    m_simTimer->stop();
    m_renderTimer->stop();
    m_idleTimer->stop();
}

// =====================================================================
// Timers
// =====================================================================

void ForceView::setupTimers()
{
    m_simTimer = new QTimer(this);//每16ms模拟一次
    m_simTimer->setInterval(16);
    connect(m_simTimer, &QTimer::timeout, this, &ForceView::onSimTick);

    m_renderTimer = new QTimer(this);//每16ms渲染一次
    m_renderTimer->setInterval(16);
    connect(m_renderTimer, &QTimer::timeout, this, &ForceView::onRenderTick);

    m_idleTimer = new QTimer(this);
    m_idleTimer->setSingleShot(true);
    m_idleTimer->setInterval(1000);
    connect(m_idleTimer, &QTimer::timeout, this, &ForceView::maybeStopRenderTimer);
}

void ForceView::ensureRenderTimerRunning()
{
    if (!m_renderActive) {
        m_renderTimer->start();
        m_renderActive = true;
    }
}

void ForceView::requestRenderActivity()
{
    ensureRenderTimerRunning();
    m_idleTimer->start();  // reset idle countdown
}

void ForceView::startSimThread()
{
    if (m_simThreadRunning.load(std::memory_order_acquire))
        return;
    m_simThreadRunning.store(true, std::memory_order_release);
    m_simThread = std::thread([this]() { simLoop(); });
}

void ForceView::stopSimThread()
{
    if (!m_simThreadRunning.load(std::memory_order_acquire))
        return;
    m_simThreadRunning.store(false, std::memory_order_release);
    if (m_simThread.joinable())
        m_simThread.join();
}

/*
* sim循环，前200次预热不限速，后面每16ms tick一次
*/
void ForceView::simLoop()
{
    bool lastActive = false;
    bool lastWarmup = false;
    auto nextTick = std::chrono::steady_clock::now();
    const auto interval = std::chrono::milliseconds(16);
    const int warmupTicks = 200;
    while (m_simThreadRunning.load(std::memory_order_acquire)) {
        float elapsed = 0.0f;
        bool active = false;
        bool didTick = false;
        bool shouldSleep = false;
        std::chrono::milliseconds sleepFor(1);
        {
            std::lock_guard<std::mutex> lock(m_simMutex);
            if (m_simulation && m_physicsState && m_simulation->isActive()) {
                active = true;
                bool allowWarmup = m_allowWarmup.load(std::memory_order_acquire);
                bool warmup = allowWarmup && m_simulation->tickCount() < warmupTicks;
                if (allowWarmup && !warmup) {
                    m_allowWarmup.store(false, std::memory_order_release);
                }
                if (!lastActive || (lastWarmup && !warmup)) {
                    nextTick = std::chrono::steady_clock::now();
                }
                auto now = std::chrono::steady_clock::now();
                if (warmup || now >= nextTick) {
                    double t0 = nowSec();
                    m_simulation->tick();
                    m_physicsState->publishRenderPos();
                    elapsed = static_cast<float>((nowSec() - t0) * 1000.0);
                    active = m_simulation->isActive();
                    didTick = true;
                    //qDebug() << "sim_tick_ms" << elapsed;
                    if (!warmup) {
                        nextTick = std::chrono::steady_clock::now() + interval;
                    }
                } else {
                    shouldSleep = true;
                    sleepFor = std::chrono::duration_cast<std::chrono::milliseconds>(nextTick - now);
                    if (sleepFor > interval) {
                        sleepFor = interval;
                    }
                }
                lastWarmup = warmup;
            } else {
                lastWarmup = false;
            }
        }

        if (active) {//后续
            m_simActive.store(active, std::memory_order_release);
            if (didTick) {
                emit tickTimeUpdated(elapsed);
                if (lastActive && !active)
                    emit simulationStopped();
            }
            lastActive = active;
            if (!didTick) {
                if (shouldSleep) {
                    std::this_thread::sleep_for(sleepFor);
                } else {
                    std::this_thread::sleep_for(std::chrono::milliseconds(1));
                }
            }
        } else {
            if (lastActive) {
                lastActive = false;
                m_simActive.store(false, std::memory_order_release);
                emit simulationStopped();
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }
}

// =====================================================================
// setGraph — main entry point from Python
// =====================================================================

void ForceView::setGraph(int nNodes,
                         const QVector<int>&   edges,
                         const QVector<float>& pos,
                         const QStringList&    id,
                         const QStringList&    labels,
                         const QVector<float>& radii,
                         const QVector<QColor>& nodeColors)
{
    // Stop existing simulation
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation)
            m_simulation->stop();
    }
    m_simTimer->stop();

    // ---- Build PhysicsState ----
    m_physicsState = std::make_unique<PhysicsState>();
    std::vector<int> edgeVec(edges.begin(), edges.end());
    m_physicsState->init(nNodes, edgeVec);

    // Copy initial positions
    for (int i = 0; i < std::min((int)pos.size(), 2 * nNodes); ++i)
        m_physicsState->pos[i] = pos[i];
    m_physicsState->syncRenderPosFromPos();
    m_physicsState->syncDragPosFromPos();

    // ---- Node ids and id→index map ----

    m_ids = id;



    // ---- Build neighbor adjacency ----
    m_neighbors.assign(nNodes, {});
    int E = static_cast<int>(edgeVec.size()) / 2;
    for (int e = 0; e < E; ++e) {
        int s = edgeVec[2 * e];
        int d = edgeVec[2 * e + 1];
        if (s >= 0 && s < nNodes && d >= 0 && d < nNodes) {
            m_neighbors[s].push_back(d);
            m_neighbors[d].push_back(s);
        }
    }

    // ---- Create / Reset NodeLayer ----
    if (m_nodeLayer == nullptr) {
        m_nodeLayer = new NodeLayer(m_physicsState.get(), radii, labels, m_neighbors, m_ids, nodeColors);
        m_scene->addItem(m_nodeLayer);
        connectNodeLayer();
    } else {
        m_nodeLayer->reset(m_physicsState.get(), radii, labels, m_neighbors, m_ids, nodeColors);
        m_nodeLayer->updateVisibleMask();
    }

    // ---- Create Simulation ----
    m_allowWarmup.store(true, std::memory_order_release);
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    startSimThread();
    requestRenderActivity();

    // Auto-fit after short delay
    QTimer::singleShot(100, this, [this]() {
        fitInView(getContentRect(), Qt::KeepAspectRatio);
    });
}

// =====================================================================
// Simulation rebuild (create forces from current params)
// =====================================================================

void ForceView::rebuildSimulation()
{
    m_simulation = std::make_unique<Simulation>(m_physicsState.get());

    auto many = std::make_unique<ManyBodyForce>(m_manyBodyStrength, 40000.0f);
    m_simulation->addForce("manybody", std::move(many));

    auto link = std::make_unique<LinkForce>(m_linkStrength, m_linkDistance);
    m_simulation->addForce("link", std::move(link));

    auto center = std::make_unique<CenterForce>(0.0f, 0.0f, m_centerStrength);
    m_simulation->addForce("center", std::move(center));

    auto collision = std::make_unique<CollisionForce>(m_collisionRadius, m_collisionStrength);
    m_simulation->addForce("collision", std::move(collision));
}

// =====================================================================
// Timer slots
// =====================================================================

void ForceView::onSimTick()
{
    if (!m_simulation || !m_simulation->isActive())
        return;

    double t0 = nowSec();
    m_simulation->tick();
    float elapsed = static_cast<float>((nowSec() - t0) * 1000.0);
    //qDebug() << "sim_tick_ms" << elapsed;

    bool active = m_simulation->isActive();
    m_simActive = active;

    if (m_nodeLayer)
        m_nodeLayer->updateVisibleMask();

    emit tickTimeUpdated(elapsed);

    if (active)
        requestRenderActivity();

    if (!active) {
        emit simulationStopped();
    }
}

void ForceView::onRenderTick()
{
    double t0 = nowSec();
    if (m_nodeLayer) {
        m_nodeLayer->updateVisibleMask();
        m_nodeLayer->advanceHover();
        m_nodeLayer->update();
    }
    float elapsed = static_cast<float>((nowSec() - t0) * 1000.0);
    //qDebug() << "paint_tick_ms" << elapsed;
}

void ForceView::maybeStopRenderTimer()
{
    if (!m_simActive
        && m_nodeLayer
        && !m_nodeLayer->isDragging()
        && m_nodeLayer->hoverIndex() == -1)
    {
        m_renderTimer->stop();
        m_renderActive = false;
    }
}

// =====================================================================
// Simulation Control
// =====================================================================

void ForceView::pauseSimulation()
{
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) m_simulation->pause();
    }
    m_simActive.store(false, std::memory_order_release);
    emit simulationStopped();
}

void ForceView::resumeSimulation()
{
    bool active = false;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            m_simulation->resume();
            active = m_simulation->isActive();
        }
    }
    m_simActive.store(active, std::memory_order_release);
    if (active) {
        requestRenderActivity();
        emit simulationStarted();
    }
}

void ForceView::restartSimulation()
{
    m_allowWarmup.store(false, std::memory_order_release);
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            m_simulation->restart();
        }
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
    emit simulationStarted();
}

// =====================================================================
// Force Parameters
// =====================================================================

void ForceView::setManyBodyStrength(float value)
{
    m_manyBodyStrength = value;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            auto* f = dynamic_cast<ManyBodyForce*>(m_simulation->getForce("manybody"));
            if (f) f->setStrength(value);
        }
    }
    restartSimulation();
}

void ForceView::setCenterStrength(float value)
{
    m_centerStrength = value;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            auto* f = dynamic_cast<CenterForce*>(m_simulation->getForce("center"));
            if (f) f->setStrength(value);
        }
    }
    restartSimulation();
}

void ForceView::setLinkStrength(float value)
{
    m_linkStrength = value;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            auto* f = dynamic_cast<LinkForce*>(m_simulation->getForce("link"));
            if (f) f->setK(value);
        }
    }
    restartSimulation();
}

void ForceView::setLinkDistance(float value)
{
    m_linkDistance = value;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            auto* f = dynamic_cast<LinkForce*>(m_simulation->getForce("link"));
            if (f) f->setDistance(value);
        }
    }
    restartSimulation();
}

void ForceView::setCollisionRadius(float value)
{
    m_collisionRadius = value;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            auto* f = dynamic_cast<CollisionForce*>(m_simulation->getForce("collision"));
            if (f) f->setRadius(value);
        }
    }
    restartSimulation();
}

void ForceView::setCollisionStrength(float value)
{
    m_collisionStrength = value;
    {
        std::lock_guard<std::mutex> lock(m_simMutex);
        if (m_simulation) {
            auto* f = dynamic_cast<CollisionForce*>(m_simulation->getForce("collision"));
            if (f) f->setStrength(value);
        }
    }
    restartSimulation();
}

// =====================================================================
// Visual Parameters
// =====================================================================

void ForceView::setRadiusFactor(float f)
{
    if (m_nodeLayer) {
        m_nodeLayer->setRadiusFactor(f);
        m_nodeLayer->update();
    }
}

void ForceView::setSideWidthFactor(float f)
{
    if (m_nodeLayer) {
        m_nodeLayer->setSideWidthFactor(f);
        m_nodeLayer->update();
    }
}

void ForceView::setTextThresholdFactor(float f)
{
    if (m_nodeLayer) {
        m_nodeLayer->setTextThresholdFactor(f);
        m_nodeLayer->update();
    }
}

// =====================================================================
// Misc
// =====================================================================

void ForceView::setDragging(int nodeId, bool dragging)
{
    int index = nodeId;
    if (m_physicsState && index >= 0 && index < m_physicsState->nNodes) {
        m_physicsState->dragging[index] = dragging ? 1 : 0;
        if (dragging) {
            const float* pos = m_physicsState->renderPosData();
            m_physicsState->setDragPos(index, pos[2 * index], pos[2 * index + 1]);
        }
        if (dragging)
            restartSimulation();
    }
}

QRectF ForceView::getContentRect() const
{
    if (!m_physicsState || m_physicsState->nNodes == 0)
        return QRectF();

    const float* pos = m_physicsState->renderPosData();
    int N = m_physicsState->nNodes;

    float minX = pos[0], maxX = pos[0];
    float minY = pos[1], maxY = pos[1];
    for (int i = 1; i < N; ++i) {
        float x = pos[2 * i], y = pos[2 * i + 1];
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
    }

    float w = maxX - minX;
    float h = maxY - minY;
    float mx = w * 0.1f;
    float my = h * 0.1f;
    return QRectF(minX - mx, minY - my, w + 2 * mx, h + 2 * my);
}

// =====================================================================
// NodeLayer signal forwarding
// =====================================================================

void ForceView::connectNodeLayer()
{
    connect(m_nodeLayer, &NodeLayer::nodePressed,      this, &ForceView::onNodePressed);
    connect(m_nodeLayer, &NodeLayer::nodeDragged,      this, &ForceView::onNodeDragged);
    connect(m_nodeLayer, &NodeLayer::nodeReleased,     this, &ForceView::onNodeReleased);
    connect(m_nodeLayer, &NodeLayer::nodeLeftClicked,   this, &ForceView::onNodeLeftClicked);
    connect(m_nodeLayer, &NodeLayer::nodeRightClicked,  this, &ForceView::onNodeRightClicked);
    connect(m_nodeLayer, &NodeLayer::nodeHovered,       this, &ForceView::onNodeHovered);
    connect(m_nodeLayer, &NodeLayer::paintTimeReady,    this, &ForceView::paintTimeUpdated);
    connect(m_nodeLayer, &NodeLayer::fpsReady,          this, &ForceView::fpsUpdated);
}

void ForceView::onNodePressed(const QString& nodeId)
{
    emit nodePressed(nodeId);
}

void ForceView::onNodeDragged(const QString& nodeId)
{
    //setDragging(nodeId, true);
    requestRenderActivity();
    emit nodePressed(nodeId);  // keep consistent with Python
}

void ForceView::onNodeReleased(const QString& nodeId)
{
    //setDragging(nodeId, false);
    emit nodeReleased(nodeId);
}

void ForceView::onNodeLeftClicked(const QString& nodeId)
{
    emit nodeLeftClicked(nodeId);
}

void ForceView::onNodeRightClicked(const QString& nodeId)
{
    emit nodeRightClicked(nodeId);
}

void ForceView::onNodeHovered(const QString& nodeId)
{
    requestRenderActivity();
    emit nodeHovered(nodeId);
}

// =====================================================================
// View events
// =====================================================================

void ForceView::wheelEvent(QWheelEvent* event)
{
    setTransformationAnchor(QGraphicsView::AnchorUnderMouse);

    bool zoomIn = event->angleDelta().y() > 0;
    float factor = zoomIn ? 1.15f : 1.0f / 1.15f;

    float currentScale = static_cast<float>(transform().m11());
    float newScale = currentScale * factor;

    if (newScale > 0.1f && newScale < 10.0f) {
        scale(factor, factor);
        m_scaleFactor = newScale;
        emit scaleChanged(newScale);
    }
    event->accept();
}

void ForceView::resizeEvent(QResizeEvent* event)
{
    if (m_renderActive && m_nodeLayer)
        m_nodeLayer->updateVisibleMask();
    QGraphicsView::resizeEvent(event);
}

void ForceView::scrollContentsBy(int dx, int dy)
{
    QGraphicsView::scrollContentsBy(dx, dy);
    if (m_nodeLayer)
        m_nodeLayer->updateVisibleMask();
}

void ForceView::closeEvent(QCloseEvent* event)
{
    stopSimThread();
    m_simTimer->stop();
    m_renderTimer->stop();
    m_idleTimer->stop();
    QGraphicsView::closeEvent(event);
}
