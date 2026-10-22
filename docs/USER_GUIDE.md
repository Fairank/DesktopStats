# Desktop Stats for Windows

Small, configurable **native Windows desktop widgets**, with configurable materials and real hardware readings. Original application source under PolyForm Noncommercial 1.0.0; see ../LICENSING.md for scope and exceptions. Development candidate **0.19.0-preview.1** restores complete miniature desktop scenes in the skin chooser and organizes menu-bar details by hardware module. Network transfer, disk I/O and battery-side input/output offer paired inline or stacked readouts. Detail charts show real amplitude scales, peaks and available sample timing; paired channels share their scale. Quantity-specific vector icons distinguish fans, temperature, power, frequency and transfer direction. Desktop widgets, menu bar and preferences save independently; existing styles and precision layout remain available. The vector icon preserves the approved Niangao face. This is a preview, not a stable public release; successful native requests are not visual proof of blur.

Windows settings and menu-bar details share an alpha-zero native raster host and transparent Qt Quick foreground. They now use the WUJI Workbench material sequence: DWM transient-window backdrop (type 3), full client-frame extension, verified type readback, black native background and transparent foreground. No accent-blur fallback is substituted for these two hosts. Their foreground remains Qt Quick rather than WUJI's WebView2. Windows 11 detail corners request the system's smooth rounded clipping; unsupported or failed requests retain the rounded-mask fallback. UI symbols use one pinned Lucide set, while the original Niangao brand artwork remains unchanged. Failed native setup or background painting selects a readable solid fallback.

No browser, WebView, web server, Rainmeter, Python installation or cloud account is required by the packaged app. Qt Quick renders native windows with DPI-scaled typography and vectors.

Menu-bar detail windows prepare their retained native material while hidden, then publish the matching foreground coating before showing. First-frame and hover activation adopt this setup without a delayed material switch. A failed initial request stays readable for that opening; explicit policy/compositor recovery keeps finite retries. Fullscreen mode blocks late hover or click events from reopening a detail panel. Closing hides a panel before attempting native cleanup, including cleanup failures.

## 安装与使用

1. 解压发布包，保留 DesktopStats.exe 与 _internal 在同一目录。双击运行，或用 Install.cmd 安装。升级前先应用或撤销待保存设置；旧版本如不能安全自动退出，请从托盘退出后重试。安装先准备新目录，再换入并保留原版备份；准备、替换或注册失败会尝试回滚并明确记录未完成的步骤，配置文件保持独立。
2. 左侧只保留 **桌面组件 / 顶部栏 / 偏好** 三个主要入口。在组件列表旁按 **＋** 添加模板。选中组件后，在同一页查看预览和指标，并调整皮肤、透明度、标题及大小；窄窗口直接上下滚动，不必逐层打开抽屉。
3. 点击 **卡片 / 横条 / 竖条** 一键选择布局。**＋添加指标** 支持连续选择，点击“添加所选”才一次加入；取消或 Esc 不更改组件。每组件最多六项，同一模板可重复添加。
4. 默认使用自适应排列，拖动指标调整顺序。需要手工编辑时展开 **精细排版**；开启 **自由摆放** 后，拖动有边缘/中心吸附和参考线，按住 Alt 临时关闭吸附。拖到另一项中央可交换位置，拖动选中项的小角可调整其区域。
5. 按住 Ctrl 点击多选，再使用 **对齐与均分**。重叠或空间不足的操作不会部分提交；新增指标会保留手动摆放的旧位置，没有空位时向下扩展。移除指标不重铺剩余项。
6. 在组件页直接修改精确宽高，或在 **精细排版** 画布拖动右下角调整真实宽高，内部自动布局随尺寸重排。**适合 / 100% / Ctrl＋滚轮** 只调整编辑显示比例；普通滚轮滚动内容。移动主窗口边缘时暂缓昂贵预览重绘，停下后恢复到最终尺寸，编辑输入和草稿保留。
7. 使用画布底部 **撤销 / 重做** 或 Ctrl+Z / Ctrl+Shift+Z 回退草稿操作。连续标题输入或滑条调整合并为一步；拖动只在松手提交，Esc 可取消当前拖动。**应用到桌面 / 应用顶部栏 / 应用偏好** 只保存当前区域；**恢复** 也只撤销当前区域。其他区域的草稿和撤销记录保留。导入或恢复默认会明确进入“将替换全部设置”预览，点击 **应用全部设置** 才整体保存；取消可回到之前的草稿。
8. 指标清单保留完整名称和实时值，可点选、排序或移除；数据来源与单位、位置等较少使用的选项按需展开。调整皮肤、透明度或圆角时，现有桌面组件即时预览；点击固定底部的 **应用到桌面** 或 Ctrl+S 才保存。关闭整个设置窗口会恢复已保存外观，未保存草稿仍可重新打开继续修改。布局、设备、采样等其它设置在应用后生效。
9. 在 **桌面组件 → 桌面默认设置** 调整组件的全局材质、大小、布局和磁吸；**偏好** 首屏设置语言、深浅外观、登录启动及检测间隔，**传感器与来源** 查看真实通道和来源。托盘“退出”完全关闭软件。

