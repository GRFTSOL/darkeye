#include "ForceViewOpenGL.h"
#include "GraphRenderer.h"

#include <QWheelEvent>
#include <QMouseEvent>
#include <QEnterEvent>
#include <QPainter>
#include <QOpenGLPaintDevice>
#include <QSurfaceFormat>
#include <QTransform>
#include <QVariantMap>
#include <QHash>

#include <cmath>
#include <chrono>
#include <algorithm>
#include <thread>
#include <limits>
#include <random>

/*
* opengl shader加速
* 抗锯齿方案，圆形，线条
* 视口剔除
* LOD
* 文字优化方案SDF/MSDF 方案
*/



// 功能：获取当前时间（秒），用于统计渲染/仿真耗时与 FPS 计算
static double nowSec()
{
    using clock = std::chrono::high_resolution_clock;
    return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

// 功能：构建 2D 正交投影矩阵，将场景坐标映射到 NDC
//OpenGL 裁剪空间范围是 [-1,1]
//这两行把世界坐标的宽高缩放到 [-1,1]
//z 是固定的 -1（2D，不管深度）
//返回4*4的变换矩阵
static void ortho2D(float left, float right, float bottom, float top, float* m)
{
    for (int i = 0; i < 16; ++i) m[i] = 0.0f;
    m[0]  = 2.0f / (right - left);
    m[5]  = 2.0f / (top - bottom);
    m[10] = -1.0f;
    m[12] = -(right + left) / (right - left);//x平移
    m[13] = -(top + bottom) / (top - bottom);//y平移
    m[14] = 0.0f;//z平移
    m[15] = 1.0f;
}

// =====================================================================
// Construction / Destruction
// =====================================================================

// 功能：构造 OpenGL 视图组件，配置表面格式、尺寸与交互
ForceViewOpenGL::ForceViewOpenGL(QWidget* parent)
    : QOpenGLWidget(parent)
{
    QSurfaceFormat fmt;
    fmt.setVersion(3, 3);
    fmt.setProfile(QSurfaceFormat::CoreProfile);
    fmt.setSamples(4);//MSAA
    setFormat(fmt);
    setMinimumSize(200, 150);
    setMouseTracking(true);
    m_fontHeight = m_fontMetrics.height();
    setupTimers();
}

// 功能：析构，清理 OpenGL 资源与线程/定时器
ForceViewOpenGL::~ForceViewOpenGL()
{
    makeCurrent();
    if (m_renderer) {
        m_renderer->cleanup();
    }
    doneCurrent();

    stopSimThread();
    if (m_renderTimer) m_renderTimer->stop();
    if (m_idleTimer) m_idleTimer->stop();
}

// =====================================================================
// Timers
// =====================================================================

// 功能：初始化渲染与空闲定时器并连接回调（仿真仅由仿真线程 simLoop 驱动）
void ForceViewOpenGL::setupTimers()
{
    m_renderTimer = new QTimer(this);
    m_renderTimer->setInterval(kRenderTimerIntervalMs);
    connect(m_renderTimer, &QTimer::timeout, this, &ForceViewOpenGL::onRenderTick);

    m_idleTimer = new QTimer(this);//当计算停止时一段时间后停止渲染
    m_idleTimer->setSingleShot(true);
    m_idleTimer->setInterval(kIdleStopDelayMs);
    connect(m_idleTimer, &QTimer::timeout, this, &ForceViewOpenGL::maybeStopRenderTimer);
}

// 功能：确保渲染定时器运行（若未运行则启动）
void ForceViewOpenGL::ensureRenderTimerRunning()
{
    if (!m_renderActive) {
        m_renderTimer->start();
        m_renderActive = true;
    }
}

// 功能：请求渲染活动（启动渲染并重置空闲计时）
void ForceViewOpenGL::requestRenderActivity()
{
    ensureRenderTimerRunning();
    m_idleTimer->start();
}

// 功能：启动仿真线程（循环执行物理 tick）
void ForceViewOpenGL::startSimThread()
{
    if (m_simThreadRunning.load(std::memory_order_acquire))
        return;
    m_simThreadRunning.store(true, std::memory_order_release);
    m_simThread = std::thread([this]() { simLoop(); });
}

// 功能：停止仿真线程并等待退出
void ForceViewOpenGL::stopSimThread()
{
    if (!m_simThreadRunning.load(std::memory_order_acquire))
        return;
    m_simThreadRunning.store(false, std::memory_order_release);
    if (m_simThread.joinable())
        m_simThread.join();
}

void ForceViewOpenGL::simLoop()
// 功能：仿真线程主循环，控制 tick 节奏、热身与休眠
{
    bool lastActive = false;
    bool lastWarmup = false;
    auto nextTick = std::chrono::steady_clock::now();
    const auto interval = std::chrono::milliseconds(kSimTickIntervalMs);
    while (m_simThreadRunning.load(std::memory_order_acquire)) {
        float elapsed = 0.0f;
        float alphaVal = 0.0f;
        bool active = false;
        bool didTick = false;
        bool shouldSleep = false;
        std::chrono::milliseconds sleepFor(1);
        {
            std::lock_guard<std::mutex> lock(m_simMutex);
            if (m_simulation && m_physicsState && m_simulation->isActive()) {
                active = true;
                // 无间隔热身次数：节点数 * 0.15 + 10
                const int warmupTicks = m_physicsState->nNodes > 0
                    ? static_cast<int>(m_physicsState->nNodes * 0.15f + 10.0f)
                    : 5;
                bool allowWarmup = m_allowWarmup.load(std::memory_order_acquire);
                bool warmup = allowWarmup && m_simulation->tickCount() < warmupTicks;
                if (allowWarmup && !warmup)
                    m_allowWarmup.store(false, std::memory_order_release);
                if (!lastActive || (lastWarmup && !warmup))
                    nextTick = std::chrono::steady_clock::now();
                auto now = std::chrono::steady_clock::now();
                if (warmup || now >= nextTick) {
                    double t0 = nowSec();
                    m_simulation->tick();
                    m_physicsState->publishRenderPos();
                    elapsed = static_cast<float>((nowSec() - t0) * 1000.0);
                    alphaVal = m_simulation->alpha();
                    active = m_simulation->isActive();
                    didTick = true;
                    if (!warmup)
                        nextTick = std::chrono::steady_clock::now() + interval;
                } else {
                    shouldSleep = true;
                    sleepFor = std::chrono::duration_cast<std::chrono::milliseconds>(nextTick - now);
                    if (sleepFor > interval) sleepFor = interval;
                }
                lastWarmup = warmup;
            } else {
                lastWarmup = false;
            }
        }
        if (active) {
            m_simActive.store(active, std::memory_order_release);
            if (didTick) {
                emit tickTimeUpdated(elapsed);
                emit alphaUpdated(alphaVal);
                if (lastActive && !active) emit simulationStopped();
            }
            lastActive = active;
            if (!didTick) {
                if (shouldSleep) std::this_thread::sleep_for(sleepFor);
                else std::this_thread::sleep_for(std::chrono::milliseconds(1));
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
// setGraph
// =====================================================================

// 功能：设置图数据（节点、边、初始位置、半径与标签），并重建仿真
void ForceViewOpenGL::setGraph(int nNodes,
                               const QVector<int>&   edges,
                               const QVector<float>& pos,
                               const QStringList&    id,
                               const QStringList&    labels,
                               const QVector<float>& radii,
                               const QVector<QColor>& nodeColors)
{
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
    initStaticTextCache();

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

// 功能：根据当前参数重建物理仿真并添加力（多体、连边、居中）
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
// Simulation control & force params (same as ForceView)
// =====================================================================

// 功能：暂停仿真
void ForceViewOpenGL::pauseSimulation()
{
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) m_simulation->pause(); }
    m_simActive.store(false, std::memory_order_release);
    emit simulationStopped();
}

// 功能：恢复仿真（如仍处于活动状态则通知开始）
void ForceViewOpenGL::resumeSimulation()
{
    bool active = false;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { m_simulation->resume(); active = m_simulation->isActive(); } }
    m_simActive.store(active, std::memory_order_release);
    if (active) { requestRenderActivity(); emit simulationStarted(); }
}

// 功能：重启仿真（关闭热身并重置状态）
void ForceViewOpenGL::restartSimulation()
{
    m_allowWarmup.store(false, std::memory_order_release);
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) m_simulation->restart(); }
    m_simActive.store(true, std::memory_order_release);
    emit alphaUpdated(1.0f);  // restart 将 alpha 置为 1.0
    requestRenderActivity();
    emit simulationStarted();
}

// 功能：设置多体力强度，并更新仿真
void ForceViewOpenGL::setManyBodyStrength(float value)
{
    m_manyBodyStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<ManyBodyForce*>(m_simulation->getForce("manybody")); if (f) f->setStrength(value); } }
    restartSimulation();
}

