

# DarkEye - 在暗黑界睁开一只眼
一个暗黑影片收藏软件，专注沉浸式采集与拟物化收藏。使用PySide6，qtquick3D做GUI，sqlite数据存储，firefox爬虫，C++加速力导向图。集采集，收藏，分析于一体的软件。

![Python](https://img.shields.io/badge/Python-3.14-blue.svg)
![License](https://img.shields.io/github/license/de4321/darkeye)
![GitHub Repo stars](https://img.shields.io/github/stars/de4321/darkeye?style=social)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)

https://de4321.github.io/darkeye-webpage/

# 开发方向
1.0 基础工具的完善，包括力导向图探索影片之间的关系
2.0 UGC，分布式同步数据
3.0 机器学习推荐算法

## 特性
- [x] 影片的手动添加，增删查改，部分爬虫
- [x] 女优的手动添加，增删查改，部分爬虫
- [x] 男优的手动添加，增删查改
- [x] 标签的手动添加，增删查改
- [x] 撸管记录的手动添加，增删查改
- [x] 做爱记录的手动添加，增删查改
- [x] 晨勃记录的手动添加，增删查改
- [x] 分析图表,数据展示
- [x] 拟物化dvd展示
- [x] 筛选作品页面
- [x] firefox爬虫插件，沉浸式摘取信息，支持javtxt,javlib,javdb
- [x] 力导向图，查看关联
- [x] 搜索本地视频，进入爬虫列表
- [ ] 备份系统
- [ ] 科普知识
- [ ] 插件化网页跳转
- [ ] 插件化爬虫
- [ ] 绿色模式

拟物化的dvd
![收藏](docs/assets/dvd.jpg)
![展开](docs/assets/dvd2.jpg)
![](docs/assets/actress.jpg)

图谱发现关系
![力导向图](docs/assets/directforceview.jpg)
分析研究数据
![](docs/assets/chart.jpg)
![](docs/assets/mutiwork.jpg)
![编辑界面](docs/assets/edit.jpg)

下面以javtxt为例展示爬虫插件，打开插件后，会与本地交互，可点击添加，自动启动爬虫爬取信息到本地，另外支持javlib与javdb，
![](docs/assets/capture.JPG)



# 快速开始
#使用下面创建虚拟环境
conda create -n avlite python=3.14
conda activate avlite

pip install -r requirements.txt

下载后请复制public基本数据包到resource/文件夹下面

## 插件安装
在firefox中
1. 打开临时加载界面
在地址栏输入：about:debugging
左边点 “This Firefox”（此 Firefox）

在 “This Firefox” 页面中，点击 “Load Temporary Add-on…”（加载临时附加组件）
在弹出的文件选择框里，选中extensions/firefox下的 manifest.json 文件
确认后，插件会立即被加载，图标会出现在工具栏/扩展列表中

## 运行
vscode解释器选择
Ctrl + Shift + P

```
Python: Select Interpreter
```
avlite
python main.py


# 使用
装好浏览器插件，启动软件，然后上javdb,点击收录开始采集

如果本地有片，可以在设置->视频里添加片的位置，然后在管理->批量操作->查找本地视频并录入添加，爬虫会慢慢启动爬取。速度很慢设置了20s一次。

快捷键w手动添加番号



# 打包发布
在powershell里，刚刚创建的conda 虚拟环境中，运行build-pyinstaller.ps1
打包后的结构，一个绿色的可移动的文件夹，运行main.exe就能运行，这个pyinstaller是高度精简后的，如果要多加库，需要改里面的文件


# 文档的构建
mkdocs serve
mkdocs build  构建的位置是在site
