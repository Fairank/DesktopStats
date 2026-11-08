# 按需硬件扩展包

0.47 源码候选的可选库共 **314 个产品＝72 CPU＋167 冷却＋75 水路**；加本体514个产品，全库为828个具名产品，另有一套非零售参考组合。六套固定画法与13个保存值共用型号和物理结构，原版无笑脸，不新增外观。

新增12款GPU冷头来自3品牌，提供4个集合／品牌替代包；旧0.46的63条水路和15包保留，水路合计75条、19个有重叠的替代下载包。**GPU冷头当前只独立检视，不替换整卡、不安装到PCB、不连接回路。** 范围、最低0.47版本、实际包字节和SHA256见[GPU冷头说明](GPU_BLOCKS047.md)与[新包索引](GPU_BLOCK_PACKS047_INDEX.json)。厂商名单匹配不等于机械安装通过。

同一型号不要重复安装集合、类别或品牌包。19个水路替代包不是19份互不重复的产品，也不应全部导入；原63条集合与新增GPU冷头集合不重叠，可按需要分别选择。没有自动下载或后台目录轮询。

## 0.46 水路包（历史范围，继续保留）

0.46 新增可独立选择的 CPU 冷头、水泵／电机／泵盖、水箱、泵箱组合、接头与管材，共63款、15个替代包，最低需要0.46或后续兼容版本。这个历史索引不包含0.47新增GPU冷头，见[0.46水路部件说明](LOOP_COMPONENTS046.md)和[原包索引及SHA256](LOOP_PACKS_INDEX.json)。

0.45 将新增风扇、散热器和独立冷排接入已有 CPU 数据包机制。全部共用六套固定展示（原版、可爱笑脸、彩色手绘、纯线条、奶油贴纸、拼色剪纸）及其余七个历史选项，不复制十三份型号或网格。现有类别和待核项完成前不增加外观方案；原版无笑脸。

在「整机视图 → 硬件扩展包」主动进入 GitHub 下载，再选择「导入扩展包」。型号进入相应的散热器、风扇、冷排、参考CPU选择器或独立水路检视类别；GPU冷头不会因此出现在已支持的整卡替换／连管流程中。删除包会保留偏好中的型号ID；缺失型号明确回退，不把别的型号当成该产品，也不借用本机另一配件的温度或RPM。

## 0.45 冷却包如何选择（历史文件，继续保留）

新增冷却库有 167 个产品：40 个风扇、23 个散热器、104 个冷排。下表 32 个文件是 **3 个整类集合＋29 个品牌分类替代包**，不是 32 份互不重复的产品。选每类集合最简单，三包共 **37,392 字节**；按品牌选择可只下载所需数据。集合和包含同一型号的品牌包不能同时导入，程序会拒绝重复 ID。不要将所有 32 个替代包一起安装。

这些0.45冷却文件最低需要0.45.0-preview.1；0.46水路包及0.47 GPU冷头包另有各自最低版本。0.47当前源码候选尚未在本机重新安装验收，不能因目录出现就宣称原生验收完成；游戏期间没有替换正在运行的Stats。CPU的Intel／AMD两包及其校验值继续见[CPU包清单](HARDWARE_PACKS_INDEX.json)。冷却包的逐型号、SHA-256、最低版本见[冷却包清单](COOLING_PACKS_INDEX.json)。

| 选择包 | 类别 | 产品数 | 字节 |
| --- | --- | ---: | ---: |
| [All fan models](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-collection-045-1.0.0.dspack) | fan | 40 | 10360 |
| [APNX fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-apnx-045-1.0.0.dspack) | fan | 1 | 3145 |
| [ARCTIC fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-arctic-045-1.0.0.dspack) | fan | 7 | 4010 |
| [Antec fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-antec-045-1.0.0.dspack) | fan | 1 | 2971 |
| [Cooler Master fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-cooler-master-045-1.0.0.dspack) | fan | 3 | 3342 |
| [Corsair fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-corsair-045-1.0.0.dspack) | fan | 1 | 3018 |
| [DeepCool fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-deepcool-045-1.0.0.dspack) | fan | 4 | 3700 |
| [Fractal Design fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-fractal-design-045-1.0.0.dspack) | fan | 2 | 3300 |
| [Lian Li fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-lian-li-045-1.0.0.dspack) | fan | 3 | 3224 |
| [Montech fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-montech-045-1.0.0.dspack) | fan | 1 | 2906 |
| [NZXT fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-nzxt-045-1.0.0.dspack) | fan | 1 | 2971 |
| [Noctua fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-noctua-045-1.0.0.dspack) | fan | 8 | 4094 |
| [Phanteks fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-phanteks-045-1.0.0.dspack) | fan | 2 | 3402 |
| [Thermaltake fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-thermaltake-045-1.0.0.dspack) | fan | 2 | 3390 |
| [be quiet! fan](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-fan-be-quiet-045-1.0.0.dspack) | fan | 4 | 3421 |
| [All cooler models](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-collection-045-1.0.0.dspack) | cooler | 23 | 9678 |
| [Cooler Master cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-cooler-master-045-1.0.0.dspack) | cooler | 1 | 2913 |
| [Corsair cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-corsair-045-1.0.0.dspack) | cooler | 5 | 4358 |
| [DeepCool cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-deepcool-045-1.0.0.dspack) | cooler | 4 | 3879 |
| [NZXT cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-nzxt-045-1.0.0.dspack) | cooler | 3 | 3936 |
| [Noctua cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-noctua-045-1.0.0.dspack) | cooler | 5 | 4565 |
| [Thermalright cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-thermalright-045-1.0.0.dspack) | cooler | 2 | 3119 |
| [be quiet! cooler](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-cooler-be-quiet-045-1.0.0.dspack) | cooler | 3 | 3294 |
| [All radiator models](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-collection-045-1.0.0.dspack) | radiator | 104 | 17354 |
| [Alphacool radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-alphacool-045-1.0.0.dspack) | radiator | 46 | 8342 |
| [Barrow radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-barrow-045-1.0.0.dspack) | radiator | 6 | 4125 |
| [Bitspower radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-bitspower-045-1.0.0.dspack) | radiator | 13 | 4912 |
| [Bykski radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-bykski-045-1.0.0.dspack) | radiator | 15 | 5521 |
| [CORSAIR radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-corsair-045-1.0.0.dspack) | radiator | 6 | 4010 |
| [EK radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-ek-045-1.0.0.dspack) | radiator | 5 | 3890 |
| [Watercool radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-watercool-045-1.0.0.dspack) | radiator | 7 | 4055 |
| [XSPC radiator](https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/cooling-library-v045/model-packs/v045/DesktopStats-radiator-xspc-045-1.0.0.dspack) | radiator | 6 | 4621 |

