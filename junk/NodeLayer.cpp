#include "NodeLayer.h"

#include <QPainter>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QGraphicsSceneMouseEvent>
#include <QGraphicsSceneHoverEvent>
#include <QStyleOptionGraphicsItem>
#include <QTransform>
#include <QLineF>
#include <QCursor>
#include <Qt>

#include <cmath>
#include <algorithm>
#include <chrono>
#include <limits>

// Utility: current time in seconds (high-res)
static double nowSec()
{
    using clock = std::chrono::high_resolution_clock;
    return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

// =====================================================================
// Construction / Reset
// =====================================================================
/*
* 绘图层，目前采用的是Qgraphicsview里加一个大的item,在一个item里用Qpainter绘图
* 实现功能：鼠标放到节点上节点边色，其他的
* 优化策略：
* 1.看不到的不画
* 2.LOD策略，缩小后文字不画
* 3.批量绘制，减少Qpen的转换次数
* 4.文字静态缓存，使用QStaticText缓存文字，避免单个绘制的时候计算文字尺寸
* 其他实现
* 自己判断交互
*/
NodeLayer::NodeLayer(PhysicsState* state,
                     const QVector<float>& showRadii,
                     const QStringList& labels,
                     const std::vector<std::vector<int>>& neighbors,
                     const QStringList& id,
                     const QVector<QColor>& nodeColors,
                     QGraphicsItem* parent)
    : QGraphicsObject(parent)
    , m_state(state)
    , m_showRadiiBase(showRadii)
    , m_labels(labels)
    , m_neighbors(neighbors)
    , m_nodeColors(nodeColors)
    , m_font("Microsoft YaHei", 5)
    , m_fontMetrics(m_font)
{
    int N = m_state->nNodes;
    m_ids=id;

    m_fontHeight = m_fontMetrics.height();

    m_neighborMask.assign(N, 0);
    m_lastNeighborMask.clear();

    setZValue(1);
    setCursor(Qt::ArrowCursor);
    setAcceptedMouseButtons(Qt::LeftButton | Qt::RightButton);
    setAcceptHoverEvents(true);
    setFlag(QGraphicsItem::ItemIsSelectable, false);
    setFlag(QGraphicsItem::ItemIsMovable, false);

    updateFactor();
    initStaticTextCache();

    m_lastFpsTime = nowSec();
}

void NodeLayer::reset(PhysicsState* state,
                      const QVector<float>& showRadii,
                      const QStringList& labels,
                      const std::vector<std::vector<int>>& neighbors,
                      const QStringList& id,
                      const QVector<QColor>& nodeColors)
{
    m_state         = state;//物理状态
    m_showRadiiBase = showRadii;//节点半径
    m_labels        = labels;//节点标签
    m_neighbors     = neighbors;//邻居节点
    m_nodeColors    = nodeColors;//每节点颜色（暂不参与绘制）

    int N = m_state->nNodes;
    m_ids=id;

    m_neighborMask.assign(N, 0);//邻居节点掩码
    m_lastNeighborMask.clear();//上一次邻居节点掩码

    m_hoverIndex     = -1;//鼠标移动上去的节点索引
    m_lastHoverIndex = -1;//上一次鼠标移动上去的节点索引
    m_selectedIndex  = -1;//鼠标点击选中的节点索引
    m_dragging       = false;//是否正在拖拽节点
    m_hoverGlobal    = 0.0f;

    m_lastDimEdges.clear();//上一次暗色边
    m_lastHighlightEdges.clear();//上一次高亮边

    m_staticTextCache.clear();//静态文本缓存
    m_labelCacheByIndex.clear();
    m_cachedHoverLabelIndex = -1;

    m_radiusFactor = 1.0f;
    updateFactor();
    initStaticTextCache();

    m_boundingDirty = true;
}

// =====================================================================
// Factor update
// =====================================================================

void NodeLayer::updateFactor()
{
    m_sideWidth = m_sideWidthBase * m_sideWidthFactor;

    int N = m_showRadiiBase.size();
    m_showRadii.resize(N);
    for (int i = 0; i < N; ++i)
        m_showRadii[i] = m_showRadiiBase[i] * m_radiusFactor;

    m_textThresholdOff  = m_textThresholdBase * m_textThresholdFactor;
    m_textThresholdShow = m_textThresholdOff * 1.5f;

    m_boundingDirty = true;
}

// =====================================================================
// Static text cache
// =====================================================================

void NodeLayer::initStaticTextCache()
{
    m_staticTextCache.clear();
    for (int i = 0; i < m_labels.size(); ++i) {
        std::string key = m_labels[i].toStdString();
        if (m_staticTextCache.count(key)) continue;
        QStaticText st(m_labels[i]);
        st.prepare(QTransform(), m_font);
        float w = static_cast<float>(st.size().width());
        m_staticTextCache[key] = {st, w};
    }
    m_labelCacheByIndex.resize(m_labels.size());
    for (int i = 0; i < m_labels.size(); ++i) {
        auto it = m_staticTextCache.find(m_labels[i].toStdString());
        if (it != m_staticTextCache.end())
            m_labelCacheByIndex[i] = it->second;
    }
}

// =====================================================================
// Bounding rect
// =====================================================================

QRectF NodeLayer::boundingRect() const
{
    if (!m_boundingDirty)
        return m_cachedBounding;

    int N = m_state->nNodes;
    if (N == 0) {
        m_cachedBounding = QRectF();
        m_boundingDirty = false;
        return m_cachedBounding;
    }

    const float* pos = m_state->renderPosData();
    float minX = pos[0], maxX = pos[0];
    float minY = pos[1], maxY = pos[1];
    for (int i = 1; i < N; ++i) {
        float x = pos[2 * i], y = pos[2 * i + 1];
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
    }

    // Same padding as Python: *3 and +-100
    minX = minX * 3.0f - 100.0f;
    maxX = maxX * 3.0f + 100.0f;
    minY = minY * 3.0f - 100.0f;
    maxY = maxY * 3.0f + 100.0f;

    m_cachedBounding = QRectF(minX, minY, maxX - minX, maxY - minY);
    m_boundingDirty = false;
    return m_cachedBounding;
}

// =====================================================================
// Visibility culling
// =====================================================================

void NodeLayer::updateVisibleMask()
{
    const int N = m_state->nNodes;
    if (N == 0) {
        m_visibleIndices.clear();
        m_visibleEdges.clear();
        return;
    }

    // Find visible rect in item coordinates
    QRectF visRect;
    QGraphicsScene* sc = scene();
    QList<QGraphicsView*> views = sc ? sc->views() : QList<QGraphicsView*>();
    if (!views.isEmpty()) {
        QGraphicsView* v = views.first();
        QRectF sceneRect = v->mapToScene(v->viewport()->rect()).boundingRect();
        visRect = mapRectFromScene(sceneRect);
    } else {
        visRect = boundingRect();
    }
    visRect.adjust(-50, -50, 50, 50);

    const float* pos = m_state->renderPosData();
    const float left = static_cast<float>(visRect.left());
    const float right = static_cast<float>(visRect.right());
    const float top = static_cast<float>(visRect.top());
    const float bottom = static_cast<float>(visRect.bottom());

    // Node culling: two-pass to help auto-vectorization (pass 1: contiguous mask write, pass 2: gather indices)
    m_nodeMask.resize(N);
    uint8_t* nodeMask = m_nodeMask.data();
    const float* radii = m_showRadii.isEmpty() ? nullptr : m_showRadii.constData();
    for (int i = 0; i < N; ++i) {
        float x = pos[2 * i];
        float y = pos[2 * i + 1];
        float r = (radii && i < m_showRadii.size()) ? radii[i] : 5.0f;
        nodeMask[i] = (x + r >= left && x - r <= right && y + r >= top && y - r <= bottom) ? 1 : 0;
    }
    m_visibleIndices.clear();
    m_visibleIndices.reserve(N);
    for (int i = 0; i < N; ++i) {
        if (nodeMask[i])
            m_visibleIndices.push_back(i);
    }

    // Edge culling: keep edge if either endpoint is visible (sequential over edges)
    const int E = m_state->edgeCount();
    const int* edges = m_state->edges.data();
    m_visibleEdges.clear();
    m_visibleEdges.reserve(E * 2);
    for (int e = 0; e < E; ++e) {
        int s = edges[2 * e];
        int d = edges[2 * e + 1];
        if (nodeMask[s] || nodeMask[d]) {
            m_visibleEdges.push_back(s);
            m_visibleEdges.push_back(d);
        }
    }
}

// =====================================================================
// Hover animation
// =====================================================================

void NodeLayer::advanceHover()
{
    float target = (m_hoverIndex != -1) ? 1.0f : 0.0f;
    if (target > m_hoverGlobal)
        m_hoverGlobal = std::min(1.0f, m_hoverGlobal + m_hoverStep);
    else if (target < m_hoverGlobal)
        m_hoverGlobal = std::max(0.0f, m_hoverGlobal - m_hoverStep);
    updateEdgeLineBuffers();
}

// =====================================================================
// Circle-edge line helper (start/end on circle boundaries)
// =====================================================================

static QLineF lineFromCircleToCircle(float sx, float sy, float rs,
                                     float dx, float dy, float rd)
{
    float vx = dx - sx;
    float vy = dy - sy;
    float L = std::sqrt(vx * vx + vy * vy);
    if (L <= 0.0f) {
        return QLineF(sx, sy, sx, sy);
    }
    float ux = vx / L;
    float uy = vy / L;
    float x1 = sx + ux * rs;
    float y1 = sy + uy * rs;
    float x2 = dx - ux * rd;
    float y2 = dy - uy * rd;
    return QLineF(x1, y1, x2, y2);
}

// =====================================================================
// updateEdgeLineBuffers (fills m_linesAll / m_linesDim / m_linesHighlight for drawEdges)
// =====================================================================

void NodeLayer::updateEdgeLineBuffers()
{
    const int VE = static_cast<int>(m_visibleEdges.size()) / 2;
    const float* pos = m_state ? m_state->renderPosData() : nullptr;
    if (VE == 0 || !pos) {
        m_linesAll.clear();
        m_linesDim.clear();
        m_linesHighlight.clear();
        return;
    }

    const int* vedge = m_visibleEdges.data();
    const int hover = m_hoverIndex;
    const float t = m_hoverGlobal;

    auto radiusAt = [this](int i) -> float {
        return (i >= 0 && i < m_showRadii.size()) ? m_showRadii[i] : 5.0f;
    };

    if (hover == -1) {
        if (t <= 0.0f) {
            m_linesAll.clear();
            m_linesAll.reserve(VE);
            for (int e = 0; e < VE; ++e) {
                int s = vedge[2 * e], d = vedge[2 * e + 1];
                m_linesAll.append(lineFromCircleToCircle(
                    pos[2*s], pos[2*s+1], radiusAt(s),
                    pos[2*d], pos[2*d+1], radiusAt(d)));
            }
            m_linesDim.clear();
            m_linesHighlight.clear();
        } else {
            m_linesAll.clear();
            int nDim = static_cast<int>(m_lastDimEdges.size()) / 2;
            int nHi = static_cast<int>(m_lastHighlightEdges.size()) / 2;
            m_linesDim.clear();
            m_linesDim.reserve(nDim);
            for (int e = 0; e < nDim; ++e) {
                int s = m_lastDimEdges[2*e], d = m_lastDimEdges[2*e+1];
                m_linesDim.append(lineFromCircleToCircle(
                    pos[2*s], pos[2*s+1], radiusAt(s),
                    pos[2*d], pos[2*d+1], radiusAt(d)));
            }
            m_linesHighlight.clear();
            m_linesHighlight.reserve(nHi);
            for (int e = 0; e < nHi; ++e) {
                int s = m_lastHighlightEdges[2*e], d = m_lastHighlightEdges[2*e+1];
                m_linesHighlight.append(lineFromCircleToCircle(
                    pos[2*s], pos[2*s+1], radiusAt(s),
                    pos[2*d], pos[2*d+1], radiusAt(d)));
            }
        }
        return;
    }

    // Hover active: split visible edges into dim / highlight and fill buffers
    m_lastDimEdges.clear();
    m_lastHighlightEdges.clear();
    m_lastDimEdges.reserve(VE * 2);
    m_lastHighlightEdges.reserve(VE * 2);
    for (int e = 0; e < VE; ++e) {
        int s = vedge[2 * e], d = vedge[2 * e + 1];
        if (s == hover || d == hover) {
            m_lastHighlightEdges.push_back(s);
            m_lastHighlightEdges.push_back(d);
        } else {
            m_lastDimEdges.push_back(s);
            m_lastDimEdges.push_back(d);
        }
    }
    m_linesAll.clear();
    int nDim = static_cast<int>(m_lastDimEdges.size()) / 2;
    int nHi = static_cast<int>(m_lastHighlightEdges.size()) / 2;
    m_linesDim.clear();
    m_linesDim.reserve(nDim);
    for (int e = 0; e < nDim; ++e) {
        int s = m_lastDimEdges[2*e], d = m_lastDimEdges[2*e+1];
        m_linesDim.append(lineFromCircleToCircle(
            pos[2*s], pos[2*s+1], radiusAt(s),
            pos[2*d], pos[2*d+1], radiusAt(d)));
    }
    m_linesHighlight.clear();
    m_linesHighlight.reserve(nHi);
    for (int e = 0; e < nHi; ++e) {
        int s = m_lastHighlightEdges[2*e], d = m_lastHighlightEdges[2*e+1];
        m_linesHighlight.append(lineFromCircleToCircle(
            pos[2*s], pos[2*s+1], radiusAt(s),
            pos[2*d], pos[2*d+1], radiusAt(d)));
    }
}

// =====================================================================
// Color mix
// =====================================================================

QColor NodeLayer::mixColor(const QColor& c1, const QColor& c2, float t)
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
// paint()
// =====================================================================

void NodeLayer::paint(QPainter* painter,
                      const QStyleOptionGraphicsItem* /*option*/,
                      QWidget* /*widget*/)
{
    double start = nowSec();

    drawEdgesUnder(painter);
    drawNodesAndText(painter);
    drawEdgesOver(painter);

    float elapsed = static_cast<float>((nowSec() - start) * 1000.0);
    emit paintTimeReady(elapsed);
    updateFps();
}

// =====================================================================
// drawEdgesUnder (dim / all edges below nodes)
// =====================================================================

void NodeLayer::drawEdgesUnder(QPainter* painter)
{
    const int VE = static_cast<int>(m_visibleEdges.size()) / 2;
    if (VE == 0) return;

    const bool needAll = (m_hoverIndex == -1 && m_hoverGlobal <= 0.0f);
    if (needAll && m_linesAll.isEmpty()) {
        updateEdgeLineBuffers();
    } else if (!needAll && m_linesDim.isEmpty() && m_linesHighlight.isEmpty()) {
        updateEdgeLineBuffers();
    }

    const float t = m_hoverGlobal;
    const int hover = m_hoverIndex;

    if (hover == -1 && t <= 0.0f) {
        if (!m_linesAll.isEmpty()) {
            painter->setPen(QPen(m_edgeColor, m_sideWidth));
            painter->drawLines(m_linesAll);
        }
        return;
    }

    if (!m_linesDim.isEmpty()) {
        QColor color = mixColor(m_edgeColor, m_edgeDimColor, t);
        painter->setPen(QPen(color, m_sideWidth));
        painter->drawLines(m_linesDim);
    }
}

// =====================================================================
// drawEdgesOver (adjacency highlight lines on top of nodes)
// =====================================================================

void NodeLayer::drawEdgesOver(QPainter* painter)
{
    const int VE = static_cast<int>(m_visibleEdges.size()) / 2;
    if (VE == 0) return;

    const bool needAll = (m_hoverIndex == -1 && m_hoverGlobal <= 0.0f);
    if (!needAll && m_linesDim.isEmpty() && m_linesHighlight.isEmpty()) {
        updateEdgeLineBuffers();
    }

    if (!m_linesHighlight.isEmpty()) {
        const float t = m_hoverGlobal;
        QColor color = mixColor(m_edgeColor, m_hoverColor, t);
        painter->setPen(QPen(color, m_sideWidth));
        painter->drawLines(m_linesHighlight);
    }
}

// =====================================================================
// drawNodesAndText
// =====================================================================

void NodeLayer::drawNodesAndText(QPainter* painter)
{
    const float* pos = m_state->renderPosData();
    const float  t   = m_hoverGlobal;

    // Reuse member vectors for groups (clear + reserve, no per-frame heap alloc)
    const int vis = static_cast<int>(m_visibleIndices.size());
    m_groupBase.clear();
    m_groupDim.clear();
    m_groupHover.clear();
    m_groupBase.reserve(vis);
    m_groupDim.reserve(vis);
    m_groupHover.reserve(vis);

    // Determine scene scale (zoom level)
    float scale = 1.0f;
    QGraphicsScene* sc = scene();
    QList<QGraphicsView*> views = sc ? sc->views() : QList<QGraphicsView*>();
    if (!views.isEmpty())
        scale = static_cast<float>(views.first()->transform().m11());

    // ---- Group classification ----
    if (m_hoverIndex != -1) {
        // Active hover
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
    } else if (t <= 0.0f) {
        // No hover, no transition
        for (int vi = 0; vi < vis; ++vi) {
            int idx = m_visibleIndices[vi];
            m_groupBase.push_back(idx);
        }
    } else {
        // Fading out from hover
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

    painter->setPen(Qt::NoPen);

    // Helper lambda: draw circle for node i
    auto nodeColorFor = [&](int i) -> QColor {
        if (i >= 0 && i < m_nodeColors.size()) return m_nodeColors[i];
        return m_baseColor;
    };

    auto drawNode = [&](int i, const QColor& color, float rScale) {
        float x = pos[2 * i], y = pos[2 * i + 1];
        float r = (i < m_showRadii.size()) ? m_showRadii[i] * rScale : 5.0f;
        painter->setBrush(QBrush(color));
        painter->drawEllipse(QPointF(x, y), r, r);
    };

    // 1. Base (neighbors or normal)
    for (int i : m_groupBase)      drawNode(i, nodeColorFor(i), 1.0f);
    // 2. Dim
    for (int i : m_groupDim)       drawNode(i, mixColor(nodeColorFor(i), m_dimColor, t),  1.0f);
    // 3. Hover
    for (int i : m_groupHover)     drawNode(i, mixColor(nodeColorFor(i), m_hoverColor, t), 1.1f);

    // ===================== Text (LOD) =====================
    if (scale > m_textThresholdOff) {
        bool prevTextAA = painter->testRenderHint(QPainter::TextAntialiasing);
        float factor = 1.0f;
        if (scale < m_textThresholdShow) {
            painter->setRenderHint(QPainter::TextAntialiasing, false);
            factor = (scale - m_textThresholdOff)
                   / (m_textThresholdShow - m_textThresholdOff);
        }
        int baseAlpha = static_cast<int>(255.0f * factor);

        painter->setFont(m_font);
        QColor colorText("#5C5C5C");

        // Lambda: draw label for node i (uses index cache, no toStdString/map in hot path)
        auto drawLabel = [&](int i, int alpha, float rScale) {
            if (i < 0 || i >= (int)m_labelCacheByIndex.size()) return;
            const auto& entry = m_labelCacheByIndex[i];
            float w = entry.second;
            if (w <= 0.0f) return;  // no cached text for this index
            float x = pos[2 * i], y = pos[2 * i + 1];
            float r = (i < m_showRadii.size()) ? m_showRadii[i] * rScale : 5.0f;
            colorText.setAlpha(alpha);
            painter->setPen(QPen(colorText));
            painter->drawStaticText(QPointF(x - w / 2.0f, y + r), entry.first);
        };

        // Base group
        for (int i : m_groupBase)      drawLabel(i, baseAlpha, 1.0f);

        // Hover group (when hoverIndex == -1, these are fading from last hover)
        if (m_hoverIndex == -1) {
            for (int i : m_groupHover) drawLabel(i, baseAlpha, 1.0f);
        }

        // Dim group (faded alpha)
        float fade = 1.0f - 0.7f * t;
        int alphaDim = static_cast<int>(baseAlpha * fade);
        for (int i : m_groupDim) drawLabel(i, alphaDim, 1.0f);

        painter->setRenderHint(QPainter::TextAntialiasing, prevTextAA);
    }

    // ===================== Hovered node label (override LOD) =====================
    if (m_hoverIndex != -1 && m_hoverIndex < m_labels.size()) {
        int i = m_hoverIndex;
        float x = pos[2 * i], y = pos[2 * i + 1];
        float r = (i < m_showRadii.size()) ? m_showRadii[i] : 5.0f;
        QString text = m_labels[i];
        float ht = m_hoverGlobal;

        // Reuse cached font/metrics when hover index, scale, and t unchanged
        if (m_cachedHoverLabelIndex != i || m_cachedHoverLabelScale != scale || m_cachedHoverLabelT != ht) {
            m_cachedHoverLabelIndex = i;
            m_cachedHoverLabelScale = scale;
            m_cachedHoverLabelT = ht;
            QFont font(m_font);
            float baseSize = m_font.pointSizeF();
            if (baseSize <= 0) baseSize = static_cast<float>(m_font.pointSize());
            float targetSize = baseSize * (1.0f + ht * 2.0f);
            float sizeFactor = (scale > 0.0f && scale <= 1.0f) ? (1.0f / scale) : (1.0f / (scale * 2.0f) + 0.5f);
            font.setPointSizeF(targetSize * sizeFactor);
            QFontMetrics fm(font);
            m_cachedHoverLabelFont = font;
            m_cachedHoverLabelAdvance = fm.horizontalAdvance(text);
            m_cachedHoverLabelRectTop = fm.boundingRect(text).top();
        }
        QColor color("#5C5C5C");
        painter->setPen(QPen(color));
        painter->setFont(m_cachedHoverLabelFont);
        float offsetY = (m_fontHeight * (0.2f * ht + 1.0f)) / scale;
        float yBase = y + r - m_cachedHoverLabelRectTop + offsetY;
        painter->drawText(QPointF(x - m_cachedHoverLabelAdvance / 2.0f, yBase), text);
    }
}

// =====================================================================
// Mouse interaction
// =====================================================================

void NodeLayer::mousePressEvent(QGraphicsSceneMouseEvent* event)
{
    const int N = m_state->nNodes;
    if (N == 0) {
        QGraphicsObject::mousePressEvent(event);
        return;
    }

    float cx = static_cast<float>(event->pos().x());
    float cy = static_cast<float>(event->pos().y());
    const float* pos = m_state->renderPosData();

    if (m_visibleIndices.empty()) {
        m_selectedIndex = -1;
        setFlag(QGraphicsItem::ItemIsSelectable, false);
        QGraphicsObject::mousePressEvent(event);
        return;
    }

    // Find closest visible node
    int bestLocal = -1;
    float bestDist2 = std::numeric_limits<float>::max();
    for (int vi = 0; vi < (int)m_visibleIndices.size(); ++vi) {
        int idx = m_visibleIndices[vi];
        float dx = pos[2 * idx] - cx;
        float dy = pos[2 * idx + 1] - cy;
        float d2 = dx * dx + dy * dy;
        if (d2 < bestDist2) { bestDist2 = d2; bestLocal = idx; }
    }

    if (bestLocal >= 0) {
        float r = (bestLocal < m_showRadii.size()) ? m_showRadii[bestLocal] : 5.0f;
        if (bestDist2 < r * r) {
            m_selectedIndex = bestLocal;
            m_dragOffsetX = pos[2 * bestLocal] - cx;
            m_dragOffsetY = pos[2 * bestLocal + 1] - cy;
            m_hoverIndex = bestLocal;
            update();
            QString nodeId = (bestLocal >= 0 && bestLocal < m_ids.size()) ? m_ids.at(bestLocal) : QString();
            emit nodePressed(nodeId);
            setFlag(QGraphicsItem::ItemIsSelectable, true);
            event->accept();

            QGraphicsObject::mousePressEvent(event);
            return;
        }
    }

    m_selectedIndex = -1;
    setFlag(QGraphicsItem::ItemIsSelectable, false);
    event->ignore(); // Let view handle pan
}

void NodeLayer::mouseMoveEvent(QGraphicsSceneMouseEvent* event)
{
    if (m_selectedIndex >= 0) {
        float nx = static_cast<float>(event->pos().x()) + m_dragOffsetX;
        float ny = static_cast<float>(event->pos().y()) + m_dragOffsetY;
        m_state->setDragPos(m_selectedIndex, nx, ny);
        m_state->updateRenderPosAt(m_selectedIndex, nx, ny);
        QString nodeId = (m_selectedIndex < m_ids.size()) ? m_ids.at(m_selectedIndex) : QString();
        emit nodeDragged(nodeId);
        m_dragging = true;
        setCursor(Qt::ClosedHandCursor);
        update();
    }
}

void NodeLayer::mouseReleaseEvent(QGraphicsSceneMouseEvent* event)
{
    if (!m_dragging) {
        if (m_hoverIndex != -1) {
            QString nodeId = (m_hoverIndex >= 0 && m_hoverIndex < m_ids.size()) ? m_ids.at(m_hoverIndex) : QString();
            if (event->button() == Qt::LeftButton)
                emit nodeLeftClicked(nodeId);
            if (event->button() == Qt::RightButton)
                emit nodeRightClicked(nodeId);
        }
    }

    m_dragging = false;
    setFlag(QGraphicsItem::ItemIsSelectable, false);
    int idx = m_selectedIndex;
    if (idx >= 0) {
        QString nodeId = (idx < m_ids.size()) ? m_ids.at(idx) : QString();
        emit nodeReleased(nodeId);
    }
    m_selectedIndex = -1;
    setCursor(Qt::ArrowCursor);

    QGraphicsObject::mouseReleaseEvent(event);
}

void NodeLayer::hoverMoveEvent(QGraphicsSceneHoverEvent* event)
{
    const int N = m_state->nNodes;
    if (N == 0) {
        QGraphicsObject::hoverMoveEvent(event);
        return;
    }

    float px = static_cast<float>(event->pos().x());
    float py = static_cast<float>(event->pos().y());
    const float* pos = m_state->renderPosData();

    if (m_visibleIndices.empty()) {
        QGraphicsObject::hoverMoveEvent(event);
        return;
    }

    int bestIdx = -1;
    float bestDist2 = std::numeric_limits<float>::max();
    for (int idx : m_visibleIndices) {
        float dx = pos[2 * idx] - px;
        float dy = pos[2 * idx + 1] - py;
        float d2 = dx * dx + dy * dy;
        if (d2 < bestDist2) { bestDist2 = d2; bestIdx = idx; }
    }

    if (bestIdx >= 0) {
        float r = (bestIdx < m_showRadii.size()) ? m_showRadii[bestIdx] : 5.0f;
        if (bestDist2 < r * r) {
            if (bestIdx != m_hoverIndex) {
                m_hoverIndex = bestIdx;
                m_lastHoverIndex = bestIdx;

                // Update neighbor mask
                m_neighborMask.assign(N, 0);
                if (bestIdx < (int)m_neighbors.size()) {
                    for (int nb : m_neighbors[bestIdx])
                        if (nb >= 0 && nb < N) m_neighborMask[nb] = 1;
                }
                m_neighborMask[bestIdx] = 0; // self not a neighbor
                m_lastNeighborMask = m_neighborMask;

                QString nodeId = (bestIdx >= 0 && bestIdx < m_ids.size()) ? m_ids.at(bestIdx) : QString();
                emit nodeHovered(nodeId);
            }
            update();
        } else {
            if (m_hoverIndex != -1) {
                m_lastHoverIndex = m_hoverIndex;
                m_hoverIndex = -1;
                emit nodeHovered(QString());
                update();
            }
        }
    }

    QGraphicsObject::hoverMoveEvent(event);
}

// =====================================================================
// FPS tracking
// =====================================================================

void NodeLayer::updateFps()
{
    ++m_frameCount;
    double now = nowSec();
    if (now - m_lastFpsTime >= 1.0) {
        m_currentFps = static_cast<float>(m_frameCount / (now - m_lastFpsTime));
        m_frameCount = 0;
        m_lastFpsTime = now;
        emit fpsReady(m_currentFps);
    }
}
