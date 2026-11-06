# Desktop Stats for Windows

Native Windows top-bar monitoring and optional desktop widgets, with real
hardware readings and local history. Preview release
**0.29.0-preview.3** organizes settings around one live top-bar
preview, separate content/appearance tasks and contextual desktop controls.
Desktop widgets, top bar and preferences save independently. Original application
source is licensed under [PolyForm Noncommercial 1.0.0](../LICENSING.md).

The packaged app needs no browser, Rainmeter, Python installation or cloud login.
Qt Quick provides the interface; Windows supplies supported native background
materials. Transparency, high contrast, remote sessions and display drivers can
change their appearance. A failed or unsupported material request keeps a
readable fallback. Offscreen screenshots and successful API requests alone do
not verify desktop blur. The original Niangao artwork and Lucide symbols remain.

The material recovery introduced in 0.27.0-preview.2 targets loss after
administrator authorization or a hidden top bar returning from fullscreen
avoidance. These return events request the
existing background material again, without permanent polling. Saved layout,
temperature authorization and sampling settings remain independent; visible
blur still needs verification on the target Windows system.
It also isolates blocked NVIDIA cleanup after missing GPU readings so other
requested sensors can continue updating. Only one cleanup may remain pending;
the app does not repeatedly close/reinitialize that source or add normal polling.

## 安装与使用

1. 解压发布包，保留 DesktopStats.exe 与 _internal 在同一目录。双击运行，或用 Install.cmd 安装。升级前先应用或撤销待保存设置；旧版本如不能安全自动退出，请从托盘退出后重试。安装先准备新目录，再换入并保留原版备份；准备、替换或注册失败会尝试回滚并明确记录未完成的步骤，配置文件保持独立。
2. 左侧保留 **桌面组件 / 顶部栏 / 历史记录 / 偏好** 四个主要入口。侧栏的组件列表、**＋** 和场景操作只在桌面编辑页显示；在组件列表旁按 **＋** 添加模板。选中组件后，在同一页查看预览和指标，并调整皮肤、透明度、标题及大小；窄窗口直接上下滚动，不必逐层打开抽屉。
3. 点击 **卡片 / 横条 / 竖条** 一键选择布局。**＋添加指标** 支持连续选择，点击“添加所选”才一次加入；取消或 Esc 不更改组件。每组件最多六项，同一模板可重复添加。
4. 默认使用自适应排列，拖动指标调整顺序。需要手工编辑时展开 **精细排版**；开启 **自由摆放** 后，拖动有边缘/中心吸附和参考线，按住 Alt 临时关闭吸附。拖到另一项中央可交换位置，拖动选中项的小角可调整其区域。
5. 按住 Ctrl 点击多选，再使用 **对齐与均分**。重叠或空间不足的操作不会部分提交；新增指标会保留手动摆放的旧位置，没有空位时向下扩展。移除指标不重铺剩余项。
6. 在组件页直接修改精确宽高，或在 **精细排版** 画布拖动右下角调整真实宽高，内部自动布局随尺寸重排。**适合 / 100% / Ctrl＋滚轮** 只调整编辑显示比例；普通滚轮滚动内容。移动主窗口边缘时暂缓昂贵预览重绘，停下后恢复到最终尺寸，编辑输入和草稿保留。
7. 使用画布底部 **撤销 / 重做** 或 Ctrl+Z / Ctrl+Shift+Z 回退草稿操作。连续标题输入或滑条调整合并为一步；拖动只在松手提交，Esc 可取消当前拖动。**应用到桌面 / 应用顶部栏 / 应用偏好** 只保存当前区域；**放弃更改** 也只撤销当前区域。页底显示 **已保存** 或 **有未应用的更改**，没有更改时不会突出应用按钮。其他区域的草稿和撤销记录保留。导入或恢复默认会明确进入“将替换全部设置”预览，点击 **应用全部设置** 才整体保存；取消可回到之前的草稿。
8. 指标清单保留完整名称和实时值，可点选、排序或移除；数据来源与单位、位置等较少使用的选项按需展开。调整皮肤、透明度或圆角时，现有桌面组件即时预览；点击固定底部的 **应用到桌面** 或 Ctrl+S 才保存。关闭整个设置窗口会恢复已保存外观，未保存草稿仍可重新打开继续修改。布局、设备、采样等其它设置在应用后生效。
9. 在 **桌面组件 → 桌面默认设置** 调整组件的全局材质、大小、布局和磁吸；**偏好** 首屏设置语言、深浅外观、登录启动及检测间隔，**传感器与来源** 查看真实通道和来源。托盘“退出”完全关闭软件。

