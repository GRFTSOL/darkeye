#include <QApplication>
#include <QMainWindow>
#include <QWidget>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QGroupBox>
#include <QRadioButton>
#include <QButtonGroup>
#include <QVector>
#include <QStringList>
#include <QDebug>
#include <QLabel>
#include <cstdlib>
#include <cmath>

#include "ForceViewOpenGL.h"

/**
 * Standalone test: creates a ForceViewOpenGL with a random graph.
 * Radio buttons allow switching between three pre-generated graphs (999, 1001, 10000 nodes).
 */

static void generateRandomGraph(int nNodes, int avgDegree, unsigned int seed,
                                QVector<int>& edges,
                                QVector<float>& pos,
                                QStringList& id,
                                QStringList& labels,
                                QVector<float>& radii,
                                QVector<QColor>& nodeColors)
{
    std::srand(static_cast<unsigned int>(seed));
    // Random initial positions in a circle
    float scale = std::sqrt(static_cast<float>(nNodes)) * 25.0f + 150.0f;
    pos.resize(2 * nNodes);
    id.resize(nNodes);
    labels.resize(nNodes);
    radii.resize(nNodes);
    nodeColors.resize(nNodes);

    for (int i = 0; i < nNodes; ++i) {
        float angle = static_cast<float>(i) / nNodes * 6.2831853f;
        float r = scale * (0.3f + 0.7f * static_cast<float>(std::rand()) / RAND_MAX);
        pos[2 * i]     = r * std::cos(angle);
        pos[2 * i + 1] = r * std::sin(angle);
        id[i] = QString("ID%1").arg(i);
        labels[i] = QString("N%1").arg(i);
        radii[i]  = 4.0f + static_cast<float>(std::rand() % 7);  // 4..10
        nodeColors[i] = QColor(std::rand() % 256, std::rand() % 256, std::rand() % 256);
    }

    // Generate random edges (Poisson-distributed connections per node, matching graph.py)
    edges.clear();
    for (int i = 0; i < nNodes; ++i) {
        // -log(1 - rand) * mean, rounded (exponential approx to Poisson)
        float u = static_cast<float>(std::rand()) / (RAND_MAX + 1.0f);
        int numConnections = static_cast<int>(std::round(-std::log(1.0f - u) * avgDegree));
        for (int k = 0; k < numConnections; ++k) {
            int target = std::rand() % nNodes;
            if (target != i) {
                edges.append(i);
                edges.append(target);
            }
        }
    }

    qDebug() << "Generated graph:" << nNodes << "nodes," << edges.size() / 2 << "edges";
}