// 功能：设置居中力强度，并更新仿真
void ForceViewOpenGL::setCenterStrength(float value)
{
    m_centerStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<CenterForce*>(m_simulation->getForce("center")); if (f) f->setStrength(value); } }
    restartSimulation();
}

// 功能：设置连边强度（弹簧系数），并更新仿真
void ForceViewOpenGL::setLinkStrength(float value)
{
    m_linkStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<LinkForce*>(m_simulation->getForce("link")); if (f) f->setK(value); } }
    restartSimulation();
}

// 功能：设置连边目标距离，并更新仿真
void ForceViewOpenGL::setLinkDistance(float value)
{
    m_linkDistance = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<LinkForce*>(m_simulation->getForce("link")); if (f) f->setDistance(value); } }
    restartSimulation();
}

// 功能：设置碰撞力作用半径
void ForceViewOpenGL::setCollisionRadius(float value)
{
    m_collisionRadius = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<CollisionForce*>(m_simulation->getForce("collision")); if (f) f->setRadius(value); } }
    restartSimulation();
}

// 功能：设置碰撞力强度
void ForceViewOpenGL::setCollisionStrength(float value)
{
    m_collisionStrength = value;
    { std::lock_guard<std::mutex> lock(m_simMutex); if (m_simulation) { auto* f = dynamic_cast<CollisionForce*>(m_simulation->getForce("collision")); if (f) f->setStrength(value); } }
    restartSimulation();
}

// 功能：设置半径缩放因子，影响显示半径与文本阈值
void ForceViewOpenGL::setRadiusFactor(float f)      { m_radiusFactor = f; updateFactor(); update(); }
// 功能：设置边宽缩放因子
void ForceViewOpenGL::setSideWidthFactor(float f)   { m_sideWidthFactor = f; updateFactor(); update(); }
// 功能：设置文本显示阈值缩放因子
void ForceViewOpenGL::setTextThresholdFactor(float f) { m_textThresholdFactor = f; updateFactor(); update(); }

// 功能：批量更新节点颜色（不重建图，实时生效）
void ForceViewOpenGL::setNodeColors(const QVector<QColor>& colors)
{
    if (!m_physicsState || colors.size() != m_physicsState->nNodes)
        return;
    m_nodeColors = colors;
    requestRenderActivity();
    update();
}

// 功能：返回当前所有节点 ID（与 m_nodeColors 索引一一对应）
QStringList ForceViewOpenGL::getNodeIds() const
{
    return m_ids;
}

// 功能：统一缩放箭头大小（长度和宽度）
void ForceViewOpenGL::setArrowScale(float f)
{
    // 限制范围，避免 0 或过大
    float clamped = std::max(0.2f, std::min(f, 5.0f));
    if (std::abs(clamped - m_arrowScale) < 1e-3f)
        return;
    m_arrowScale = clamped;
    requestRenderActivity();
    update();
}

// 功能：设置背景颜色（OpenGL 清屏颜色）
void ForceViewOpenGL::setBackgroundColor(const QColor& color)
{
    if (!color.isValid()) return;
    m_backgroundColor = color;
    requestRenderActivity();
    update();
}

// 功能：设置是否绘制箭头
void ForceViewOpenGL::setArrowEnabled(bool enabled)
{
    if (m_arrowEnabled == enabled)
        return;
    m_arrowEnabled = enabled;
    requestRenderActivity();
    update();
}

// 功能：根据当前 hover 节点与 m_neighborDepth 用 BFS 更新邻居掩码（供 setNeighborDepth / mouseMove 共用）
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

// 功能：设置邻居深度（1-5），BFS 扩展层数
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

// 功能：设置某节点拖拽状态，并在开始拖拽时同步位置与重启仿真（nodeId 为节点下标 index）
void ForceViewOpenGL::setDragging(int index, bool dragging)
{
    if (m_physicsState && index >= 0 && index < m_physicsState->nNodes) {
        m_physicsState->dragging[index] = dragging ? 1 : 0;
        if (dragging) { const float* pos = m_physicsState->renderPosData(); m_physicsState->setDragPos(index, pos[2*index], pos[2*index+1]); }
        if (dragging) restartSimulation();
    }
}


// 功能：计算所有节点的包围矩形（带 10% 边距），用于自动缩放/居中
QRectF ForceViewOpenGL::getContentRect() const
{
    if (!m_physicsState || m_physicsState->nNodes == 0) return QRectF();
    const float* pos = m_physicsState->renderPosData();
    int N = m_physicsState->nNodes;
    float minX = pos[0], maxX = pos[0], minY = pos[1], maxY = pos[1];
    for (int i = 1; i < N; ++i) {
        float x = pos[2*i], y = pos[2*i+1];
        if (x < minX) minX = x; if (x > maxX) maxX = x;
        if (y < minY) minY = y; if (y > maxY) maxY = y;
    }
    float w = maxX - minX;
    float h = maxY - minY;
    float mx = w * kContentPaddingRatio;
    float my = h * kContentPaddingRatio;
    return QRectF(minX - mx, minY - my, w + 2*mx, h + 2*my);
}

// 功能：缩放并平移视图，使整图容纳所有节点并居中
void ForceViewOpenGL::fitViewToContent()
{
    QRectF r = getContentRect();
    if (r.isEmpty() || m_viewportW <= 0 || m_viewportH <= 0) return;
    float w = static_cast<float>(r.width());
    float h = static_cast<float>(r.height());
    if (w <= 0.0f || h <= 0.0f) return;
    float z = std::min(static_cast<float>(m_viewportW) / w, static_cast<float>(m_viewportH) / h) * kFitViewScaleMargin;
    z = std::max(kFitViewZoomMin, std::min(kFitViewZoomMax, z));
    m_zoom = z;
    m_panX = static_cast<float>(r.center().x());
    m_panY = static_cast<float>(r.center().y());
    emit scaleChanged(m_zoom);
    update();
}

// 功能：通过节点ID获取节点的当前位置
QPointF ForceViewOpenGL::getNodePosition(const QString& nodeId) const
{
    if (!m_physicsState || m_physicsState->nNodes == 0 || nodeId.isEmpty()) {
        return QPointF();
    }

    // 查找节点索引
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == nodeId) {
            // 获取当前位置
            const float* pos = m_physicsState->renderPosData();
            if (pos) {
                return QPointF(pos[2 * i], pos[2 * i + 1]);
            }
            break;
        }
    }

    return QPointF();
}

// 功能：渲染定时器回调，更新可见与悬停动画后请求刷新
void ForceViewOpenGL::onRenderTick()
{
    update();
}

// 功能：在空闲时机停止渲染定时器（仿真停止、未拖拽、无悬停）
void ForceViewOpenGL::maybeStopRenderTimer()
{
    if (!m_simActive && !m_dragging && m_hoverIndex == -1) {
        if (m_renderTimer) m_renderTimer->stop();
        m_renderActive = false;
    }
}

