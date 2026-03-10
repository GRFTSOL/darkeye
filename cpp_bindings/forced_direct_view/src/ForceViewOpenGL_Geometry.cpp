#include "ForceViewOpenGL.h"

#include <cmath>
#include <algorithm>

// 功能：构建 2D 正交投影矩阵，将场景坐标映射到 NDC（供 prepareFrame 使用）
static void ortho2D(float left, float right, float bottom, float top, float* m)
{
    for (int i = 0; i < 16; ++i) m[i] = 0.0f;
    m[0]  = 2.0f / (right - left);
    m[5]  = 2.0f / (top - bottom);
    m[10] = -1.0f;
    m[12] = -(right + left) / (right - left);
    m[13] = -(top + bottom) / (top - bottom);
    m[14] = 0.0f;
    m[15] = 1.0f;
}

// =====================================================================
// updateFactor, updateVisibleMask, advanceHover, updateEdgeLineBuffers
// =====================================================================

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
    float left   = m_panX - halfW - kViewPadding;
    float right  = m_panX + halfW + kViewPadding;
    float top    = m_panY - halfH - kViewPadding;
    float bottom = m_panY + halfH + kViewPadding;
    float viewW = 2.0f * halfW;
    float viewH = 2.0f * halfH;
    float scaleX = (m_viewportW > 0) ? viewW / m_viewportW : 0.0f;
    float scaleY = (m_viewportH > 0) ? viewH / m_viewportH : 0.0f;
    float scenePerPixel = 0.5f * (std::abs(scaleX) + std::abs(scaleY));
    float dpr = devicePixelRatioF();
    float scenePerDevicePixel = (dpr > 0.0f) ? (scenePerPixel / dpr) : scenePerPixel;
    m_scenePerPixel = scenePerDevicePixel;

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
        if (s < 0 || s >= N || d < 0 || d >= N) continue;
        if (m_nodeMask[s] || m_nodeMask[d]) {
            m_visibleEdges.push_back(s);
            m_visibleEdges.push_back(d);
        }
    }
}

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

    auto pushQuad = [&](std::vector<float>& out, int s, int d) {
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

        out.push_back(ax + ox); out.push_back(ay + oy); out.push_back(1.0f);
        out.push_back(ax - ox); out.push_back(ay - oy); out.push_back(-1.0f);
        out.push_back(bx - ox); out.push_back(by - oy); out.push_back(-1.0f);

        out.push_back(ax + ox); out.push_back(ay + oy); out.push_back(1.0f);
        out.push_back(bx - ox); out.push_back(by - oy); out.push_back(-1.0f);
        out.push_back(bx + ox); out.push_back(by + oy); out.push_back(1.0f);
    };

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

        float ax = x0 + dirx * r0;
        float ay = y0 + diry * r0;
        float bx = x1 - dirx * r1;
        float by = y1 - diry * r1;
        float sdx = bx - ax;
        float sdy = by - ay;
        float slen = std::sqrt(sdx * sdx + sdy * sdy);
        if (slen <= minLen) return;

        const float kArrowLenBase = 4.0f;
        const float kArrowWidthBase = 3.0f;
        float arrowLen = kArrowLenBase * m_arrowScale;
        float arrowHalfWidth = 0.5f * kArrowWidthBase * m_arrowScale;
        if (arrowLen > slen * 0.8f) {
            arrowLen = std::max(slen * 0.5f, minLen);
        }

        float baseCx = bx - dirx * arrowLen;
        float baseCy = by - diry * arrowLen;

        float nx = -sdy / slen;
        float ny = sdx / slen;

        float baseLx = baseCx + nx * arrowHalfWidth;
        float baseLy = baseCy + ny * arrowHalfWidth;
        float baseRx = baseCx - nx * arrowHalfWidth;
        float baseRy = baseCy - ny * arrowHalfWidth;

        const float across = 0.2f;

        out.push_back(bx);    out.push_back(by);    out.push_back(across);
        out.push_back(baseLx); out.push_back(baseLy); out.push_back(across);
        out.push_back(baseRx); out.push_back(baseRy); out.push_back(across);
    };

    if (hover == -1) {
        if (t <= 0.0f) {
            m_lineVertsAll.clear();
            m_lineVertsAll.reserve(VE * 18);
            m_arrowVertsAll.clear();
            if (m_arrowEnabled) {
                m_arrowVertsAll.reserve(VE * 9);
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
        } else {
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

void ForceViewOpenGL::buildNodeInstanceData()
{
    const float* pos = m_physicsState->renderPosData();
    const float t = m_hoverGlobal;
    const int vis = static_cast<int>(m_visibleIndices.size());

    auto nodeColorFor = [this](int i) -> QColor {
        if (i >= 0 && i < m_nodeColors.size())
            return m_nodeColors[i];
        return m_baseColor;
    };

    m_groupBase.clear();
    m_groupDim.clear();
    m_groupHover.clear();
    m_groupBase.reserve(vis);
    m_groupDim.reserve(vis);
    m_groupHover.reserve(vis);

    if (m_hoverIndex != -1) {
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
        for (int vi = 0; vi < vis; ++vi) {
            int idx = m_visibleIndices[vi];
            m_groupBase.push_back(idx);
        }
    } else {
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

void ForceViewOpenGL::prepareFrame()
{
    if (!m_glReady || !m_physicsState) {
        return;
    }

    updateVisibleMask();
    advanceHover();
    buildNodeInstanceData();

    float maxShowRadius = 0.0f;
    for (int vi : m_visibleIndices) {
        if (vi >= 0 && vi < m_showRadii.size()) {
            float r = m_showRadii[vi];
            if (r > maxShowRadius) maxShowRadius = r;
        }
    }
    float maxRadiusPixels = (m_scenePerPixel > 0.0f) ? (maxShowRadius / m_scenePerPixel) : 0.0f;
    m_cachedUsePointSprite = (m_scenePerPixel > 0.0f && maxRadiusPixels < kPointSpriteMaxRadiusPixels);

    float left   = m_panX - (m_viewportW / 2.0f) / m_zoom;
    float right  = m_panX + (m_viewportW / 2.0f) / m_zoom;
    float bottom = m_panY + (m_viewportH / 2.0f) / m_zoom;
    float top    = m_panY - (m_viewportH / 2.0f) / m_zoom;
    ortho2D(left, right, bottom, top, m_cachedMvp);

    m_cachedLeft = left;
    m_cachedRight = right;
    m_cachedTop = top;
    m_cachedBottom = bottom;
}
