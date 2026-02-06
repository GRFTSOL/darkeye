# ForceView

Minimal C++ Qt 6 Widgets application, built with CMake.

## Prerequisites

- [Qt 6](https://www.qt.io/download) (Desktop component, e.g. MSVC 2019/2022 64-bit or MinGW)
- CMake 3.16+
- C++17 compiler (Visual Studio with C++ workload, or MinGW from Qt installer)

## Build

From the project root (`forceview/`), set `CMAKE_PREFIX_PATH` to your Qt installation (e.g. `C:/Qt/6.5.0/msvc2019_64` or `C:/Qt/6.5.0/mingw_64`), then configure and build:

```bash
cmake -B build -DCMAKE_PREFIX_PATH=<Qt_install_path>/<version>/<kit>
cmake --build build
```

Example (adjust paths to your system):

```bash
cmake -B build -DCMAKE_PREFIX_PATH=C:/Qt/6.5.0/msvc2019_64
cmake --build build --config Release
```

## Run

- **From build tree**: Run `build\Debug\forceview.exe` or `build\Release\forceview.exe`. If Qt DLLs are not in PATH, the app may fail to start.
- **Standalone**: Copy the built `.exe` into a folder, then run `windeployqt` on that folder so Qt DLLs and plugins are deployed:

  ```bash
  windeployqt build\Release\forceview.exe
  ```

  Then run `build\Release\forceview.exe` (or copy the whole `Release` directory to another location and run from there).

## 编译（命令行）

在项目根目录打开终端（PowerShell 或 “x64 Native Tools Command Prompt for VS”），执行：

```powershell
# 1. 配置（把路径改成你的 Qt 安装目录）
cmake -B build -DCMAKE_PREFIX_PATH=C:/Qt/6.5.0/msvc2019_64 -A x64

# 2. 编译 Debug（可断点调试）
cmake --build build --config Debug

# 或编译 Release（发布用）
cmake --build build --config Release
```

可执行文件位置：`build\Debug\forceview.exe` 或 `build\Release\forceview.exe`。

## 调试

### 方式一：Qt Creator（推荐）

1. 打开 [Qt Creator](https://www.qt.io/product/qt-creator)，**文件 → 打开文件或项目**，选择本项目的 `CMakeLists.txt`。
2. 选择 Kit（如 “Desktop Qt 6.x.x MSVC2019 64bit”），点击 **Configure Project**。
3. 左下角选择 **Debug**，点击 **锤子** 编译，点击 **绿色三角** 运行，**虫子图标** 进入调试。
4. 在源码行号左侧点击即可下断点，F5 继续、F10 单步跳过、F11 单步进入。

### 方式二：Visual Studio

1. 先用命令行生成 VS 解决方案（同上，`cmake -B build -DCMAKE_PREFIX_PATH=...`）。
2. 用 Visual Studio **打开** `build\forceview.sln`。
3. 在解决方案资源管理器中右键 **forceview** → **设为启动项目**。
4. 顶部选择 **Debug**、**x64**，在 `main.cpp` 或 `MainWindow.cpp` 里设断点，按 **F5** 开始调试。

### 方式三：VS Code

1. 安装扩展：**C/C++**、**CMake Tools**。
2. 打开项目文件夹，`Ctrl+Shift+P` → **CMake: Configure**，选择 Kit（含 Qt 的 MSVC 或 MinGW）。
3. 在 `CMakeLists.txt` 或状态栏选择 **Debug**，**CMake: Build** 编译。
4. 在 `src/main.cpp` 行号左侧点一下设断点，**Run and Debug**（或 F5），选择 **C++ (Windows)** 或 **CMake: debug forceview** 即可开始调试。

若 VS Code 找不到 Qt DLL，在 `.vscode/launch.json` 里为对应配置加上环境变量，把 Qt 的 `bin` 目录加入 `PATH`，例如：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug forceview",
      "type": "cppvsdbg",
      "request": "launch",
      "program": "${workspaceFolder}/build/Debug/forceview.exe",
      "cwd": "${workspaceFolder}",
      "environment": [{"name": "PATH", "value": "C:/Qt/6.5.0/msvc2019_64/bin;${env:PATH}"}]
    }
  ]
}
```

（将 `C:/Qt/6.5.0/msvc2019_64` 换成你的 Qt 安装路径。）

## Project layout

- `CMakeLists.txt` — CMake + Qt6 configuration
- `src/main.cpp` — Application entry, `QApplication` and main window
- `src/MainWindow.cpp` / `include/MainWindow.h` — Main window (Qt Widgets)