// =====================================================================
// updateFactor, updateVisibleMask, advanceHover, updateEdgeLineBuffers
// =====================================================================

// 功能：根据缩放因子重新计算边宽、显示半径与文本阈值
void ForceViewOpenGL::updateFactor()
{
    m_sideWidth = m_sideWidthBase * m_sideWidthFactor;
    int N = static_cast<int>(m_showRadiiBase.size());
    m_showRadii.resize(N);
    for (int i = 0; i < N; ++i)
        m_showRadii[i] = m_showRadiiBase[i] * m_radiusFactor;
    m_textThresholdOff  = m_textThresholdBase * m_textThresholdFactor;
    m_textThresholdShow = m_textThresholdOff * kTextThresholdShowMul;
}

// 功能：根据当前视口与缩放计算可见节点与边集合（做裁剪）
void ForceViewOpenGL::updateVisibleMask()
{
    const int N = m_physicsState ? m_physicsState->nNodes : 0;
    if (N == 0) {
        m_visibleIndices.clear();
        m_visibleEdges.clear();
        return;
    }

    float halfW = (m_viewportW / 2.0f) / m_zoom;
    float halfH = (m_viewportH / 2.0f) / m_zoom;
    // 可见区域裁剪使用带 padding 的边界，便于边缘附近的节点/边也被绘制
    float left   = m_panX - halfW - kViewPadding;
    float right  = m_panX + halfW + kViewPadding;
    float top    = m_panY - halfH - kViewPadding;
    float bottom = m_panY + halfH + kViewPadding;
    // m_scenePerPixel 与 m_lineHalfWidthScene 必须使用与 paintGL 中 MVP 一致的视口范围（无 padding），
    // 否则点精灵尺寸会偏小，与线端产生间隙。
    float viewW = 2.0f * halfW;
    float viewH = 2.0f * halfH;
    float scaleX = (m_viewportW > 0) ? viewW / m_viewportW : 0.0f;
    float scaleY = (m_viewportH > 0) ? viewH / m_viewportH : 0.0f;
    float scenePerPixel = 0.5f * (std::abs(scaleX) + std::abs(scaleY));
    float dpr = devicePixelRatioF();
    float scenePerDevicePixel = (dpr > 0.0f) ? (scenePerPixel / dpr) : scenePerPixel;
    m_scenePerPixel = scenePerDevicePixel;

    // 保持固定的世界坐标尺寸：圆形半径和线条宽度在世界坐标系中保持固定值
    //让缩放矩阵处理视觉效果：通过 ortho2D 矩阵和 m_zoom 参数来控制显示大小
    //float lineWidth = std::max(1.0f, m_sideWidth) / m_zoom;
    //m_lineHalfWidthScene = 0.5f * lineWidth;
    m_lineHalfWidthScene = 0.5f * m_sideWidth;

    const float* pos = m_physicsState->renderPosData();
    m_nodeMask.resize(N);
    const float* radii = m_showRadii.isEmpty() ? nullptr : m_showRadii.constData();
    for (int i = 0; i < N; ++i) {
        float x = pos[2*i], y = pos[2*i+1];
        float r = (radii && i < m_showRadii.size()) ? radii[i] : kDefaultNodeRadius;
        m_nodeMask[i] = (x + r >= left && x - r <= right && y + r >= top && y - r <= bottom) ? 1 : 0;
    }
    m_visibleIndices.clear();
    m_visibleIndices.reserve(N);
    for (int i = 0; i < N; ++i)
        if (m_nodeMask[i]) m_visibleIndices.push_back(i);

    const int E = m_physicsState->edgeCount();
    const int* edges = m_physicsState->edges.data();
    m_visibleEdges.clear();
    m_visibleEdges.reserve(E * 2);
    for (int e = 0; e < E; ++e) {
        int s = edges[2*e], d = edges[2*e+1];
        if (m_nodeMask[s] || m_nodeMask[d]) {
            m_visibleEdges.push_back(s);
            m_visibleEdges.push_back(d);
        }
    }
}

// 功能：推进悬停过渡动画参数 t（0→1），并重建边线缓冲
void ForceViewOpenGL::advanceHover()
{
    if (m_dragging) {
        m_hoverGlobal = 1.0f;
    } else {
        float target = (m_hoverIndex != -1) ? 1.0f : 0.0f;
        if (target > m_hoverGlobal)
            m_hoverGlobal = std::min(1.0f, m_hoverGlobal + m_hoverStep);
        else if (target < m_hoverGlobal)
            m_hoverGlobal = std::max(0.0f, m_hoverGlobal - m_hoverStep);
    }
    updateEdgeLineBuffers();
}

