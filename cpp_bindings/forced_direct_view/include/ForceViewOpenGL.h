#ifndef FORCEVIEWOPENGL_H
#define FORCEVIEWOPENGL_H

#include <QOpenGLWidget>
#include <QOpenGLFunctions_3_3_Core>
#include <QTimer>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QEnterEvent>
#include <QEvent>
#include <QVector>
#include <QStringList>
#include <QColor>
#include <QRectF>

#include <memory>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>
#include <string>
#include <unordered_map>
#include <QVariant>

#include "PhysicsState.h"
#include "Simulation.h"
#include "Forces.h"
#include "MsdfFontAtlas.h"

class GraphRenderer;
class MsdfTextRenderer;

#ifdef BINDINGS_BUILD
#  define FORCEVIEW_OPENGL_EXPORT Q_DECL_EXPORT
#else
#  define FORCEVIEW_OPENGL_EXPORT Q_DECL_IMPORT
#endif

/**
 * ForceViewOpenGL — QOpenGLWidget that renders the same force-directed graph
 * as ForceView but using OpenGL for points, lines, and QPainter overlay for text.
 *
 * Same public API as ForceView (setGraph, simulation control, visual params, signals).
 * Does not use NodeLayer or ForceView; duplicates display logic and reuses
 * PhysicsState + Simulation unchanged.
 */
class FORCEVIEW_OPENGL_EXPORT ForceViewOpenGL : public QOpenGLWidget, protected QOpenGLFunctions_3_3_Core
{
    Q_OBJECT

public:
    explicit ForceViewOpenGL(QWidget* parent = nullptr);
    ~ForceViewOpenGL() override;

    // ======================== Graph Data ========================
    void setGraph(int nNodes,
                  const QVector<int>&   edges,
                  const QVector<float>& pos,
                  const QStringList&   id,
                  const QStringList&   labels,
                  const QVector<float>& radii,
                  const QVector<QColor>& nodeColors = QVector<QColor>());

    // ======================== Simulation Control ========================
    void pauseSimulation();
    void resumeSimulation();
    void restartSimulation();

    // ======================== Force Parameters ========================
    void setManyBodyStrength(float value);
    void setCenterStrength(float value);
    void setLinkStrength(float value);
    void setLinkDistance(float value);
    void setCollisionRadius(float value);
    void setCollisionStrength(float value);

    // ======================== Visual Parameters ========================
    void setRadiusFactor(float f);
    void setSideWidthFactor(float f);
    void setTextThresholdFactor(float f);
    void setNodeColors(const QVector<QColor>& colors);
    void setArrowScale(float f);
    void setArrowEnabled(bool enabled);
    void setNeighborDepth(int depth);  // 1-5*** End Patch】} ***!
    void setBackgroundColor(const QColor& color);

    // 边颜色
    void setEdgeColor(const QColor& c);
    QColor edgeColor() const;
    void setEdgeDimColor(const QColor& c);
    QColor edgeDimColor() const;

    // 节点颜色
    void setBaseColor(const QColor& c);
    QColor baseColor() const;
    void setDimColor(const QColor& c);
    QColor dimColor() const;
    void setHoverColor(const QColor& c);
    QColor hoverColor() const;

    // 文本颜色
    void setTextColor(const QColor& c);
    QColor textColor() const;
    void setTextDimColor(const QColor& c);
    QColor textDimColor() const;

    // 字体路径
    void setFontPath(const QString& path);
    QString fontPath() const;

    // ======================== Misc ========================
    void setDragging(int nodeId, bool dragging);
    QRectF getContentRect() const;
    void fitViewToContent();

    // 获取视图变换信息（用于坐标转换）
    float getPanX() const { return m_panX; }
    float getPanY() const { return m_panY; }
    float getZoom() const { return m_zoom; }

