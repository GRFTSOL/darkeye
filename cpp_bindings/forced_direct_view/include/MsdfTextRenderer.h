#ifndef MSDF_TEXT_RENDERER_H
#define MSDF_TEXT_RENDERER_H

#include <vector>

class QOpenGLFunctions_3_3_Core;

class MsdfTextRenderer
{
public:
    MsdfTextRenderer() = default;
    ~MsdfTextRenderer() = default;

    bool initialize(QOpenGLFunctions_3_3_Core* gl);
    void cleanup();

    void uploadAtlas(const unsigned char* pixels, int width, int height, int generation);

    // vertices: interleaved [x, y, u, v, r, g, b, a] per vertex, 6 vertices per glyph
    void draw(const std::vector<float>& vertices, const float* mvp, float screenPxRange);

private:
    QOpenGLFunctions_3_3_Core* m_gl = nullptr;
    unsigned int m_program = 0;
    unsigned int m_vao = 0;
    unsigned int m_vbo = 0;
    unsigned int m_texture = 0;
    int m_atlasGeneration = -1;
    int m_uniformMvp = -1;
    int m_uniformScreenPxRange = -1;
    int m_uniformAtlas = -1;
};

#endif // MSDF_TEXT_RENDERER_H