// 功能：根据悬停状态构建三类边线顶点缓冲（全部/变暗/高亮）
void ForceViewOpenGL::updateEdgeLineBuffers()
{
    const int VE = static_cast<int>(m_visibleEdges.size()) / 2;
    const float* pos = m_physicsState ? m_physicsState->renderPosData() : nullptr;
    if (VE == 0 || !pos) {
        m_lineVertsAll.clear();
        m_lineVertsDim.clear();
        m_lineVertsHighlight.clear();
        m_arrowVertsAll.clear();
        m_arrowVertsDim.clear();
        m_arrowVertsHighlight.clear();
        return;
    }

    const int* vedge = m_visibleEdges.data();
    const int hover = m_hoverIndex;
    const float t = m_hoverGlobal;
    const float* radii = m_showRadii.isEmpty() ? nullptr : m_showRadii.constData();
    const float halfWidth = std::max(0.5f, m_lineHalfWidthScene);
    const float minLen = kLineMinLength;

    // 计算四边形的四个顶点，变成两个三角形的顶点输出
    auto pushQuad = [&](std::vector<float>& out, int s, int d) {//s起点节点索引，d终点节点索引
        float x0 = pos[2*s], y0 = pos[2*s+1];
        float x1 = pos[2*d], y1 = pos[2*d+1];
        float dx = x1 - x0;
        float dy = y1 - y0;
        float len = std::sqrt(dx * dx + dy * dy);
        if (len <= minLen) return;
        float r0 = (radii && s < m_showRadii.size()) ? radii[s] : kDefaultNodeRadius;
        float r1 = (radii && d < m_showRadii.size()) ? radii[d] : kDefaultNodeRadius;
        if (len <= r0 + r1 + minLen) return;
        float dirx = dx / len;
        float diry = dy / len;
        float ax = x0 + dirx * r0;
        float ay = y0 + diry * r0;
        float bx = x1 - dirx * r1;
        float by = y1 - diry * r1;
        float sdx = bx - ax;
        float sdy = by - ay;
        float slen = std::sqrt(sdx * sdx + sdy * sdy);
        if (slen <= minLen) return;
        float nx = -sdy / slen;
        float ny = sdx / slen;
        float ox = nx * halfWidth;
        float oy = ny * halfWidth;

        // 三角形1：(+,+, across=+1) , (-,-, across=-1) , (b-, across=-1)
        out.push_back(ax + ox); out.push_back(ay + oy); out.push_back(1.0f);
        out.push_back(ax - ox); out.push_back(ay - oy); out.push_back(-1.0f);
        out.push_back(bx - ox); out.push_back(by - oy); out.push_back(-1.0f);

        // 三角形2：(+,+, +1) , (b-, -1) , (b+, +1)
        out.push_back(ax + ox); out.push_back(ay + oy); out.push_back(1.0f);
        out.push_back(bx - ox); out.push_back(by - oy); out.push_back(-1.0f);
        out.push_back(bx + ox); out.push_back(by + oy); out.push_back(1.0f);
    };

    // 计算箭头三角形，箭头从 s 指向 d，位于终点节点外侧
    auto pushArrow = [&](std::vector<float>& out, int s, int d) {
        if (!m_arrowEnabled)
            return;
        float x0 = pos[2*s], y0 = pos[2*s+1];
        float x1 = pos[2*d], y1 = pos[2*d+1];
        float dx = x1 - x0;
        float dy = y1 - y0;
        float len = std::sqrt(dx * dx + dy * dy);
        if (len <= minLen) return;

        float r0 = (radii && s < m_showRadii.size()) ? radii[s] : kDefaultNodeRadius;
        float r1 = (radii && d < m_showRadii.size()) ? radii[d] : kDefaultNodeRadius;
        if (len <= r0 + r1 + minLen) return;

        float dirx = dx / len;
        float diry = dy / len;

        // 线段端点（与 pushQuad 保持一致）
        float ax = x0 + dirx * r0;
        float ay = y0 + diry * r0;
        float bx = x1 - dirx * r1;
        float by = y1 - diry * r1;
        float sdx = bx - ax;
        float sdy = by - ay;
        float slen = std::sqrt(sdx * sdx + sdy * sdy);
        if (slen <= minLen) return;

        // 箭头长度与宽度（只受 m_arrowScale 控制，与线段长度无关）
        const float kArrowLenBase = 4.0f;   // 基准长度（世界坐标）
        const float kArrowWidthBase = 3.0f; // 基准总宽度
        float arrowLen = kArrowLenBase * m_arrowScale;
        float arrowHalfWidth = 0.5f * kArrowWidthBase * m_arrowScale;
        // 极短边上做一下裁剪，防止箭头比有效线段还长太多
        if (arrowLen > slen * 0.8f) {
            arrowLen = std::max(slen * 0.5f, minLen);
        }

        // 箭头尖端在 bx,by 处，再往后退 arrowLen 得到底边中心
        float baseCx = bx - dirx * arrowLen;
        float baseCy = by - diry * arrowLen;

        // 法线方向
        float nx = -sdy / slen;
        float ny = sdx / slen;

        float baseLx = baseCx + nx * arrowHalfWidth;
        float baseLy = baseCy + ny * arrowHalfWidth;
        float baseRx = baseCx - nx * arrowHalfWidth;
        float baseRy = baseCy - ny * arrowHalfWidth;

        // 使用较小的 across 值，让箭头主体不受线条中心渐变影响，只有边缘有少量抗锯齿
        const float across = 0.2f;

        // 三角形：tip(bx,by) -> baseL -> baseR
        out.push_back(bx);    out.push_back(by);    out.push_back(across);
        out.push_back(baseLx); out.push_back(baseLy); out.push_back(across);
        out.push_back(baseRx); out.push_back(baseRy); out.push_back(across);
    };

    if (hover == -1) {
        if (t <= 0.0f) {//无悬停，过渡结束
            m_lineVertsAll.clear();
            m_lineVertsAll.reserve(VE * 18);//每条边6顶点*3float
            m_arrowVertsAll.clear();
            if (m_arrowEnabled) {
                m_arrowVertsAll.reserve(VE * 9);//每条边3顶点*3float
            }
            for (int e = 0; e < VE; ++e) {
                int s = vedge[2*e], d = vedge[2*e+1];
                pushQuad(m_lineVertsAll, s, d);
                if (m_arrowEnabled)
                    pushArrow(m_arrowVertsAll, s, d);
            }
            m_lineVertsDim.clear();
            m_lineVertsHighlight.clear();
            m_arrowVertsDim.clear();
            m_arrowVertsHighlight.clear();
        } else {//无悬停，过渡进行中
            int nDim = static_cast<int>(m_lastDimEdges.size()) / 2;
            int nHi  = static_cast<int>(m_lastHighlightEdges.size()) / 2;
            m_lineVertsDim.clear();
            m_lineVertsDim.reserve(nDim * 18);
            m_arrowVertsDim.clear();
            if (m_arrowEnabled) {
                m_arrowVertsDim.reserve(nDim * 9);
            }
            for (int e = 0; e < nDim; ++e) {
                int s = m_lastDimEdges[2*e], d = m_lastDimEdges[2*e+1];
                pushQuad(m_lineVertsDim, s, d);
                if (m_arrowEnabled)
                    pushArrow(m_arrowVertsDim, s, d);
            }
            m_lineVertsHighlight.clear();
            m_lineVertsHighlight.reserve(nHi * 18);
            m_arrowVertsHighlight.clear();
            if (m_arrowEnabled) {
                m_arrowVertsHighlight.reserve(nHi * 9);
            }
            for (int e = 0; e < nHi; ++e) {
                int s = m_lastHighlightEdges[2*e], d = m_lastHighlightEdges[2*e+1];
                pushQuad(m_lineVertsHighlight, s, d);
                if (m_arrowEnabled)
                    pushArrow(m_arrowVertsHighlight, s, d);
            }
            m_lineVertsAll.clear();
            m_arrowVertsAll.clear();
        }
        return;
    }
    // 有悬停的情况：高亮 = 连到悬停节点的边 + 两端都是邻居的边（邻居之间的边）
    m_lastDimEdges.clear();
    m_lastHighlightEdges.clear();
    m_lastDimEdges.reserve(VE * 2);
    m_lastHighlightEdges.reserve(VE * 2);
    const size_t nmSize = m_neighborMask.size();
    for (int e = 0; e < VE; ++e) {
        int s = vedge[2*e], d = vedge[2*e+1];
        bool toHover = (s == hover || d == hover);
        bool bothNeighbors = (s != hover && d != hover
            && (size_t)s < nmSize && (size_t)d < nmSize
            && m_neighborMask[s] && m_neighborMask[d]);
        if (toHover || bothNeighbors) {
            m_lastHighlightEdges.push_back(s);
            m_lastHighlightEdges.push_back(d);
        } else {
            m_lastDimEdges.push_back(s);
            m_lastDimEdges.push_back(d);
        }
    }
    int nDim = static_cast<int>(m_lastDimEdges.size()) / 2;
    int nHi  = static_cast<int>(m_lastHighlightEdges.size()) / 2;
    m_lineVertsDim.clear();
    m_lineVertsDim.reserve(nDim * 18);
    m_arrowVertsDim.clear();
    if (m_arrowEnabled) {
        m_arrowVertsDim.reserve(nDim * 9);
    }
    for (int e = 0; e < nDim; ++e) {
        int s = m_lastDimEdges[2*e], d = m_lastDimEdges[2*e+1];
        pushQuad(m_lineVertsDim, s, d);
        if (m_arrowEnabled)
            pushArrow(m_arrowVertsDim, s, d);
    }
    m_lineVertsHighlight.clear();
    m_lineVertsHighlight.reserve(nHi * 18);
    m_arrowVertsHighlight.clear();
    if (m_arrowEnabled) {
        m_arrowVertsHighlight.reserve(nHi * 9);
    }
    for (int e = 0; e < nHi; ++e) {
        int s = m_lastHighlightEdges[2*e], d = m_lastHighlightEdges[2*e+1];
        pushQuad(m_lineVertsHighlight, s, d);
        if (m_arrowEnabled)
            pushArrow(m_arrowVertsHighlight, s, d);
    }
    m_lineVertsAll.clear();
    m_arrowVertsAll.clear();
}

