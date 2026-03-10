#include "GraphRenderer.h"
#include "GLShaderUtils.h"

#include <QDebug>
#include <QOpenGLFunctions_3_3_Core>

#if defined(DEBUG) || defined(QT_DEBUG)
static void checkGLError(QOpenGLFunctions_3_3_Core* gl, const char* op) {
    for (GLenum err; (err = gl->glGetError()) != GL_NO_ERROR; ) {
        qWarning("GraphRenderer: OpenGL error 0x%X after %s", err, op);
    }
}
#define GL_CHECK(gl, op) do { (op); checkGLError(gl, #op); } while(0)
#else
#define GL_CHECK(gl, op) (op)
#endif


//有数据后怎么画，都在这个代码里

// ========== Shaders ==========
// 说明：顶点着色器
// 功能：将输入的 2D 位置（aPos）转换为 MVP 变换后的屏幕坐标（gl_Position）
static const char* lineVertSrc = R"(
#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in float aAcross;//到线中心的横向位置，顶点传入
uniform mat4 uMvp;
out float vAcross;//传递到片元用于计算透明
void main() {
    vAcross = aAcross;
    gl_Position = uMvp * vec4(aPos, 0.0, 1.0);
}
)";

// 说明：片元着色器
// 功能：将输入的颜色（uColor）直接输出为片段颜色（fragColor）
static const char* lineFragSrc = R"(
#version 330 core
uniform vec4 uColor;
in float vAcross;//到中心线的横向距离（归一化）
out vec4 fragColor;
void main() {
    float dist = abs(vAcross);
    float edge = fwidth(dist);
    edge = min(edge, 0.5);   // 限制过渡带宽度，避免整条线被当成“边缘”
  
    float alpha = 1.0 - smoothstep(1.0 - edge, 1.0, dist);
    float a = uColor.a * alpha;
    fragColor = vec4(uColor.rgb * a, a);
}
)";

// 生成一个四边形，移动
static const char* nodeVertSrc = R"(
#version 330 core
layout(location = 0) in vec2 aQuadPos; // 原始范围 [-1, 1]
layout(location = 1) in vec2 aCenter; // 圆心
layout(location = 2) in float aRadius; // 半径
layout(location = 3) in vec4 aColor; // 颜色

uniform mat4 uMvp;//变换矩阵

out vec4 vColor;
out vec2 vQuadPos;

void main() {
    // 1. 设置一个固定的外扩比例（比如 10%），这足以容纳任何分辨率下的抗锯齿边缘
    float paddingScale = 1.2; 
    
    // 2. 扩大顶点位置
    vec2 expandedPos = aQuadPos * paddingScale;
    vec2 worldPos = aCenter + (expandedPos * aRadius);
    
    gl_Position = uMvp * vec4(worldPos, 0.0, 1.0);
    
    // 3. 关键：将扩大后的坐标传给 Fragment
    // 这样在圆心处 vQuadPos 是 (0,0)，在圆边界处长度刚好是 1.0
    vQuadPos = expandedPos; 
    vColor = aColor;
}
)";

//不要的丢弃，就画成一个圆形
static const char* nodeFragSrc = R"(
#version 330 core
in vec4 vColor;
in vec2 vQuadPos;
out vec4 fragColor;
void main() {
    float dist = length(vQuadPos);

    // 限制过渡带宽度：缩小视图时 fwidth(dist) 会很大，导致边缘过软，用 max 保证至少 1 像素左右过渡
    float edge = fwidth(dist);
    
    // 现在的 dist 可以在 1.0 附近平滑摆动，而不会被 gl_FragCoord 之外的区域剪裁
    float alpha = 1.0 - smoothstep(1.0 - edge, 1.0 + edge, dist);

    // 如果 alpha 极小，依然可以 discard 掉以优化深度测试（可选）
    if (alpha < 0.001) discard;

    fragColor = vec4(vColor.rgb * (vColor.a * alpha), vColor.a * alpha);
}
)";

// 点精灵：缩小情况下每节点 1 顶点，gl_PointSize + gl_PointCoord 画圆
static const char* nodePointVertSrc = R"(
#version 330 core
layout(location = 0) in vec2 aCenter;
layout(location = 1) in float aRadius;
layout(location = 2) in vec4 aColor;

uniform mat4 uMvp;
uniform float uScenePerPixel;

out vec4 vColor;

void main() {
    gl_Position = uMvp * vec4(aCenter, 0.0, 1.0);
    float sizePx = 2.0 * aRadius / uScenePerPixel;
    gl_PointSize = clamp(sizePx * 1.2, 1.0, 64.0);
    vColor = aColor;
}
)";

static const char* nodePointFragSrc = R"(
#version 330 core
in vec4 vColor;
out vec4 fragColor;
void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float dist = length(uv);
    if (dist > 0.5) discard;
    float edge = fwidth(dist);
    float alpha = 1.0 - smoothstep(0.5 - edge, 0.5, dist);
    fragColor = vec4(vColor.rgb * (vColor.a * alpha), vColor.a * alpha);
}
)";