在侧栏 **顶部栏** 设置系统屏幕边缘栏：可选择主屏、所有屏幕或指定屏幕，高度 28/32/40 个逻辑像素，最多 64 项指标。顶部固定开关直接启停；预览明确标出未启用状态。先选“紧凑数字 / 均衡 / 迷你图表”模板，再点单项编辑。检查器保留一个实际比例预览，点击 **显示方式** 在原页展开完整样式预览，选中即收起；位置、精度、单位和设备可直接调整，来源按需展开，错误原因直接显示。原有八种显示方式保留：标签、纯数值、图标、趋势、柱状、圆环、迷你图表、上下两行。网络速度、磁盘读写和电池侧充放电另外支持 **双向读数 / 单行双向**；两方向共用同一个所选设备和单位，缺读数显示“—”，真实零值保留。已知 0–100% 量程才推荐柱状和圆环，NVMe 已用寿命不冒充占用率。拖动列表或预览可放到左侧、右侧并排序，实时顶部栏也可直接拖排；存在未应用的顶部栏修改时，需先应用后再拖实时栏。趋势复用最近最多 40 次已有读数，不额外采集；无效读数留断点。此页应用只保存顶部栏，保留其他组件的草稿和撤销记录。

**顶栏外观** 可跟随全局，或独立选择材质和 0–100% 连续底色透明度；改变底色不反复调用原生材质。详情与设置页按 WUJI 工作台的 DWM 磨砂流程准备，普通顶部横栏保留其现有 Windows 模糊路径。原生请求成功后才允许透明涂层，失败保留可读实色；API 成功仍不等于已确认系统模糊。Windows 透明效果关闭或高对比度启用时也恢复可读实色。

它通过 Windows AppBar 为普通应用预留空间；全屏时让位，关闭后注销预留。停留约 350 毫秒显示来源和相关读数，点击可固定详情；放不下的完整指标统一收入 **+N**，不截单位、不缩字体。此模式默认关闭，不迁移已有桌面条。原来的 **＋ → 顶部状态条** 与“横条”仍是普通桌面组件，不预留系统工作区域。真实 Shell、多屏和第三方窗口兼容性仍需要候选版实机验收。

可读性限制与实际布局共用：自动布局变窄时换行，不丢弃已选指标；手动区域保留最低可读尺寸，空间不足时明确提示。每组件最多六项，宽高上限 4096×2160，实际尺寸还受屏幕可用区域限制。画布放大使用更高分辨率绘制；效果示意不能证明原生系统模糊已经启用。

在 **偏好 → 检测频率** 输入 0.01–5 秒，支持两位小数，默认 2 秒。增减按钮每次调整 0.01 秒，输入遵循当前语言的小数点或小数逗号。修改后点击 **应用偏好**，从下一轮采样生效；未应用或撤销不会改变实际采集设置。更短的请求间隔会增加系统开销，不保证每种硬件传感器都能提供 100 Hz 的新读数。