// 功能：按分组生成节点实例数据（中心/悬停/基础/变暗），用于实例化渲染
void ForceViewOpenGL::buildNodeInstanceData()
{
    const float* pos = m_physicsState->renderPosData();
    const float t = m_hoverGlobal;
    const int vis = static_cast<int>(m_visibleIndices.size());

    // 根据每个节点的自定义颜色（如未提供则使用基础颜色）
    auto nodeColorFor = [this](int i) -> QColor {
        if (i >= 0 && i < m_nodeColors.size())
            return m_nodeColors[i];
        return m_baseColor;
    };

    m_groupBase.clear();//普通节点
    m_groupDim.clear();
    m_groupHover.clear();
    m_groupBase.reserve(vis);//为 vis 个节点预留的空间
    m_groupDim.reserve(vis);//为 vis 个节点预留的空间
    m_groupHover.reserve(vis);//为 vis 个节点预留的空间

    if (m_hoverIndex != -1) {//有悬停节点
        for (int vi = 0; vi < vis; ++vi) {
            int idx = m_visibleIndices[vi];
            if (idx == m_hoverIndex) {
                m_groupHover.push_back(idx);
            } else if (idx < (int)m_neighborMask.size() && m_neighborMask[idx]) {
                m_groupBase.push_back(idx);
            } else {
                m_groupDim.push_back(idx);
            }
        }
    } else if (t <= 0.0f) {//无悬停，过渡结束
        for (int vi = 0; vi < vis; ++vi) {
            int idx = m_visibleIndices[vi];
            m_groupBase.push_back(idx);
        }
    } else {//无悬停，过渡进行中
        for (int vi = 0; vi < vis; ++vi) {
            int idx = m_visibleIndices[vi];
            if (idx == m_lastHoverIndex) {
                m_groupHover.push_back(idx);
            } else if (idx < (int)m_lastNeighborMask.size() && m_lastNeighborMask[idx]) {
                m_groupBase.push_back(idx);
            } else {
                m_groupDim.push_back(idx);
            }
        }
    }

    //每个节点输出 7 个 float：(x, y, radius, r, g, b, a)
    auto emitNode = [&](std::vector<float>& out, int i, const QColor& color, float rScale) {
        float x = pos[2*i], y = pos[2*i+1];
        float r = (i < m_showRadii.size()) ? m_showRadii[i] * rScale : kDefaultNodeRadius;
        out.push_back(x);
        out.push_back(y);
        out.push_back(r);
        out.push_back(color.redF());
        out.push_back(color.greenF());
        out.push_back(color.blueF());
        out.push_back(color.alphaF());
    };

    m_nodeInstanceDataDim.clear();
    m_nodeInstanceDataRest.clear();
    m_nodeInstanceDataDim.reserve(m_groupDim.size() * 7);
    m_nodeInstanceDataRest.reserve((m_groupBase.size() + m_groupHover.size()) * 7);
    for (int i : m_groupDim) {
        QColor base = nodeColorFor(i);
        emitNode(m_nodeInstanceDataDim, i, mixColor(base, m_dimColor, t), 1.0f);
    }
    for (int i : m_groupBase) {
        QColor base = nodeColorFor(i);
        emitNode(m_nodeInstanceDataRest, i, base, 1.0f);
    }
    for (int i : m_groupHover) {
        QColor base = nodeColorFor(i);
        emitNode(m_nodeInstanceDataRest, i, mixColor(base, m_hoverColor, t), kHoverRadiusScale);
    }
}

// 功能：准备帧数据（将数据准备从 paintGL 分离出来）
void ForceViewOpenGL::prepareFrame()
{
    if (!m_glReady || !m_physicsState) {
        return;
    }

    updateVisibleMask();
    advanceHover();
    buildNodeInstanceData();

    // 计算最大显示半径和是否使用点精灵
    float maxShowRadius = 0.0f;
    for (int vi : m_visibleIndices) {
        if (vi >= 0 && vi < m_showRadii.size()) {
            float r = m_showRadii[vi];
            if (r > maxShowRadius) maxShowRadius = r;
        }
    }
    float maxRadiusPixels = (m_scenePerPixel > 0.0f) ? (maxShowRadius / m_scenePerPixel) : 0.0f;
    m_cachedUsePointSprite = (m_scenePerPixel > 0.0f && maxRadiusPixels < kPointSpriteMaxRadiusPixels);

    // 计算投影矩阵
    float left   = m_panX - (m_viewportW / 2.0f) / m_zoom;
    float right  = m_panX + (m_viewportW / 2.0f) / m_zoom;
    float bottom = m_panY + (m_viewportH / 2.0f) / m_zoom;
    float top    = m_panY - (m_viewportH / 2.0f) / m_zoom;
    ortho2D(left, right, bottom, top, m_cachedMvp);

    // 缓存投影边界供文本绘制使用
    m_cachedLeft = left;
    m_cachedRight = right;
    m_cachedTop = top;
    m_cachedBottom = bottom;
}

// 功能：线性混合两种颜色（t∈[0,1]）
QColor ForceViewOpenGL::mixColor(const QColor& c1, const QColor& c2, float t)
{
    if (t <= 0.0f) return c1;
    if (t >= 1.0f) return c2;
    int r = c1.red()   + static_cast<int>((c2.red()   - c1.red())   * t);
    int g = c1.green() + static_cast<int>((c2.green() - c1.green()) * t);
    int b = c1.blue()  + static_cast<int>((c2.blue()  - c1.blue())  * t);
    int a = c1.alpha() + static_cast<int>((c2.alpha() - c1.alpha()) * t);
    return QColor(r, g, b, a);
}

// 功能：构建标签的静态缓存（QStaticText），用于高效绘制与宽度计算
void ForceViewOpenGL::initStaticTextCache()
{
    m_staticTextCache.clear();
    for (int i = 0; i < m_labels.size(); ++i) {
        std::string key = m_labels[i].toStdString();
        if (m_staticTextCache.count(key)) continue;
        QStaticText st(m_labels[i]);
        st.prepare(QTransform(), m_font);
        float w = static_cast<float>(st.size().width());
        m_staticTextCache[key] = { st, w };
    }
    m_labelCacheByIndex.resize(m_labels.size());
    for (int i = 0; i < m_labels.size(); ++i) {
        auto it = m_staticTextCache.find(m_labels[i].toStdString());
        if (it != m_staticTextCache.end()) m_labelCacheByIndex[i] = it->second;
    }
}

// 功能：屏幕坐标转换为场景坐标（考虑平移与缩放）
void ForceViewOpenGL::screenToScene(float sx, float sy, float& outX, float& outY) const
{
    outX = m_panX + (sx - m_viewportW / 2.0f) / m_zoom;
    outY = m_panY + (sy - m_viewportH / 2.0f) / m_zoom;
}

// =====================================================================
// OpenGL: initializeGL, resizeGL, paintGL
// =====================================================================

// 功能：初始化 OpenGL 资源（编译/链接着色器、VAO/VBO、清屏颜色）
//你这个函数把 OpenGL 渲染管线搭好、VAO/VBO 都准备好、shader 也编好
//之后就可以直接用 glDrawArrays 或 glDrawArraysInstanced 画线和节点了。
void ForceViewOpenGL::initializeGL()
{
    initializeOpenGLFunctions();

    glEnable(GL_MULTISAMPLE);//开启多重采样抗锯齿,不开了自己弄shader，setSamples(4)
    glEnable(GL_BLEND);//开启混合
    glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);//混合函数
    glEnable(GL_PROGRAM_POINT_SIZE);
    m_renderer = std::make_unique<GraphRenderer>();
    m_glReady = m_renderer->initialize(this);
    if (!m_glReady) return;

    glClearColor(m_backgroundColor.redF(), m_backgroundColor.greenF(),
                 m_backgroundColor.blueF(), m_backgroundColor.alphaF());
}

// 功能：视口尺寸变化时更新缓存尺寸并设置 glViewport
void ForceViewOpenGL::resizeGL(int w, int h)
{
    m_viewportW = (w > 0) ? w : 1;
    m_viewportH = (h > 0) ? h : 1;
    float dpr = devicePixelRatioF();
    int vpW = std::max(1, static_cast<int>(std::lround(m_viewportW * dpr)));
    int vpH = std::max(1, static_cast<int>(std::lround(m_viewportH * dpr)));
    glViewport(0, 0, vpW, vpH);
}

