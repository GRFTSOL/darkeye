# DarkEye 产品宣传页

静态产品宣传网页，可托管到 GitHub Pages。

## 本地预览

在项目根目录下启动本地服务器：

```bash
# Python 3
python -m http.server 8080 --directory web

# 或使用 npx
npx serve web -p 8080
```

浏览器打开 http://localhost:8080 即可预览。

## GitHub Pages 部署

### 方式 A：使用 `docs` 目录（推荐）

1. 将 `web/` 文件夹中的**所有文件**复制到仓库根目录下的 `docs/` 目录，使 `docs/index.html` 存在。
2. 在 GitHub 仓库：**Settings** → **Pages**
3. 在 **Build and deployment** 中：
   - **Source** 选择 `Deploy from a branch`
   - **Branch** 选择 `main`（或你使用的主分支）
   - **Folder** 选择 `/docs`
4. 保存后，页面会部署到 `https://<username>.github.io/<repo>/`

### 方式 B：使用 `gh-pages` 分支

1. 新建分支 `gh-pages`
2. 将 `web/` 中的文件作为该分支的根目录内容（即 `gh-pages` 根目录下有 `index.html`、`css/`、`js/`、`assets/`）
3. 在 **Settings** → **Pages** 中：
   - **Source** 选择 `Deploy from a branch`
   - **Branch** 选择 `gh-pages`，Folder 为 `/ (root)`

### 方式 C：仅发布 `web` 子目录

若希望保留 `web` 作为子目录结构，可将 `web` 配置为 Pages 源码，或使用 GitHub Actions 从 `web/` 构建并部署到 `gh-pages`。

## 文件结构

```
web/
├── index.html      # 主页面
├── css/
│   └── styles.css  # 样式
├── js/
│   └── main.js     # 滚动渐显与交互
├── assets/
│   └── logo.svg    # Logo
└── README.md       # 本说明
```

## 技术说明

- 纯静态 HTML/CSS/JS，无构建工具依赖
- 使用 Intersection Observer 实现滚动触发渐显
- 暗色主题，适配移动端
- 字体通过 Google Fonts 加载（Noto Serif SC、Noto Sans SC）
