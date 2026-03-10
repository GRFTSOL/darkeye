#include "ForceViewOpenGL.h"

#include <QWheelEvent>
#include <QMouseEvent>
#include <QEnterEvent>
#include <QEvent>

#include <limits>

void ForceViewOpenGL::screenToScene(float sx, float sy, float& outX, float& outY) const
{
    outX = m_panX + (sx - m_viewportW / 2.0f) / m_zoom;
    outY = m_panY + (sy - m_viewportH / 2.0f) / m_zoom;
}

// =====================================================================
// Mouse & wheel
// =====================================================================

void ForceViewOpenGL::wheelEvent(QWheelEvent* event)
{
    bool zoomIn = event->angleDelta().y() > 0;
    float factor = zoomIn ? kZoomWheelFactor : 1.0f / kZoomWheelFactor;
    float newZoom = m_zoom * factor;
    newZoom = qBound(kZoomMin, newZoom, kZoomMax);

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

void ForceViewOpenGL::mousePressEvent(QMouseEvent* event)
{
    if (!m_physicsState || m_physicsState->nNodes == 0) { QOpenGLWidget::mousePressEvent(event); return; }
    updateVisibleMask();
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

void ForceViewOpenGL::mouseMoveEvent(QMouseEvent* event)
{
    float sx = static_cast<float>(event->pos().x()), sy = static_cast<float>(event->pos().y());

    if (m_selectedIndex >= 0 && m_physicsState) {
        float nx, ny;
        screenToScene(sx, sy, nx, ny);
        nx += m_dragOffsetX; ny += m_dragOffsetY;
        {
            std::lock_guard<std::mutex> lock(m_simMutex);
            if (!m_physicsState || m_selectedIndex < 0 || m_selectedIndex >= m_physicsState->nNodes) {
                m_selectedIndex = -1;
            } else {
                m_physicsState->setDragPos(m_selectedIndex, nx, ny);
                m_physicsState->updateRenderPosAt(m_selectedIndex, nx, ny);
            }
        }
        if (m_selectedIndex < 0) {
            QOpenGLWidget::mouseMoveEvent(event);
            return;
        }
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
    if (m_hoverIndex != -1) {
        m_lastHoverIndex = m_hoverIndex;
        m_hoverIndex = -1;
        emit nodeHovered(QString());
        emit nodeHoveredWithInfo(QString(), 0.0f, 0.0f, 0.0f, 0.0f, false);
        requestRenderActivity();
    }
    setCursor(Qt::ArrowCursor);
    QOpenGLWidget::leaveEvent(event);
}