// 功能：核心绘制流程（调用 prepareFrame 函数准备数据，然后渲染）
//类似与Qpainter
void ForceViewOpenGL::paintGL()
{
    if (!m_glReady || !m_physicsState) {
        glClear(GL_COLOR_BUFFER_BIT);
        return;
    }

    double paintStart = nowSec();//记录开始时间

    // 准备帧数据（分离出来的数据准备逻辑）
    prepareFrame();

    // 使用缓存的数据进行渲染
    auto drawNodeBatch = [&](const std::vector<float>& data) {
        if (!m_renderer) return;
        m_renderer->drawNodes(data, m_cachedUsePointSprite, m_scenePerPixel, m_cachedMvp);
    };

    glClearColor(m_backgroundColor.redF(), m_backgroundColor.greenF(),
                 m_backgroundColor.blueF(), m_backgroundColor.alphaF());
    glClear(GL_COLOR_BUFFER_BIT);//每帧都清屏

    if (m_hoverIndex == -1 && m_hoverGlobal <= 0.0f && !m_lineVertsAll.empty()) {
        float color[4] = { m_edgeColor.redF(), m_edgeColor.greenF(), m_edgeColor.blueF(), m_edgeColor.alphaF() };
        if (m_renderer) {
            m_renderer->drawLines(m_lineVertsAll, color, m_cachedMvp);
            if (!m_arrowVertsAll.empty()) {
                m_renderer->drawLines(m_arrowVertsAll, color, m_cachedMvp);
            }
        }

        drawNodeBatch(m_nodeInstanceDataRest);
    } else {
        if (!m_lineVertsDim.empty()) {
            QColor c = mixColor(m_edgeColor, m_edgeDimColor, m_hoverGlobal);
            float color[4] = { c.redF(), c.greenF(), c.blueF(), c.alphaF() };
            if (m_renderer) {
                m_renderer->drawLines(m_lineVertsDim, color, m_cachedMvp);
                if (!m_arrowVertsDim.empty()) {
                    m_renderer->drawLines(m_arrowVertsDim, color, m_cachedMvp);
                }
            }
        }

        drawNodeBatch(m_nodeInstanceDataDim);

        if (!m_lineVertsHighlight.empty()) {
            QColor c = mixColor(m_edgeColor, m_hoverColor, m_hoverGlobal);
            float color[4] = { c.redF(), c.greenF(), c.blueF(), c.alphaF() };
            if (m_renderer) {
                m_renderer->drawLines(m_lineVertsHighlight, color, m_cachedMvp);
                if (!m_arrowVertsHighlight.empty()) {
                    m_renderer->drawLines(m_arrowVertsHighlight, color, m_cachedMvp);
                }
            }
        }

        drawNodeBatch(m_nodeInstanceDataRest);
    }

    float scale = m_zoom;
    if (scale > m_textThresholdOff && !m_labelCacheByIndex.empty()) {
        float dpr = devicePixelRatioF();
        int deviceW = std::max(1, static_cast<int>(std::lround(m_viewportW * dpr)));
        int deviceH = std::max(1, static_cast<int>(std::lround(m_viewportH * dpr)));
        QOpenGLPaintDevice device(deviceW, deviceH);
        device.setDevicePixelRatio(dpr);
        QPainter painter(&device);
        painter.setRenderHint(QPainter::TextAntialiasing, true);//文字抗锯齿常开
        painter.setFont(m_font);
        QColor colorText(m_textColor);
        float factor = 1.0f;
        if (scale < m_textThresholdShow)
            factor = (scale - m_textThresholdOff) / (m_textThresholdShow - m_textThresholdOff);
        int baseAlpha = static_cast<int>(255.0f * factor);
        const float* pos = m_physicsState->renderPosData();
        painter.save();
        painter.scale(scale, scale);
        float invScaleDpr = 1.0f / (scale * dpr);

        auto alignToDevice = [&](float xPainter, float yPainter, float& outX, float& outY) {
            float px = xPainter * scale * dpr;
            float py = yPainter * scale * dpr;
            float pxRounded = std::lround(px);
            float pyRounded = std::lround(py);
            outX = pxRounded * invScaleDpr;
            outY = pyRounded * invScaleDpr;
        };

        auto drawLabel = [&](int i, int alpha, float rScale) {
            if (i < 0 || i >= (int)m_labelCacheByIndex.size()) return;
            const auto& entry = m_labelCacheByIndex[i];
            float w = entry.second;
            if (w <= 0.0f) return;
            float x = pos[2*i], y = pos[2*i+1];
            float r = (i < m_showRadii.size()) ? m_showRadii[i] * rScale : kDefaultNodeRadius;
            float sx = (x - m_cachedLeft) / (m_cachedRight - m_cachedLeft) * m_viewportW;
            float sy = (y - m_cachedTop) / (m_cachedBottom - m_cachedTop) * m_viewportH;
            colorText.setAlpha(alpha);
            painter.setPen(colorText);
            float drawX = sx / scale - w / 2.0f;
            float drawY = sy / scale + r;
            float alignedX = drawX;
            float alignedY = drawY;
            alignToDevice(drawX, drawY, alignedX, alignedY);
            painter.drawStaticText(QPointF(alignedX, alignedY), entry.first);
        };

        for (int i : m_groupBase) drawLabel(i, baseAlpha, 1.0f);
        if (m_hoverIndex == -1) { for (int i : m_groupHover) drawLabel(i, baseAlpha, 1.0f); }
        float fade = 1.0f - 0.7f * m_hoverGlobal;
        int alphaDim = static_cast<int>(baseAlpha * fade);
        for (int i : m_groupDim) drawLabel(i, alphaDim, 1.0f);

        if (m_hoverIndex != -1 && m_hoverIndex < m_labels.size()) {
            int i = m_hoverIndex;
            float x = pos[2*i], y = pos[2*i+1];
            float r = (i < m_showRadii.size()) ? m_showRadii[i] : kDefaultNodeRadius;
            float sx = (x - m_cachedLeft) / (m_cachedRight - m_cachedLeft) * m_viewportW;
            float sy = (y - m_cachedTop) / (m_cachedBottom - m_cachedTop) * m_viewportH;
            QString text = m_labels[i];
            if (m_cachedHoverLabelIndex != i || m_cachedHoverLabelScale != scale || m_cachedHoverLabelT != m_hoverGlobal) {
                m_cachedHoverLabelIndex = i;
                m_cachedHoverLabelScale = scale;
                m_cachedHoverLabelT = m_hoverGlobal;
                QFont font(m_font);
                float baseSize = m_font.pointSizeF();
                if (baseSize <= 0) baseSize = static_cast<float>(m_font.pointSize());
                float targetSize = baseSize * (1.0f + m_hoverGlobal * 2.0f);
                font.setPointSizeF(targetSize);
                QFontMetrics fm(font);
                m_cachedHoverLabelFont = font;
                m_cachedHoverLabelAdvance = fm.horizontalAdvance(text);
                m_cachedHoverLabelRectTop = fm.boundingRect(text).top();
            }
            painter.setPen(m_textColor);
            painter.setFont(m_cachedHoverLabelFont);
            float offsetY = m_fontHeight * (0.2f * m_hoverGlobal + 1.0f);
            float yBase = sy / scale + r - m_cachedHoverLabelRectTop + offsetY;
            float drawX = sx / scale - m_cachedHoverLabelAdvance / 2.0f;
            float drawY = yBase;
            float alignedX = drawX;
            float alignedY = drawY;
            alignToDevice(drawX, drawY, alignedX, alignedY);//文字对齐到设备像素
            painter.drawText(QPointF(alignedX, alignedY), text);
        }
        painter.restore();
        painter.end();
    }

    float elapsed = static_cast<float>((nowSec() - paintStart) * 1000.0);
    emit paintTimeUpdated(elapsed);

    ++m_frameCount;
    double now = nowSec();
    if (now - m_lastFpsTime >= 1.0) {
        m_currentFps = static_cast<float>(m_frameCount / (now - m_lastFpsTime));
        m_frameCount = 0;
        m_lastFpsTime = now;
        emit fpsUpdated(m_currentFps);
    }
}