全屏游戏或应用位于前台时，顶部栏会在被覆盖的屏幕上自动隐藏，关联的详情浮窗和提示也会关闭；切回该屏幕的普通桌面窗口后恢复。启动时即检查已运行的全屏窗口。避让期间保留采样与本地历史，隐藏栏的动效停止，不增加周期性的窗口检查。

设置隐藏或最小化时，预览动效、实时预览投影、历史页查询和额外传感器检查暂停，常规采样继续按已保存的间隔运行。最小化保留未确认分组、筛选与滚动位置；恢复窗口立即显示最近的读数。只改标题、间距等外观内容不会触发额外硬件检查。

### 顶部栏设置

仅启用顶部栏、关闭全部桌面组件的已保存配置，首次打开设置会直接进入 **顶部栏**；
从历史或组件入口打开时仍进入指定页面。正常切页保留本次会话的位置。

顶部栏页共用一个实时预览。**内容与排列** 显示完整指标列表，可拖动排序、选择左右
位置，并通过每项右侧按钮调整或删除；**外观** 集中选择整体设计、材质与透明度。
切换任务不保存草稿；未确认的组合编辑需先确认，否则按取消处理。
**显示顶部栏** 开关立即生效，布局更改须点击 **应用顶部栏** 保存。

### 顶部栏组合读数

选中 CPU 或 GPU 指标后，打开 **组合指标**。可一键加入使用率、温度与功耗，也可从同一硬件的读数中选择最多四项。主指标保留在首位，其余项可调整顺序或移除；清除附加项即可回到原来的单项显示。每组沿用同一个显卡选择、单位和显示样式，拖动、溢出收纳与悬停都以整组为单位。缺测项显示“—”，不会从另一块显卡借数。混合温度、功率的组合使用数字、图标或趋势等样式，不将不同单位当成同一个百分比仪表。

列表每项右侧的调整按钮打开该项设置，垃圾桶移除当前项，误删可撤销。组合窗口内的修改先暂存，点击 **确认** 才提交到顶部栏草稿，再点击 **应用顶部栏** 保存；**取消**、Esc 或点窗口外部不提交。保存失败保留输入，组合在别处被更改时会提示重新打开，避免互相覆盖。

### CPU 详情与可选动效

悬停 CPU 组或 CPU 指标可打开详情，先查看当前值、趋势与软件排行；点击 **逻辑处理器** 展开每核网格，编号从 CPU 0 开始。逻辑处理器可能包括同时多线程，不能当作独立物理核心；物理核心数另列。展开后随详情页滚动查看较多通道，最多展示 1024 项并明确显示截断数量。温度、频率、封装功率与 CPU 风扇按实际来源关联，不编造每核心温度或功耗。首轮采样或故障恢复时先建立基线，过期或失败读数显示原因，不以 0 代替。逐逻辑读数仅实时展示，不增加硬件轮询或持久历史。

顶部栏指标设置中的 **图标动效** 默认关闭，可选择硬件联动、热感、流动、旋转或呼吸（按指标提供适用选项）。硬件联动按各硬件的真实通道分别呈现，组合成员及网络上下行也各自判断。动效仅为视觉反馈，不代表告警或额外传感器；缺测、零活动、窗口隐藏和系统减少动画时停止，切换温度或网速单位不会改变其强度。原有静态图标与显示样式保留。

硬件联动对 CPU/GPU 分别使用负载、温度和功耗，黄红热感与蓝色功耗电弧可同时出现。短电弧会在不同位置和方向出现、分叉、熄灭，十个视觉阶段逐步增加幅度、放电次数和重叠细丝，并在阶段之间平滑过渡；真实读数不分成十档。内存使用实际占用量，网络和磁盘分别使用两个方向，电池分别使用电量、充电和放电，风扇使用实际转速或设备报告的风扇百分比，NVMe 使用真实温度。只叠加有来源的通道；缺测不借另一块设备的值，不从内存占用推测温度，也不把 SSD 损耗作为当前负载。主使用率为零或缺失时，有真实温度或功耗的层仍可独立呈现。

开启动效后可连续调节 **强度**（0–100%）及 **速度**（0.5–2 倍）。强度为零时静止。动效只用于带图标的显示方式；选择没有图标的格式时保留动效设置，不自动改格式。选择“图标与数值”或双向读数即可看到效果。通用风扇符号与功率流动属于装饰反馈。预览版的实物显卡叶轮单独跟随当前 RPM，以固定 120 倍慢放，速度偏好不改变其比例；详见下文显卡风扇说明。

