#include "ForceViewOpenGL.h"
#include "MsdfFontAtlas.h"

#include <thread>
#include <mutex>
#include <string>
#include <unordered_map>

void ForceViewOpenGL::startMsdfAtlasBuildAsync()
{
    if (!m_fontAtlas || !m_fontAtlas->isReady())
        return;
    if (m_msdfAtlasThreadRunning.load(std::memory_order_acquire))
        return;

    if (m_msdfAtlasThread.joinable()) {
        m_msdfAtlasThread.join();
    }

    const MsdfFontAtlas::Config cfg = makeFontConfig();

    const QStringList labels = m_labels;
    const int buildId = m_msdfAtlasBuildId;

    m_msdfAtlasThreadRunning.store(true, std::memory_order_release);
    m_msdfAtlasThread = std::thread([this, cfg, labels, buildId]() {
        MsdfAtlasBuildResult result;
        result.buildId = buildId;
        QString error;
        MsdfFontAtlas::AtlasData data;
        if (MsdfFontAtlas::BuildAtlasStandalone(cfg, labels, data, &error)) {
            result.success = true;
            result.data = std::move(data);
        } else {
            result.success = false;
            result.error = error;
        }
        {
            std::lock_guard<std::mutex> lock(m_msdfAtlasMutex);
            m_msdfAtlasResult = std::move(result);
            m_msdfAtlasThreadRunning.store(false, std::memory_order_release);
            m_msdfAtlasResultReady = true;
        }
    });
}

void ForceViewOpenGL::applyMsdfAtlasResultIfReady()
{
    MsdfAtlasBuildResult result;
    {
        std::lock_guard<std::mutex> lock(m_msdfAtlasMutex);
        if (!m_msdfAtlasResultReady)
            return;
        result = std::move(m_msdfAtlasResult);
        m_msdfAtlasResultReady = false;
    }
    if (result.buildId != m_msdfAtlasBuildId) {
        startMsdfAtlasBuildAsync();
        return;
    }
    if (result.success && m_fontAtlas) {
        m_fontAtlas->applyAtlasData(std::move(result.data));
        rebuildLabelLayoutCache();
        m_lastAtlasGeneration = -1;
    }
}

void ForceViewOpenGL::rebuildMsdfAtlas()
{
    if (!m_fontAtlas || !m_fontAtlas->isReady()) return;
    m_fontAtlas->buildForLabels(m_labels);
    rebuildLabelLayoutCache();
}

void ForceViewOpenGL::rebuildLabelLayoutCache()
{
    m_labelLayoutCache.clear();
    if (!m_fontAtlas || !m_fontAtlas->isReady()) {
        m_labelLayoutByIndex.clear();
        return;
    }
    for (int i = 0; i < m_labels.size(); ++i) {
        std::string key = m_labels[i].toStdString();
        if (m_labelLayoutCache.count(key)) continue;
        const QList<uint> cps = m_labels[i].toUcs4();
        LabelLayoutEntry entry;
        entry.totalWidth = 0.0f;
        float cursorX = 0.0f;
        uint32_t prev = 0;
        bool hasPrev = false;
        for (const uint cpQ : cps) {
            uint32_t cp = static_cast<uint32_t>(cpQ);
            const MsdfFontAtlas::GlyphInfo* g = m_fontAtlas->findGlyph(cp);
            if (!g) continue;
            if (hasPrev) cursorX += m_fontAtlas->kerning(prev, cp);
            if (g->drawable) {
                GlyphQuad q;
                q.x0 = cursorX + g->planeLeft;
                q.y0 = g->planeBottom;
                q.x1 = cursorX + g->planeRight;
                q.y1 = g->planeTop;
                q.u0 = g->u0; q.v0 = g->v0;
                q.u1 = g->u1; q.v1 = g->v1;
                entry.quads.push_back(q);
            }
            cursorX += g->advance;
            prev = cp;
            hasPrev = true;
        }
        entry.totalWidth = cursorX;
        m_labelLayoutCache[key] = std::move(entry);
    }
    m_labelLayoutByIndex.resize(m_labels.size());
    for (int i = 0; i < m_labels.size(); ++i) {
        auto it = m_labelLayoutCache.find(m_labels[i].toStdString());
        m_labelLayoutByIndex[i] = (it != m_labelLayoutCache.end()) ? &it->second : nullptr;
    }
}