记录频率与绘制频率分开：每个收到的样本继续进入既有历史，快速采样的界面通知合并至约 30 Hz，保证最后一个读数也会刷新。顶部栏只在几何变化时重新排版，悬停后才生成相关详情，减少操作时的重复工作。

详情按处理器、显卡、内存、网络、磁盘读写、卷容量、NVMe 健康、电池、散热等实际模块组织，不再从同一采集来源随便取前六项。支持配对的模块显示两个方向；内存、显存和卷容量只有取得完整真实数据时才显示已用/总量条。已有趋势标明实际采样数，不假定固定时间跨度。没有读数的通道可展开查看明确原因，不补造数值。完整设备名与数据来源也可展开。主设置窗口的隐藏页面不持续重画实时卡片；缩放时保留页面实例和未提交输入，停下后统一更新布局。

在 **外观与布局 → 磁吸避让** 开启组件间的吸附与避让，间距可设为 0–64 个逻辑像素，默认 12。松手后仅调整所拖动的组件，保持其它组件原位；支持组合面板和负坐标副屏。回弹使用轻微的两段弹动，可单独关闭，也尊重 Windows 的动画效果设置。空间不足时明确提示，不能通过重叠或偷偷缩小间距来冒充成功。默认关闭磁吸以保留已有手动布局。

每个组件可独立开关 **显示标题**；隐藏标题保留原文字并回收顶部空间。六种皮肤提供清透玻璃、柔雾玻璃、柔彩玻璃、经典卡片、石墨黑和无底色的极简数字。单组件选择“跟随全局”才会随全局皮肤变化；明确设置的局部皮肤保持独立。

右击组件可直接切换标题、皮肤、尺寸、卡片比例、信息样式、图表或隐藏该组件。这些快捷操作只保存所选属性，保留设置页中其他尚未保存的更改。组合面板内右击卡片会编辑命中的那一个组件。托盘、顶部栏及组件菜单使用统一的紧凑圆角面板、矢量图标和深浅主题，皮肤与尺寸等子菜单旁直接显示当前值。设置页的“更多”和“对齐与均分”菜单也采用同样的视觉，靠近触发按钮展开。菜单保留键盘、勾选、单选及滚动操作；“锁定桌面位置”和“显示桌面组件”明确作用于全部桌面组件。菜单采用可读的实色涂层，不额外延迟切换背景材质。

**透明背景与系统模糊：** 小组件和顶部栏复用已认可主窗口的透光底色及轻边框。0–100% 连续透明度只调整底板；50% 对应主窗口的浅/深色配方，文字保持清晰。继承全局时拖动滑条会只覆盖当前组件，也可恢复全局。圆角连续调节，非玻璃皮肤隐藏无效参数。现有 Alpha 路径保留不抢焦点和桌面层级；不新增复杂折射后端，不把透明底色说成已验证的系统模糊。Windows 关闭透明效果或启用高对比度时恢复可读实色；主设置窗口保留既有独立系统材质。

“极简数字”不绘制底板，也不请求系统背景模糊。同一组合中成员皮肤相同时共享该材质；混合皮肤时分别绘制，避免全局底板透到无底色组件下。无底色与玻璃可以在同一个组合内保留各自的 Alpha 涂层，不再因为混合使用而强制玻璃变成实色。

玻璃组件中可直接拖动“玻璃透明度”和“圆角曲率”。继承全局时第一次拖动只为当前组件、当前参数建立独立值；勾回“跟随全局”恢复继承，不改变其它组件。极简、经典卡片和石墨黑不使用玻璃参数，检查器不显示无效滑条。外观页的玻璃默认参数始终可编辑，只影响仍继承该参数的玻璃组件。应用或 Ctrl+S 后保存到桌面。

0.7 重做了卡片数字、单位与留白：三项使用主值与两项辅助信息，四项使用两列，五至六项使用紧凑布局。大数字、圆环、进度条和每核负载也保留其它已选指标。趋势线只描边，不意外填充；多核网格计入真实行间距。实时组件预览使用拟合后的布局尺寸和实际材质请求结果；皮肤样例标为示意，不能用于证明系统模糊已启用。

