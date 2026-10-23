# 年糕 · Desktop Stats for Windows

可自由组合的原生 Windows 桌面监控组件与顶部状态栏。选择自己需要的指标，
用卡片、横条或竖条显示；悬停顶部栏可展开图表、设备和数据来源。

**0.19.0-preview.2 · 开发预览 · Windows x64 · 仅允许许可规定的非商业用途**

原创应用代码采用 [PolyForm Noncommercial 1.0.0](LICENSE)。未经另行书面授权，
不授予商业使用、商业集成或转售的权利。第三方依赖和旧版 MIT 权利保留，
详见 [许可范围](LICENSING.md)。公开仓库可被下载，许可证不提供技术防复制功能。

## 功能

- 桌面卡片、横条、竖条；组合或独立显示，支持自适应布局、拖动排序与对齐吸附。
- 多屏顶部栏；按需选择指标、显示样式、位置和单位，悬停查看详情。
- 网络上下行、磁盘读写、电池充放电支持同框显示。
- 六种皮肤、连续透明度和圆角、可选标题与图表；全局默认和单组件设置独立。
- CPU、GPU、内存、电池、网络、磁盘与部分温度、功率、风扇读数。
  每项数据保留来源与不可用原因，不把缺测显示为零。
- 设置分区保存，支持撤销、导入导出、多语言及 0.01–5 秒请求采样间隔。

使用随硬件而异。普通电脑不一定提供整机输入功率或噪声传感器；本软件不从
CPU/GPU 功率推算整机功率，不从风扇转速编造分贝。更快的请求间隔不保证硬件
以同样频率返回新读数。Windows 透明效果、系统策略及显示驱动可能影响玻璃效果。

## 安装与使用

公开预览目前提供经过检查的源码快照，Windows 安装包暂未发布。

解压 Windows 发布包，保留 `DesktopStats.exe` 与 `_internal` 在同一目录，运行
`Install.cmd`。源码包不能直接当作安装包使用。托盘图标可打开设置或退出程序。
升级前先应用或撤销未保存设置，安装程序会保留可恢复的旧安装备份。

在“桌面组件”按 **＋** 添加模板，在“顶部栏”选择屏幕与样式；各页面的“应用”
只保存当前区域。更多操作、传感器来源与限制见 [使用和开发说明](docs/USER_GUIDE.md)。

## 开发与检查

Python 3.12、Windows x64：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools\fetch_sensor_dependencies.py
.\.venv\Scripts\python.exe tools\build_collector.py --self-test
.\.venv\Scripts\python.exe tools\test_isolated.py
.\.venv\Scripts\python.exe tools\export_source.py
```

检查使用独立数据目录和离屏绘制，不操作鼠标、不打开桌面测试窗，也不改正在运行
的软件配置。离屏检查只能验证布局与交互，不能证明原生 Windows 磨砂效果。
源码导出按白名单包含当前快照和文件校验清单，不包含旧版本程序、私人配置或日志。
源码快照不携带第三方 DLL 或采集器 EXE。依赖准备工具只从固定的官方发布获取
经校验的九个库，不执行下载内容；随后由本机编译原创采集器。构建需要已有的
Windows .NET Framework 编译器；脚本不会自动安装驱动或 SDK。
打包与依赖重建步骤见 [开发说明](docs/USER_GUIDE.md#develop-verify-and-build)。

The application runs locally with Python/PySide6. The packaged build needs no
browser, Rainmeter, Python installation or cloud login. Original application code
is source-available under PolyForm Noncommercial 1.0.0; this is not an
OSI-approved open-source license. Third-party notices and LGPL library replacement
rights remain intact. See [LICENSING.md](LICENSING.md),
[third-party notices](THIRD_PARTY_NOTICES.md) and [changes](CHANGELOG.md).