### 硬件图标与型号（0.30.0 预览版）

选单前四项依次为 **1 · 原版**（此前的可爱卡通）、**2 · 可爱笑脸**、**3 · 彩色手绘**、**4 · 纯线条**，每套都使用同一份具体硬件目录，不退回统一盒子图案。其余旧外观仍在选单中。升级保留你当前的选择。

新增 **随手线条、手涂淡彩、笑脸手绘**：随手线条只有略歪、不齐的笔触；手涂淡彩在相同线条间加入疏松的铅笔色；笑脸手绘单独增加小表情。透明图标不带方格纸底纹，方格纸只用于样式预览。三套覆盖当前 147 个显卡、28 个内存、3 个 CPU 条目，沿用已核型号和手动外观选择。Intel 长方形封装与 AMD AM5 八缺口顶盖分别绘制；相同 AM5 封装不虚构外形差异，用型号小标识区分。小标识用于辅助辨认，不复刻原厂刻字位置。

**手绘线稿** 使用简单、略有不齐的线条和留白，不加立体阴影、大片填色或表情。图标切换不需要重启软件，已有 CPU 温度连接会继续使用；只有软件本身重启才需要按已选偏好重新确认系统授权。

在 **顶部栏 → 外观 → 硬件图标** 选择 **经典通用、结构线稿、精简实物、微型实物、柔和双色、可爱卡通、手绘线稿、随手线条、手涂淡彩、笑脸手绘**。十种版本都可选择，升级保留已保存的外观；切换后按现有 **应用顶部栏** 流程保存。实物及卡通风格按已核型号绘制盖板、风扇、外露 PCB 边缘、分段金手指、挡板和散热鳍片边缘；有官方依据时保留型号特征。卡通版覆盖现有 178 个型号，以及磁盘、网络、电池、风扇与其他指标符号；圆润描边和小表情属于插画，不代表厂商印刷或实测状态。标准 32 像素顶部栏中，实物、卡通及手绘显卡使用 30×22 显示区域，CPU/内存为 22×22；经典与原结构线稿仍为 18×18。未知外形与叶片继续明确标注，不补造内部元件或走线。

基础图库包括 103 个显卡代表型号、16 个内存代表型号，以及原有 CPU 示例。经过核实且图示已就绪的完整版本型号会另行加入匹配；同系列的 OC、非 OC、白色、特殊供电和修订版分别记录，不通过删除型号后缀自动合并。有证据证明外观相同的版本才共用图示；结构不同的版本需要单独实现。例如 MSI RTX 5090 SUPRIM SOC/OC 使用独立金属盖板和 STORMFORCE 七叶前扇，不套用 RTX 4090 的外壳；ROG Astral RTX 5090 标准版/OC 版在逐项核对官方图库和外部规格后，共用已核 Astral RTX 5080 OC 的可见散热外观。共用外观不会把另一型号的芯片、显存或读数带过来。

未识别出具体非公型号时，可在该指标的 **外观型号** 中手动选择，详情会标明 **手动外观**。显卡候选只来自当前所选设备已缓存的 GPU 芯片身份，Ti、SUPER、XT 等不同芯片变体不会混为一个候选；设备缺失或身份不明确时，不借用另一块显卡来提供候选或读数。内存也可手动选择图示。手动选择仅改变图示，不改变所选设备、指标、传感器来源和数值，也不证明电脑实际安装了所选零售型号。选回 **自动匹配** 可恢复现有识别规则；切换所选显卡时，也会只清除该项手动外观并恢复自动匹配，保留其余显示设置。打开或切换外观选项复用缓存身份，不增加硬件查询。

展开硬件说明后，**查看接口** 与 **查看供电** 按已有资料提供实体插口的类型和数量示意。视频口的排列、供电插座的安装位置和挡板开孔未核实时会明确说明；示意图不代表已确认的实物顺序。已确认无需外接供电的型号会单独标明；未知供电不当作没有供电。主机接口区分 PCIe/AGP，电气通道数不会被画成未经确认的短金手指。内存接口按已确认的代际、DIMM/SO-DIMM 和物理引脚规格说明；三种实物风格的 DDR4 DIMM、DDR5 DIMM、DDR4 SO-DIMM 缺口按官方正视 PCB 尺寸图的中心、宽度和深度比例绘制，其他未核规格仍保留简化示意。图中的触点细线不是逐针工程图，经典通用与结构线稿保持原样。

