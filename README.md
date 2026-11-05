# 年糕 · Desktop Stats for Windows

<p align="center"><img src="assets/icon-128.png" width="64" height="64" alt="年糕图标"></p>

可自由组合的原生 Windows 顶部状态栏与桌面监控组件。可只保留上方栏，
也可按需添加卡片、横条或竖条；悬停查看趋势，点击固定硬件详情。

**0.27.0-preview.1 · 预览版 · Windows x64 · 仅限许可规定的非商业用途**

顶部栏设置只保留一个实时预览，**内容与排列** 调整指标和顺序，**外观** 选择
整体设计、材质与连续透明度。桌面组件列表只在编辑桌面时显示；保存状态和待应用
更改在页底明确提示，原有布局、图标及版本 12 动效继续保留。

硬件详情先呈现当前读数与趋势，再按需显示 **占用最多的软件**。CPU、内存、GPU
和专用显存支持前五名排行；CPU 的逻辑处理器网格可展开，来源与限制另行查看。
顶部栏排行仅在详情及排行区域可见时采集，离开即停止，不写入历史或设置。

全屏游戏或应用位于前台时，顶部栏和详情自动避让，回到普通桌面后恢复。
设置隐藏或最小化时暂停预览动画、历史页查询和额外来源检查，保留草稿与滚动位置；
常规采样继续使用已保存的间隔，不通过缩短采样来改善视觉效果。

