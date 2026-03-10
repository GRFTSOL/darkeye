cmake_minimum_required(VERSION 3.26)

#项目名+语言
project(colorwheel 
    VERSION 1.0.0
    DESCRIPTION "Qt6取色轮盘"
    LANGUAGES CXX
)
# 全局设置
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
#set(CMAKE_CXX_EXTENSIONS        OFF)   # 关闭编译器扩展
set(CMAKE_INCLUDE_CURRENT_DIR ON)
set(CMAKE_AUTOMOC ON)#自动处理 Qt 的元对象编译 (MOC)
#set(CMAKE_AUTOUIC ON)#需要用到.ui文件
#set(CMAKE_AUTORCC ON)#需要用到.rcc资源时


set(CMAKE_EXPORT_COMPILE_COMMANDS ON)#VS Code / Neovim / Vim 等编辑器提供代码补全

# =============================================
# 找包
# =============================================

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets) #常见的三项，基本上开发qt与下面链接库对应


set(wiggly_library "colorwheellib")#这个是C++中生成.dll的项目名
set(bindings_library "PyColorWheel")#这个是python的的包名
set(wrapped_header ${CMAKE_SOURCE_DIR}/bindings.h)
set(typesystem_file ${CMAKE_SOURCE_DIR}/bindings.xml)


set(generated_sources
    ${CMAKE_CURRENT_BINARY_DIR}/${bindings_library}/pycolorwheel_module_wrapper.cpp#模块包装器，前面是模块的小写
    ${CMAKE_CURRENT_BINARY_DIR}/${bindings_library}/colorwheelsimple_wrapper.cpp)#类包装器,哪个类就是哪个类的小写