    // 获取指定节点的当前位置（通过节点ID）
    QPointF getNodePosition(const QString& nodeId) const;
    // 获取当前所有节点 ID（与 m_nodeColors 索引一一对应，用于颜色重算）
    QStringList getNodeIds() const;

    // ======================== Runtime Graph Modification ========================
    // 运行时添加节点（nodeId 为字符串 id，如 "a100"、"w123"、"c200"）
    void add_node_runtime(const QString& nodeId, float x = 0.0f, float y = 0.0f,
                          const QString& label = QString(), float radius = 7.0f,
                          const QColor& color = QColor());
    // 运行时删除节点（nodeId 为字符串 id）
    void remove_node_runtime(const QString& nodeId);
    // 运行时添加边（nodeId 为字符串 id）
    void add_edge_runtime(const QString& uNodeId, const QString& vNodeId);
    // 运行时删除边（nodeId 为字符串 id）
    void remove_edge_runtime(const QString& uNodeId, const QString& vNodeId);

    // 批量应用运行时图变更（Python 可传 list[dict]）
    void apply_diff_runtime(const QVariantList& diffList);

signals:
    void nodeLeftClicked(const QString& nodeId);
    void nodeRightClicked(const QString& nodeId);
    void nodeHovered(const QString& nodeId);   // empty string = no hover
    void nodeHoveredWithInfo(const QString& nodeId, float x, float y, float radius, float scale, bool dragging);
    void nodePressed(const QString& nodeId);
    void nodeDragged(const QString& nodeId);
    void nodeReleased(const QString& nodeId);
    void scaleChanged(float scale);
    void alphaUpdated(float alpha);
    void fpsUpdated(float fps);
    void paintTimeUpdated(float ms);
    void tickTimeUpdated(float ms);
    void simulationStarted();
    void simulationStopped();

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void enterEvent(QEnterEvent* event) override;
    void leaveEvent(QEvent* event) override;

private slots:
    void onRenderTick();
    void maybeStopRenderTimer();

private:
    // ---- Constants (timing, layout, view, interaction, geometry) ----
    static constexpr float kRenderTimerIntervalMs      = 8.3f;
    static constexpr int   kIdleStopDelayMs            = 500;
    static constexpr int   kSimTickIntervalMs          = 16;
    static constexpr int   kFitViewDelayMs             = 100;

    static constexpr float kInitialLayoutScaleFactor   = 25.0f;
    static constexpr float kInitialLayoutBaseOffset    = 50.0f;
    static constexpr float kContentPaddingRatio        = 0.1f;
    static constexpr float kViewPadding                = 50.0f;

    static constexpr float kFitViewScaleMargin         = 0.9f;
    static constexpr float kFitViewZoomMin             = 0.01f;
    static constexpr float kFitViewZoomMax             = 1000.0f;

    static constexpr float kZoomMin                    = 0.1f;
    static constexpr float kZoomMax                    = 10.0f;
    static constexpr float kZoomWheelFactor            = 1.15f;

    static constexpr float kDefaultNodeRadius          = 5.0f;
    static constexpr float kLineMinLength              = 1e-3f;
    static constexpr float kHoverRadiusScale           = 1.1f;

    static constexpr float kTextThresholdShowMul       = 1.5f;

    static constexpr float kManyBodyDistanceLimitSq    = 40000.0f;

    void setupTimers();
    void ensureRenderTimerRunning();
    void requestRenderActivity();
    void rebuildSimulation();
    void rebuildNeighborsFromEdges();

    void startSimThread();
    void stopSimThread();
    void simLoop();

    // Visible rect in scene coords (from pan/zoom + viewport)
    void updateVisibleMask();
    void advanceHover();
    void updateFactor();

    // Edge line buffers: float arrays [x1,y1,x2,y2, ...] for GL
    void updateEdgeLineBuffers();

    // Build node instance data (pos, radius, color) for visible nodes in draw order
    void buildNodeInstanceData();

    // Prepare frame data before rendering
    void prepareFrame();