本次运行图库共 178 项：147 个显卡、28 个内存和 3 个 CPU 示例。清单中的 56 个具体版本已全部支持，待实现版本为 0；其中 34 项有明确的专用绘图登记，包含原有两款 SUPRIM 5090 和本次新增的 32 个版本处理。就绪表示可以精确选择这个版本，不表示每个外观细节都已查明。ZOTAC Infinity 5080 10A、GIGABYTE GTX 460 Rev2/Rev3 和 BIOSTAR RX 7600 OC 的叶片数仍未知，保持静态；BIOSTAR OC 的盖板未核，界面明确显示为技术示意。基础图库、版本、来源及逐项未知字段见 [硬件覆盖报告](HARDWARE_COVERAGE.json)；它不表示已覆盖市面上每个品牌、系列和版本。

有来源支持的原厂背板和可拆装饰背板可分别按需查看，装饰件图不表示电脑已安装该配件。GC_HPWR 与 16pin 仅在有依据的 SAPPHIRE NITRO+ PhantomLink 版本中按替代供电路线说明，不同时画成两个必接插口。内存 RGB 导光罩只画物理结构，不增加灯效动画，也不读取或推测当前灯光。三种实物风格继续采用浅薄侧面投影；新增外观、接口和背板只按需构建，不增加硬件轮询、动画计时器或采样频率。

### 顶部栏整体设计

在 **外观** 中选择 **经典菜单栏 / 分组胶囊 / 精密仪表**，上方同一个实时预览随选择更新。经典保留紧凑菜单栏轮廓；胶囊用轻底板区分每组；仪表以细分隔和量程刻线组织信息。三套设计共用当前真实指标和原有十种显示方式，不重置单位、设备或排序，也不关闭“跟随全局”材质。旧设置默认沿用经典设计，切换后点 **应用顶部栏** 保存，未应用的改动可撤销。

实时顶部栏拖动时会显示与原项同宽的随行预览及落位线，读数更新不会移动原来的命中区域。松手到栏外，或按住左键时点击右键，可取消本次拖动；实时栏不抢走下方应用的键盘焦点。设置页中的拖动仍可按 Esc 取消。

详情先展示当前读数、最近趋势和按需软件排行；逻辑处理器负载可展开，相关数据与来源继续向下查看。组合采用主项加双列排布；小屏可继续滚动查看来源和缺测原因。图表可用鼠标或方向键逐点查看实际样本，空缺不补成零。自动网卡及系统卷的历史按当前设备身份投影，设备尚未出现的时段保留缺口；“所有物理磁盘”仍表示总吞吐。

动效保留可辨认的硬件结构与固定轴心。CPU/GPU 的过载热感使用黄、橙、红色电弧，功耗使用独立的蓝白色电弧；独立温度计使用随实际温度变化的温柱和局部黄红热晕，不显示任何电流。接收与发送分别使用青蓝及紫色，风扇为青绿，负载内核为蓝紫。颜色、活动范围和节奏根据当前原始读数平滑变化，再受所选强度与速度调节；数字仍直接显示真实读数，不被动画插值。电弧是装饰性的状态表现，不代表测到了物理放电，不是校准转速或温度告警。旧配置仍默认静止；停用动画、缺测、零活动或隐藏时停止。

### 历史记录、场景与诊断

**历史记录** 直接选择指标及设备，再切换 10 分钟、1 小时或 24 小时。右上角可独立暂停记录，不影响实时读数；暂停保留已有记录。清空需要再次确认，作用于本机全部历史，不能撤销。顶部栏详情中的时钟按钮可直达对应指标与设备的历史；未纳入记录的通道不显示该入口。

目前记录 CPU、内存、电池、已支持的功率与风扇指标，以及明确设备标识的显卡和网卡通道。扩展采集器和磁盘通道暂未纳入持久历史。设备断开后仍保留已经选择的历史，不自动混入另一设备。数据库位于独立用户数据目录的 `sensor-history.sqlite3`，不上传；磁盘上的设备标识采用哈希，不写设备名称或地址。

折线连接实际区间均值，不使用平滑曲线；每段细线保留真实最低值到峰值，悬停可查看具体时间、均值及范围。刷新时保持固定时间分组，避免旧样本仅因时间窗移动就重新混成不同均值；首尾分组仍裁剪到查询范围。空白代表缺测，零仍是有效读数。数据按来源时间戳去重，缓存重复读取不算新样本。一秒桶保留一小时，分钟汇总保留七天；普通写盘采用五秒批次门槛（两秒采样时约六秒一次），查询会合并未提交尾部；暂停记录或正常退出时尝试保存尾部。意外终止可能丢失最近尚未提交的一批数据。页面最多约每两秒查询一次，不随每个快速采样事件反复绘制。存储失败会保留错误和有界内存缓冲，实时采样继续运行；退出时尝试保存剩余记录。

