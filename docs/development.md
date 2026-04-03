

## 开发环境准备
### python环境
1. 用conda的输入下面指令

```
conda create -n venv python=3.13
conda activate venv
pip install -e ".[docs]"
```

2. 复制resources/develop_resources 复制到data下面

简单来说就是运行脚本scripts/develop_pre.ps1


### C++ qt环境(如果要修改绑定项目)
安装qt6.10.1

vs2022，选择C++桌面开发

下载第三方C++包




### 开发前准备
下载后请运行`scripts/develop_pre.ps1`

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


### 代码规范

官方样式指南，约定包括：
缩进：4 个空格，不用 Tab 混用。
行长：常见约定每行 ≤79（文档/注释）或 ≤88/100（很多项目用工具放宽）。
命名：模块/包 lowercase；类 CapWords；函数/方法/变量 lower_with_underscores；常量 ALL_CAPS；私有约定 _leading_underscore。
qt信号，小驼峰

导入：标准库 → 第三方 → 本地，各组空一行；尽量不用 import *。
空格：运算符两侧、逗号后等留白习惯；不在括号里无故加空格。
字符串：与同文件已有风格一致；无特殊理由可优先双引号或统一用一种。
PEP 257
docstring 的写法和格式约定。

类型注解
PEP 484 及后续（typing / | 联合类型等），是否强制由项目决定。

使用black作为代码的风格的整理


## 打包发布
在powershell里，刚刚创建的conda 虚拟环境中，运行build-pyinstaller.ps1，这个是快速打包，大概打包时间200s，
确定无问题后，可以用build-nuitka.ps1打包，这个打包后提升速度，但是包体大一点，打包时间3000s
打包后的结构，一个绿色的可移动的文件夹，运行main.exe就能运行，这个pyinstaller是高度精简后的，如果要多加库，需要改里面的文件

现在的打包属于激进排除，几乎把不需要的dll文件全删除了，所以当需要用到新的东西时很可能少dll。需要重新修改打包的配置





