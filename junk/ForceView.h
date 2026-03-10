#ifndef FORCEVIEW_H
#define FORCEVIEW_H

#include <QGraphicsView>
#include <QGraphicsScene>
#include <QTimer>
#include <QVector>
#include <QStringList>
#include <QRectF>
#include <QGraphicsLineItem>

#include <memory>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>

#include "PhysicsState.h"
#include "Simulation.h"
#include "Forces.h"
#include "NodeLayer.h"

#ifdef BINDINGS_BUILD
#  define FORCEVIEW_EXPORT Q_DECL_EXPORT
#else
#  define FORCEVIEW_EXPORT Q_DECL_IMPORT
#endif

/**
 * ForceView — QGraphicsView that owns a force-directed simulation + renderer.
 *
 * Public API designed for Python (via Shiboken): call setGraph() with flat
 * arrays, connect to Qt signals for business events.
 *
 * Merges the roles of the Python ForceView + ForceGraphController,
 * eliminating multi-process IPC entirely.
 */
class FORCEVIEW_EXPORT ForceView : public QGraphicsView
{
    Q_OBJECT

public:
    explicit ForceView(QWidget* parent = nullptr);
    ~ForceView() override;

    // ======================== Graph Data ========================
    /**
     * Load / replace graph.  All arrays are flat and ordered by node index.
     *
     * @param nNodes  Number of nodes.
     * @param edges   Flat [src0, dst0, src1, dst1, …], length 2*E.
     * @param pos     Flat [x0, y0, x1, y1, …], length 2*N.
     * @param id      Length N (external node id per node); used for display and signals.
     * @param labels  Length N (display name per node).
     * @param radii      Length N (display radius per node).
     * @param nodeColors Optional length N (per-node color); empty = use layer defaults.
     */
    void setGraph(int nNodes,
                  const QVector<int>&   edges,
                  const QVector<float>& pos,
                  const QStringList&    id,
                  const QStringList&    labels,
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

    // ======================== Misc ========================
    void setDragging(int nodeId, bool dragging);
    QRectF getContentRect() const;

signals:
    void nodeLeftClicked(const QString& nodeId);
    void nodeRightClicked(const QString& nodeId);
    void nodeHovered(const QString& nodeId);
    void nodePressed(const QString& nodeId);
    void nodeReleased(const QString& nodeId);
    void scaleChanged(float scale);
    void fpsUpdated(float fps);
    void paintTimeUpdated(float ms);
    void tickTimeUpdated(float ms);
    void simulationStarted();
    void simulationStopped();

protected:
    void wheelEvent(QWheelEvent* event) override;
    void resizeEvent(QResizeEvent* event) override;
    void scrollContentsBy(int dx, int dy) override;
    void closeEvent(QCloseEvent* event) override;

private slots:
    void onSimTick();
    void onRenderTick();
    void maybeStopRenderTimer();

    // NodeLayer signal forwarders (receive nodeId from NodeLayer)
    void onNodePressed(const QString& nodeId);
    void onNodeDragged(const QString& nodeId);
    void onNodeReleased(const QString& nodeId);
    void onNodeLeftClicked(const QString& nodeId);
    void onNodeRightClicked(const QString& nodeId);
    void onNodeHovered(const QString& nodeId);

private:
    void setupTimers();
    void ensureRenderTimerRunning();
    void requestRenderActivity();
    void rebuildSimulation();    // (re-)create Simulation + Forces from current params
    void connectNodeLayer();
    void startSimThread();
    void stopSimThread();
    void simLoop();

    // ---- Owned objects ----
    QGraphicsScene* m_scene     = nullptr;
    NodeLayer*      m_nodeLayer = nullptr;   // owned by scene

    std::unique_ptr<PhysicsState> m_physicsState;
    std::unique_ptr<Simulation>   m_simulation;
    std::thread m_simThread;
    std::atomic<bool> m_simThreadRunning{false};
    std::mutex m_simMutex;

    // ---- Graph metadata (used for neighbor lookup, etc.) ----
    std::vector<std::vector<int>> m_neighbors;
    QStringList m_ids;               // length N: external id per node (QString)

    // ---- Timers ----
    QTimer* m_simTimer    = nullptr;   // 16 ms — drives simulation tick
    QTimer* m_renderTimer = nullptr;   // 16 ms — drives repaint
    QTimer* m_idleTimer   = nullptr;   // 1000 ms single-shot — stops render when idle
    bool    m_renderActive = false;

    // ---- View state ----
    float m_scaleFactor = 1.0f;

    // ---- Force parameters ----
    float m_manyBodyStrength  = 10000.0f;
    float m_linkStrength      = 0.3f;
    float m_linkDistance      = 30.0f;
    float m_centerStrength    = 0.01f;
    float m_collisionRadius   = 10.0f;
    float m_collisionStrength = 50.0f;

    std::atomic<bool> m_simActive{false};
    std::atomic<bool> m_allowWarmup{false};

    // Coordinate axis items (for show_coordinate_sys — retained for compat)
    QList<QGraphicsLineItem*> m_axisItems;
};

#endif // FORCEVIEW_H
