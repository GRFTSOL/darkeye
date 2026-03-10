cmake_minimum_required(VERSION 3.26)

project(forceview
    VERSION 1.0.0
    DESCRIPTION "Force-directed graph view (simulation + rendering)"
    LANGUAGES CXX
)

# =============================================
# Global settings
# =============================================
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_INCLUDE_CURRENT_DIR ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# =============================================
# Find Qt
# =============================================
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets OpenGLWidgets OpenGL)

# =============================================
# Names
# =============================================
set(forceview_library  "forceviewlib")      # C++ shared library  (.dll)
set(bindings_library   "PyForceView")       # Python binding      (.pyd)
set(wrapped_header     ${CMAKE_SOURCE_DIR}/bindings.h)
set(typesystem_file    ${CMAKE_SOURCE_DIR}/bindings.xml)


set(generated_sources
    ${CMAKE_CURRENT_BINARY_DIR}/${bindings_library}/pyforceview_module_wrapper.cpp#模块包装器
    ${CMAKE_CURRENT_BINARY_DIR}/${bindings_library}/forceviewopengl_wrapper.cpp#类包装器
)

# =============================================
# Find Python + Shiboken
# =============================================
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Override Python_SITELIB to ensure correct site-packages path on all platforms
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

# Qt include dirs for shiboken
get_property(QT_WIDGETS_INCLUDE_DIRS TARGET Qt6::Widgets PROPERTY INTERFACE_INCLUDE_DIRECTORIES)
set(INCLUDES "")
foreach(INCLUDE_DIR ${QT_WIDGETS_INCLUDE_DIRS})
    list(APPEND INCLUDES "-I${INCLUDE_DIR}")
endforeach()

# macOS framework support
get_target_property(QtCore_is_framework Qt6::Core FRAMEWORK)
if(QtCore_is_framework)
    get_target_property(qt_core_library_location Qt6::Core LOCATION)
    get_filename_component(qt_core_library_location_dir "${qt_core_library_location}" DIRECTORY)
    get_filename_component(lib_dir "${qt_core_library_location_dir}/../" ABSOLUTE)
    list(APPEND INCLUDES "--framework-include-paths=${lib_dir}")
endif()

# PySide additional includes
set(pyside_additional_includes "")
foreach(INCLUDE_DIR ${pyside_include_dir})
    list(APPEND pyside_additional_includes "${INCLUDE_DIR}/QtCore")
    list(APPEND pyside_additional_includes "${INCLUDE_DIR}/QtGui")
    list(APPEND pyside_additional_includes "${INCLUDE_DIR}/QtWidgets")
endforeach()
find_package(OpenMP REQUIRED COMPONENTS CXX)

# =============================================
# MSDF text rendering dependencies
# =============================================
set(MSDFGEN_USE_VCPKG OFF CACHE BOOL "" FORCE)
set(MSDFGEN_BUILD_STANDALONE OFF CACHE BOOL "" FORCE)
set(MSDFGEN_USE_SKIA OFF CACHE BOOL "" FORCE)
set(MSDFGEN_DISABLE_SVG ON CACHE BOOL "" FORCE)
set(MSDFGEN_DISABLE_PNG ON CACHE BOOL "" FORCE)
set(MSDFGEN_DYNAMIC_RUNTIME ON CACHE BOOL "" FORCE)

set(SKIP_INSTALL_ALL TRUE)
add_subdirectory(3rdparty/freetype)
if(NOT TARGET Freetype::Freetype)
    add_library(Freetype::Freetype ALIAS freetype)
endif()
set_target_properties(freetype PROPERTIES
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL"
)
add_subdirectory(3rdparty/msdfgen)

# =============================================
# Project 1: Shared library (forceviewlib.dll)
# =============================================
set(${forceview_library}_sources
    src/Forces.cpp
    src/QuadTree.cpp
    src/Simulation.cpp
    src/ForceViewOpenGL.cpp
    src/ForceViewOpenGL_Simulation.cpp
    src/ForceViewOpenGL_Geometry.cpp
    src/ForceViewOpenGL_Text.cpp
    src/ForceViewOpenGL_Input.cpp
    src/ForceViewOpenGL_Runtime.cpp
    src/GraphRenderer.cpp
    src/MsdfFontAtlas.cpp
    src/MsdfTextRenderer.cpp
    include/Forces.h
    include/QuadTree.h
    include/Simulation.h
    include/ForceViewOpenGL.h
    include/GraphRenderer.h
    include/PhysicsState.h
    include/MsdfFontAtlas.h
    include/MsdfTextRenderer.h
)

add_library(${forceview_library} SHARED ${${forceview_library}_sources})
set_property(TARGET ${forceview_library} PROPERTY PREFIX "")
target_compile_definitions(${forceview_library} PRIVATE BINDINGS_BUILD)
target_include_directories(${forceview_library} PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(${forceview_library}
    PUBLIC Qt6::Widgets Qt6::OpenGLWidgets Qt6::OpenGL
    PRIVATE OpenMP::OpenMP_CXX
            msdfgen::msdfgen-core
            msdfgen::msdfgen-ext
            Freetype::Freetype
)

# =============================================
# Project 2: Test executable
# =============================================
qt_add_executable(forceview_test WIN32 src/test_main.cpp)
target_include_directories(forceview_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(forceview_test PRIVATE ${forceview_library} Qt6::Widgets)

#这个测试的不要安装了
#install(TARGETS forceview_test ${forceview_library}
#    EXPORT forceview_export
#    RUNTIME DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}
#    LIBRARY DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}
#)

if(WIN32)
    get_target_property(_qmake_executable Qt6::qmake IMPORTED_LOCATION)
    get_filename_component(_qt_bin_dir "${_qmake_executable}" DIRECTORY)
    find_program(WINDEPLOYQT_EXECUTABLE windeployqt HINTS "${_qt_bin_dir}")
    install(CODE "
        execute_process(COMMAND \"${WINDEPLOYQT_EXECUTABLE}\"
                        --no-compiler-runtime
                        --verbose 0
                        \"\${CMAKE_INSTALL_PREFIX}/forceview_test.exe\")
    ")
endif()

# =============================================
# Project 3: Shiboken binding (PyForceView.pyd)
# =============================================
set(qt_modules Core Gui Widgets)

shiboken_generator_create_binding(
    EXTENSION_TARGET ${bindings_library}
    GENERATED_SOURCES ${generated_sources}
    HEADERS ${wrapped_header}
    TYPESYSTEM_FILE ${typesystem_file}
    LIBRARY_TARGET ${forceview_library}
    QT_MODULES Core Gui Widgets OpenGLWidgets OpenGL
)

# Windows: handle shiboken shared library and python linking
set(windows_shiboken_shared_libraries)

if(WIN32)
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

    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        get_target_property(dll_path Shiboken6::libshiboken IMPORTED_LOCATION_DEBUG)
    else()
        get_target_property(dll_path Shiboken6::libshiboken IMPORTED_LOCATION_RELEASE)
    endif()
    file(TO_CMAKE_PATH "${dll_path}" dll_path)
    set(windows_shiboken_shared_libraries "${dll_path}")
endif()

# Install binding + library to source dir for easy Python import
install(TARGETS ${bindings_library} ${forceview_library}
        LIBRARY DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}
        RUNTIME DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}
)
message("Shiboken .dll location: ${windows_shiboken_shared_libraries}")
install(FILES ${windows_shiboken_shared_libraries} DESTINATION ${CMAKE_CURRENT_SOURCE_DIR})
