#ifndef GRAPHRENDERER_H
#define GRAPHRENDERER_H

#include <vector>

class QOpenGLFunctions_3_3_Core;

class GraphRenderer
{
public:
    GraphRenderer() = default;
    ~GraphRenderer() = default;

    bool initialize(QOpenGLFunctions_3_3_Core* gl);
    void cleanup();

    void drawLines(const std::vector<float>& verts, const float* colorRgba, const float* mvp);
    void drawNodes(const std::vector<float>& instanceData, bool usePointSprite, float scenePerPixel, const float* mvp);

private:
    QOpenGLFunctions_3_3_Core* m_gl = nullptr;

    unsigned int m_lineProgram = 0;
    unsigned int m_nodeProgram = 0;
    unsigned int m_nodePointProgram = 0;
    int m_lineUniformMvp = -1;
    int m_lineUniformColor = -1;
    int m_nodeUniformMvp = -1;
    int m_nodePointUniformMvp = -1;
    int m_nodePointUniformScenePerPixel = -1;

    unsigned int m_lineVao = 0;
    unsigned int m_lineVbo = 0;
    unsigned int m_nodeVao = 0;
    unsigned int m_nodeVbo = 0;
    unsigned int m_quadVbo = 0;
    unsigned int m_nodePointVao = 0;
    unsigned int m_nodePointVbo = 0;
};

#endif // GRAPHRENDERER_H