组件列表旁的 **场景** 提供日常办公、性能观察和电池续航方案。先点击卡片看真实组件的当前读数预览，再选择 **使用方案**；预览本身不保存。场景只替换桌面组件与顶部栏设置，保留语言、采样、登录启动等通用偏好。内置方案沿用当前屏幕和材质；自存方案恢复保存时的组件与栏设置。尚有布局草稿时会在面板内提示确认。**保存布局** 可保留最多八个自定义方案，名称最多二十个字，场景文件共用 8 MiB 的 UTF-8 大小上限；自定义卡片可通过垃圾桶移除，需要行内再次确认。**上次布局** 恢复场景切换前的已保存布局，不是恢复未保存输入。方案保存在独立的 `scenes.json`，不随公开源码导出。

在 **偏好 → 传感器与来源 → 来源诊断**，每张卡先说明状态、明确原因和可执行的下一步，接口名和数值错误码按需展开。**重新检查** 请求新一轮读数，保留各来源的重试间隔，不安装驱动或改变权限；没有收到新样本时会明确提示。**导出诊断** 只包含软件版本及白名单内的接口状态、原因和错误码，不包含原始读数、设备标识或本地路径。

在侧栏 **顶部栏** 设置系统屏幕边缘栏：可选择主屏、所有屏幕或指定屏幕，高度 28/32/40 个逻辑像素，最多 64 项指标。顶部固定开关直接启停；预览明确标出未启用状态。先选“紧凑数字 / 均衡 / 迷你图表”模板，再点单项编辑。检查器保留一个实际比例预览，点击 **显示方式** 在原页展开完整样式预览，选中即收起；位置、精度、单位和设备可直接调整，来源按需展开，错误原因直接显示。原有八种显示方式保留：标签、纯数值、图标、趋势、柱状、圆环、迷你图表、上下两行。网络速度、磁盘读写和电池侧充放电另外支持 **双向读数 / 单行双向**；两方向共用同一个所选设备和单位，缺读数显示“—”，真实零值保留。已知 0–100% 量程才推荐柱状和圆环，NVMe 已用寿命不冒充占用率。拖动列表或预览可放到左侧、右侧并排序，实时顶部栏也可直接拖排；存在未应用的顶部栏修改时，需先应用后再拖实时栏。趋势复用最近最多 40 次已有读数，不额外采集；无效读数留断点。此页应用只保存顶部栏，保留其他组件的草稿和撤销记录。

**顶栏外观** 可跟随全局，或独立选择材质和 0–100% 连续底色透明度。跟随全局时直接拖动透明度，会自动改为当前栏的独立设置；实时预览后点击 **应用顶部栏** 保存。底色透明度与 Windows 背景模糊分别处理：透明底板不代表模糊已生效。系统不支持、关闭透明效果或启用高对比度时使用可读回退。

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

Per-user installation: %LOCALAPPDATA%\Programs\DesktopStats. The ordinary app runs without administrator rights and installs no drivers. The optional ASUS temperature bridge requires a separately authorized administrator session. Desktop and Start menu shortcuts are included. Start at login is optional and off by default. Bridge recovery is a separate opt-in preference that still requires authorization after the app starts. Uninstall via Windows Settings or Uninstall.cmd; preferences are retained for a reinstall.

## Available readings

### Runtime resource behavior

The native GUI delivers readings directly in memory. Periodic legacy
`state.txt`/`latest.json` exports are disabled for this path; old files can remain
on disk with their old timestamps. `--headless` and standalone sampler operation
retain those exports. Use the existing current-user IPC `--status` or
`--diagnose JSON` for a fresh on-demand report.

Disk throughput does not request volume-capacity queries. Capacity metrics and
explicit source inspection still request them. Inactive/hidden/minimized history
pages do not project device options or query the store; selection metadata is
restored on reopening. Decorative icon cadence, assets and visible interpolation
remain in use, with unused channel calculations skipped.