find_package(Python COMPONENTS Interpreter Development REQUIRED)
# On RHEL and some other distros, Python wheels and site-packages may be installed under 'lib64'
# instead of 'lib'. The FindPython CMake module may set Python_SITELIB to 'lib', which is incorrect
# for these cases. To ensure compatibility, we override Python_SITELIB by querying Python directly.
# This guarantees the correct site-packages path is used regardless of platform or Python build.
execute_process(
    COMMAND ${Python_EXECUTABLE} -c
    "import site; print(next(p for p in site.getsitepackages() if 'site-packages' in p))"
    OUTPUT_VARIABLE Python_SITELIB
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
list(APPEND CMAKE_PREFIX_PATH
    "${Python_SITELIB}/shiboken6_generator/lib/cmake"
)
find_package(Shiboken6Tools REQUIRED)



# Get the relevant Qt include dirs, to pass them on to shiboken.
get_property(QT_WIDGETS_INCLUDE_DIRS TARGET Qt6::Widgets PROPERTY INTERFACE_INCLUDE_DIRECTORIES)
set(INCLUDES "")
foreach(INCLUDE_DIR ${QT_WIDGETS_INCLUDE_DIRS})
    list(APPEND INCLUDES "-I${INCLUDE_DIR}")
endforeach()

# On macOS, check if Qt is a framework build. This affects how include paths should be handled.
get_target_property(QtCore_is_framework Qt6::Core FRAMEWORK)
if (QtCore_is_framework)
    get_target_property(qt_core_library_location Qt6::Core LOCATION)
    get_filename_component(qt_core_library_location_dir "${qt_core_library_location}" DIRECTORY)
    get_filename_component(lib_dir "${qt_core_library_location_dir}/../" ABSOLUTE)
    list(APPEND INCLUDES "--framework-include-paths=${lib_dir}")
endif()

set(pyside_additional_includes "")
foreach(INCLUDE_DIR ${pyside_include_dir})
    list(APPEND pyside_additional_includes "${INCLUDE_DIR}/QtCore")
    list(APPEND pyside_additional_includes "${INCLUDE_DIR}/QtGui")
    list(APPEND pyside_additional_includes "${INCLUDE_DIR}/QtWidgets")
endforeach()


# =============================================
# 项目1 生成共享的库
# =============================================
set(${wiggly_library}_sources  MyCustomWidget.cpp)
add_library(${wiggly_library} SHARED ${${wiggly_library}_sources})
set_property(TARGET ${wiggly_library} PROPERTY PREFIX "")
target_compile_definitions(${wiggly_library} PRIVATE BINDINGS_BUILD)
target_link_libraries(${wiggly_library} PRIVATE Qt6::Widgets)


# ===============================
# 项目2 生成exe可执行文件用于测试
# ===============================
qt_add_executable(colorwheel WIN32 test_main.cpp)
target_link_libraries(colorwheel PRIVATE ${wiggly_library} Qt6::Widgets)

if(WIN32)
    # 找到 windeployqt 工具的路径
    get_target_property(_qmake_executable Qt6::qmake IMPORTED_LOCATION)
    get_filename_component(_qt_bin_dir "${_qmake_executable}" DIRECTORY)
    find_program(WINDEPLOYQT_EXECUTABLE windeployqt HINTS "${_qt_bin_dir}")

    # 在安装时运行 windeployqt
    # 它会扫描安装目录下的 exe，并把需要的插件文件夹(platforms等)拷进去
    install(CODE "
        execute_process(COMMAND \"${WINDEPLOYQT_EXECUTABLE}\" 
                        --no-compiler-runtime 
                        --verbose 0
                        \"\${CMAKE_INSTALL_PREFIX}/colorwheel.exe\")
    ")
endif()

# ===============================
# 项目3 Shiboken 生成绑定，这个东西要在命令行里操作
# ===============================

set(qt_modules Core Gui Widgets)

shiboken_generator_create_binding(
    EXTENSION_TARGET ${bindings_library}
    GENERATED_SOURCES ${generated_sources}
    HEADERS ${wrapped_header}
    TYPESYSTEM_FILE ${typesystem_file}
    LIBRARY_TARGET ${wiggly_library}
    QT_MODULES Core Gui Widgets
)

set(windows_shiboken_shared_libraries)

if(WIN32)
    # =========================================================================================
    # !!! (The section below is deployment related, so in a real world application you will
    # want to take care of this properly (this is simply to eliminate errors that users usually
    # encounter.
    # =========================================================================================
    # Circumvent some "#pragma comment(lib)"s in "include/pyconfig.h" which might force to link
    # against a wrong python shared library.

    set(python_versions_list 3 36 37 38 39)
    set(python_additional_link_flags "")
    foreach(ver ${python_versions_list})
        set(python_additional_link_flags
            "${python_additional_link_flags} /NODEFAULTLIB:\"python${ver}_d.lib\"")
        set(python_additional_link_flags
            "${python_additional_link_flags} /NODEFAULTLIB:\"python${ver}.lib\"")
    endforeach()

    set_target_properties(${bindings_library}
                           PROPERTIES LINK_FLAGS "${python_additional_link_flags}")

    # Get the correct DLL path for the current build type
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        get_target_property(dll_path Shiboken6::libshiboken IMPORTED_LOCATION_DEBUG)
    else()
        get_target_property(dll_path Shiboken6::libshiboken IMPORTED_LOCATION_RELEASE)
    endif()
    file(TO_CMAKE_PATH "${dll_path}" dll_path)
    set(windows_shiboken_shared_libraries "${dll_path}")
    # =========================================================================================
endif()



install(TARGETS ${bindings_library} ${wiggly_library}#将绑定.pyd和.dll
        LIBRARY DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}
        RUNTIME DESTINATION ${CMAKE_CURRENT_SOURCE_DIR} #.dll .pyd 都移到${CMAKE_CURRENT_SOURCE_DIR}这个地址
        )
message("shiboken的.dll位置:${windows_shiboken_shared_libraries}")
install(FILES ${windows_shiboken_shared_libraries} DESTINATION ${CMAKE_CURRENT_SOURCE_DIR})#把shiboken.dll的地址拷贝到模块旁


