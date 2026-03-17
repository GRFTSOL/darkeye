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


# 💡 快速开始
## 下载
[![下载 Windows 版本](https://img.shields.io/badge/%20下载-Windows%20-blue?style=for-the-badge&logo=windows)](https://github.com/de4321/darkeye/releases/download/v1.1.1/DarkEye.7z)
下载程序，解压,打开exe即可使用

[![下载FireFox插件](https://img.shields.io/badge/%20下载-Firefox插件%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.1.1/firefox_capture.7z)按照下面的插件安装，否则爬虫收集功能将不可用。

## 插件安装
在 Firefox 中
1. 打开临时加载界面
在地址栏输入`about:debugging`
左边点 “This Firefox”（此 Firefox）

2. 在 “This Firefox” 页面中，点击 “Load Temporary Add-on…”（加载临时附加组件）。在弹出的文件选择框里，选中解压后firefox_capture的 manifest.json 文件，确认后，插件会立即被加载，图标会出现在工具栏/扩展列表中。


## 使用
启动后有闪一下属于正常现象，需要加载opengl环境，这个我目前无法解决这个闪一下的问题。

下面是三种方式收藏与采集片子的数据。

1. 装好浏览器插件，启动软件，然后上javdb或者javlibrary或者javtxt,点击收录开始采集。
2. 如果本地有片，可以在设置->视频里添加片的位置，然后在管理->批量操作->查找本地视频并录入添加，爬虫会慢慢启动爬取。速度很慢设置了20s一次。现在这个识别很不准。
3. 快捷键w手动添加番号

当采集时会弹出firefox窗口，javlibrary第一次需要点击一次过cloudflare盾，大概这个过盾可以持续20分钟。

采集女优数据，这个自动化会非常的不准，在点击女优栏后右键可以到编辑界面，点击爬虫直接更新，但是这个仅限于无重名女优。有重名女优需要用浏览器插件手动选择更新。

更详细的使用说明参考[help](resources/help/help.md) 


## 版本迁移
所有的数据库文件均在resources/public和resources/private这两个文件夹的下面

在没有数据库迁移工具时只能手动复制主要的文件夹，resources/public和resources/private，把对应的文件夹移动到新版本的对应的位置就行了。

有迁移工具后，点击备份私库与公库，然后选择电脑上的一个位置，用新的版本点击还原后选择对应的meta.json和.db文件然后重启软件。现在暂时做不到无缝，总有问题。

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
- [x] 影片的手动添加，增删查改，部分爬虫
- [x] 女优的手动添加，增删查改，部分爬虫
- [x] 男优的手动添加，增删查改
- [x] 标签的手动添加，增删查改
- [x] 撸管记录的手动添加，增删查改
- [x] 做爱记录的手动添加，增删查改
- [x] 晨勃记录的手动添加，增删查改
- [x] 分析图表,数据展示,还有部分未完成
- [x] 拟物化dvd展示
- [x] 筛选作品页面
- [ ] tag计算器，高级tag过滤系统，tag重定向
- [x] firefox爬虫插件，沉浸式摘取信息，支持javtxt,javlib,javdb交互式摘取信息，
- [x] 多链路爬虫，主要使用javlib,avdanyuwiki,javtxt,javdb,对于正规片的爬取很有效，且易过盾。
- [x] 力导向图，查看关联，承受1w节点60帧率
- [x] 搜索本地视频，进入爬虫列表
- [ ] graph系统的更改，关联算法
- [x] 备份系统，按私库重建喜欢的番号
- [ ] 科普知识与持续更新
- [x] json驱动外链跳转
- [ ] 插件化爬虫
- [ ] 绿色模式，现在实现了一半，不过貌似没用
- [x] 主题更改，剩下3D场景没有更改明亮黑暗
- [ ] i18n,未来打算支持简体中文，繁体中文，日文，韩文与一切能支持竖排的语言。
- [ ] 以竖排风格为核心，优化UI的界面
- [ ] 编辑界面高级停靠系统的保存
- [ ] 其他格式的信息导出功能，目前只能导.csv，还没想好怎么导出
- [x] 部分截图功能，女优界面C键截图
- [ ] 安装版本，减少换版本时手动切换数据库

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

# 文档

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