// =====================================================================
// Mouse & wheel
// =====================================================================

// 功能：滚轮缩放（围绕光标位置进行比例缩放并调整平移）
void ForceViewOpenGL::wheelEvent(QWheelEvent* event)
{
    bool zoomIn = event->angleDelta().y() > 0;
    float factor = zoomIn ? kZoomWheelFactor : 1.0f / kZoomWheelFactor;
    float newZoom = m_zoom * factor;
    if (newZoom < kZoomMin || newZoom > kZoomMax) { event->accept(); return; }

    QPointF pos = event->position();
    float sx = static_cast<float>(pos.x()), sy = static_cast<float>(pos.y());
    float sceneX, sceneY;
    screenToScene(sx, sy, sceneX, sceneY);
    m_zoom = newZoom;
    m_panX = sceneX - (sx - m_viewportW / 2.0f) / m_zoom;
    m_panY = sceneY - (sy - m_viewportH / 2.0f) / m_zoom;
    emit scaleChanged(m_zoom);
    requestRenderActivity();
    update();
    event->accept();
}

// 功能：按下鼠标，选中并准备拖拽节点；否则进入平移模式
void ForceViewOpenGL::mousePressEvent(QMouseEvent* event)
{
    if (!m_physicsState || m_physicsState->nNodes == 0) { QOpenGLWidget::mousePressEvent(event); return; }
    // 准备帧数据（包括更新可见掩码）
    prepareFrame();
    float sx = static_cast<float>(event->pos().x()), sy = static_cast<float>(event->pos().y());
    float cx, cy;
    screenToScene(sx, sy, cx, cy);
    const float* pos = m_physicsState->renderPosData();

    if (m_visibleIndices.empty()) {
        m_selectedIndex = -1;
        m_panStartX = sx; m_panStartY = sy;
        m_panStartPanX = m_panX; m_panStartPanY = m_panY;
        m_isPanning = true;
        setCursor(Qt::ClosedHandCursor);
        QOpenGLWidget::mousePressEvent(event);
        return;
    }

    int bestLocal = -1;
    float bestDist2 = std::numeric_limits<float>::max();
    for (int vi = 0; vi < (int)m_visibleIndices.size(); ++vi) {
        int idx = m_visibleIndices[vi];
        float dx = pos[2*idx] - cx, dy = pos[2*idx+1] - cy;
        float d2 = dx*dx + dy*dy;
        if (d2 < bestDist2) { bestDist2 = d2; bestLocal = idx; }
    }
    if (bestLocal >= 0) {
        float r = (bestLocal < m_showRadii.size()) ? m_showRadii[bestLocal] : kDefaultNodeRadius;
        if (bestDist2 < r * r) {
            m_selectedIndex = bestLocal;
            m_dragOffsetX = pos[2*bestLocal] - cx;
            m_dragOffsetY = pos[2*bestLocal+1] - cy;
            m_hoverIndex = bestLocal;
            if (bestLocal >= 0 && bestLocal < m_ids.size())
                emit nodePressed(m_ids[bestLocal]);
            update();
            event->accept();
            return;
        }
    }
    m_selectedIndex = -1;
    m_panStartX = sx; m_panStartY = sy;
    m_panStartPanX = m_panX; m_panStartPanY = m_panY;
    m_isPanning = true;
    setCursor(Qt::ClosedHandCursor);
    QOpenGLWidget::mousePressEvent(event);
}

// 功能：鼠标移动，处理节点拖拽、视图平移与悬停高亮
void ForceViewOpenGL::mouseMoveEvent(QMouseEvent* event)
{
    float sx = static_cast<float>(event->pos().x()), sy = static_cast<float>(event->pos().y());

    if (m_selectedIndex >= 0 && m_physicsState) {
        float nx, ny;
        screenToScene(sx, sy, nx, ny);
        nx += m_dragOffsetX; ny += m_dragOffsetY;
        m_physicsState->setDragPos(m_selectedIndex, nx, ny);
        m_physicsState->updateRenderPosAt(m_selectedIndex, nx, ny);
        if (!m_dragging) {
            setDragging(m_selectedIndex, true);
            setCursor(Qt::PointingHandCursor);
        }
        if (m_selectedIndex >= 0 && m_selectedIndex < m_ids.size())
            emit nodeDragged(m_ids[m_selectedIndex]);
        m_dragging = true;
        requestRenderActivity();
        update();
        event->accept();
        return;
    }

    if (m_isPanning) {
        setCursor(Qt::ClosedHandCursor);
        float dx = (sx - m_panStartX) / m_zoom;
        float dy = (sy - m_panStartY) / m_zoom;
        m_panX = m_panStartPanX - dx;
        m_panY = m_panStartPanY - dy;
        update();
        event->accept();
        return;
    }

    if (!m_physicsState || m_physicsState->nNodes == 0) { QOpenGLWidget::mouseMoveEvent(event); return; }
    float cx, cy;
    screenToScene(sx, sy, cx, cy);
    const float* pos = m_physicsState->renderPosData();

    if (m_visibleIndices.empty()) { QOpenGLWidget::mouseMoveEvent(event); return; }
    int bestIdx = -1;
    float bestDist2 = std::numeric_limits<float>::max();
    for (int idx : m_visibleIndices) {
        float dx = pos[2*idx] - cx, dy = pos[2*idx+1] - cy;
        float d2 = dx*dx + dy*dy;
        if (d2 < bestDist2) { bestDist2 = d2; bestIdx = idx; }
    }
    if (bestIdx >= 0) {
        float r = (bestIdx < m_showRadii.size()) ? m_showRadii[bestIdx] : kDefaultNodeRadius;
        if (bestDist2 < r * r) {
            if (bestIdx != m_hoverIndex) {
                m_hoverIndex = bestIdx;
                m_lastHoverIndex = bestIdx;
                updateNeighborMaskForHover(bestIdx);
                if (bestIdx >= 0 && bestIdx < m_ids.size()) {
                    emit nodeHovered(m_ids[bestIdx]);
                    // Emit enhanced hover signal with position and scale info
                    float x = pos[2*bestIdx];
                    float y = pos[2*bestIdx+1];
                    float radius = (bestIdx < m_showRadii.size()) ? m_showRadii[bestIdx] : kDefaultNodeRadius;
                    emit nodeHoveredWithInfo(m_ids[bestIdx], x, y, radius, m_zoom, m_dragging);
                }
                requestRenderActivity();
            }
            update();
        } else {
            if (m_hoverIndex != -1) {
                m_lastHoverIndex = m_hoverIndex;
                m_hoverIndex = -1;
                emit nodeHovered(QString());
                emit nodeHoveredWithInfo(QString(), 0.0f, 0.0f, 0.0f, 0.0f, false);
                update();
            }
        }
    }
    setCursor(m_hoverIndex >= 0 ? Qt::PointingHandCursor : Qt::ArrowCursor);
    QOpenGLWidget::mouseMoveEvent(event);
}

// 功能：释放鼠标，结束拖拽/平移并触发点击事件（左/右键）
void ForceViewOpenGL::mouseReleaseEvent(QMouseEvent* event)
{
    if (!m_dragging && m_hoverIndex != -1 && m_hoverIndex < m_ids.size()) {
        if (event->button() == Qt::LeftButton) emit nodeLeftClicked(m_ids[m_hoverIndex]);
        if (event->button() == Qt::RightButton) emit nodeRightClicked(m_ids[m_hoverIndex]);
    }
    if (m_selectedIndex >= 0) {
        if (m_dragging)
            setDragging(m_selectedIndex, false);
        if (m_selectedIndex < m_ids.size())
            emit nodeReleased(m_ids[m_selectedIndex]);
    }
    m_dragging = false;
    m_selectedIndex = -1;
    m_isPanning = false;
    setCursor(Qt::ArrowCursor);
    QOpenGLWidget::mouseReleaseEvent(event);
}

