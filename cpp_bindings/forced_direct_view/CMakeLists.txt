cmake_minimum_required(VERSION 3.16)
project(forceview LANGUAGES CXX)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_PREFIX_PATH "E:/Qt/6.10.1/msvc2022_64")
# 2. 查找 Qt 库（确保你的环境变量里有 Qt 路径，或者手动指定 CMAKE_PREFIX_PATH）
find_package(Qt6 REQUIRED COMPONENTS Widgets)

# 1. 自动处理 Qt 的元对象编译 (MOC)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

qt_add_executable(forceview
    src/main.cpp
    src/MainWindow.cpp
    src/MyCustomWidget.cpp
    include/MainWindow.h
    include/MyCustomWidget.h
)

target_include_directories(forceview PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/eigen-5.0.1
)

# 链接库
target_link_libraries(forceview PRIVATE Qt6::Widgets)

# Optional: generate deploy script for packaging (windeployqt at install time)
qt_generate_deploy_app_script(
    TARGET forceview
    OUTPUT_SCRIPT deploy_script
)
install(SCRIPT ${deploy_script})
