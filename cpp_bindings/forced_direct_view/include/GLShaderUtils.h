#ifndef GL_SHADER_UTILS_H
#define GL_SHADER_UTILS_H

#include <QDebug>
#include <QOpenGLFunctions_3_3_Core>

inline unsigned int compileShader(QOpenGLFunctions_3_3_Core* gl, unsigned int type, const char* src)
{
    unsigned int sh = gl->glCreateShader(type);
    gl->glShaderSource(sh, 1, &src, nullptr);
    gl->glCompileShader(sh);
    int ok = 0;
    gl->glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char buf[512];
        gl->glGetShaderInfoLog(sh, sizeof(buf), nullptr, buf);
        qCritical("GLShaderUtils: %s shader compile failed:\n%s",
            type == GL_VERTEX_SHADER ? "Vertex" : "Fragment", buf);
        gl->glDeleteShader(sh);
        return 0;
    }
    return sh;
}

inline unsigned int linkProgram(QOpenGLFunctions_3_3_Core* gl, unsigned int vs, unsigned int fs)
{
    unsigned int prog = gl->glCreateProgram();
    gl->glAttachShader(prog, vs);
    gl->glAttachShader(prog, fs);
    gl->glLinkProgram(prog);
    gl->glDeleteShader(vs);
    gl->glDeleteShader(fs);
    int ok = 0;
    gl->glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    if (!ok) {
        char buf[512];
        gl->glGetProgramInfoLog(prog, sizeof(buf), nullptr, buf);
        qCritical("GLShaderUtils: program link failed:\n%s", buf);
        gl->glDeleteProgram(prog);
        return 0;
    }
    return prog;
}

#endif // GL_SHADER_UTILS_H