    bool removeNodeInternal(int indexToRemove);

    static QString detectDefaultFontPath();
    MsdfFontAtlas::Config makeFontConfig() const;

    static QColor mixColor(const QColor& c1, const QColor& c2, float t);

    // Screen (pixel) to scene coords using inverse view matrix
    void screenToScene(float sx, float sy, float& outX, float& outY) const;

    // BFS 更新 m_neighborMask / m_lastNeighborMask（由 setNeighborDepth 与 mouseMove 共用）
    void updateNeighborMaskForHover(int hoverIndex);

    // ---- Simulation (same as ForceView) ----
    std::unique_ptr<PhysicsState> m_physicsState;
    std::unique_ptr<Simulation>   m_simulation;
    std::thread m_simThread;
    std::atomic<bool> m_simThreadRunning{false};
    std::mutex m_simMutex;

    std::vector<std::vector<int>> m_neighbors;
    QStringList m_ids;                  // same as m_labels: external id per node (string)

    QTimer* m_renderTimer = nullptr;
    QTimer* m_idleTimer   = nullptr;
    bool    m_renderActive = false;

    float m_manyBodyStrength  = 10000.0f;
    float m_linkStrength      = 0.3f;
    float m_linkDistance      = 30.0f;
    float m_centerStrength    = 0.01f;
    float m_collisionRadius   = 10.0f;
    float m_collisionStrength = 50.0f;

    std::atomic<bool> m_simActive{false};
    std::atomic<bool> m_allowWarmup{false};

    // ---- Display data (from NodeLayer logic) ----
    QVector<float>  m_showRadiiBase;
    QVector<float>  m_showRadii;
    QStringList     m_labels;
    QVector<QColor> m_nodeColors;

    float m_sideWidthBase   = 2.0f;
    float m_sideWidthFactor = 1.0f;
    float m_sideWidth       = 1.0f;
    float m_radiusFactor    = 1.0f;
    float m_arrowScale      = 1.0f;
    bool  m_arrowEnabled    = true;
    float m_textThresholdBase   = 0.7f;
    float m_textThresholdFactor = 1.0f;
    float m_textThresholdOff    = 0.7f;
    float m_textThresholdShow  = 1.05f;

    int m_neighborDepth = 2;  // 邻居深度，1-5


    QColor m_edgeColor      = QColor("#D5D5D5");//基础边颜色
    QColor m_edgeDimColor   = QColor("#F7F7F7");//融入背景的边颜色
    QColor m_baseColor      = QColor("#5C5C5C");//基础节点颜色
    QColor m_dimColor       = QColor("#F7F7F7");//融入背景的节点颜色
    QColor m_hoverColor     = QColor("#8F6AEE");//悬浮高亮颜色
    QColor m_textColor      = QColor("#5C5C5C");//基础文本颜色
    QColor m_textDimColor   = QColor("#F7F7F7");//文字融入背景色（与 m_edgeDimColor 一致）
    QColor m_backgroundColor = QColor(255, 255, 255);//背景颜色


    std::vector<uint8_t> m_neighborMask;
    std::vector<uint8_t> m_lastNeighborMask;
    std::vector<int>    m_visibleIndices;
    std::vector<int>    m_visibleEdges;
    std::vector<uint8_t> m_nodeMask;

    std::vector<int> m_groupBase;//节点分组，普通节点
    std::vector<int> m_groupDim;//变暗的节点
    std::vector<int> m_groupHover;//悬停与周边要突出显示的节点

    int   m_hoverIndex     = -1;
    int   m_lastHoverIndex = -1;
    int   m_selectedIndex  = -1;
    bool  m_dragging       = false;
    float m_dragOffsetX    = 0.0f;
    float m_dragOffsetY    = 0.0f;

    float m_hoverStep   = 0.1f;
    float m_hoverGlobal = 0.0f;

    std::vector<int> m_lastDimEdges;
    std::vector<int> m_lastHighlightEdges;