The native history backend uses a five-second normal write gate. With the default
two-second sampling interval, commits normally occur about six seconds apart.
Every accepted observation is still aggregated, and queries merge the pending
memory tail with the database. Explicit recording pause and normal shutdown
attempt to save pending data. Unexpected process termination can lose the most
recent uncommitted batch; a paused or failing writer does not establish a strict
five-second durability guarantee. The pending buffer and existing retention
limits remain bounded. This batching does not change sensor polling frequency.

### Hardware appearances, model selection and fan RPM (development)

The source-linked base catalog contains 103 GPU and 16 RAM representatives,
alongside the existing CPU examples. Ready exact versions extend that catalog
only after their visible exterior is reviewed and either confirmed to share art
or given an independent structural recipe. OC/non-OC, white, rear-power and
revision suffixes are not discarded. MSI RTX 5090 SUPRIM SOC/OC has its own
metal-panel cover and STORMFORCE seven-blade front rotors; reviewed ROG Astral
RTX 5090 standard/OC exteriors share the reviewed Astral RTX 5080 OC art only
after checking official images and external specifications. The
[coverage report](HARDWARE_COVERAGE.json)
records all 56 supported version registrations, with zero pending versions, and
the unknown fields that remain. The 0.28.0-preview.2 runtime catalog has 178
entries: 147 GPU, 28 RAM and 3 CPU. Its 34 explicit artwork registrations include
the two earlier SUPRIM 5090 entries and 32 new treatments. This is a bounded
inventory, not a claim of full market coverage or complete visual verification.

All seven selectable icon versions remain available: Classic, Outline, Solid,
Miniature, Soft, Cute Cartoon and Hand-drawn Lines. Existing settings retain Classic. Reviewed model colors,
exposed PCB edges, separated contacts, bracket and heatsink edges refine the
hardware drawings. Internal PCB layouts, unverified notches and bare-board
lengths are not invented. Electrical PCIe lanes do not establish mechanical
connector length. Port and power views show documented connector types and
counts, with unverified order and position explicitly labelled; they are not
physical installation diagrams.

Factory backplates and documented removable accessories have separate on-demand
views. GC_HPWR and 16-pin are alternative routes only on the source-confirmed
SAPPHIRE NITRO+ PhantomLink editions, never simultaneous required sockets. RAM RGB covers are
static physical diffusers. Modern drawings retain shallow side projection, and
these new exterior views add no hardware polls, timers or sampling cadence.

Modern DDR4 DIMM, DDR5 DIMM and DDR4 SO-DIMM keys use the nominal center,
width and depth ratios from published front-view PCB mechanical drawings.
Other unreviewed classes retain schematic keys; contact dividers do not depict
every physical pin. Classic and Outline remain unchanged.

An optional Appearance model choice is labelled Manual appearance. GPU choices
use only the selected device's cached chip identity; chip variants and missing
secondary GPUs cannot borrow another device's cooler or readings. RAM art can
also be selected manually. Only the illustration changes: metrics, device
targets, sensor sources and values stay the same. Selecting Automatic matching
restores the existing resolver, and opening or changing these choices adds no
hardware query. Manual art does not establish the installed retail model.
Changing the GPU target clears only that item's manual artwork choice and
restores automatic matching, preserving its other display preferences.

Blade counts, rings, linked blade groups, hubs and relative counter-rotation
are applied only where exact-model references support them. A bare GPU chip
name does not establish a retail cooler. Illustration proportions are visual
estimates, not measured factory dimensions. Source-confirmed light and dark
rotors retain their own colors; fixed shroud rings do not rotate with the fan.
Unreviewed active fan faces are labelled pending and remain neutral and static.
The completed export has 119 motion-ready GPU entries. ZOTAC Infinity 5080 10A,
GIGABYTE GTX 460 Rev2/Rev3 and BIOSTAR RX 7600 OC retain unknown blade counts.
BIOSTAR OC's unverified cover is explicitly labelled as a technical schematic.
The offline gallery enables motion only for reviewed fan faces; field-level
limits remain recorded in the coverage report. Black and white Astral front
fans preserve the source-confirmed reversed center fan.

Solid, Miniature and Soft Auto effects use fresh same-card current RPM, displayed
unchanged and animated at a fixed 120x slow-motion scale. Higher RPM rotates
faster in the same proportion. Zero stops; missing, failed or stale readings
remain unknown and stop. Load, temperature, percentage and intended fan speed
do not substitute for current RPM. Classic, Outline and manual Pulse keep their
static hardware illustrations. The offline gallery's RPM control is explicitly
simulated and never reads the computer.