CPU 温度取决于机器实际提供的来源。本机 ASUS 适配使用可选的**只读会话桥接**，
需要已有 ASUS 服务及明确的管理员授权，随当前应用退出，不安装驱动或服务。
可在偏好中开启 **启动时恢复 CPU 温度**（默认关闭）：每次启动确认一次管理员授权，
全屏游戏时延后到回桌面；取消后本次会话不再提示。桥接本身不设开机启动，
不支持的机器或失效读数会显示原因。
见 [CPU 温度桥接说明](docs/USER_GUIDE.md#asus-cpu-temperature-bridge)。

[使用指南](docs/USER_GUIDE.md) 介绍布局、历史和数据来源；
[视觉指南](VISUAL-GUIDE.md) 展示可选动效；历次修改见 [变更记录](CHANGELOG.md)。

原创应用代码采用 [PolyForm Noncommercial 1.0.0](LICENSE)。未经另行书面授权，
不授予商业使用、商业集成或转售的权利。第三方依赖和旧版 MIT 权利保留，
详见 [许可范围](LICENSING.md)。公开仓库可被下载，许可证不提供技术防复制功能。

## 界面预览

以下是原生界面的离屏绘制图，全部使用合成示例数据。点击图片可查看高清原图；
图片不作为 Windows 原生磨砂外观的验收。

### 读数更新，动画继续

[![深色实际 QML 动画与独立读数更新，合成示例数据](assets/showcase/motion-continuity-dark.gif)](assets/showcase/motion-continuity-dark.gif)

每秒改变一次合成读数，动画在读数之间继续运行。上图展示实际大小的读数图标与 36 DIP 细节参考，
强度 65%、速度 1×；GIF 为 20 fps 的离屏演示，并非实际电脑帧率测试。
[查看浅色演示](assets/showcase/motion-continuity-light.gif) · [完整视觉指南](VISUAL-GUIDE.md)

### 三套顶部栏设计

[![三套顶部栏的实际深浅色对比，合成示例数据](assets/showcase/top-bar-designs.png)](assets/showcase/top-bar-designs.png)

在 **外观** 中选择经典菜单栏、分组胶囊或精密仪表，共用同一个实时预览，保留指标、组合、单位与设备设置。

可选图标动效默认关闭。开启后，CPU/GPU 的温度驱动黄橙红电弧，功耗驱动蓝白电流；短电弧在不同位置闪出、分叉、熄灭。独立温度计使用温柱和黄红热晕，不显示电流；风扇平滑旋转。强度与速度连续调节，缺测、零活动和减少动画时静止。

选择 **图标动效 → 硬件联动** 可让同一图标显示独立的硬件通道：CPU/GPU 的负载、黄红热感与蓝色功耗反馈可以同时出现，网络和电池分别处理两个方向。电弧在十个视觉阶段之间连续过渡，逐渐增加伸展幅度、放电频率和同时出现的细丝；真实数值不分档。内存没有温度传感器时不编造发热，NVMe 损耗也不会被当成负载。

[![硬件图标动态效果，原尺寸与细节参考，合成示例读数](assets/showcase/hardware-motion-dark.gif)](assets/showcase/hardware-motion-dark.gif)

动画使用合成示例读数；[查看浅色动画](assets/showcase/hardware-motion-light.gif)。电弧为状态装饰，不代表检测到了物理放电。

| 硬件联动 · 浅色 | 硬件联动 · 深色 |
| --- | --- |
| [![浅色硬件图标十状态原生绘制，合成读数](assets/showcase/hardware-feedback-light.png)](assets/showcase/hardware-feedback-light.png) | [![深色硬件图标十状态原生绘制，合成读数](assets/showcase/hardware-feedback-dark.png)](assets/showcase/hardware-feedback-dark.png) |
| 真实控制器投影的合成数据，保留实际图标大小。 | 独立通道可以叠加，静态图只能展示一个动画时刻。 |

### 硬件详情与指标编辑

[![指标右侧直接调整和删除的原生界面，合成示例数据](assets/showcase/top-bar-actions.png)](assets/showcase/top-bar-actions.png)

每项右侧直接调整或删除，组合编辑先暂存，再确认；可选图标动效默认关闭。

| CPU：读数、趋势与软件排行 | 组合：明确确认与取消 |
| --- | --- |
| [![CPU 当前读数、趋势与占用最多的软件，合成示例数据](assets/showcase/cpu-details.png)](assets/showcase/cpu-details.png) | [![组合编辑确认与取消，合成示例数据](assets/showcase/group-confirm.png)](assets/showcase/group-confirm.png) |
| 逻辑处理器按需展开；缺测与零值明确区分，不编造每核温度或功耗。 | 取消不提交，确认后保留到草稿，再应用顶部栏。 |

双向网络详情保留上下行、真实缺口、共同量程及逐点读数：[查看高清预览](assets/showcase/network-details.png)。

### CPU / GPU 组合读数

[![CPU 与 GPU 组合读数的原生界面，合成示例数据](assets/showcase/top-bar-groups.png)](assets/showcase/top-bar-groups.png)

使用率、温度和功耗放在同一组，整组拖动；组内内容与顺序可调整。原有单项样式保留。

| 组件编辑与实时预览 | 顶部栏：屏幕、指标与显示样式 |
| --- | --- |
| [![组件编辑与实时预览，示例数据](assets/showcase/widgets-editor.png)](assets/showcase/widgets-editor.png) | [![顶部栏设置与显示样式，示例数据](assets/showcase/top-bar-styles.png)](assets/showcase/top-bar-styles.png) |
| 自适应布局与精细排版，按需调整组件内容。 | 选择显示器、排列指标，网络上下行支持同框。 |

| 历史趋势 · 浅色 | 历史趋势 · 深色 |
| --- | --- |
| [![浅色历史趋势，合成示例数据](assets/showcase/history-light.png)](assets/showcase/history-light.png) | [![深色历史趋势，合成示例数据](assets/showcase/history-dark.png)](assets/showcase/history-dark.png) |
| 查看时间走势、范围和记录状态。 | 悬停或使用方向键查看具体时间和读数。 |

| 场景：先预览，再应用 | 来源诊断：原因与下一步 |
| --- | --- |
| [![场景预览，合成示例数据](assets/showcase/scene-preview.png)](assets/showcase/scene-preview.png) | [![来源诊断，合成示例数据](assets/showcase/source-diagnostics.png)](assets/showcase/source-diagnostics.png) |
| 内置方案、自存布局与上次布局恢复。 | 分开显示来源状态，接口详情按需展开。 |

## 功能

- 桌面卡片、横条、竖条；组合或独立显示，支持自适应布局、拖动排序与对齐吸附。
- 多屏顶部栏；按需选择指标、显示样式、位置和单位，悬停查看详情。
- 顶部栏以单一实时预览连接“内容与排列”和“外观”，支持三套整体设计与连续透明度。
- CPU 与 GPU 支持组合读数：同一格放入最多四项指标，整组拖排，组内可调整内容和顺序。
- CPU 详情可展开逻辑处理器使用率，关联频率、温度、功耗与风扇读数；CPU、内存、GPU、显存的 Top 5 软件排行按需采集。
- 指标行右侧直接调整或删除；组合编辑可确认或取消。图标动效按项选择，强度和速度连续可调，默认关闭，并遵循系统减少动画设置。
- 动效围绕图标局部结构呈现，保留清晰的静态轮廓；彩色细节和节奏随真实读数平滑变化，不作为告警或标定转速。详情按当前读数、真实趋势、软件排行和可展开核心明细排列。自动切换网卡或系统卷后，图表仍只显示当前设备的历史，不混入其他设备。
- 网络上下行、磁盘读写、电池充放电支持同框显示。
- 六种皮肤、连续透明度和圆角、可选标题与图表；全局默认和单组件设置独立。
- CPU、GPU、内存、电池、网络、磁盘与部分温度、功率、风扇读数。
  每项数据保留来源与不可用原因，不把缺测显示为零。
- 设置分区保存，支持撤销、导入导出、多语言及 0.01–5 秒请求采样间隔。
- 本机历史记录，支持 10 分钟、1 小时与 24 小时查看；折线保留缺测，聚合保留峰值范围。
- 日常办公、性能观察、续航场景，以及自存布局和上次布局恢复；先预览再应用。
- 来源诊断先显示原因和下一步，接口错误按需展开；支持重新检查与脱敏导出。

使用随硬件而异。普通电脑不一定提供整机输入功率或噪声传感器；本软件不从
CPU/GPU 功率推算整机功率，不从风扇转速编造分贝。更快的请求间隔不保证硬件
以同样频率返回新读数。Windows 透明效果、系统策略及显示驱动可能影响玻璃效果。

## 安装与使用

公开预览目前提供经过检查的源码快照，Windows 安装包暂未发布。

解压 Windows 发布包，保留 `DesktopStats.exe` 与 `_internal` 在同一目录，运行
`Install.cmd`。源码包不能直接当作安装包使用。托盘图标可打开设置或退出程序。
升级前先应用或撤销未保存设置，安装程序会保留可恢复的旧安装备份。

在“桌面组件”按 **＋** 添加模板；只用上方栏时可关闭全部桌面组件。已保存为仅顶部栏
的配置首次打开设置会直接进入顶部栏页。**内容与排列** 调整指标，**外观** 调整样式；
“应用”或“放弃更改”只处理当前区域。更多操作、传感器来源与限制见 [使用和开发说明](docs/USER_GUIDE.md)。

“历史记录”可独立暂停和清空，数据仅保存在本机。按来源原始时间戳记录；普通写盘
采用五秒批次门槛，两秒采样时约六秒一次，实时查询包含未提交尾部；不把重复读取的
缓存当作新的硬件样本。暂停记录或正常退出时尝试保存尾部。

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

电弧图集已经包含在源码中，正常运行和打包无需重新生成。需要修改动效素材时，
另行安装 `requirements-artwork.txt`，运行
`python tools/generate_metric_motion.py --output assets/metric-motion-new`。
生成器写入新的项目内目录，保留现有素材和清单；使用新资源前核对生成参数、
实际小尺寸动画和哈希。Three 算法署名与 MIT 例外见第三方说明。

The application runs locally with Python/PySide6. The packaged build needs no
browser, Rainmeter, Python installation or cloud login. Original application code
is source-available under PolyForm Noncommercial 1.0.0; this is not an
OSI-approved open-source license. Third-party notices and LGPL library replacement
rights remain intact. See [LICENSING.md](LICENSING.md),
[third-party notices](THIRD_PARTY_NOTICES.md) and [changes](CHANGELOG.md).
