# DarkEye - 在暗黑界睁开一只眼
>一个完全本地，隐私导向的暗黑影片收藏软件，专注沉浸式采集与拟物化收藏软件。使用PySide6，qtquick3D做GUI，sqlite数据存储，firefox爬虫，fastapi本地与浏览器插件交互，C++加速力导向图。集采集，收藏，分析于一体的软件。

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Framework](https://img.shields.io/badge/framework-PySide6%20(Qt6)-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/github/license/de4321/darkeye)
![GitHub last commit](https://img.shields.io/github/last-commit/de4321/darkeye)
![GitHub release](https://img.shields.io/github/v/release/de4321/darkeye)
![GitHub Repo stars](https://img.shields.io/github/stars/de4321/darkeye?style=social)
![GitHub all releases](https://img.shields.io/github/downloads/de4321/darkeye/total)
[![Homepage](https://img.shields.io/badge/homepage-darkeye-blue)](https://de4321.github.io/darkeye-webpage/)
[![Discord](https://img.shields.io/discord/1482965984104153229?label=Discord&logo=discord)](https://discord.gg/3thnEguWUk)


[📖 在线文档](https://de4321.github.io/darkeye/)


# 💡 快速开始
## 下载
[![下载 Windows 版本](https://img.shields.io/badge/%20下载-Windows%20-blue?style=for-the-badge&logo=windows)](https://github.com/de4321/darkeye/releases/download/v1.1.2/DarkEye-v1.1.2.zip)
下载程序，解压,打开exe即可使用

[![下载FireFox插件](https://img.shields.io/badge/%20下载-Firefox插件%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.1.2/firefox_capture.zip)按照下面的插件安装，否则爬虫收集功能将不可用。

[![下载Chrome/Edge插件](https://img.shields.io/badge/%20下载-Chrome/Edge插件%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.1.2/chrome_capture.zip)按照下面的插件安装，否则爬虫收集功能将不可用。

## 插件安装
见文档 https://de4321.github.io/darkeye/usage/#_2

## 使用
见文档 https://de4321.github.io/darkeye/usage/#_3

## 版本迁移
见文档 https://de4321.github.io/darkeye/usage/#_8

# Community

问题，想法？加入discord社区 https://discord.gg/3thnEguWUk

- 新手支持
“文档没看懂可以来问，现在文档属于没有状态”

- 提前知道进展
“新功能、开发进展、预发布版本会先在 Discord 讨论”

- 参与方向讨论
“想影响 roadmap，可以来参与讨论”

# 🚀 开发方向
- 1.0 基础工具的完善，包括力导向图探索影片之间的关系，收藏体验的增强
- 2.0 UGC，分布式同步数据
- 3.0 机器学习推荐算法

## 特性
- [x] 影片，女优，男优，标签的手动添加，增删查改，部分爬虫
- [x] 撸管，做爱，晨勃记录的手动添加，增删查改
- [x] 分析图表,数据展示,还有部分未完成
- [x] 拟物化dvd展示
- [x] 筛选作品页面
- [x] firefox/chrome/edge爬虫插件，沉浸式摘取信息，支持javtxt,javlib,javdb交互式采集信息，
- [x] 多链路爬虫，主要使用javlib,avdanyuwiki,javtxt,javdb,对于正规片的爬取很有效，且易过盾。
- [x] 力导向图，查看关联，承受1w节点60帧率
- [x] 搜索本地视频，进入爬虫列表
- [x] 备份系统，按私库重建喜欢的番号
- [x] json驱动外链跳转
- [x] 主题更改，剩下3D场景没有更改明亮黑暗
- [x] 部分截图功能，女优界面C键截图


拟物化的dvd
![收藏](docs/assets/dvd.jpg)
![展开](docs/assets/dvd2.jpg)
![女优](docs/assets/actress.jpg)

图谱发现关系
![力导向图](docs/assets/directforceview.jpg)
分析研究数据
![图表](docs/assets/chart.jpg)
![多作品](docs/assets/mutiwork.jpg)
![编辑界面](docs/assets/edit.jpg)

下面以javtxt为例展示爬虫插件，打开插件后，会与本地交互，可点击添加，自动启动爬虫爬取信息到本地，另外支持javlib与javdb。注意下面的这个中间的收藏与与收录在网站上是没有的，只有打开插件与本地软件后才会出现。
![javtxt网站为例](docs/assets/capture.JPG)

## 爬虫
目前爬虫对于作品只爬取发布时间，导演，中日文标题与剧情，女优，男优(如果有)，标签，封面图片。没有爬影片长度，制作商，厂牌，系列等信息。
未来会加上影片长度，主要我认为影片长度不重要，av质量的好坏和影片长度无任何关系，长时间的很水。制作商与厂牌的信息目前是靠番号的常识信息推理，没有写入作品，有些番号的前缀比如AVOP和PFES这种不固定制作商的，目前就没有制作商的分类，后面都会加上去的。

对女优信息的爬取只爬头像，生日，出道日，三维，身高罩杯，与曾用名，目前没有曾用名的更新机制。会有一个问题，如果一开始用的日文名是曾用名，则会有问题。


# 🚀 开发

```
conda create -n venv python=3.13
conda activate venv
pip install -e ".[docs]"
```

下载后请复制 `resources/develop_resources/public` 基本数据包到 `resources/` 文件夹下

插件加载，需要手动的按照上面去浏览器临时加载选择extensions/firefox_capture里的manifest.json


## 运行
vscode解释器选择
Ctrl + Shift + P

```
Python: Select Interpreter
```
venv
python main.py

或者直接按F5

## 打包发布
在powershell里，刚刚创建的conda 虚拟环境中，运行build-pyinstaller.ps1，这个是快速打包，大概打包时间200s，
确定无问题后，可以用build-nuitka.ps1打包，这个打包后提升速度，但是包体大一点，打包时间3000s
打包后的结构，一个绿色的可移动的文件夹，运行main.exe就能运行，这个pyinstaller是高度精简后的，如果要多加库，需要改里面的文件

现在的打包属于激进排除，几乎把不需要的dll文件全删除了，所以当需要用到新的东西时很可能少dll。需要重新修改打包的配置

# 📚 文档
👉 完整文档请访问：https://de4321.github.io/darkeye/

[![Architecture](https://img.shields.io/badge/📐_Architecture-blue?style=for-the-badge)](docs/architecture.md)
[![Development](https://img.shields.io/badge/🧰_Development-green?style=for-the-badge)](docs/development.md)
[![Security](https://img.shields.io/badge/🔒_Security-red?style=for-the-badge)](docs/security.md)
[![Changelog](https://img.shields.io/badge/📋_Changelog-orange?style=for-the-badge)](docs/CHANGELOG.md)

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | 整体架构 |
| [Development](docs/development.md) | 开发环境 |
| [Security](docs/security.md) | 数据存储 |
| [Changelog](docs/CHANGELOG.md) | 版本更新 |