## 占用控制

- 未安装的作者目录不由运行程序导入；包读取本身不启动后台下载、定时目录轮询或新增硬件查询。
- 目录初始化只保留有界的型号索引；完整许可与声明校验后释放，以完整清单摘要检查后续读取一致性。所有类别共用最多 8 条已选记录的缓存。
- 新增散热器保存其已核原装风扇描述，独立下载即可绘制。相同原装描述直接复用，避免再读另一个可选包；用户另选不同风扇仍按相应 ID 读取。
- 只为所选配件生成几何。包不持有网格、贴图或图形上下文；整机仍复用一个物理场景，风格切换不重建物理数组，关闭释放。更新／删除包会使相关场景及小图缓存失效。
- 单包最多 256 型号、1.5 MiB 文件；单配置最多 16 包、共 1,024 可选型号；现有几何和线条预算不提高。

0.45历史隔离测量中，三集合167产品的索引对象图为155,401字节；加上体积最大的8条已选记录为244,906字节。40次缓存命中没有读盘或目录扫描。此处只计当时的Python对象图，**不包括Python／Qt、窗口、网格、GPU，也不是0.47全库314条可选记录或整个软件的内存**；全程序真实占用仍待桌面验收。方法及范围见[性能记录](SCOPED_PERFORMANCE045.json)。

0.47图库制图按需交给低优先级工作线程串行执行，需求队列有界；隐藏、关闭或换需求会使过期结果失效，运行任务通过取消检查退出。这改善界面响应，仍需要制图CPU，未测得整款CPU／RAM降幅。CPU／GPU模型小组件最小化时暂停快照刷新，恢复后更新当前状态；全局硬件采样不由此推断停止。见[异步任务回归](../tests/test_accessory_jobs047.py)和[模型小组件回归](../tests/test_desktop_hardware_models040.py)。

## 数据、来源和边界

包是只含 `manifest.json` 与 `models.json` 的 ZIP，程序不解压、不加载脚本、不自动请求来源链接。严格校验成员、数量、大小、重复 JSON 字段、有限数值、各类字段、身份／选择器一致性、SHA-256 与型号冲突。内容摘要检查一致性，不是数字签名或发布者认证。

五个顶层数据类别为CPU、fan、cooler、radiator、loop；loop现严格区分CPU冷头、GPU冷头、泵、水箱、泵箱、接头与管材七个子类。GPU冷头是loop子类，不是整张显卡数据包。完整显卡本体、主板、机箱、内存、电源和存储尚不能作为相应同格式包导入。不能改文件后缀冒充受支持的数据包。冷排、风扇分别选择；密封AIO保留其原厂冷排，不将它改成任意自定义回路。

新增冷排中 15 条 Bykski 使用明确标注的独家美国经销商资料，其余引用厂商公开来源。全部精确端口坐标与内部水道未核；已观察口才绘制。新风扇有 11 条叶数未核，保留静态参考；定性叶型也不是 CAD。未确认孔距、尺寸、方向和独立测速不自动变成已验证数值。产品完整外包络、部分轴尺寸及参考值分开记录，参考屏幕不显示伪造读数。

包包含完整 PolyForm Noncommercial 1.0.0 许可与原创声明。原创代码和数据禁止商业使用，产品名称／商标归各自权利人；第三方组件许可独立保留，见 [LICENSING.md](../LICENSING.md) 与 [NOTICE](../NOTICE)。不包含装机模拟器资产、厂商照片、CAD 或商标图像。

## 可复现导出

CPU作者工具为`python tools/export_hardware_packs.py`。冷却工具`python tools/export_cooling_packs045.py`导出`model-packs/v045`；原水路工具`python tools/export_loop_packs046.py`保留`model-packs/v046`与旧索引；新增GPU冷头工具`python tools/export_gpu_block_packs047.py`导出`model-packs/v047`与独立新索引。同数据产生同字节，不覆盖不同内容的既有版本。已发布包必须变更数据版本和文件名后再发布。作者模块只在明确导出时使用，运行程序没有导入它们的路径。