设置界面使用组件侧栏、紧凑编辑区和尺寸预览，浅色采用中性灰白，深色采用石墨色。切换主栏目时，共享的玻璃选中底板用 200 毫秒平滑移动；Windows 关闭动画时直接到位。正文与控件字号、文字对比度和间距统一调整；预设布局收进选择器，样式与设备选项分组显示。窄窗口保留滚动编辑与实际大小预览入口。

Per-user installation: %LOCALAPPDATA%\Programs\DesktopStats. No drivers or administrator rights are installed. Desktop and Start menu shortcuts are included. Start at login is optional and off by default. Uninstall via Windows Settings or Uninstall.cmd; preferences are retained for a reinstall.

## Available readings

The gallery offers editable templates, fixed readings and device-specific channels discovered by the bundled sensor engine. These are choices in the picker, not permanently visible settings.

| Area | Choices | Source / scope |
| --- | --- | --- |
| CPU | Usage, per-logical-processor load, frequency, cores and threads | Windows / psutil. Frequency is the value reported by Windows, not a claim of per-core effective clock. |
| Thermals | CPU and GPU temperature | Existing ASUS read-only temperature interface; NVIDIA NVML; optional fresh HWiNFO VSB |
| GPU | Usage, board power, core/memory clock, fan percentage, VRAM used/total/percentage | NVIDIA NVML. Select a reported GPU. Unsupported queries stay unavailable. |
| Memory | Used, available, total, utilization, page file usage | Windows / psutil |
| Battery | Charge percentage, remaining energy, Windows-estimated time, charge/discharge watts, optional voltage | Native Windows battery information; voltage needs fresh HWiNFO VSB |
| Power | CPU package, GPU, battery charging input and discharge output; optional charger input / total system | Native read-only Windows Energy Meter for supported package-0 channels; NVIDIA NVML; fresh HWiNFO VSB fallback. Domains remain separate. |
| Network | Download/upload rates, cumulative received/sent bytes | Select an active adapter or automatic active-adapter selection. Automatic mode chooses one adapter rather than summing VPN/bridge traffic. |
| Disk | Read/write rates, partition used/free/total/percentage | Select a physical disk for I/O and a fixed local volume for capacity. |
| Cooling | CPU/GPU chassis fan RPM where supported | Read-only ASUS status endpoints on tested compatible machines. Unsupported third fans stay unavailable. Fan duty percentage is a different measurement. |
| Extra sensors | Discovered temperatures, voltage, current, power, clocks, load, capacity, throughput and energy | Bundled LibreHardwareMonitorLib 0.9.6, in a separate owned background collector. Sensor names include their hardware. Availability depends on the device, driver and access rights. |

**扩展传感器：** 在“传感器”页搜索或分类查看实际发现的通道，点击“重新扫描”重新识别。组件内的“＋添加指标”也会列出这些通道，可以和原有指标混合，仍以每组件六项为上限。绑定保留准确的来源、传感器标识及类型；断开、超时或类型改变后显示不可用，不自动切换到另一个同名设备。复制、导出和导入保留绑定。设备重排或更换采集器版本可能改变上游标识，届时需重新选择。

The restricted collector enables GPU, storage and network groups. CPU/motherboard/PSU/controller/low-level memory groups remain disabled; native CPU, ASUS fan, battery and NVML providers remain separate. The library's battery group is disabled because version 0.9.6 can retain old values after a failed query. No third-party GUI settings, fan/power controls, drivers or services are installed. The current GA402XV probe exposed 115 GPU/network channels, 114 with values. That is a timestamped observation, not a hardware guarantee.

The library did not expose storage on this machine. Its exact physical-disk read/write open was reproduced with Win32 error 5, while a metadata-only open succeeded. A separate Windows NVMe health query now reads composite temperature, available spare percentage and percentage of endurance used on a zero-access metadata handle. It uses only the fixed `IOCTL_STORAGE_QUERY_PROPERTY` health page, with no pass-through or setters. An owned child limits each request to three seconds, polls at most once per five seconds, clears stale/failed values, and runs before Qt/IPC. The source candidate was measured successfully on this host without elevation; SATA, USB bridges and other controllers may return a concrete query error. Choose the physical disk explicitly; no replacement disk is silently substituted. Spare percentage and wear are not free-space or disk-usage percentages.

