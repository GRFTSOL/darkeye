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
[🎥 视频介绍](https://www.bilibili.com/video/BV162AuzXEQe/?share_source=copy_web&vd_source=e470911706e2af5719ccc7bb4efe5ff1)

# 💡 快速开始
## 下载
[![下载 Windows 版本](https://img.shields.io/badge/%20下载-Windows%20-blue?style=for-the-badge&logo=windows)](https://github.com/de4321/darkeye/releases/download/v1.2.2/DarkEye-v1.2.2.zip)
下载程序，解压,打开exe即可使用

[![下载Chrome/Edge插件](https://img.shields.io/badge/%20下载-Chrome/Edge插件%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.2.2/chrome_capture.zip)按照下面的插件安装，否则爬虫收集功能将不可用。

[![下载FireFox插件](https://img.shields.io/badge/%20下载-Firefox插件%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.2.2/firefox_capture.zip)按照下面的插件安装，否则爬虫收集功能将不可用。

## 插件安装
👉 https://de4321.github.io/darkeye/usage/#_2

## 使用
👉 https://de4321.github.io/darkeye/usage/#_3

## 版本迁移
👉 https://de4321.github.io/darkeye/faq/

现在正常情况下在设置里点击自动更新就行了，但是这个只更新了软件的本体，插件还是要手动去下载更新的。目前似乎找不到一种更好的更新插件的方式，主要是这个插件上架不了市场。

版本迁移时注意`更新浏览器插件`，由于爬虫的特殊性，这个爬虫很可能老失效。需要反馈然后人工修改。

## Jvedio迁移数据
下载下面的脚本，然后按照提示运行
[`scripts/jvedio2nfo.py`](https://raw.githubusercontent.com/de4321/darkeye/main/scripts/jvedio2nfo.py)

要求电脑上有python,然后最主要的是改地址。运行后会得到一个里面都是nfo文件的文件夹。使用软件中导入nfo就行了。

# Community

问题，想法？加入discord社区，现在社区没什么建设 https://discord.gg/3thnEguWUk

- 新手支持
“文档没看懂可以来问，现在文档属于没有状态”

- 提前知道进展
“新功能、开发进展、预发布版本会先在 Discord 讨论”

- 参与方向讨论
“想影响 roadmap，可以来参与讨论”

# 参考项目

- [mdcz](https://github.com/ShotHeadman/mdcz) 参考其中从本地视频名字中提取番号的代码，并且尝试去适配其nfo
- [Jvedio](https://github.com/hitchao/Jvedio) 接入其数据库，将数据导出
- [JavSP](https://github.com/Yuukiy/JavSP) 看看某些网站的爬虫逻辑


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
- [x] chrome/edge/firefox爬虫插件，沉浸式摘取信息，支持javtxt,javlib,javdb交互式采集信息，
- [x] 多链路爬虫，主要使用javlib,avdanyuwiki,javtxt,javdb,minnano-av,对于正规片的爬取很有效，且易过盾。
- [x] 力导向图，查看关联，承受1w节点60帧率
- [x] 搜索本地视频，进入爬虫列表
- [x] 备份系统，按私库重建喜欢的番号
- [x] json驱动外链跳转，可自定义。
- [x] 主题更改，剩下3D场景没有更改明亮黑暗
- [x] 部分截图功能，女优界面C键截图
- [x] NFO数据导入(测试中)
- [x] Jvedio数据导出NFO(测试中)
- [ ] NFO数据导出(形成共识后开发)
- [x] 自动检测下载更新


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
目前爬虫对于作品只爬取发布时间，导演，中日文标题与剧情，女优，男优(如果有)，标签，封面图片，影片长度，制作商，厂牌，系列，剧照等信息。

对女优信息的爬取只爬头像，生日，出道日，三维，身高罩杯，与曾用名，目前没有曾用名的更新机制。会有一个问题，如果一开始用的日文名是曾用名，则会有问题。

测试下来第一次爬虫一定触发javlib盾，然后基本上爬100次会遇到javdb的点击盾，交互点掉就行了。后续会研究机器点会怎么样。

软件不解决代理问题，目标网站能用浏览器打开就是能爬。


# 🚀 开发
👉 请访问：https://de4321.github.io/darkeye/development/


# 📚 文档
👉 完整文档请访问：https://de4321.github.io/darkeye/