    // Line vertex data for GL: [x, y, across] per vertex (6 vertices per edge quad)
    std::vector<float> m_lineVertsAll;
    std::vector<float> m_lineVertsDim;
    std::vector<float> m_lineVertsHighlight;

    // Arrow head vertex data for GL: [x, y, across] per vertex (3 vertices per arrow triangle)
    std::vector<float> m_arrowVertsAll;
    std::vector<float> m_arrowVertsDim;
    std::vector<float> m_arrowVertsHighlight;

    // Node instance data: interleaved [x, y, radius, r, g, b, a] per visible node (draw order)

    std::vector<float> m_nodeInstanceDataDim;
    std::vector<float> m_nodeInstanceDataRest;

    // ---- View (pan/zoom) ----
    float m_panX  = 0.0f;
    float m_panY  = 0.0f;
    float m_zoom  = 1.0f;
    int   m_viewportW = 1;
    int   m_viewportH = 1;
    bool  m_isPanning = false;
    float m_panStartX = 0.0f;
    float m_panStartY = 0.0f;
    float m_panStartPanX = 0.0f;
    float m_panStartPanY = 0.0f;

    float m_lineHalfWidthScene = 0.5f;

    // ---- MSDF Text ----
    struct GlyphQuad {
        float x0, y0, x1, y1; // local position (em-normalized, origin at text left-baseline)
        float u0, v0, u1, v1; // atlas UV
    };
    struct LabelLayoutEntry {
        float totalWidth; // em-normalized total width (with kerning)
        std::vector<GlyphQuad> quads;
    };
    struct MsdfAtlasBuildResult {
        MsdfFontAtlas::AtlasData data;
        bool success = false;
        QString error;
        int buildId = 0;
    };
    std::unique_ptr<MsdfFontAtlas> m_fontAtlas;
    std::unique_ptr<MsdfTextRenderer> m_textRenderer;
    QString m_fontPath;
    float m_msdfFontSize = 8.0f;
    int m_lastAtlasGeneration = -1;
    std::unordered_map<std::string, LabelLayoutEntry> m_labelLayoutCache;
    std::vector<const LabelLayoutEntry*> m_labelLayoutByIndex;
    std::vector<float> m_textVerticesDim;    // 融入背景的文字（先画）
    std::vector<float> m_textVerticesRest;   // 正常文字（后画，压在上层）
    std::vector<float> m_textVerticesHover;  // 悬停放大文字（单独绘制以匹配缩放的 pxRange）
    // 后台 MSDF atlas 构建线程状态
    std::thread m_msdfAtlasThread;
    std::atomic<bool> m_msdfAtlasThreadRunning{false};
    std::mutex m_msdfAtlasMutex;
    bool m_msdfAtlasResultReady = false;
    MsdfAtlasBuildResult m_msdfAtlasResult;
    int m_msdfAtlasBuildId = 0;

    void rebuildMsdfAtlas();
    void startMsdfAtlasBuildAsync();
    void applyMsdfAtlasResultIfReady();
    void rebuildLabelLayoutCache();
    void buildTextVertices();

    // ---- OpenGL ----
    static constexpr float kPointSpriteMaxRadiusPixels = 12.0f;
    std::unique_ptr<GraphRenderer> m_renderer;
    float m_scenePerPixel = 0.0f;
    bool m_glReady = false;
    
    // Cached data from prepareFrame for paintGL
    bool m_cachedUsePointSprite = false;
    float m_cachedMvp[16] = {0};
    float m_cachedLeft = 0.0f;
    float m_cachedRight = 0.0f;
    float m_cachedTop = 0.0f;
    float m_cachedBottom = 0.0f;

    // ---- FPS ----
    int    m_frameCount  = 0;
    double m_lastFpsTime  = 0.0;
    float  m_currentFps   = 0.0f;
};

#endif // FORCEVIEWOPENGL_H