Source diagnostics retain actual per-channel API codes, invalid raw values, absent/stale HWiNFO exports and provider recovery state. NVML error 3 means that particular query returned Not Supported; it does not mean every sensor or chassis fan is unsupported. A missing VSB key is reported separately from access denied. Missing adapter/whole-system power and acoustic dBA are not fabricated from CPU/GPU sums, battery flow or fan RPM.

Collector refresh is 1 second, independent of the UI sampling preference. It runs only while a selected extra channel or the sensor browser needs it. A stalled process is stopped and retried with backoff; stale values disappear while their channel labels remain available. Battery Energy is normalized from upstream mWh to Wh. Upstream Data/SmallData use binary scaling with their GB/MB labels. Observed minima/maxima are session extrema, not safe operating limits.

Fan noise needs a real acoustic sensor, and adapter input / whole-PC watts need dedicated measurements. They cannot be recovered by converting RPM to dBA or adding CPU and GPU watts. This laptop has no verified acoustic or whole-input measurement. See the pinned [LibreHardwareMonitor release](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6).

**Power meanings:** battery charging input is energy entering the battery; discharge output is energy leaving it. Neither is the charger's input nor the whole machine's consumption. Plugged in with an idle battery can correctly mean **0.0 W**. Charger input and total system power require their own sensors and are never calculated by summing CPU/GPU/battery readings. Missing or unknown values show **—**, separately from zero.

