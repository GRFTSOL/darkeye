#include "MsdfTextRenderer.h"
#include "GLShaderUtils.h"

#include <QOpenGLFunctions_3_3_Core>

static const char* kTextVS = R"(
#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUV;
layout(location = 2) in vec4 aColor;
uniform mat4 uMVP;
out vec2 vUV;
out vec4 vColor;
void main() {
    gl_Position = uMVP * vec4(aPos, 0.0, 1.0);
    vUV = aUV;
    vColor = aColor;
}
)";

static const char* kTextFS = R"(
#version 330 core
in vec2 vUV;
in vec4 vColor;
uniform sampler2D uAtlas;
uniform float uScreenPxRange;
out vec4 fragColor;
float median(float r, float g, float b) {
    return max(min(r, g), min(max(r, g), b));
}
void main() {
    vec3 msdf = texture(uAtlas, vUV).rgb;
    float sd = median(msdf.r, msdf.g, msdf.b);
    float screenPxDist = uScreenPxRange * (sd - 0.5);
    float alpha = clamp(screenPxDist + 0.5, 0.0, 1.0);
    alpha *= vColor.a;
    fragColor = vec4(vColor.rgb * alpha, alpha);
}
)";

bool MsdfTextRenderer::initialize(QOpenGLFunctions_3_3_Core* gl)
{
    m_gl = gl;

    unsigned int vs = compileShader(gl, GL_VERTEX_SHADER, kTextVS);
    unsigned int fs = compileShader(gl, GL_FRAGMENT_SHADER, kTextFS);
    if (!vs || !fs) {
        if (vs) gl->glDeleteShader(vs);
        if (fs) gl->glDeleteShader(fs);
        return false;
    }
    m_program = linkProgram(gl, vs, fs);
    if (!m_program) return false;

    m_uniformMvp = gl->glGetUniformLocation(m_program, "uMVP");
    m_uniformScreenPxRange = gl->glGetUniformLocation(m_program, "uScreenPxRange");
    m_uniformAtlas = gl->glGetUniformLocation(m_program, "uAtlas");

    gl->glGenVertexArrays(1, &m_vao);
    gl->glGenBuffers(1, &m_vbo);

    gl->glBindVertexArray(m_vao);
    gl->glBindBuffer(GL_ARRAY_BUFFER, m_vbo);

    const int stride = 8 * sizeof(float);
    // aPos (location 0): vec2
    gl->glEnableVertexAttribArray(0);
    gl->glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, (void*)0);
    // aUV (location 1): vec2
    gl->glEnableVertexAttribArray(1);
    gl->glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, (void*)(2 * sizeof(float)));
    // aColor (location 2): vec4
    gl->glEnableVertexAttribArray(2);
    gl->glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, stride, (void*)(4 * sizeof(float)));

    gl->glBindVertexArray(0);

    gl->glGenTextures(1, &m_texture);
    gl->glBindTexture(GL_TEXTURE_2D, m_texture);
    gl->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    gl->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    gl->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    gl->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    gl->glBindTexture(GL_TEXTURE_2D, 0);

    return true;
}

void MsdfTextRenderer::cleanup()
{
    if (!m_gl) return;
    if (m_program) { m_gl->glDeleteProgram(m_program); m_program = 0; }
    if (m_vao)     { m_gl->glDeleteVertexArrays(1, &m_vao); m_vao = 0; }
    if (m_vbo)     { m_gl->glDeleteBuffers(1, &m_vbo); m_vbo = 0; }
    if (m_texture) { m_gl->glDeleteTextures(1, &m_texture); m_texture = 0; }
    m_atlasGeneration = -1;
}

void MsdfTextRenderer::uploadAtlas(const unsigned char* pixels, int width, int height, int generation)
{
    if (!m_gl || !m_texture || !pixels || width <= 0 || height <= 0) return;
    if (generation == m_atlasGeneration) return;

    m_gl->glBindTexture(GL_TEXTURE_2D, m_texture);
    m_gl->glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    m_gl->glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, width, height, 0,
                       GL_RGB, GL_UNSIGNED_BYTE, pixels);
    m_gl->glBindTexture(GL_TEXTURE_2D, 0);
    m_atlasGeneration = generation;
}

void MsdfTextRenderer::draw(const std::vector<float>& vertices, const float* mvp, float screenPxRange)
{
    if (!m_gl || !m_program || !m_vao || !m_texture || vertices.empty()) return;

    const int vertexCount = static_cast<int>(vertices.size()) / 8;
    if (vertexCount <= 0) return;

    m_gl->glUseProgram(m_program);
    m_gl->glUniformMatrix4fv(m_uniformMvp, 1, GL_FALSE, mvp);
    m_gl->glUniform1f(m_uniformScreenPxRange, screenPxRange);

    m_gl->glActiveTexture(GL_TEXTURE0);
    m_gl->glBindTexture(GL_TEXTURE_2D, m_texture);
    m_gl->glUniform1i(m_uniformAtlas, 0);

    m_gl->glBindVertexArray(m_vao);
    m_gl->glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
    m_gl->glBufferData(GL_ARRAY_BUFFER,
                       static_cast<long long>(vertices.size()) * sizeof(float),
                       vertices.data(), GL_STREAM_DRAW);

    m_gl->glDrawArrays(GL_TRIANGLES, 0, vertexCount);
    m_gl->glBindVertexArray(0);
}
