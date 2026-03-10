#ifndef NODELAYER_H
#define NODELAYER_H

#include "PhysicsState.h"

#include <QGraphicsObject>
#include <QColor>
#include <QFont>
#include <QFontMetrics>
#include <QStaticText>
#include <QString>
#include <QStringList>
#include <QVector>
#include <QRectF>
#include <QPointF>
#include <QPair>

#include <vector>
#include <unordered_map>

/**
 * NodeLayer — QGraphicsObject that renders all nodes, edges, and labels.
 *
 * Reads positions directly from PhysicsState::pos.
 * Ports Python NodeLayer from ForceGraphView.py (minus draw_images).
 */
class NodeLayer : public QGraphicsObject
{
    Q_OBJECT

public:
    NodeLayer(PhysicsState* state,
              const QVector<float>& showRadii,
              const QStringList& labels,
              const std::vector<std::vector<int>>& neighbors,
              const QStringList& id,
              const QVector<QColor>& nodeColors = QVector<QColor>(),
              QGraphicsItem* parent = nullptr);

    // Reset with new graph data (reuse the QGraphicsItem)
    void reset(PhysicsState* state,
               const QVector<float>& showRadii,
               const QStringList& labels,
               const std::vector<std::vector<int>>& neighbors,
               const QStringList& id,
               const QVector<QColor>& nodeColors = QVector<QColor>());

    // QGraphicsItem interface
    QRectF boundingRect() const override;
    void paint(QPainter* painter, const QStyleOptionGraphicsItem* option,
               QWidget* widget = nullptr) override;

    // Visibility culling (call when pos changes or viewport scrolls/zooms)
    void updateVisibleMask();

    // Hover animation step (call from render timer)
    void advanceHover();

    // Update display factors after changing base values
    void updateFactor();

    // --- Visual parameters ---
    void setRadiusFactor(float f)           { m_radiusFactor = f; updateFactor(); }
    void setSideWidthFactor(float f)        { m_sideWidthFactor = f; updateFactor(); }
    void setTextThresholdFactor(float f)    { m_textThresholdFactor = f; updateFactor(); }

    // read by ForceView
    bool isDragging() const  { return m_dragging; }
    int  hoverIndex() const  { return m_hoverIndex; }

signals:
    void nodePressed(const QString& nodeId);
    void nodeDragged(const QString& nodeId);
    void nodeReleased(const QString& nodeId);
    void nodeLeftClicked(const QString& nodeId);
    void nodeRightClicked(const QString& nodeId);
    void nodeHovered(const QString& nodeId);   // empty string = no hover
    void paintTimeReady(float ms);
    void fpsReady(float fps);

protected:
    void mousePressEvent(QGraphicsSceneMouseEvent* event) override;
    void mouseMoveEvent(QGraphicsSceneMouseEvent* event) override;
    void mouseReleaseEvent(QGraphicsSceneMouseEvent* event) override;
    void hoverMoveEvent(QGraphicsSceneHoverEvent* event) override;

private:
    // Drawing helpers (Under = below nodes, Over = above nodes so adjacency lines float on top)
    void drawEdgesUnder(QPainter* painter);
    void drawEdgesOver(QPainter* painter);
    void drawNodesAndText(QPainter* painter);

    // Color interpolation
    static QColor mixColor(const QColor& c1, const QColor& c2, float t);

    // Static text cache
    void initStaticTextCache();

    // Fill m_linesAll / m_linesDim / m_linesHighlight from visible edges and hover state (call from advanceHover)
    void updateEdgeLineBuffers();

    // FPS tracking
    void updateFps();

    // ---------- Data ----------
    PhysicsState* m_state = nullptr;

    // Per-node display
    QVector<float>  m_showRadiiBase;
    QVector<float>  m_showRadii;       // = base * factor
    QStringList     m_labels;
    QStringList     m_ids;             // length N: external node id per node (emit m_ids[index])
    QVector<QColor> m_nodeColors;       // length N: per-node color (optional; empty = use layer defaults)

    // Neighbors adjacency (index → list of neighbor indices)
    std::vector<std::vector<int>> m_neighbors;

    // Neighbor highlight mask (length N, true = neighbor of hovered node)
    std::vector<uint8_t> m_neighborMask;
    std::vector<uint8_t> m_lastNeighborMask;

    // Visible subset after culling
    std::vector<int> m_visibleIndices;
    std::vector<int> m_visibleEdges;  // flat [src0,dst0, ...]  (subset of state edges)
    std::vector<uint8_t> m_nodeMask;   // length N, 1 = visible (reused for culling, no per-frame alloc)

    // Node groups for draw order (reused each frame to avoid per-frame allocations)
    std::vector<int> m_groupBase;
    std::vector<int> m_groupDim;
    std::vector<int> m_groupHover;

    // Center-node index (-1 = none)

    // ---- Colors ----
    QColor m_edgeColor      = QColor("#D5D5D5");
    QColor m_edgeDimColor   = QColor("#F7F7F7");
    QColor m_baseColor      = QColor("#5C5C5C");
    QColor m_dimColor       = QColor("#DEDEDE");
    QColor m_hoverColor     = QColor("#8F6AEE");

    // ---- Factors ----
    float m_sideWidthBase        = 1.0f;
    float m_sideWidthFactor      = 1.0f;
    float m_sideWidth            = 1.0f;

    float m_radiusFactor         = 1.0f;

    float m_textThresholdBase    = 0.7f;
    float m_textThresholdFactor  = 1.0f;
    float m_textThresholdOff     = 0.7f;   // derived
    float m_textThresholdShow    = 1.05f;  // derived

    // ---- Text ----
    QFont m_font;
    QFontMetrics m_fontMetrics;
    int   m_fontHeight = 0;
    std::unordered_map<std::string, QPair<QStaticText, float>> m_staticTextCache;
    std::vector<QPair<QStaticText, float>> m_labelCacheByIndex;  // per-node cache for paint (no toStdString/map in hot path)

    // ---- Interaction state ----
    int   m_hoverIndex      = -1;
    int   m_lastHoverIndex  = -1;
    int   m_selectedIndex   = -1;
    bool  m_dragging        = false;
    float m_dragOffsetX     = 0.0f;
    float m_dragOffsetY     = 0.0f;

    // ---- Hover animation ----
    float m_hoverStep   = 0.1f;
    float m_hoverGlobal = 0.0f;

    // ---- Edge animation cache (for fade transition) ----
    std::vector<int> m_lastDimEdges;        // flat
    std::vector<int> m_lastHighlightEdges;  // flat

    // Pre-built line buffers for drawEdges (filled in updateEdgeLineBuffers, used in paint)
    QVector<QLineF> m_linesAll;
    QVector<QLineF> m_linesDim;
    QVector<QLineF> m_linesHighlight;

    // ---- Bounding rect cache ----
    mutable bool   m_boundingDirty = true;
    mutable QRectF m_cachedBounding;

    // ---- Hover label cache (avoid QFont/QFontMetrics per frame) ----
    int   m_cachedHoverLabelIndex = -1;
    float m_cachedHoverLabelScale = 0.0f;
    float m_cachedHoverLabelT     = -1.0f;
    QFont m_cachedHoverLabelFont;
    int   m_cachedHoverLabelAdvance = 0;
    int   m_cachedHoverLabelRectTop = 0;

    // ---- FPS ----
    int    m_frameCount   = 0;
    double m_lastFpsTime  = 0.0;
    float  m_currentFps   = 0.0f;
};

#endif // NODELAYER_H
