<div align="center">
  <a href="https://de4321.github.io/darkeye-webpage/" target="_blank">
    <img src="https://raw.githubusercontent.com/de4321/darkeye/main/resources/icons/logo.svg" alt="DarkEye" width="128" />
  </a>
  <h1>DarkEye</h1>
  <p><strong>在暗黑界睁开一只眼</strong></p>
  <p>一款完全本地、注重隐私的日本成人影片收藏与管理工具，支持浏览器插件沉浸式采集与拟物化 DVD 陈列。</p>
  <p>基于 PySide6 / Qt Quick 3D、SQLite、本地 FastAPI 与浏览器扩展协同，并含 C++ 力导向图加速；集采集、整理、分析与可视化于一体。</p>
  <br />

[![README · 简体中文][badge-readme-zh-CN]](README.md)
[![README · 繁體中文][badge-readme-zh-TW]](README.zh-TW.md)
[![README · 日本語][badge-readme-ja]](README.ja.md)

![Python][badge-python]
![Framework][badge-framework]
![Platform][badge-platform]
![License][badge-license]
![GitHub last commit][badge-last-commit]
![GitHub release][badge-release]
![GitHub Repo stars][badge-stars]
![GitHub all releases][badge-downloads]

<br />

[📖 在线文档][link-docs]
　[🎥 视频介绍][link-video]
　[🌐 官网][link-website]
　[💬 Discord][link-discord]

</div>

<p align="center">
  <a href="#download">下载与插件</a> •
  <a href="#features">特性</a> •
  <a href="#screenshots">界面预览</a> •
  <a href="#privacy">隐私与数据</a> •
  <a href="#migration">迁移与导入</a> •
  <a href="#crawler">爬虫说明</a> •
  <a href="#development">开发</a> •
  <a href="#community">社群</a> •
  <a href="#references">参考项目</a>
</p>

<div align="center">
  <a href="https://github.com/de4321/darkeye/releases" target="_blank">
    <img src="./docs/assets/show.jpg" alt="DarkEye 拟物化 DVD 陈列" width="100%" />
  </a>
</div>


---

<a id="download"></a>

## 下载与插件

<div align="center">

[![下载 Windows 版本][badge-dl-app]][link-dl-app]

<br />

[![下载 Chrome/Edge 插件][badge-dl-chrome]][link-dl-chrome]　　
[![下载 Firefox 插件][badge-dl-firefox]][link-dl-firefox]

</div>

下载程序并解压，运行 exe 即可；浏览器扩展随软件附带在 `extensions` 目录内。若需爬虫采集，请按下方文档安装**对应浏览器的一种**扩展。

### 插件安装