The NVIDIA provider uses a bounded read-only NvAPI query, at most once per
second per requested card, with cached capability/PCI matching and five-second
transient-failure backoff. The private CurrentRpm interface follows
[LibreHardwareMonitor v0.9.6](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/blob/v0.9.6/LibreHardwareMonitorLib/Interop/NvApi.cs);
it is labelled driver current RPM, without claiming independent physical
validation. Where unavailable, the provider tries the public single-channel
[tachometer](https://docs.nvidia.com/nvapi/group__gpucooler.html). Driver cooler
channel IDs do not establish left/center/right physical positions: a labelled
card channel mean drives the illustrated fans together. This does not claim
independent per-fan speed. AMD/Intel RPM remains unknown without a compatible
same-card provider. No fan controls, new driver, service, administrator prompt,
polling thread or animation timer is added. Existing sampling and hidden-window
animation pause behavior remain; an enabled Auto item still requests sampling
while the bar is temporarily hidden by fullscreen avoidance.

### ASUS CPU temperature bridge

The optional local adaptation can read the already-running ASUS COM service's
exact `CPU` sensor (`0x06030012`, decimal `100859922`) on the verified ASUS desktop.
The source is labelled **ASUS COM · CPU**. It does not claim a package or core
temperature. The tenths-Celsius convention is corroborated by the original
[client implementation and protocol notes](https://github.com/fjorge9-arch/gmk104-aura/blob/6809c252a14abf656874d443d5b10979a196d2f9/python/gmk104aura/cpu_temp.py);
this is client evidence, not an ASUS specification. Only the documented sensor
ID plus exact name is accepted; arbitrary motherboard/ACPI temperatures are not
substituted. The app does not copy that client's monitoring-start or refresh code.

This is a machine-specific adaptation, not a universal CPU temperature
provider. A PC without the verified ASUS service/sensor remains unsupported.

An ordinary process cannot activate this machine's ASUS COM interface. Therefore
an explicitly authorized **separate elevated bridge** reads the cache; the main
Desktop Stats app stays unelevated. The bridge checks the existing `asComSvc`
service is running and locates the unique fixed CPU sensor once. Every two
seconds it obtains a fresh `Sensors` collection, reads that fixed index, verifies
the exact ID/name and reads `current`, then releases the snapshot. Retaining only
an old sensor view produced unchanged readings in the machine comparison while
reacquired views changed. The vendor's internal cache policy is undocumented;
this implementation uses the observed updating path rather than assuming that
a successful getter alone proves freshness. It never calls setters,
monitoring startup, refresh, fan controls, or service start/stop. There are no new
drivers, services, scheduled tasks or startup entries.

The bridge publishes a 64-byte seqlock snapshot in current-session shared memory.
The current user receives read access only; the mapping includes the user SID
and owning app PID. The bridge verifies the installed executable path, same user
and process creation time, then exits when that app process exits. No polling
files, HTTP port or arbitrary command interface is used. Launching a second
bridge for the same app is refused. The bridge has no startup entry and cannot
approve its own elevation.

In **Preferences**, **Restore CPU temperature at startup** is disabled by default.
Enable it only on a supported machine with the existing ASUS service. Each app
session then offers one Windows administrator authorization prompt; fullscreen
games/apps defer it until returning to the desktop. Canceling suppresses further
prompts for that session. Accepting starts the read-only bridge for that app
process; it still exits with the app. This option does not install a general CPU
temperature driver or start a missing ASUS service.

Alternatively, to enable it for one running application session, run this PowerShell code and
approve Windows' UAC prompt:

~~~powershell
$statsExe = Join-Path $env:LOCALAPPDATA 'Programs\DesktopStats\DesktopStats.exe'
$statsInstances = @(Get-Process DesktopStats -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $statsExe })
if ($statsInstances.Count -ne 1) { throw 'Start exactly one installed Desktop Stats instance first.' }
$statsBridge = Join-Path (Split-Path $statsExe) '_internal\cpu-temperature\AsusCpuTemperatureBridge.exe'
Start-Process -FilePath $statsBridge -WindowStyle Hidden -Verb RunAs `
    -ArgumentList @('--app-pid', [string]$statsInstances[0].Id)
~~~

Successful getter time is an observation of the ASUS service cache, not a promise
about the hardware's internal sampling rate. The ordinary sampler reads shared
memory at most once per two seconds; faster UI requests reuse the same observation
timestamp. Invalid, future, failed or over-eight-second-old snapshots produce a
missing value. A persistent COM failure clears the snapshot immediately and waits
60 seconds before reconnecting. The existing ASUS ACPI and HWiNFO fallbacks remain
available. Source diagnostics expose the fixed API name and actual error code.

For a source rebuild, run
`python tools/build_cpu_temperature_bridge.py --self-test` before `tools/build.py`.
The self-test uses synthetic anonymous memory only, without COM, hardware or
elevation. The pinned original collector's enabled hardware groups are unchanged.

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

- Windows provides the native background material behind the Qt Quick interface. Appearance depends on system support and policy; first show, activation and restoration need on-device verification. Desktop/screen capture is not used to simulate glass.
- Windows transparency/high contrast, Remote Desktop and drivers may affect the material. Unsupported or failed requests retain a legible fallback; minimal digits keep their transparent background.
- Light/dark modes; six shared skins with global or per-widget choices; optional titles and global or per-widget sizing.
- Independent width/height and five internal layout modes; responsive strips flow actual-sized readings instead of stretching a fixed square canvas. Manual positions are normalized and validated against overlap and bounds.
- Desktop widgets default to above wallpaper and below ordinary windows. Each standalone strip/widget can optionally remain on top and target a specific monitor. The settings host has accessible minimize, maximize and close controls, native drag/resize requests and close-to-tray behavior; native snapping and mixed-DPI resize still require Windows acceptance.
- Optional magnetic spacing keeps released widget windows apart, with a configurable 0–64 logical-pixel gap and a short spring animation. Only the dragged window is moved. System or user motion preferences disable the animation. The feature is off by default, preserving existing manual positions.
- A native-frame candidate avoids Qt 6.10's layered frameless path for eligible Windows 11 glass widgets. It processes only registered, current-process window messages, preserves nonactivation, and restores the old flags on failure. Minimal and mixed no-background panels retain the original alpha path. API success remains an unverified material request, not visual proof of desktop blur.
- Automatic layout fits each monitor and retains readable minimum sizes. Unrepresentable arrangements are rejected with a capacity message instead of hiding readings. Combined members retain independent sizes.
- Up to 24 added instances; import/export, undo before applying, atomic preferences and last-valid backup.
- Eight offline languages: 简体中文、繁體中文、English、日本語、한국어、Deutsch、Français、Español. Titles entered by users are preserved. Some diagnostic errors retain English fallback.

Reference ideas: [Apple widget gallery and editing](https://support.apple.com/guide/mac-help/add-and-customize-widgets-mchl52be5da5/mac), [Stats modules and configuration](https://github.com/exelban/stats), [Microsoft Desktop Acrylic](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type). This is original Windows software, not an Apple product.

Stats also includes richer macOS-specific information such as Bluetooth device batteries, advanced Wi-Fi information and timezone clocks. These are not claimed as supported here. Windows AMD/Intel GPU sensor coverage, battery design-capacity/health, OEM power sensors and shell-extension compatibility need further provider work and hardware verification.

### Software using this hardware

CPU, RAM, GPU and dedicated-VRAM details show up to five software names, sorted
by actual usage after merging processes with the same case-insensitive name.
CPU percentages use the whole machine's logical-processor capacity. RAM shows
working-set bytes, including shared pages. GPU rankings select the busiest
engine after grouping software on the identified Windows adapter; percentages
from different engines are not added. Dedicated VRAM includes cross-process
shared allocations, so summing the software rows does not give device totals.
These definitions follow [psutil](https://psutil.readthedocs.io/stable/#psutil.Process.memory_info)
and [Microsoft's GPU accounting](https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/).

The separate process worker normally updates about once per second while
software activity is needed. In top-bar details the ranking area must also be
in view; scrolling it away, closing/hiding the detail or minimizing its native
host releases demand. Desktop-widget details retain their visible-card demand.
CPU needs an initial rate baseline; unavailable or warming-up readings explain
their state. Source notes and technical details are under Sources and limitations.

Names are transient and excluded from history, settings and diagnostic
exports; command lines, accounts and executable paths are not requested. Access
restrictions produce a partial-coverage notice. GPU mapping uses DXGI LUIDs and
physical locations, with explicit errors for ambiguous or unavailable sources.
Temperature/power pages can show associated CPU/GPU activity, never an invented
per-software temperature or watts value. Per-process network tracing is not
enabled, and general process I/O is not mislabelled as selected-disk traffic.

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

Native background materials are prepared separately from the Qt Quick
foreground. Keep fallback diagnostics and respect high contrast and system
transparency settings. Verify the packaged app on Windows after material changes;
offscreen captures and API success do not establish the visible backdrop result.

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