void ForceViewOpenGL::buildTextVertices()
{
    m_textVerticesDim.clear();
    m_textVerticesRest.clear();
    m_textVerticesHover.clear();
    if (!m_fontAtlas || !m_fontAtlas->isReady() || !m_physicsState) return;
    if (m_labelLayoutByIndex.size() != static_cast<size_t>(m_labels.size())) return;
    if (m_labels.size() != static_cast<size_t>(m_physicsState->nNodes)) return;

    const float scale = m_zoom;
    if (scale <= m_textThresholdOff) return;

    float baseAlpha = 1.0f;
    if (scale < m_textThresholdShow)
        baseAlpha = (scale - m_textThresholdOff) / (m_textThresholdShow - m_textThresholdOff);

    const float* pos = m_physicsState->renderPosData();
    const float dpr = devicePixelRatioF();
    const float invZoomDpr = 1.0f / (scale * dpr);
    const float fontSize = m_msdfFontSize;
    const float descent = static_cast<float>(m_fontAtlas->descender());

    const int nNodes = m_physicsState->nNodes;
    auto emitLabel = [&](int i, const QColor& color, float alpha, float fontScale, std::vector<float>& out) {
        if (i < 0 || i >= nNodes || i >= static_cast<int>(m_labelLayoutByIndex.size())) return;
        const LabelLayoutEntry* layout = m_labelLayoutByIndex[i];
        if (!layout || layout->quads.empty()) return;

        float nodeX = pos[2 * i];
        float nodeY = pos[2 * i + 1];
        float r = (i < m_showRadii.size()) ? m_showRadii[i] : kDefaultNodeRadius;
        float fs = fontSize * fontScale;

        float labelW = layout->totalWidth * fs;
        float baseX = nodeX - labelW * 0.5f;
        float baseY = nodeY + r - descent * fs + fs * 1.25f;

        float devX = baseX * scale * dpr;
        float devY = baseY * scale * dpr;
        baseX = std::round(devX) * invZoomDpr;
        baseY = std::round(devY) * invZoomDpr;

        float cr = color.redF(), cg = color.greenF(), cb = color.blueF();
        for (const GlyphQuad& q : layout->quads) {
            float x0 = baseX + q.x0 * fs;
            float y0 = baseY - q.y1 * fs;
            float x1 = baseX + q.x1 * fs;
            float y1 = baseY - q.y0 * fs;

            out.push_back(x0); out.push_back(y0);
            out.push_back(q.u0); out.push_back(q.v1);
            out.push_back(cr); out.push_back(cg); out.push_back(cb); out.push_back(alpha);

            out.push_back(x0); out.push_back(y1);
            out.push_back(q.u0); out.push_back(q.v0);
            out.push_back(cr); out.push_back(cg); out.push_back(cb); out.push_back(alpha);

            out.push_back(x1); out.push_back(y1);
            out.push_back(q.u1); out.push_back(q.v0);
            out.push_back(cr); out.push_back(cg); out.push_back(cb); out.push_back(alpha);

            out.push_back(x0); out.push_back(y0);
            out.push_back(q.u0); out.push_back(q.v1);
            out.push_back(cr); out.push_back(cg); out.push_back(cb); out.push_back(alpha);

            out.push_back(x1); out.push_back(y1);
            out.push_back(q.u1); out.push_back(q.v0);
            out.push_back(cr); out.push_back(cg); out.push_back(cb); out.push_back(alpha);

            out.push_back(x1); out.push_back(y0);
            out.push_back(q.u1); out.push_back(q.v1);
            out.push_back(cr); out.push_back(cg); out.push_back(cb); out.push_back(alpha);
        }
    };

    QColor dimTextColor = mixColor(m_textColor, m_textDimColor, m_hoverGlobal);
    for (int i : m_groupDim) emitLabel(i, dimTextColor, baseAlpha, 1.0f, m_textVerticesDim);

    for (int i : m_groupBase) emitLabel(i, m_textColor, baseAlpha, 1.0f, m_textVerticesRest);
    if (m_hoverIndex == -1) {
        for (int i : m_groupHover) emitLabel(i, m_textColor, baseAlpha, 1.0f, m_textVerticesRest);
    } else if (m_hoverIndex >= 0 && m_hoverIndex < m_labels.size()) {
        float hoverFontScale = 1.0f + m_hoverGlobal * 2.0f;
        emitLabel(m_hoverIndex, m_textColor, 1.0f, hoverFontScale, m_textVerticesHover);
    }
}
