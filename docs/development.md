

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