👉 [在线文档：插件安装](https://de4321.github.io/darkeye/usage/#_2)

### 使用说明

👉 [在线文档：使用](https://de4321.github.io/darkeye/usage/#_3)

### 版本与更新

👉 [常见问题：更新与迁移](https://de4321.github.io/darkeye/faq/)

设置中可自动更新**软件本体**；浏览器扩展因无法上架商店，仍需在 [Releases][link-releases] 手动下载更新。迁移版本时请关注**更新浏览器插件**；爬虫易随站点策略失效，需反馈后人工维护。软件不解决代理问题——目标站点能在浏览器打开，一般即可爬取。

---

<a id="features"></a>

## 特性

### 已实现

| **功能** | **说明** | **状态** |
| -------- | -------- | -------- |
| **数据管理** | 影片、女优、男优、标签的手动添加与增删查改；部分爬虫辅助 | ✅ |
| **私有数据记录** | 撸管、做爱、晨勃记录的手动添加与增删查改 | ✅ |
| **分析与图表** | 分析图表与数据展示（仍有部分未完成功能） | ✅ |
| **拟物化DVD盒子陈列** | 拟物化 DVD 陈列与收藏体验 | ✅ |
| **筛选过滤展示** | 筛选作品页面 | ✅ |
| **浏览器扩展** | Chrome / Edge / Firefox 插件沉浸式摘取；支持 javtxt、javlib、javdb 等交互式采集 | ✅ |
| **多链路爬虫** | javlib、avdanyuwiki、javtxt、javdb、minnano-av 等；正规片源爬取较有效，且易过盾 | ✅ |
| **关联图谱** | 查看关联；约 1 万节点下约 60 帧 | ✅ |
| **翻译** | LLM 翻译 + 一键覆盖翻译 | ✅ |
| **mdcz NFO导入** | [mdcz](https://github.com/ShotHeadman/mdcz) 刮削 NFO 导入 | ✅ |
| **Jvedio NFO导入** | Jvedio 数据导出 NFO（测试中） | ✅ |
| **外链跳转** | JSON 驱动外链跳转外部网站，可自定义 | ✅ |
| **本地视频链接** | 如果本地存在视频可将视频链接到数据库中 | ✅ |
| **备份** | 备份系统，按私库重建喜欢的番号 | ✅ |
| **主题** | 主题切换（3D 场景尚不完全跟随时明/暗） | ✅ |
| **截图** | 部分截图能力；女优界面 `C` 键截图 | ✅ |
| **自动更新** | 自动检测并下载更新 | ✅ |


### 计划与推进中

| **功能** | **说明** | **状态** |
| -------- | -------- | -------- |
| **NFO 导出** | 形成共识后开发；各工具实现不一，当前数据字段仍不齐 | 🔄 |

---

<a id="migration"></a>

## 迁移与导入

### mdcz 项目 NFO 导入

已支持 [mdcz](https://github.com/ShotHeadman/mdcz) 刮削产出的 NFO 导入。

👉 [在线文档：mdcz NFO](https://de4321.github.io/darkeye/usage/#mdcz-nfo)

### Jvedio 迁移数据

👉 [在线文档：Jvedio](https://de4321.github.io/darkeye/usage/#jvedio)

---

<a id="privacy"></a>

## 隐私与数据

- **数据与联网**：默认数据在程序旁的 `data/`（数据库、配置、封面与头像等，可在设置中改路径）。不会向第三方上传你的片库；联网主要来自爬虫与资源拉取，以及可选的更新检查（Cloudflare R2）、翻译（Google 或你自配的 LLM API）等。


---

<a id="screenshots"></a>

## 界面预览

### 拟物化 DVD

![收藏](docs/assets/dvd.jpg)

![展开](docs/assets/dvd2.jpg)

![女优](docs/assets/actress.jpg)

### 力导向图

![力导向图](docs/assets/directforceview.jpg)

### 分析图表

![图表](docs/assets/chart.jpg)

### 瀑布流

![多作品](docs/assets/mutiwork.jpg)

### 作品编辑

![编辑界面](docs/assets/edit.jpg)

### 浏览器扩展（以 javtxt 为例）

打开扩展后与本机交互，可点击添加并自动触发爬虫写入本地，另支持 javlib、javdb。界面中的「收藏 / 收录」等能力仅在连接本机软件时可用。

![javtxt 网站为例](docs/assets/capture.JPG)

---

<a id="crawler"></a>

## 爬虫说明

目前爬虫对作品会尽力获取：发布时间、导演、中日文标题与剧情、女优、男优（若有）、标签、封面、片长、制作商、厂牌、系列、剧照等。

对女优信息主要获取：头像、生日、出道日、三围、身高罩杯、曾用名（尚无曾用名更新机制；若初始使用曾用名可能导致数据问题）。

首次爬取往往会触发 javlib 盾；约百次量级可能遇到 javdb 点击盾，按页面提示操作即可。

---

<a id="development"></a>

## 开发

👉 [开发文档](https://de4321.github.io/darkeye/development/)

---

<a id="community"></a>

## 社群

有问题或想法？欢迎加入 Discord：[加入社群][link-discord]

- **新手支持**：文档阅读中有疑问欢迎提问；在线文档持续完善中。
- **提前获知进展**：新功能、开发进展与预发布版本会先在 Discord 讨论。
- **参与方向**：想影响 roadmap，欢迎来讨论。

---

<a id="references"></a>

## 参考项目

- [mdcz](https://github.com/ShotHeadman/mdcz)：本地视频名提取番号与 NFO 适配参考
- [Jvedio](https://github.com/hitchao/Jvedio)：数据库接入与导出
- [JavSP](https://github.com/Yuukiy/JavSP)：部分站点爬虫逻辑参考
- [JAV-JHS](https://sleazyfork.org/zh-CN/scripts/558525-jav-jhs)：javdb、FC2 等信息参考
- [JAV_MovieManager](https://github.com/4evergaeul/JAV_MovieManager)
- [stash](https://github.com/stashapp/stash)
- [AMMDS](https://github.com/QYG2297248353/AMMDS-Docker)
- [mdc-ng](https://github.com/mdc-ng/mdc-ng)

---

## 贡献者

<a href="https://github.com/de4321/darkeye/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=de4321/darkeye" alt="Contributors" width="500" />
</a>

---

<div align="center" style="color: gray;">DarkEye — 本地收藏，安心整理。</div>

<!-- Badge images -->

[badge-readme-zh-CN]: https://img.shields.io/badge/README%20%C2%B7%20%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-2ea44f?style=for-the-badge
[badge-readme-zh-TW]: https://img.shields.io/badge/README%20%C2%B7%20%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87-555555?style=for-the-badge
[badge-readme-ja]: https://img.shields.io/badge/README%20%C2%B7%20%E6%97%A5%E6%9C%AC%E8%AA%9E-555555?style=for-the-badge
[badge-python]: https://img.shields.io/badge/Python-3.13-blue.svg
[badge-framework]: https://img.shields.io/badge/framework-PySide6%20(Qt6)-orange
[badge-platform]: https://img.shields.io/badge/Platform-Windows-blue
[badge-license]: https://img.shields.io/github/license/de4321/darkeye
[badge-last-commit]: https://img.shields.io/github/last-commit/de4321/darkeye
[badge-release]: https://img.shields.io/github/v/release/de4321/darkeye
[badge-stars]: https://img.shields.io/github/stars/de4321/darkeye?style=social
[badge-downloads]: https://img.shields.io/github/downloads/de4321/darkeye/total
[badge-dl-app]: https://img.shields.io/badge/%E4%B8%8B%E8%BD%BD-Windows-blue?style=for-the-badge&logo=windows
[badge-dl-chrome]: https://img.shields.io/badge/%E4%B8%8B%E8%BD%BD-Chrome%2FEdge%20%E6%8F%92%E4%BB%B6-blue?style=for-the-badge
[badge-dl-firefox]: https://img.shields.io/badge/%E4%B8%8B%E8%BD%BD-Firefox%20%E6%8F%92%E4%BB%B6-blue?style=for-the-badge

<!-- Links -->

[link-docs]: https://de4321.github.io/darkeye/
[link-video]: https://youtu.be/VCsw1D0ccgY?si=e9typx4kPnzaVFZq
[link-website]: https://de4321.github.io/darkeye-webpage/
[link-discord]: https://discord.gg/3thnEguWUk
[link-releases]: https://github.com/de4321/darkeye/releases
[link-dl-app]: https://github.com/de4321/darkeye/releases/download/v1.2.4/DarkEye-v1.2.4.zip
[link-dl-chrome]: https://github.com/de4321/darkeye/releases/download/v1.2.4/chrome_capture.zip
[link-dl-firefox]: https://github.com/de4321/darkeye/releases/download/v1.2.4/firefox_capture.zip
