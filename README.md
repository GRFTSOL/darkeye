

# DarkEye - 在暗黑界睁开一只眼
一个暗黑影片收藏软件，专注沉浸式采集与拟物化收藏。使用PySide6，qtquick3D做GUI，sqlite数据存储，firefox爬虫，C++加速力导向图。集采集，收藏，分析于一体的软件。

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![License](https://img.shields.io/github/license/de4321/darkeye)
![GitHub Repo stars](https://img.shields.io/github/stars/de4321/darkeye?style=social)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![GitHub last commit](https://img.shields.io/github/last-commit/de4321/darkeye)
![Framework](https://img.shields.io/badge/framework-PySide6%20(Qt6)-orange)

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
- [ ] graph系统的更改，关联算法
- [x] 备份系统，按私库重建喜欢的番号
- [x] 科普知识
- [x] json驱动外链跳转
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
## 下载
[![下载 Windows 版本](https://img.shields.io/badge/⬇️%20下载-Windows%20(.exe)-blue?style=for-the-badge&logo=windows)](https://github.com/de4321/darkeye/releases/download/v1.1.1/DarkEye.7z)
下载程序，解压,打开exe即可使用
[![下载FireFox插件](https://img.shields.io/badge/⬇️%20下载-Firefox插件%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.1.1/firefox_capture.7z)

## 插件安装
在firefox中
1. 打开临时加载界面
在地址栏输入：about:debugging
左边点 “This Firefox”（此 Firefox）

在 “This Firefox” 页面中，点击 “Load Temporary Add-on…”（加载临时附加组件）
在弹出的文件选择框里，选中extensions/firefox下的 manifest.json 文件
确认后，插件会立即被加载，图标会出现在工具栏/扩展列表中

## 使用
装好浏览器插件，启动软件，然后上javdb,点击收录开始采集

如果本地有片，可以在设置->视频里添加片的位置，然后在管理->批量操作->查找本地视频并录入添加，爬虫会慢慢启动爬取。速度很慢设置了20s一次。

快捷键w手动添加番号


## 版本迁移

在没有数据库迁移工具时只能手动复制主要的文件夹，resources/public和resources/private，把对应的文件夹移动到新版本的对应的位置就行了。

有迁移工具后，点击备份私库与公库，然后选择电脑上的一个位置，用新的版本点击还原后选择对应的meta.json和.db文件然后重启软件。现在暂时做不到无缝，总有问题。

# 开发

```
conda create -n venv python=3.13
conda activate venv
pip install -e ".[docs]"
```

下载后请复制resources/develop_resources/public 基本数据包到resource/文件夹下面


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

# 文档的构建
mkdocs serve
mkdocs build  构建的位置是在site