bool GraphRenderer::initialize(QOpenGLFunctions_3_3_Core* gl)
{
    m_gl = gl;
    if (!m_gl) return false;

    unsigned int lineVs = compileShader(m_gl, GL_VERTEX_SHADER, lineVertSrc);
    unsigned int lineFs = compileShader(m_gl, GL_FRAGMENT_SHADER, lineFragSrc);
    m_lineProgram = linkProgram(m_gl, lineVs, lineFs);
    if (!m_lineProgram) return false;

    unsigned int nodeVs = compileShader(m_gl, GL_VERTEX_SHADER, nodeVertSrc);
    unsigned int nodeFs = compileShader(m_gl, GL_FRAGMENT_SHADER, nodeFragSrc);
    m_nodeProgram = linkProgram(m_gl, nodeVs, nodeFs);
    if (!m_nodeProgram) return false;

    m_lineUniformMvp = m_gl->glGetUniformLocation(m_lineProgram, "uMvp");
    m_lineUniformColor = m_gl->glGetUniformLocation(m_lineProgram, "uColor");
    m_nodeUniformMvp = m_gl->glGetUniformLocation(m_nodeProgram, "uMvp");

    unsigned int nodePointVs = compileShader(m_gl, GL_VERTEX_SHADER, nodePointVertSrc);
    unsigned int nodePointFs = compileShader(m_gl, GL_FRAGMENT_SHADER, nodePointFragSrc);
    m_nodePointProgram = linkProgram(m_gl, nodePointVs, nodePointFs);
    if (!m_nodePointProgram) return false;
    m_nodePointUniformMvp = m_gl->glGetUniformLocation(m_nodePointProgram, "uMvp");
    m_nodePointUniformScenePerPixel = m_gl->glGetUniformLocation(m_nodePointProgram, "uScenePerPixel");

    m_gl->glGenVertexArrays(1, &m_nodePointVao);
    m_gl->glGenBuffers(1, &m_nodePointVbo);
    m_gl->glBindVertexArray(m_nodePointVao);
    m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_nodePointVbo);
    m_gl->glEnableVertexAttribArray(0);
    m_gl->glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 7 * sizeof(float), reinterpret_cast<void*>(0));
    m_gl->glEnableVertexAttribArray(1);
    m_gl->glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 7 * sizeof(float), reinterpret_cast<void*>(2 * sizeof(float)));
    m_gl->glEnableVertexAttribArray(2);
    m_gl->glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 7 * sizeof(float), reinterpret_cast<void*>(3 * sizeof(float)));
    m_gl->glBindVertexArray(0);
    m_gl->glBindBuffer(GL_ARRAY_BUFFER, 0);

    m_gl->glGenVertexArrays(1, &m_lineVao);
    m_gl->glGenBuffers(1, &m_lineVbo);
    m_gl->glBindVertexArray(m_lineVao);
    m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_lineVbo);
    m_gl->glEnableVertexAttribArray(0);
    m_gl->glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 3 * sizeof(float), reinterpret_cast<void*>(0));
    m_gl->glEnableVertexAttribArray(1);
    m_gl->glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 3 * sizeof(float), reinterpret_cast<void*>(2 * sizeof(float)));

    m_gl->glGenVertexArrays(1, &m_nodeVao);
    m_gl->glGenBuffers(1, &m_nodeVbo);
    m_gl->glGenBuffers(1, &m_quadVbo);

    float quad[] = { -1.f, -1.f, 1.f, -1.f, 1.f, 1.f, -1.f, -1.f, 1.f, 1.f, -1.f, 1.f };
    m_gl->glBindVertexArray(m_nodeVao);

    m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_quadVbo);
    m_gl->glBufferData(GL_ARRAY_BUFFER, sizeof(quad), quad, GL_STATIC_DRAW);

    m_gl->glEnableVertexAttribArray(0);
    m_gl->glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), nullptr);

    m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_nodeVbo);
    m_gl->glEnableVertexAttribArray(1);
    m_gl->glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 7 * sizeof(float), reinterpret_cast<void*>(0));
    m_gl->glVertexAttribDivisor(1, 1);

    m_gl->glEnableVertexAttribArray(2);
    m_gl->glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, 7 * sizeof(float), reinterpret_cast<void*>(2 * sizeof(float)));
    m_gl->glVertexAttribDivisor(2, 1);

    m_gl->glEnableVertexAttribArray(3);
    m_gl->glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 7 * sizeof(float), reinterpret_cast<void*>(3 * sizeof(float)));
    m_gl->glVertexAttribDivisor(3, 1);

    m_gl->glBindVertexArray(0);
    m_gl->glBindBuffer(GL_ARRAY_BUFFER, 0);
    return true;
}