void ForceViewOpenGL::enterEvent(QEnterEvent* event)
{
    setCursor(Qt::ArrowCursor);
    QOpenGLWidget::enterEvent(event);
}

void ForceViewOpenGL::leaveEvent(QEvent* event)
{
    setCursor(Qt::ArrowCursor);
    QOpenGLWidget::leaveEvent(event);
}

// =====================================================================
// Runtime Graph Modification
// =====================================================================

void ForceViewOpenGL::add_node_runtime(const QString& nodeId, float x, float y,
                                         const QString& label, float radius,
                                         const QColor& color)
{
    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    // 检查是否已存在该节点
    for (const QString& existingId : m_ids) {
        if (existingId == nodeId) return; // 已存在，不重复添加
    }

    // 在PhysicsState中添加节点
    int newIndex = m_physicsState->addNode(x, y);

    // 更新显示数据
    m_ids.append(nodeId);
    m_labels.append(label.isEmpty() ? nodeId : label);
    m_showRadiiBase.append(radius);
    m_nodeColors.append(color.isValid() ? color : m_baseColor);

    // 更新m_neighbors
    m_neighbors.push_back({});

    // 更新m_neighborMask和m_lastNeighborMask
    m_neighborMask.push_back(0);
    m_lastNeighborMask.push_back(0);

    // 更新显示半径
    updateFactor();

    // 更新标签缓存
    initStaticTextCache();

    // 同步渲染位置
    m_physicsState->syncDragPosFromPos();

    // 重启仿真以应用变化
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
    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    // 查找节点索引
    int indexToRemove = -1;
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == nodeId) {
            indexToRemove = i;
            break;
        }
    }

    if (indexToRemove == -1) return; // 未找到

    // swap-last 语义：PhysicsState 会把 last 节点搬到 indexToRemove
    const int lastNodeIndex = m_physicsState->nNodes - 1;

    // 在PhysicsState中删除节点
    bool removed = m_physicsState->removeNode(indexToRemove);
    if (!removed) return;

    // 同步 swap-last 更新并行容器（保持与 PhysicsState 索引一致）
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

    // swap-last 修正交互索引（hover/selected/lastHover）
    auto fixIdx = [&](int& idx) {
        if (idx == indexToRemove) idx = -1;
        else if (idx == lastNodeIndex) idx = indexToRemove;
    };
    fixIdx(m_hoverIndex);
    fixIdx(m_lastHoverIndex);
    fixIdx(m_selectedIndex);

    const int newN = m_physicsState->nNodes;
    if (m_hoverIndex < 0 || m_hoverIndex >= newN) m_hoverIndex = -1;
    if (m_lastHoverIndex < 0 || m_lastHoverIndex >= newN) m_lastHoverIndex = -1;
    if (m_selectedIndex < 0 || m_selectedIndex >= newN) m_selectedIndex = -1;

    // 结构变更后稳妥重建邻接表与掩码（避免增量修正出错）
    rebuildNeighborsFromEdges();
    m_neighborMask.assign(std::max(0, newN), 0);
    m_lastNeighborMask.assign(std::max(0, newN), 0);
    if (m_hoverIndex >= 0) updateNeighborMaskForHover(m_hoverIndex);

    // 更新显示半径
    updateFactor();

    // 更新标签缓存
    initStaticTextCache();

    // 重启仿真以应用变化
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
    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    // 查找两个节点的索引
    int u = -1, v = -1;
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == uNodeId) u = i;
        if (m_ids[i] == vNodeId) v = i;
        if (u >= 0 && v >= 0) break;
    }

    if (u < 0 || v < 0 || u == v) return; // 未找到或自环

    // 在PhysicsState中添加边
    bool added = m_physicsState->addEdge(u, v);
    if (!added) return; // 边已存在

    // 更新m_neighbors
    m_neighbors[u].push_back(v);
    m_neighbors[v].push_back(u);

    // 重启仿真以应用变化
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
    if (!m_physicsState) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    // 查找两个节点的索引
    int u = -1, v = -1;
    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == uNodeId) u = i;
        if (m_ids[i] == vNodeId) v = i;
        if (u >= 0 && v >= 0) break;
    }

    if (u < 0 || v < 0) return; // 未找到

    // 在PhysicsState中删除边
    bool removed = m_physicsState->removeEdge(u, v);
    if (!removed) return; // 边不存在

    // 更新m_neighbors
    auto removeFromNeighbors = [&](int node, int neighbor) {
        auto& neighbors = m_neighbors[node];
        neighbors.erase(std::remove(neighbors.begin(), neighbors.end(), neighbor),
                       neighbors.end());
    };
    removeFromNeighbors(u, v);
    removeFromNeighbors(v, u);

    // 重启仿真以应用变化
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
    if (!m_physicsState) return;
    if (diffList.isEmpty()) return;

    std::lock_guard<std::mutex> lock(m_simMutex);

    // 分阶段应用，避免引用不存在节点
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
            m_physicsState->removeEdge(u, v);
        }
    }

    // 2) 删除节点（逐个按当前 id->index 解析，避免索引变化问题）
    for (const QVariantMap& m : delNodes) {
        const QString nodeId = m.value(QStringLiteral("id")).toString();
        if (nodeId.isEmpty()) continue;

        int indexToRemove = -1;
        for (int i = 0; i < m_ids.size(); ++i) {
            if (m_ids[i] == nodeId) { indexToRemove = i; break; }
        }
        if (indexToRemove < 0) continue;

        const int lastNodeIndex = m_physicsState->nNodes - 1;
        if (!m_physicsState->removeNode(indexToRemove)) continue;

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

        // swap-last 修正交互索引
        auto fixIdx = [&](int& idx) {
            if (idx == indexToRemove) idx = -1;
            else if (idx == lastNodeIndex) idx = indexToRemove;
        };
        fixIdx(m_hoverIndex);
        fixIdx(m_lastHoverIndex);
        fixIdx(m_selectedIndex);
    }

    // 3) 添加节点（无 x/y 时用随机位置，避免重合无法散开）
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
        if (!(radiusD > 0.0)) radiusD = 7.0;//这里没有就是默认的半径，要在python侧把半径给计算好

        const QVariant colorVar = getAttr(m, QStringLiteral("color"));
        const QColor color = parseColor(colorVar);

        m_physicsState->addNode(static_cast<float>(x), static_cast<float>(y));
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
            m_physicsState->addEdge(u, v);
        }
    }

    // 结构变更后统一刷新一次
    rebuildNeighborsFromEdges();
    const int newN = m_physicsState->nNodes;
    if (m_hoverIndex < 0 || m_hoverIndex >= newN) m_hoverIndex = -1;
    if (m_lastHoverIndex < 0 || m_lastHoverIndex >= newN) m_lastHoverIndex = -1;
    if (m_selectedIndex < 0 || m_selectedIndex >= newN) m_selectedIndex = -1;

    m_neighborMask.assign(std::max(0, newN), 0);
    m_lastNeighborMask.assign(std::max(0, newN), 0);
    if (m_hoverIndex >= 0) updateNeighborMaskForHover(m_hoverIndex);

    updateFactor();
    initStaticTextCache();
    m_physicsState->syncDragPosFromPos();

    if (m_simulation) {
        m_simulation->stop();
        rebuildSimulation();
        m_simulation->start();
    }
    m_simActive.store(true, std::memory_order_release);
    requestRenderActivity();
}
