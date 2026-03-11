# 清理旧的构建目录
Write-Host "Cleaning old build and dist folders..."

if (Test-Path build) {
    Remove-Item build -Recurse -Force
}

if (Test-Path dist) {
    Remove-Item dist -Recurse -Force
}

# 如果存在 __pycache__，也清掉
if (Test-Path __pycache__) {
    Remove-Item __pycache__ -Recurse -Force
}

# 1. 记录开始时间
$startTime = Get-Date

# 运行 pyinstaller 打包
Write-Host "Building with PyInstaller..."
pyinstaller --clean --noconfirm .\main.spec


#手动删除一些不用的包
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Pdf.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebEngineCore.dll" -Force 
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DRender.dll" -Force 
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Graphs.dll" -Force 
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickTemplates2.dll" -Force 
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6VirtualKeyboard.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\translations" -Force -Recurse
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Location.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Multimedia.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2Imagine.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickDialogs2QuickImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2Material.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2Basic.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2BasicStyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2ImagineStyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2UniversalStyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2WindowsStyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2Universal.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2Fusion.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6DataVisualization.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Quick3DXr.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6RemoteObjects.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DExtras.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6SpatialAudio.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebEngineQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6ChartsQml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickParticles.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6PdfQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickRender.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DCore.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DAnimation.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Positioning.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Scxml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Quick3DParticles.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6DataVisualizationQml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Quick3DEffects.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickEffects.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Test.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DInput.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6PositioningQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6StateMachine.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickTest.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2MaterialStyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2Impl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6MultimediaQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsPlatform.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6SensorsQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickExtras.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Sensors.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebChannel.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebSockets.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickVectorImageGenerator.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2FluentWinUI3StyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsQmlModels.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebEngineQuickDelegatesQml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickControls2FusionStyleImpl.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsAnimation.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsFolderListModel.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsSettings.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsSharedImage.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6LabsWavefrontMesh.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6RemoteObjectsQml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6TextToSpeech.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6VirtualKeyboardQml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6VirtualKeyboardSettings.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebChannelQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebView.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6WebViewQuick.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DLogic.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickAnimation.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickInput.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickLogic.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickScene2D.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt63DQuickScene3D.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6StateMachineQml.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickDialogs2.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickDialogs2Utils.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QmlXmlListModel.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Sql.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QmlLocalStorage.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Quick3DSpatialAudio.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6Quick3DParticleEffects.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\Qt6QuickShapes.dll" -Force

Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qtga.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qtiff.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qwbmp.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qwebp.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qpdf.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qgif.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\imageformats\qicns.dll" -Force

Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\platforms\qminimal.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\platforms\qdirect2d.dll" -Force
Remove-Item -Path ".\dist\DarkEye\_internal\PySide6\plugins\platforms\qoffscreen.dll" -Force


Remove-Item ".\dist\DarkEye\_internal\cv2" -Recurse -Force -ErrorAction SilentlyContinue

Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtMultimedia" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtGraphs" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtLocation" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtPositioning" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtSensors" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtTest" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtTextToSpeech" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtWebChannel" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtWebEngine" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtWebSockets" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtWebView" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtRemoteObjects" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtScxml" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtDataVisualization" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\Qt" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\Qt5Compat" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\Qt3D" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtCharts" -Recurse -Force -ErrorAction SilentlyContinue


Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtQuick\Controls" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtQuick\VirtualKeyboard" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\qml\QtQuick\NativeStyle" -Recurse -Force -ErrorAction SilentlyContinue

Remove-Item ".\dist\DarkEye\_internal\PySide6\plugins\tls" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\plugins\styles" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\plugins\qmltooling" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\plugins\generic" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\plugins\networkinformation" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\DarkEye\_internal\PySide6\plugins\platforminputcontexts" -Recurse -Force -ErrorAction SilentlyContinue



Write-Host "Build complete."
# 3. 记录结束时间
$endTime = Get-Date

# 4. 计算耗时
$timeElapsed = $endTime - $startTime

# 5. 输出结果
Write-Host "spend time: $($timeElapsed.TotalSeconds) seconds"
