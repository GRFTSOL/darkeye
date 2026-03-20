# 这个脚本是开发前的准备
# 获取脚本所在目录（scripts）以及项目根目录
$scriptDir = $PSScriptRoot
$rootDir   = Split-Path -Parent $scriptDir

$src  = Join-Path $rootDir "resources\develop_resources"
$dest = Join-Path $rootDir "data"          # 目标文件夹：data（将把 develop_resources 移进去）

# 确保 data 目录存在
if (!(Test-Path $dest)) {
  New-Item -ItemType Directory -Path $dest | Out-Null
}

# 将 develop_resources 下的文件夹及内容复制到 data
Copy-Item -Path "$src\*" -Destination $dest -Recurse -Force