void GraphRenderer::cleanup()
{
    if (!m_gl) return;
    if (m_lineVao) m_gl->glDeleteVertexArrays(1, &m_lineVao);
    if (m_lineVbo) m_gl->glDeleteBuffers(1, &m_lineVbo);
    if (m_nodeVao) m_gl->glDeleteVertexArrays(1, &m_nodeVao);
    if (m_nodeVbo) m_gl->glDeleteBuffers(1, &m_nodeVbo);
    if (m_quadVbo) m_gl->glDeleteBuffers(1, &m_quadVbo);
    if (m_nodePointVao) m_gl->glDeleteVertexArrays(1, &m_nodePointVao);
    if (m_nodePointVbo) m_gl->glDeleteBuffers(1, &m_nodePointVbo);
    if (m_lineProgram) m_gl->glDeleteProgram(m_lineProgram);
    if (m_nodeProgram) m_gl->glDeleteProgram(m_nodeProgram);
    if (m_nodePointProgram) m_gl->glDeleteProgram(m_nodePointProgram);

    m_lineProgram = 0;
    m_nodeProgram = 0;
    m_nodePointProgram = 0;
    m_lineUniformMvp = -1;
    m_lineUniformColor = -1;
    m_nodeUniformMvp = -1;
    m_nodePointUniformMvp = -1;
    m_nodePointUniformScenePerPixel = -1;
    m_lineVao = 0;
    m_lineVbo = 0;
    m_nodeVao = 0;
    m_nodeVbo = 0;
    m_quadVbo = 0;
    m_nodePointVao = 0;
    m_nodePointVbo = 0;
    m_gl = nullptr;
}

void GraphRenderer::drawLines(const std::vector<float>& verts, const float* colorRgba, const float* mvp)
{
    if (!m_gl || !m_lineProgram || verts.empty()) return;
    GL_CHECK(m_gl, m_gl->glUseProgram(m_lineProgram));
    GL_CHECK(m_gl, m_gl->glUniformMatrix4fv(m_lineUniformMvp, 1, GL_FALSE, mvp));
    GL_CHECK(m_gl, m_gl->glUniform4f(m_lineUniformColor, colorRgba[0], colorRgba[1], colorRgba[2], colorRgba[3]));
    GL_CHECK(m_gl, m_gl->glBindVertexArray(m_lineVao));
    GL_CHECK(m_gl, m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_lineVbo));
    GL_CHECK(m_gl, m_gl->glBufferData(GL_ARRAY_BUFFER, verts.size() * sizeof(float), verts.data(), GL_DYNAMIC_DRAW));
    GL_CHECK(m_gl, m_gl->glDrawArrays(GL_TRIANGLES, 0, static_cast<GLsizei>(verts.size() / 3)));
    GL_CHECK(m_gl, m_gl->glBindVertexArray(0));
    GL_CHECK(m_gl, m_gl->glUseProgram(0));
}

void GraphRenderer::drawNodes(const std::vector<float>& instanceData, bool usePointSprite, float scenePerPixel, const float* mvp)
{
    int n = static_cast<int>(instanceData.size() / 7);
    if (!m_gl || n <= 0) return;
    if (usePointSprite) {
        if (!m_nodePointProgram) return;
        GL_CHECK(m_gl, m_gl->glUseProgram(m_nodePointProgram));
        GL_CHECK(m_gl, m_gl->glUniformMatrix4fv(m_nodePointUniformMvp, 1, GL_FALSE, mvp));
        GL_CHECK(m_gl, m_gl->glUniform1f(m_nodePointUniformScenePerPixel, scenePerPixel));
        GL_CHECK(m_gl, m_gl->glBindVertexArray(m_nodePointVao));
        GL_CHECK(m_gl, m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_nodePointVbo));
        GL_CHECK(m_gl, m_gl->glBufferData(GL_ARRAY_BUFFER, instanceData.size() * sizeof(float), instanceData.data(), GL_DYNAMIC_DRAW));
        GL_CHECK(m_gl, m_gl->glDrawArrays(GL_POINTS, 0, n));
    } else {
        if (!m_nodeProgram) return;
        GL_CHECK(m_gl, m_gl->glUseProgram(m_nodeProgram));
        GL_CHECK(m_gl, m_gl->glUniformMatrix4fv(m_nodeUniformMvp, 1, GL_FALSE, mvp));
        GL_CHECK(m_gl, m_gl->glBindVertexArray(m_nodeVao));
        GL_CHECK(m_gl, m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_nodeVbo));
        GL_CHECK(m_gl, m_gl->glBufferData(GL_ARRAY_BUFFER, instanceData.size() * sizeof(float), instanceData.data(), GL_DYNAMIC_DRAW));
        GL_CHECK(m_gl, m_gl->glDrawArraysInstanced(GL_TRIANGLES, 0, 6, n));
    }
    GL_CHECK(m_gl, m_gl->glBindVertexArray(0));
    GL_CHECK(m_gl, m_gl->glUseProgram(0));
}