The power template now puts CPU package, GPU, battery charging and discharging together. The native package counter is sampled twice, converted from milliwatts to watts, and resets its baseline after sleep; unavailable channels remain unavailable. It runs in the sensor thread without helper processes or a new driver. HWiNFO VSB accepts explicit watts in its standard `ValueN` field as well as optional `UnitN`; mW/kW are not mislabelled as W. See [Windows PDH](https://learn.microsoft.com/windows/win32/api/pdh/nf-pdh-pdhaddenglishcounterw), the [Energy Meter usage in G-Helper](https://github.com/seerge/g-helper/blob/main/app/HardwareControl.cs), and the [VSB field documentation](https://docs.rainmeter.net/tips/hwinfo/).

The power-flow template includes separate battery input/output, charger input and total-system fields. A device that does not expose charger/system sensors shows unavailable values. You can remove these fields or add other power readings.

Rates require two samples. Reconnection, reset counters and long sleep gaps reset the rate baseline, preventing false spikes. Network speed supports MB/s or Mbps (decimal bytes/bits); cumulative network totals are adapter counters, not a persistent monthly meter. Memory and disk capacity follow Windows binary capacity conventions, labeled GB.

Explicitly selected disconnected devices do not silently switch to another device. On first use, unavailable CPU temperature falls back to usage, and unsupported GPU/battery desktop items are hidden. Unavailable fan or voltage readings are not invented. No fan, power limit, clock, voltage or thermal controls are issued.

Sampling request intervals accept 0.01–5 seconds in Sensors, with up to two decimal places and two seconds as the default. Input follows the current language's decimal separator. Applied changes take effect from the next sampling cycle; uncommitted edits do not affect sampling. Shorter intervals increase overhead and cannot make hardware sensors deliver new data at 100 Hz. CPU package power can reuse a successful value within its 50 ms query window; failures, resume and reset still discard it. Native windows receive readings directly; diagnostic file exports are limited to five writes per second. GPU/activity providers run when requested by visible widget contents; opening the gallery or Sensors briefly enables discovery. Data older than 35 seconds is cleared. Monitoring remains local; the app does not check public IP or contact network services.

## Glass, layout and languages

- Settings request Desktop Acrylic on their separate native background host after the transparent Quick child submits a current frame. Host and child lifetimes are guarded independently. Windows may adapt Acrylic when inactive, as in WUJI. First-show, activation and restore appearance remain visual acceptance gates. Desktop/screen capture is not used to fake glass.
- Windows transparency/high contrast, Remote Desktop and drivers may affect the material. When Acrylic is unavailable, glass skins use a legible solid fallback; minimal digits keep their transparent background.
- Light/dark modes; six shared skins with global or per-widget choices; optional titles and global or per-widget sizing.
- Independent width/height and five internal layout modes; responsive strips flow actual-sized readings instead of stretching a fixed square canvas. Manual positions are normalized and validated against overlap and bounds.
- Desktop widgets default to above wallpaper and below ordinary windows. Each standalone strip/widget can optionally remain on top and target a specific monitor. The settings host has accessible minimize, maximize and close controls, native drag/resize requests and close-to-tray behavior; native snapping and mixed-DPI resize still require Windows acceptance.
- Optional magnetic spacing keeps released widget windows apart, with a configurable 0–64 logical-pixel gap and a short spring animation. Only the dragged window is moved. System or user motion preferences disable the animation. The feature is off by default, preserving existing manual positions.
- A native-frame candidate avoids Qt 6.10's layered frameless path for eligible Windows 11 glass widgets. It processes only registered, current-process window messages, preserves nonactivation, and restores the old flags on failure. Minimal and mixed no-background panels retain the original alpha path. API success remains an unverified material request, not visual proof of desktop blur.
- Automatic layout fits each monitor and retains readable minimum sizes. Unrepresentable arrangements are rejected with a capacity message instead of hiding readings. Combined members retain independent sizes.
- Up to 24 added instances; import/export, undo before applying, atomic preferences and last-valid backup.
- Eight offline languages: 简体中文、繁體中文、English、日本語、한국어、Deutsch、Français、Español. Titles entered by users are preserved. Some diagnostic errors retain English fallback.

Reference ideas: [Apple widget gallery and editing](https://support.apple.com/guide/mac-help/add-and-customize-widgets-mchl52be5da5/mac), [Stats modules and configuration](https://github.com/exelban/stats), [Microsoft Desktop Acrylic](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type). This is original Windows software, not an Apple product.

Stats also includes richer macOS-specific information such as Bluetooth device batteries, advanced Wi-Fi information, top-process popups and timezone clocks. These are not claimed as supported here. Windows AMD/Intel GPU coverage, battery design-capacity/health, OEM power sensors and shell-extension compatibility need further provider work and hardware verification.

## Data and migration

Preferences, positions and bounded logs live in %LOCALAPPDATA%\DesktopStats. No telemetry, cloud service, auto-download or listening TCP port. A current-user named pipe reopens the existing instance.

Version 4/5/6/7 preferences migrate to version 8 without losing custom titles, units, contents or independent widget identities. An old 10-second interval migrates to the new 5-second maximum. Old unused hardware tabs are kept as dormant preferences but do not appear in the added-widget list. Explicit widget order and independent identities preserve duplicates and deletions.

The first native launch unloads only this app's former Rainmeter skins and restores its recorded Rainmeter DPI override when unchanged. Other Rainmeter skins and HWiNFO are retained.

## Develop, verify and build

Python 3.12, Windows x64:

The public source snapshot contains no collector EXE or dependency DLLs. Run
`tools/fetch_sensor_dependencies.py` once before building the collector or
running the complete tests/exporter. It downloads only the pinned official
LibreHardwareMonitor 0.9.6 release, verifies the archive and all nine selected
libraries, and extracts no GUI, driver or installer. It never executes downloaded
code and refuses to replace a differing local library. An offline copy of the
same verified official ZIP can be supplied with `--archive PATH`.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools\fetch_sensor_dependencies.py
$env:DESKTOP_STATS_DATA = Join-Path $PWD '.qa-profile'
.\.venv\Scripts\python.exe tools\build_collector.py --self-test
.\.venv\Scripts\python.exe tools\test_isolated.py
.\.venv\Scripts\python.exe tools\verify_customization.py
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe tools\build.py
~~~

The customization verifier forces offscreen rendering, isolated private settings, synthetic local mouse events, stubbed hardware/composition, and no tray. It does not move the OS mouse, touch the system clipboard, activate windows, or change the installed app. The legacy native/upgrade/scroll tools refuse to open windows unless explicitly passed `--allow-visible-desktop`; run them only while the user is idle. Offscreen captures exclude Windows' composited backdrop and cannot verify actual desktop blur. Physical sensor verification covers Windows 11 x64 at 175% DPI on Ryzen 7940HS / RTX 4060 Laptop; it does not establish universal hardware support.

The main settings and detail raster hosts use the guarded WUJI-style DWM type-3/full-frame/readback path. Existing layered desktop widgets and the top strip keep their separate compatibility backend. The app keeps explicit fallback diagnostics and respects high contrast and system transparency settings. No further native visual test is claimed for this candidate; the user requested implementation directly from the working WUJI source.

The settings window coalesces native surface, visibility, theme and composition events before restoring its material. A transient failure has at most two delayed retries; hidden/minimized windows pause recovery. Native request metadata and the exact transparency policy cause are available through the read-only `--status` command, without screenshots. Explicit high contrast or transparency-off settings keep the readable fallback. Recovery does not spoof focus or override system accessibility settings.

CLI: --background (widgets/tray), --headless (sampler), --quit, --status, --diagnose JSON. DESKTOP_STATS_DATA selects an isolated data folder. `--self-check JSON` requires an explicit empty isolated data folder and a new report path within it; it forces offscreen software rendering, checks bundled QML/assets and draws a card without showing windows, starting hardware sampling, IPC, migration or installation. Failure never displays a message box in this mode.

To extend the app, add a typed metric to metrics.py, implement its read-only provider and optional device scope, then reference it from widget_catalog.py. The gallery, formatting, dependency collection and per-widget picker consume these registries. Test provider failures, unknown values, deltas and migrations. This is source-level extensibility, not an unrestricted executable plugin loader.

The directory build includes replaceable Qt libraries, license texts, application source, immutable upstream source references and SHA-256 checksums. It excludes private preferences, logs, snapshots, credentials and development environments. The preview is unsigned; a checksum is not a signing certificate.

`tools/export_source.py` publishes a different, source-only artifact. Its fixed
file inventory excludes all executable libraries and collector runtime files,
including the old runtime build manifest. It retains canonical dependency
manifests, license texts and source references. Preparing dependencies and
compiling the original collector locally is required before running the full
test suite or re-exporting. A new binary distribution still needs its own
third-party notice and corresponding-source review; a passing source export
does not certify a future binary package.

## Licensing

See [the current application license and exceptions](../LICENSING.md). Public availability does not grant commercial permission for new original application code.

Original application source: PolyForm Noncommercial 1.0.0, subject to the scope in ../LICENSING.md. Previously MIT-licensed Niangao artwork and the unchanged collector wrapper retain their prior rights. UI symbols use unmodified Lucide SVG geometry (ISC, with Feather-derived MIT notices), pinned to Lucide 1.61.0. Complete notices and provenance ship in `assets/lucide/` and `THIRD_PARTY_NOTICES.md`. Qt/PySide/Shiboken: LGPL v3 option with dynamically loaded, replaceable libraries. Reverse engineering for debugging modified LGPL libraries is permitted. Application source, rebuilding instructions, upstream source links and license texts ship in source/ and THIRD_PARTY_LICENSES.txt.

The separately loaded, unmodified LibreHardwareMonitor, DiskInfoToolkit, RAMSPDToolkit-NDD and BlackSharp.Core libraries use MPL-2.0. HidSharp uses Apache-2.0; Microsoft support assemblies use MIT. Embedded PawnIO modules carry LGPL-2.1 notices and exact corresponding-source links, although their hardware groups are disabled here. The collector runtime includes an exact dependency manifest, source provenance and full license texts. See `_internal/collector/THIRD-PARTY-NOTICES.md` in a packaged runtime or `third_party/librehardwaremonitor/0.9.6/NOTICE.md` in source. The app's noncommercial license does not replace or restrict those dependency licenses. Rebuild after changing collector source; packaging verifies hashes and refuses to overwrite a versioned release archive.

Read-only ASUS protocol reference: [G-Helper](https://github.com/seerge/g-helper). [Windows battery structure and units](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_battery_state).

