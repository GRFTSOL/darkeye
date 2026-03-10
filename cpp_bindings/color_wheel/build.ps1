
#请把build.ps1拖到项目地址中执行

# 1. 设置控制台当前的页码为 UTF-8 (等同于 CMD 的 chcp 65001)
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 2. 设置 PowerShell 内部字符串处理的编码
$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. 设置路径变量（方便修改）
$projectRoot = Get-Location
$targetDir = Join-Path $projectRoot "cpp_bindings/color_wheel" #如果项目地址改了这个也要改

# 定义 VS 安装路径（请根据你的版本 Community/Professional/Enterprise 修改）
$vsPath = "C:\Program Files\Microsoft Visual Studio\2022\Community"


# 2. 定位到目标文件夹
if (Test-Path $targetDir) {
    Set-Location $targetDir
    Write-Host "find taggetDir: $targetDir" -ForegroundColor Cyan
} else {
    Write-Error "ERROR Cannot find target directory: $targetDir"
    exit
}

# 执行初始化脚本，并指定架构为 x64
& "$vsPath\Common7\Tools\Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64 -SkipAutomaticLocation

# 2. 清理并创建 build 文件夹
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}
New-Item -ItemType Directory -Force -Path "build"
Set-Location "build"

# 3. 激活 Conda 环境
# 注意：在 PS 中如果 conda activate 报错，请确保运行过 conda init powershell
conda activate avlite2  #环境变了这个也要改

# 打印当前所在目录，并用黄色高亮显示
Write-Host "`Current working directory: $((Get-Location).Path)" -ForegroundColor Yellow

# 4. 运行 CMake (使用 ` 作为换行符)
cmake -S .. -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    -DShiboken6_DIR="C:/Users/yin/anaconda3/envs/avlite2/Lib/site-packages/Shiboken6/lib/cmake/Shiboken6" `
    -DPySide6_DIR="C:/Users/yin/anaconda3/envs/avlite2/Lib/site-packages/PySide6/cmake/PySide6" `
    -DCMAKE_PREFIX_PATH="E:\Qt\6.10.1\msvc2022_64\lib\cmake"

# 5. 编译与安装
ninja
ninja install

# 6. 返回上级目录
Set-Location ../../..