int main(int argc, char* argv[])
{
    QApplication app(argc, argv);

    // Pre-generate three graph datasets
    QVector<int>   edges1, edges2, edges3;
    QVector<float> pos1, pos2, pos3;
    QStringList    ids1, ids2, ids3;
    QStringList    labels1, labels2, labels3;
    QVector<float> radii1, radii2, radii3;
    QVector<QColor> nodeColors1, nodeColors2, nodeColors3;

    generateRandomGraph(999, 1, 42u, edges1, pos1, ids1, labels1, radii1, nodeColors1);
    generateRandomGraph(1001, 1, 99u, edges2, pos2, ids2, labels2, radii2, nodeColors2);
    generateRandomGraph(10000, 1, 123u, edges3, pos3, ids3, labels3, radii3, nodeColors3);

    // Main window
    QMainWindow mainWin;
    mainWin.setWindowTitle("ForceView OpenGL Test");
    mainWin.resize(1100, 700);

    QWidget* central = new QWidget(&mainWin);
    QHBoxLayout* mainLayout = new QHBoxLayout(central);
    mainLayout->setContentsMargins(4, 4, 4, 4);
    mainLayout->setSpacing(8);

    ForceViewOpenGL* view = new ForceViewOpenGL(central);
    view->setMinimumSize(400, 300);
    mainLayout->addWidget(view, 1);

    // Right panel: switch graph
    QWidget* panel = new QWidget(central);
    QVBoxLayout* panelLayout = new QVBoxLayout(panel);
    panelLayout->setContentsMargins(0, 0, 0, 0);

    QGroupBox* groupBox = new QGroupBox("切换图", panel);
    QVBoxLayout* groupLayout = new QVBoxLayout(groupBox);

    QRadioButton* rb1 = new QRadioButton("图1 (999节点)", groupBox);
    QRadioButton* rb2 = new QRadioButton("图2 (1001节点)", groupBox);
    QRadioButton* rb3 = new QRadioButton("图3 (10000节点)", groupBox);
    rb1->setChecked(true);

    QButtonGroup* btnGroup = new QButtonGroup(central);
    btnGroup->addButton(rb1, 0);
    btnGroup->addButton(rb2, 1);
    btnGroup->addButton(rb3, 2);

    groupLayout->addWidget(rb1);
    groupLayout->addWidget(rb2);
    groupLayout->addWidget(rb3);
    panelLayout->addWidget(groupBox);

    // 性能信息面板：展示 tick / paint 耗时与 FPS
    QGroupBox* perfGroup = new QGroupBox("性能 (ms / FPS)", panel);
    QVBoxLayout* perfLayout = new QVBoxLayout(perfGroup);
    QLabel* tickLabel  = new QLabel("Tick: -- ms", perfGroup);
    QLabel* paintLabel = new QLabel("Paint: -- ms", perfGroup);
    QLabel* fpsLabel   = new QLabel("FPS: --", perfGroup);
    perfLayout->addWidget(tickLabel);
    perfLayout->addWidget(paintLabel);
    perfLayout->addWidget(fpsLabel);
    perfLayout->addStretch();
    panelLayout->addWidget(perfGroup);

    panelLayout->addStretch();
    mainLayout->addWidget(panel, 0);

    mainWin.setCentralWidget(central);

    // Apply graph based on selected radio button
    auto applyGraph = [view, &edges1, &pos1, &ids1, &labels1, &radii1, &nodeColors1,
                       &edges2, &pos2, &ids2, &labels2, &radii2, &nodeColors2,
                       &edges3, &pos3, &ids3, &labels3, &radii3, &nodeColors3](int id) {
        if (id == 0) {
            view->setGraph(999, edges1, pos1, ids1, labels1, radii1, nodeColors1);
        } else if (id == 1) {
            view->setGraph(1001, edges2, pos2, ids2, labels2, radii2, nodeColors2);
        } else {
            view->setGraph(10000, edges3, pos3, ids3, labels3, radii3, nodeColors3);
        }
    };

    QObject::connect(btnGroup, &QButtonGroup::idClicked, applyGraph);
    applyGraph(0);  // Default: graph 1

    QObject::connect(view, &ForceViewOpenGL::nodeLeftClicked,
                     [](const QString& nodeId) { qDebug() << "Left-clicked node: id[" << nodeId << "]"; });
    QObject::connect(view, &ForceViewOpenGL::nodeHovered,
                     [](const QString& nodeId) { if (!nodeId.isEmpty()) qDebug() << "Hovered node: id:" << nodeId; });

    // 将 FPS、paint / tick 耗时显示在右侧性能面板（使用标签作为上下文对象，保证跨线程安全）
    QObject::connect(view, &ForceViewOpenGL::fpsUpdated,
                     fpsLabel,
                     [fpsLabel](float fps) {
                         fpsLabel->setText(QString("FPS: %1").arg(fps, 0, 'f', 1));
                         qDebug() << "FPS:" << fps;
                     });
    QObject::connect(view, &ForceViewOpenGL::paintTimeUpdated,
                     paintLabel,
                     [paintLabel](float ms) {
                         paintLabel->setText(QString("Paint: %1 ms").arg(ms, 0, 'f', 2));
                         qDebug() << "Paint time (ms):" << ms;
                     });
    QObject::connect(view, &ForceViewOpenGL::tickTimeUpdated,
                     tickLabel,
                     [tickLabel](float ms) {
                         tickLabel->setText(QString("Tick: %1 ms").arg(ms, 0, 'f', 2));
                         qDebug() << "Tick time (ms):" << ms;
                     });

    mainWin.show();
    return app.exec();
}
