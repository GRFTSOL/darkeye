#include "ForceViewOpenGL.h"
#include "GraphRenderer.h"
#include "MsdfFontAtlas.h"
#include "MsdfTextRenderer.h"

#include <QSurfaceFormat>
#include <QFileInfo>

#include <algorithm>
#include <cmath>
#include <chrono>
#include <thread>

// 功能：获取当前时间（秒），用于统计渲染/仿真耗时与 FPS 计算
static double nowSec()
{
    using clock = std::chrono::high_resolution_clock;
    return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

// =====================================================================
// Construction / Destruction
// =====================================================================

ForceViewOpenGL::ForceViewOpenGL(QWidget* parent)
    : QOpenGLWidget(parent)
{
    m_fontPath = detectDefaultFontPath();

    QSurfaceFormat fmt;
    fmt.setVersion(3, 3);
    fmt.setProfile(QSurfaceFormat::CoreProfile);
    fmt.setSamples(4);
    setFormat(fmt);
    setMinimumSize(200, 150);
    setMouseTracking(true);
    setupTimers();
}

ForceViewOpenGL::~ForceViewOpenGL()
{
    makeCurrent();
    if (m_textRenderer) {
        m_textRenderer->cleanup();
    }
    if (m_renderer) {
        m_renderer->cleanup();
    }
    m_fontAtlas.reset();
    doneCurrent();

    m_msdfAtlasThreadRunning.store(false, std::memory_order_release);
    if (m_msdfAtlasThread.joinable()) {
        m_msdfAtlasThread.join();
    }

    stopSimThread();
    if (m_renderTimer) m_renderTimer->stop();
    if (m_idleTimer) m_idleTimer->stop();
}

// =====================================================================
// Font path
// =====================================================================

QString ForceViewOpenGL::detectDefaultFontPath()
{
    static const char* const candidates[] = {
#ifdef Q_OS_WIN
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhl.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/arial.ttf",
#elif defined(Q_OS_MAC)
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
#else
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
#endif
    };

    for (const char* path : candidates) {
        if (QFileInfo::exists(QString::fromUtf8(path)))
            return QString::fromUtf8(path);
    }
    return QString();
}

MsdfFontAtlas::Config ForceViewOpenGL::makeFontConfig() const
{
    MsdfFontAtlas::Config cfg;
    cfg.fontPath = m_fontPath;
    cfg.atlasWidth = 2048;
    cfg.atlasHeight = 2048;
    cfg.pxRange = 6.0f;
    return cfg;
}

void ForceViewOpenGL::setFontPath(const QString& path)
{
    if (m_fontPath == path) return;
    m_fontPath = path;

    if (m_fontAtlas && m_glReady) {
        m_fontAtlas->initialize(makeFontConfig());
        m_labelLayoutCache.clear();
        m_labelLayoutByIndex.clear();
        {
            std::lock_guard<std::mutex> lock(m_msdfAtlasMutex);
            m_msdfAtlasResultReady = false;
        }
        ++m_msdfAtlasBuildId;
        if (!m_labels.isEmpty())
            startMsdfAtlasBuildAsync();
        requestRenderActivity();
    }
}

QString ForceViewOpenGL::fontPath() const
{
    return m_fontPath;
}

// =====================================================================
// Timers
// =====================================================================

void ForceViewOpenGL::setupTimers()
{
    m_renderTimer = new QTimer(this);
    m_renderTimer->setInterval(kRenderTimerIntervalMs);
    connect(m_renderTimer, &QTimer::timeout, this, &ForceViewOpenGL::onRenderTick);

    m_idleTimer = new QTimer(this);
    m_idleTimer->setSingleShot(true);
    m_idleTimer->setInterval(kIdleStopDelayMs);
    connect(m_idleTimer, &QTimer::timeout, this, &ForceViewOpenGL::maybeStopRenderTimer);
}

void ForceViewOpenGL::ensureRenderTimerRunning()
{
    if (!m_renderActive) {
        m_renderTimer->start();
        m_renderActive = true;
    }
}

void ForceViewOpenGL::requestRenderActivity()
{
    ensureRenderTimerRunning();
    m_idleTimer->start();
}

void ForceViewOpenGL::startSimThread()
{
    if (m_simThreadRunning.load(std::memory_order_acquire))
        return;
    m_simThreadRunning.store(true, std::memory_order_release);
    m_simThread = std::thread([this]() { simLoop(); });
}

void ForceViewOpenGL::stopSimThread()
{
    if (!m_simThreadRunning.load(std::memory_order_acquire))
        return;
    m_simThreadRunning.store(false, std::memory_order_release);
    if (m_simThread.joinable())
        m_simThread.join();
}

void ForceViewOpenGL::simLoop()
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
                const int n = m_physicsState->nNodes;
                const int warmupTicks = n > 0
                    ? static_cast<int>(n * std::log(static_cast<float>(std::max(2, n))) * 0.2f + 10.0f)
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






// 功能：计算所有节点的包围矩形（带 10% 边距），用于自动缩放/居中

QRectF ForceViewOpenGL::getContentRect() const
{
    if (!m_physicsState || m_physicsState->nNodes == 0) return QRectF();
    const float* pos = m_physicsState->renderPosData();
    if (!pos) return QRectF();

    const int N = m_physicsState->nNodes;
    const bool useScaledRadii = (m_showRadii.size() == N);
    const bool useBaseRadii = (!useScaledRadii && m_showRadiiBase.size() == N);
    auto radiusAt = [&](int i) -> float {
        float r = kDefaultNodeRadius;
        if (useScaledRadii) {
            r = m_showRadii[i];
        } else if (useBaseRadii) {
            r = m_showRadiiBase[i] * m_radiusFactor;
        }
        if (!std::isfinite(r) || r <= 0.0f) r = kDefaultNodeRadius;
        return r;
    };

    float r0 = radiusAt(0);
    float minX = pos[0] - r0;
    float maxX = pos[0] + r0;
    float minY = pos[1] - r0;
    float maxY = pos[1] + r0;
    for (int i = 1; i < N; ++i) {
        float x = pos[2 * i];
        float y = pos[2 * i + 1];
        float r = radiusAt(i);
        if (x - r < minX) minX = x - r;
        if (x + r > maxX) maxX = x + r;
        if (y - r < minY) minY = y - r;
        if (y + r > maxY) maxY = y + r;
    }
    float w = maxX - minX;
    float h = maxY - minY;
    float mx = std::max(w * kContentPaddingRatio, kContentPaddingAbs);
    float my = std::max(h * kContentPaddingRatio, kContentPaddingAbs);
    return QRectF(minX - mx, minY - my, w + 2 * mx, h + 2 * my);
}

void ForceViewOpenGL::fitViewToContent()
{
    if (!m_physicsState || m_physicsState->nNodes <= 0) return;
    QRectF r = getContentRect();
    if (r.isEmpty() || m_viewportW <= 0 || m_viewportH <= 0) return;

    float w = static_cast<float>(r.width());
    float h = static_cast<float>(r.height());
    if (w <= 0.0f || h <= 0.0f) return;

    const int N = m_physicsState->nNodes;
    float margin = kFitViewScaleMargin;
    if (N <= 2) {
        margin = 0.65f;
    } else if (N <= 10) {
        margin = 0.75f;
    } else if (N <= 50) {
        margin = 0.85f;
    }

    float z = std::min(static_cast<float>(m_viewportW) / w,
                       static_cast<float>(m_viewportH) / h) * margin;

    float fitZoomUpper = kFitViewZoomMax;
    if (N <= 2) {
        fitZoomUpper = std::min(fitZoomUpper, 1.2f);
    } else if (N <= 10) {
        fitZoomUpper = std::min(fitZoomUpper, 1.8f);
    } else if (N <= 50) {
        fitZoomUpper = std::min(fitZoomUpper, 2.8f);
    }

    if (N <= 50) {
        float maxNodeRadius = 0.0f;
        if (m_showRadii.size() == N) {
            for (int i = 0; i < N; ++i) {
                const float rNode = m_showRadii[i];
                if (std::isfinite(rNode) && rNode > maxNodeRadius) maxNodeRadius = rNode;
            }
        } else if (m_showRadiiBase.size() == N) {
            for (int i = 0; i < N; ++i) {
                const float rNode = m_showRadiiBase[i] * m_radiusFactor;
                if (std::isfinite(rNode) && rNode > maxNodeRadius) maxNodeRadius = rNode;
            }
        }
        if (maxNodeRadius > 0.0f) {
            const float radiusZoomUpper = kFitViewMaxNodeRadiusPx / maxNodeRadius;
            fitZoomUpper = std::min(fitZoomUpper, radiusZoomUpper);
        }
    }

    fitZoomUpper = std::max(kFitViewZoomMin, fitZoomUpper);
    z = std::max(kFitViewZoomMin, std::min(fitZoomUpper, z));

    m_zoom = z;
    m_panX = static_cast<float>(r.center().x());
    m_panY = static_cast<float>(r.center().y());
    emit scaleChanged(m_zoom);
    update();
}

QPointF ForceViewOpenGL::getNodePosition(const QString& nodeId) const
{
    if (!m_physicsState || m_physicsState->nNodes == 0 || nodeId.isEmpty()) {
        return QPointF();
    }

    for (int i = 0; i < m_ids.size(); ++i) {
        if (m_ids[i] == nodeId) {
            const float* pos = m_physicsState->renderPosData();
            if (pos) {
                return QPointF(pos[2 * i], pos[2 * i + 1]);
            }
            break;
        }
    }

    return QPointF();
}

void ForceViewOpenGL::onRenderTick()
{
    update();
}

void ForceViewOpenGL::maybeStopRenderTimer()
{
    if (!m_simActive && !m_dragging && m_hoverIndex == -1) {
        if (m_renderTimer) m_renderTimer->stop();
        m_renderActive = false;
    }
}

// =====================================================================
// mixColor (used by Geometry and Text)
// =====================================================================

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

// =====================================================================
// OpenGL: initializeGL, resizeGL, paintGL
// =====================================================================

void ForceViewOpenGL::initializeGL()
{
    initializeOpenGLFunctions();

    glEnable(GL_MULTISAMPLE);
    glEnable(GL_BLEND);
    glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
    glEnable(GL_PROGRAM_POINT_SIZE);
    m_renderer = std::make_unique<GraphRenderer>();
    m_glReady = m_renderer->initialize(this);
    if (!m_glReady) return;


    m_fontAtlas = std::make_unique<MsdfFontAtlas>();
    m_fontAtlas->initialize(makeFontConfig());

    m_textRenderer = std::make_unique<MsdfTextRenderer>();
    m_textRenderer->initialize(this);

    if (!m_labels.isEmpty()) {
        startMsdfAtlasBuildAsync();
    }


    glClearColor(m_backgroundColor.redF(), m_backgroundColor.greenF(),
                 m_backgroundColor.blueF(), m_backgroundColor.alphaF());

}

void ForceViewOpenGL::resizeGL(int w, int h)
{
    m_viewportW = (w > 0) ? w : 1;
    m_viewportH = (h > 0) ? h : 1;
    float dpr = devicePixelRatioF();
    int vpW = std::max(1, static_cast<int>(std::lround(m_viewportW * dpr)));
    int vpH = std::max(1, static_cast<int>(std::lround(m_viewportH * dpr)));
    glViewport(0, 0, vpW, vpH);
}

void ForceViewOpenGL::paintGL()
{
    if (!m_glReady || !m_physicsState) {
        glClearColor(m_backgroundColor.redF(), m_backgroundColor.greenF(),
                    m_backgroundColor.blueF(), m_backgroundColor.alphaF());
        glClear(GL_COLOR_BUFFER_BIT);
        return;
    }

    double paintStart = nowSec();

    prepareFrame();

    applyMsdfAtlasResultIfReady();

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

        if (m_zoom > m_textThresholdOff && m_textRenderer && m_fontAtlas && m_fontAtlas->isReady()) {
            if (m_fontAtlas->generation() != m_lastAtlasGeneration) {
                m_textRenderer->uploadAtlas(
                    m_fontAtlas->atlasPixels().data(),
                    m_fontAtlas->atlasWidth(),
                    m_fontAtlas->atlasHeight(),
                    m_fontAtlas->generation());
                m_lastAtlasGeneration = m_fontAtlas->generation();
            }
            buildTextVertices();
            if (!m_textVerticesRest.empty()) {
                float dpr = devicePixelRatioF();
                float screenGlyphSize = m_msdfFontSize * m_zoom * dpr;
                float atlasGlyphSize = m_fontAtlas->targetInnerPixels();
                float screenPxRange = m_fontAtlas->pxRange() * screenGlyphSize / atlasGlyphSize;
                if (screenPxRange < 1.0f) screenPxRange = 1.0f;
                m_textRenderer->draw(m_textVerticesRest, m_cachedMvp, screenPxRange);
            }
        }
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

        if (m_zoom > m_textThresholdOff && m_textRenderer && m_fontAtlas && m_fontAtlas->isReady()) {
            if (m_fontAtlas->generation() != m_lastAtlasGeneration) {
                m_textRenderer->uploadAtlas(
                    m_fontAtlas->atlasPixels().data(),
                    m_fontAtlas->atlasWidth(),
                    m_fontAtlas->atlasHeight(),
                    m_fontAtlas->generation());
                m_lastAtlasGeneration = m_fontAtlas->generation();
            }
            buildTextVertices();
            float dpr = devicePixelRatioF();
            float baseScreenGlyphSize = m_msdfFontSize * m_zoom * dpr;
            float atlasGlyphSize = m_fontAtlas->targetInnerPixels();
            float baseScreenPxRange = m_fontAtlas->pxRange() * baseScreenGlyphSize / atlasGlyphSize;
            if (baseScreenPxRange < 1.0f) baseScreenPxRange = 1.0f;
            if (!m_textVerticesDim.empty()) {
                m_textRenderer->draw(m_textVerticesDim, m_cachedMvp, baseScreenPxRange);
            }
        }

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

        if (m_zoom > m_textThresholdOff && m_textRenderer && m_fontAtlas && m_fontAtlas->isReady()) {
            float dpr = devicePixelRatioF();
            float baseScreenGlyphSize = m_msdfFontSize * m_zoom * dpr;
            float atlasGlyphSize = m_fontAtlas->targetInnerPixels();
            float baseScreenPxRange = m_fontAtlas->pxRange() * baseScreenGlyphSize / atlasGlyphSize;
            if (baseScreenPxRange < 1.0f) baseScreenPxRange = 1.0f;

            if (!m_textVerticesRest.empty()) {
                m_textRenderer->draw(m_textVerticesRest, m_cachedMvp, baseScreenPxRange);
            }

            if (!m_textVerticesHover.empty()) {
                float hoverScale = 1.0f + m_hoverGlobal * 2.0f;
                float hoverGlyphSize = baseScreenGlyphSize * hoverScale;
                float hoverScreenPxRange = m_fontAtlas->pxRange() * hoverGlyphSize / atlasGlyphSize;
                if (hoverScreenPxRange < 1.0f) hoverScreenPxRange = 1.0f;
                m_textRenderer->draw(m_textVerticesHover, m_cachedMvp, hoverScreenPxRange);
            }
        }
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
