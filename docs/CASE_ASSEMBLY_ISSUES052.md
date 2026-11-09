# 0.52 机箱下舱、风扇与装配参考的实际问题

本文记录已复现的模型错误、对应的来源和继续验收的边界。它不是机箱兼容表、厂商 CAD 或全市场完成声明。本轮没有安装或重启运行中的 Stats，没有读取游戏画面、真实硬件或控制设备；Windows 原生验收仍未完成。

## 审计范围与问题口径

初次检查从现有 **96 款机箱**中，选取目录明确声明前置 120／140 mm 风扇的 **27 款**，形成 **49 组构建**：25 组 120 mm、24 组 140 mm。使用明确选择的 ARCTIC P12／P14 参考风扇，先保留实际部件，再检查前下风扇与旧实心电源罩。

其中 **18 组配置、涉及 12 款机箱**取得了实际穿插的正证据：不仅是空包络重叠，还找到实际风扇材料与封闭实心罩的共同内部区域。风扇中央的空孔不能算成实心，也不能把没有成功生成部件当作“没有碰撞”。其余构建未得到同类正证据，不能据此签发净空或兼容证书。

另外 **69 款没有相应的目录前置声明**，未进入这一批构建。这是数据／检查范围缺口，不是现实产品不支持前扇；例如目录空声明不能反过来证明某个零售机箱无法安装风扇。27／49 也不代表 96 款全通过，更不是市场覆盖率。

后续各阶段的风扇、PSU、主板、软管、界面和渲染检查范围不同；不把这些测试数相加成一个最终通过总数。最终结论必须绑定同一份冻结源码及实际配置。

## 12 款确证问题与结构修正

下表的 120／140 指初次取得穿插正证据的试件尺寸，不是该型号全部支持尺寸或全部失败配置。外观事实与未标注的坐标分开：薄板厚度、孔位比例、前缘深度、折弯及安装间隙仍是固定原创参考，`positions_verified`／`dimensions_verified` 不因此改成制造已核。

| 确切机箱与初始正证据 | 原错误与本轮结构差异 | 仍须保留的边界 |
| --- | --- | --- |
| **NZXT H5 Flow 2024**（`nzxt-h5-flow-2024`）；120 | 以开孔薄顶、可见侧网皮和前端 U 形下探缺口替代整块填满的舱。官方 2024 手册明确 PSU 风扇朝上；两把底扇安装在电源罩顶部，不能沿通用底扇平面塞入 PSU 舱，也不能套用 2022 款斜向进风结构。 | 顶面高度、缺口大小、网孔采样及底扇间隙是参考；旧手册的过时净空数值不覆盖现行厂家更正。来源：[2024 规格](https://support.nzxt.com/hc/en-us/articles/40225168535451-H5-Flow-2024-Specs)、[官方手册 p2](https://cdn-g.nzxt.com/dl/1724123146-h5-flow-h5-flow-rgb-2024-digital-manual_240401_v1.pdf)。 |
| **Fractal North Mesh**（`fractal-north-mesh`）；120 | 标准 North 自己的薄顶、侧围、前端下落与圆弯过渡，不能借 North XL 的尺寸和前缘。下舱保持空腔，不用实心盒封住最低前扇。 | 前下落位置和厚度为图示比例；顶置冷排另有宽度／内存限高条件，不能由前扇通过推导顶排通过。来源：[确切 North](https://www.fractal-design.com/products/cases/north-series/north/north-chalk-white/)、[官方手册](https://www.fractal-design.com/app/uploads/2022/12/North-Manual-V1.2.pdf)。 |
| **Cooler Master HAF 700 EVO**（`cooler-master-haf-700-evo`）；140 | 主舱底部实际为开放冷却支架，PSU 在主板背后；删除不存在的主舱水平实心罩。补独立通风底架和带开口的主板托盘，PSU／板位按后舱参考布局处理。 | 厂商背线空间事实不等于本模型内部锚点实测；选择的后舱宽度、板到托盘间隔及 PSU 位置仍是参考，不能把主舱当传统底置 PSU 舱。来源：[官方产品／内部结构](https://www.coolermaster.com/en-us/products/haf-700-evo.html)。 |
| **be quiet! Shadow Base 800 FX**（`be-quiet-shadow-base-800-fx`）；120、140 | 薄上盖、侧皮与独立通风导流盖保留，下方是空 PSU 舱；导流盖不是封死前下扇的竖直端墙。 | G／J 部件区分来自厂商署名手册图；本次手册读取使用镜像，未核实镜像与失效原端点的逐字节同一性。未标孔／折角仍为参考，不能称厂商 CAD。主来源：[官方产品](https://www.bequiet.com/en/case/4483)。 |
| **LIAN LI LANCOOL III**（`lian-li-lancool-iii`）；120、140 | 两侧下方翻网门、独立上方通风托架、三块可拆 fan／SSD 安装盖板各保身份。手册要求装上方风扇／冷排前卸安装盖板；不填满 PSU／HDD 舱。前扇支架四种固定模式也不能简化为任意动态挖孔。 | PSU 手册图为下吹。拆盖协议只对实际已生成的对应上方冷却部件成立；当前 `above_psu_shroud` 的独立机箱风扇选择／安装消费链已分阶段通过7项公共主机、5项消费端、7项配置与6项条件检查；360毫米冷排、水路与真实机械拆卸仍待单独完成。来源：[产品说明](https://lian-li.com/product/lancool-iii/)、[官方链接手册 p2／6／9／12／16](https://drive.google.com/file/d/1kd9ku_raF2uXWeLD7voGfT4ZZ10XOizy/view?usp=sharing)。 |
| **NZXT H7 Flow 2024**（`nzxt-h7-flow-2024`）；120、140 | PSU 竖置在下部后侧，主舱底部开放供三把 120 mm 风扇；用下部隔板、窄折边和开放底架替代全宽实心罩及封住进风的通用底板。没有把整个机箱改成全高双仓。 | PSU／主板／底扇位置是参考；底扇绕安装轴半转只代表一种合法参考安装朝向，不能声称检测到用户实际朝向。来源：[2024 规格](https://support.nzxt.com/hc/en-us/articles/40379376386203-H7-Flow-2024-Specs)、[2024 官方手册 p2](https://cdn-g.nzxt.com/dl/1716886070-h7-flow-h7-flow-rgb-2024-digital-manual_240322.pdf)。 |
| **Fractal Meshify 2 Light TG**（`fractal-meshify-2-light-tg`）；120、140 | 固定薄罩加两块独立可拆前顶盖；前置实际冷却进入相应材料区域时，按手册移除完整顶盖，保留固定侧围与支承，不按风扇轮廓临时切洞。 | 标准布局与储存布局不能混为一谈；顶置 120 外轨／140 内轨及 RAM／VRM／软管的实际链仍在补验。来源：[确切型号](https://www.fractal-design.com/products/cases/meshify-series/meshify-2/meshify-2-black-light-tg/)、[官方手册](https://www.fractal-design.com/app/uploads/2023/08/Meshify-2-Manual-V.4-2023-08-21.pdf)。 |
| **Fractal Define 7 Compact Solid**（`fractal-define-7-compact-solid`）；120 | 保留真实薄罩、侧围及两块可拆前顶盖，把可拆完整部件与固定材料分开，避免实心舱堵住最低前扇。 | 顶置冷排的 40 mm 内存限高条件不能省略；顶排／低矮 DIMM 的实际构建、管路和界面仍须同源补验。来源：[确切型号](https://www.fractal-design.com/products/cases/define-series/define-7-compact/define-7-compact-black-solid/)、[官方手册](https://www.fractal-design.com/app/uploads/2023/08/Define-7-Compact-Manual-V.2-2023-08-21.pdf)。 |
| **ASUS TUF Gaming GT302 ARGB**（`asus-tuf-gt302-argb`）；140 | 薄顶、可见侧皮与开放前下进风舱；通风孔为真实开孔的有限采样，不是黑色贴点，也不是整块实体舱。 | PSU 下吹为手册图示参考；PSU、ATX 板及特定 AIR 配置的检查不能升级为所有 AIO／接线组合完成。来源：[官方产品](https://www.asus.com/us/motherboards-components/cases/tuf-gaming/tuf-gaming-gt302-argb/)、[官方用户手册](https://dlcdnets.asus.com/pub/ASUS/ODD/DC/GT302/Q27043_TUF_Gaming_GT302_ARGB_WW_UM_WEB.pdf)。 |
| **Phanteks Eclipse G500A D-RGB**（`phanteks-eclipse-g500a-drgb`）；120、140 | 固定前端冷却空腔、薄实顶和真实侧面 PSU 观察开口；删除没有来源的“通用多排顶孔”，不把侧孔补成假显示器或功率读数。 | 侧窗／线孔及前缘比例未标制造坐标，安装模式与冷排厚度要逐配置核对。来源：[官方产品](https://phanteks.com/product/eclipse-g500a-drgb-black/)、[官方手册](https://phanteks.com/manuals/Eclipse_G500A_Manual_v1.0.pdf)。 |
| **InWin DUBILI**（`inwin-dubili`）；120、140 | 按开放下舱和底部通风支架建模，不再添加不存在的全宽水平 PSU 罩；背线遮板不能误当 PSU 舱实体。 | PSU 支承／位置和支架孔样仍是参考；开放架不代表无需净空或机械固定。来源：[官方产品](https://www.in-win.com/en/ibuild-ishare/dubili)、[官方手册](https://www.in-win.com/uploads/Product/ibuild-ishare/dubili_new/user-manual/dubili_eum_en.pdf)。 |
| **Corsair FRAME 4000D**（`corsair-frame-4000d`）；120 | 使用原配 STANDARD 薄罩及固定前端开口，保留线孔与通风材料；不把另售／可选的 LCD、木板、Vault 或自印小罩套成原配结构。 | PSU 下吹按原配安装说明；前开口、薄板位置仍是自绘参考，其他 FRAME 配件和任意厚排不是本次验收范围。来源：[官方系列／安装说明](https://www.corsair.com/us/en/explorer/diy-builder/cases/corsair-frame-4000-series/)、[官方原配罩与扩展罩区分](https://www.corsair.com/us/en/explorer/diy-builder/accessories/3d-printed-frame-4000d-psu-shroud-cover-and-fan-scoop/)。 |

## 扩大检查后发现的独立结构问题

前述12款是第一次下罩专项的精确范围。后续实际前扇材料检查又找到 **Torrent TG** 的旧满深顶部PSU箱体穿过最上前扇，已改为短后上薄仓和独立开放底架。首个完整主机检查还发现新薄皮穿主板上缘，保留失败后调整固定上仓参考高度与PSU安装面，主板和显卡不缩放、不迁就外壳。7项结构、两套精选120／140完整公共风冷主机4项检查通过；RGB条、水路及任意电源并未由此全部验收。[Torrent官方手册](https://assets.fractal-design.com/files/uxzbxy2o/production/af5f587352e8fa20cb09151326dae43796eebb44.pdf)

底扇材料专项覆盖33款有声明机箱、53组配置。初轮43组实际穿插；第二轮仍6组实际穿插、44组有限未见证、3组无在审材料。第二轮不是全装机检查，不能拿没有材料或没有证据当净空保证。随后专项修正的状态如下；源码阶段和实际主机阶段分开记录。

| 确切型号 | 结构错误与源参考修正 | 当前验收边界 |
| --- | --- | --- |
| **HYTE Y70 非Touch** | 旧通用实心底板、向内缩的脚穿入夹层底扇，后舱还被假实心盒填满。改为可拆薄托盘、真实开口和外缘支脚，后舱保空；保留原底扇平面、主板、GPU与竖PSU姿态。主源改绑非Touch官方资料；Touch手册仅作相关架构旁证，不能冒充精确制造图。 | 7项纯结构／真实PSU和底扇3LOD检查通过。另两套新鲜公共120／140风冷主机4项检查通过，所选硬件完整，新增材料、隔板、架空底板与硬件未见正穿插，六版实体一致。厚度、脚数采样和孔位仍参考；顶部／侧框尺寸仍未核。[官方产品](https://hyte.com/store/y70/cs-hyte-y70-b)、[装机指南](https://support.hyte.com/hc/en-us/articles/27797939292436-Build-Guide) |
| **Geometric Future Model8 CowBoy** | 旧下置实心罩、后下水平PSU和未消费的主板90°标志一起错误。现在板／CPU／RAM／GPU及接口锚点围绕主板中心作同一右手刚体变换，I/O向顶；PSU前上置、AC朝顶，另有薄侧皮、空安装环和长条开放底架。 | 独立helper7项及两套公共120／140完整风冷主机5项通过；实际网格／法线、接口与叶轮轴按同一刚体变化，新材料未检出穿插，六版复用实体。PSU进风侧、内部基准、螺钉、延长线与实物公差仍未核。[CowBoy官方页](https://www.geometricfuture.com/product-1/3)、[全Model8通用手册](https://www.geometricfuture.com/uploads/20210512/M8-Dharma-Manual.pdf) |
| **Phanteks NV5 原版** | 底部单120扇应在斜前盖前方的独立水平架，不在整个PSU仓中；后长盖、独立斜盖和前底架分开建，不能把扇轴随斜盖倾斜。 | 独立helper7项及两套公共完整风冷主机4项已分阶段通过；完整最终同源回归仍待执行。原版与MKII不混用；未标PSU轻滚转角度不猜实物值。官网／手册底部冷排声明不一致，容量不能直接开放为已验安装。[官方原版](https://phanteks.com/product/nv5-black/)、[原版v1.1手册](https://www.phanteks.com/manuals/NV5_Manual_v1.1.pdf) |
| **Phanteks Evolv X2 标准版** | 三把底扇是悬浮主体内可抽出的蜂窝托盘，与后下PSU支承层分开；不套普通满深实心罩，也不因透视照片就套O11D竖PSU模板。新的独立下支承出现时，后续外观装饰不再额外造一片旧通用实心地板。 | 独立helper7项及公共完整风冷主机4项已分阶段通过；薄层、托盘、板位与PSU仍是固定原创参考，完整最终同源回归待执行。标准版非Matrix；抬高比例、PSU安装方向、内部固定与灯条分区仍分别待核。[官方标准版](https://phanteks.com/product/evolv-x2-black/)、[v1.2手册](https://phanteks.com.tw/assets/manuals/Manual_Evolv%20X2_v1.2_WEB.pdf) |

以上阶段通过不覆盖所有电源长度、所有风扇型号或其他95款整机。不按选中部件动态挖孔、隐藏碰撞材料、移动端口或缩短管线。

## 新增17款后舱与18款后墙的核对

旧通用后仓在17个候选配置中有16个实际PSU穿插正证据，MSI PANO一项超时；此处保留超时为未决，不补写成通过。现按下表各自来源建立固定原创薄结构，独立电源框／承托和空置硬盘架保留身份，后仓不再填成实体盒。第二组五款保留旧3毫米薄底板作为绘图参考，并非已重画厂商底架；NV7同名后罩现为有独立身份的薄侧皮，不按名称误判成旧实心块。随后17款已各选一套主要硬件齐全的风冷参考，公共主机链102项／0跳过通过（41.246秒），但不含完整接线、水冷或原生安装验收，也不代表其它选件组合。早期三个部件专项的数量不与102项累计。

| 确切型号 | 来源与结构差异 | 本轮仍须补核 |
| --- | --- | --- |
| [O11D EVO RGB](https://lian-li.com/product/o11d-evo-rgb/)、[6500X](https://www.corsair.com/us/en/explorer/diy-builder/cases/corsair-6500-series/)、[Y60](https://hyte.com/store/y60/cs-hyte-y60-b)、[TUF GT502](https://www.asus.com/motherboards-components/cases/tuf-gaming/tuf-gaming-gt502/) | 各自下部后舱、固定竖PSU参考；底板、后框、窄承托及空支架分开。GT502本轮已按官方手册打印35页补3×120底扇，不把顶部2×140推成底部支持。 | 5款组含H6的早期11项部件检查保留；GT502顶扇参考面修正后另有12项部件检查。精选AIR公共主机已纳上文102项；全部线束、其它显卡／板型组合仍待核。 |
| [H6 Flow 2023](https://cdn-g.nzxt.com/dl/1698993634-h6-flow_digital-manual_231027_v2-pdf.pdf) | 按2023手册保留上部后舱PSU与下方硬盘架，不套新年份资料。 | 后舱内部坐标为参考；不能由后舱通过宣称斜侧扇／所有显卡通过。 |
| [NV7](https://www.phanteks.com/manuals/NV7_Manual_v1.1.pdf) | 上部PSU与下方主板区分开，托盘上沿固定停止在上舱下方；不在选中的PSU周围动态挖墙。 | 精选ATX风冷公共主机已纳上文102项；其它板型、所有顶排／软管组合和完整接线仍待验。 |
| [C8 ARGB](https://antec.com/product/case/c8-argb)、[MAG PANO 100R PZ](https://us.msi.com/PC-Case/MAG-PANO-100R-PZ/Specification)、[O11 Vision](https://lian-li.com/product/o11-vision/) | 保留各自中下部后舱位置、空框与独立底进风面；O11 Vision厂商15毫米外凸架事实与当前未应用的参考PSU姿态分别记录。 | 5款组含NV7、KING95的早期9项部件检查保留，精选AIR公共主机已纳上文102项；15毫米外凸架实体、完整走线和其它组合仍待验。 |
| [KING 95 原版／PRO共用手册](https://www.telon.com.tw/en/products_detail.php?nid=388&s_ok2=) | 厂商旧站与原版手册绑定，默认下部电源、上部备选位不自动多装一只；不是MKII／3D版。 | PSU长185／190毫米、侧排240／280毫米的来源差异保留，不静默取更大值。 |
| [H9 Flow 2023](https://cdn-g.nzxt.com/dl/1673509545-case_h9-flow_digital-manual-en-220929.pdf) | 上部竖PSU与下方空储存架，各自薄结构；不是H9其他年份。 | 精选风冷公共主机已纳上文102项；全部走线、顶排水路及其它选件组合仍待验。 |
| [JONSBO TK2 Black](https://www.jonsbo.com/en/products/TK2Black.html) | 下部竖PSU、独立空HDD架和开放底面。 | 产品165与手册155毫米风冷限高冲突，暂按较低值门禁且明确资料未决。 |
| [DeepCool CH780](https://www.deepcool.com/download/pdf/CH780.pdf) | 抬高PSU承托、底部宽进风区；托盘下沿为固定参考，避免全高隔板横穿120／140／180／200的底部结构空间。 | 120／140实际底扇框检查已补；180／200虽保留厂商容量，不能借前者结果称整机通过。132毫米风冷限高已消费。 |
| [Corsair 2500X](https://www.corsair.com/us/en/explorer/diy-builder/cases/corsair-2500-series/) | 下部后舱竖PSU、独立上方空架；按mATX／ITX选择板型。 | 产品／现目录深469与系列指南479毫米冲突保留，不拉伸机箱或默认放入ATX主板。 |
| [O11 Vision Compact](https://lian-li.com/product/o11-vision-compact/) | 自己的中部后舱和独立底部支承，不能套标准Vision坐标。 | 手册PSU200与网页小于220毫米冲突；15毫米外凸不直接加进允许电源长度。 |
| [Light Base 600 LX](https://www.bequiet.com/en/case/5294) | 435毫米主体加20毫米脚座；PSU架和后墙均用主体基准，脚座接到实际底板材料。 | 厂商PSU“小于200”是严格边界，不改为“小于等于”；反置／横置不是本轮默认姿态。 |
| [HAVN HS420 标准版](https://havn.global/products/hs-420) | 混合下舱与上部板托，不套VGPU专属倾斜底架。P14短线／接头穿罩已用整把风扇180度刚体朝向修正，旧姿态保留作失败对照。 | 风扇中心／法向不变；参考朝向不声称检测到用户实际装法，完整线束待验。 |

新增七款部件8项与风冷限高6项均已分阶段通过。后墙共18款确切白名单（含Y70），真实电源孔的空区、邻接金属和闭合边13项检查通过；其它78款不替换。当前后墙未做全部PCIe／主板I/O制造开孔、15毫米外凸托架或实物螺钉。厚度、位置、孔样和弯曲仍是参考，`positions_verified`／`dimensions_verified`保持false。

底扇第五轮：34款有声明机箱、55组120／140参考，52组有限未见证、3组材料范围缺口、0组正证据（45.250秒，源码稳定）。这不是55款机箱，也不覆盖GPU、PSU、主板、冷排和全线束的组合。在该第五轮报告中，MOD5的120及C700M的120／140当时缺少在审材料；后续全部实际材料诊断和MOD5局部修正在下节单列。C700M两种配置仅有限未见证，其独立厂商底架仍未完成，不把历史55组统计改成修正后的全表通过。

## H5接线与MOD5后续修正

H5 Flow2024两把底扇的已知4针口原有参考引线穿过主板底边，末级碰撞因此拒绝整条连接。仅对该确切型号增加有限短引线候选，固定端点、板件、障碍与双线束末级检查不变；新目标插头、针脚及邻接口也参与实际检查。6项／0跳过通过（21.529秒），旧7条路线及326个实体完整F64／身份不变，新2条线分别保留插头、针脚和双线束。这是参考布线，不证明实际控制模式或测速；Helios两条前面板接口容量未核仍保留。[实现](../assembly_auxiliary.py)／[专用检查](../tests/test_h5_fan_route052.py)

MOD5的全部实际材料复核先找到两把底扇框穿旧满宽脚块，再发现旧floor12电源位和位于PCB前侧的托盘杆错误。按[官方手册第6／13步](https://www.jonsbo.com/Upfiles/down/MOD5.pdf)改为外围支承、开放底框和抬高后部电源座三件独立结构；旧lower实心横撑改窄外围支承。托盘杆仅作固定X刚体后移，放在参考PCB背面；8毫米间隔、02图示电源姿态及内外深度均非制造测量。旧脚、旧电源位和旧托盘的真实穿插证据保留。

扩大到全部保留case／panel材料与所选实际硬件后，9项／0跳过通过（96.387秒），656个代码文件在该阶段前后稳定；一套主要硬件齐全的AIR参考含CPU、GPU、两条DIMM、PSU及三把P12，六版同实体。两侧承托有正面积接触，脚和框接到保留外壳；其他95款×三档仅外形函数的F64／字段保持相同，不是95套整机通过。线缆明确关闭，水路、精确孔位、真实内外PSU深度及托盘倾角仍未核。[独立结构与来源](../assembly_mod5_bottom052.py)／[外形接入](../assembly_case_exteriors040.py)／[专用检查](../tests/test_mod5_bottom052.py)

## 固定参考坐标与实际硬件尺寸

坐标统一为 X 宽、Y 高、Z 深，原点在机箱包络中心，前方为 +Z；下表用 `base = -H/2`。这些参数是程序中的固定原创参考，不是实物公差或测量值。PSU 中心由所选产品的真实长／宽／高经刚体基变换后求得；不会为了通过检查缩放 PSU、主板、GPU、风扇、接口或冷排。

| 机箱 | 固定参考布局／PSU 朝向 | 主板与边界 |
| --- | --- | --- |
| H5 Flow 2024 | 罩顶 `Y=-0.26H`；水平 PSU 底面 `base+20 mm`，绕 Z 半转使原 PSU 风扇朝上，前后接口 Z 不互换；两底扇安装面在罩顶上方 1 mm。 | ATX 板中心 `Y=0.10H`，板、CPU、GPU、RAM 与锚点一起移动。1 mm 是绘图间隙，不是厂家公差。 |
| H7 Flow 2024 | 下背隔板顶 `Y=-0.19H`；竖 PSU 的 150／86 两横向轴转为世界 Y／X，风扇面朝右的姿态为手册图参考；PSU 基准底面 `base+12 mm`。 | 板中心 `Y=0.10H`。开放底架替换通用实心底板，保留支架与脚；主舱底扇安装平面与 PSU 后舱分开。 |
| LANCOOL III | 罩顶 `Y=-0.29H`；水平 PSU 下吹，参考底面 `base+21 mm`。 | 板中心 `Y=0.10H`；三块安装盖板与两翻网门是独立部件，上方托架不能变实心舱。 |
| North／Meshify 2／Define 7 Compact | 固定罩顶为 `base+0.24H`，水平 PSU 参考底面 `base+20 mm`；下吹为手册图示参考，未将绝对安装方向一律标为已核。 | 板中心 `Y=0.10H`；各自前端／可拆盖差异仍按确切型号，不借 XL 或同品牌其他机箱。 |
| Shadow Base 800 FX／GT302／G500A／FRAME 4000D | 四者罩顶分别为 `-0.28H / -0.275H / -0.28H / -0.265H`；水平 PSU 底面参考 `base+20 mm`。 | 四者板中心 `Y=0.10H`；下吹的来源可靠程度分别保留，不能把图示方向一律改成厂家强制要求。 |
| HAF 700 EVO | 无主舱水平 PSU 罩；竖 PSU 放后舱，参考底面 `base+46 mm`；托盘和 PSU 由确切后舱布局生成。 | 主板 X 依托盘参考安排，90–101 mm 背线空间事实与选用的 96 mm 后舱／8 mm 板间距参考分开；不能沿用普通塔式主板 X。 |
| DUBILI | 开放下舱；水平 PSU 下吹为图示参考，底面 `base+21 mm`。 | 没有为了不存在的水平罩统一抬板；既有板位仍是参考，实际配件须另验。 |

直接沿用旧通用 `-0.32H` 罩顶和 `base+12 mm` 水平 PSU 底位曾产生新的真实错误：ATX PSU 高度超过舱高，或 PSU 外壳／脚／风扇面进入通用底板。修复使用按确切机箱来源确定的固定参考布局，不按当前所选 PSU 动态挖罩。三角检查还必须包含 PSU 实际风扇面和突出小件，不能只比较名义 86 mm 盒子。

H7 的第一次完整参考检查还抓到：三把底扇框、叶轮和 PSU 均清楚分开，但其三个参考电源接头伸入了下背隔板。修正为底扇绕安装轴 **180°** 的参考安装方向，保持安装面法向、三个中心的无序集合、实际风扇形状／叶片／轴／数量；连接件朝主舱左侧。实际 15 个风扇网格的顶点与法线符合该刚体变换，原三个接头的材料穿插归零。没有切隔板、缩接头或只在图片里隐藏它们；也没有据此证明真实电脑采用这一安装朝向。

## 顶排与完整配置仍在补验

下舱修正不能替代顶排、RAM、VRM、CPU 散热器和软管的组合检查。以下来源约束已进入实现，实际低矮 DIMM／冷排／风扇／软管整条消费链仍在集成核对，本文不提前标为最终通过：

- **标准 North**：官方顶置 120 mm 系冷排约束为宽度不超过 122 mm、内存高度不超过 35 mm；顶置 140 mm 系不在该支持声明内。[官方冷排兼容说明](https://support.fractal-design.com/support/solutions/articles/4000189453-north-radiator-compatibility)
- **Define 7 Compact**：顶置 120 mm 系的 40 mm 内存限高须保持；缺少的宽度、VRM／I/O 具体高度不能补成任意净空。[官方支持说明](https://support.fractal-design.com/support/solutions/articles/4000174752-define-7-compact)
- **Meshify 2 标准布局**：120 mm 系走外侧安装轨，已录宽度条件为 124 mm；140 mm 系走内侧参考轨并保留 36 mm RAM 条件。120 mm 系没有同一条 RAM 高度限制，不等于 VRM、板载 I/O、管路和任意冷排都没有干涉；储存布局未因此实现。外轨的 `X=-0.16W` 是原创参考坐标。[官方支持说明](https://support.fractal-design.com/support/solutions/articles/4000174746-meshify-2)

**North XL 与 Helios 是额外的既有问题，不计入上表 12 款的重复新增数。** North XL 曾有最低前扇与通用实心罩初始穿插 17.12 mm，改为该确切 XL 的薄顶／可见侧皮／前落缺口；它不能替标准 North 作证。[North XL 官方规格](https://www.fractal-design.com/products/cases/north-series/north-xl/north-xl-chalk-white-mesh/)

Helios **GX601** 的前置 LF III 冷排曾与旧实心罩初始穿插 9.88 mm；用户／维修手册显示前罩、后罩和透明观察窗可分开。实际前冷排进入下舱时才参考卸前罩，保后罩与窗口，不能挪冷排、缩 450 mm 软管或删除整罩。没有前置冷排的原厂三把 140 mm 配置，在尚未核准的前罩前缘参考中仍可能冲突；软件须明确拒绝该参考放置并提示待核，不能说实物不支持厂家原配风扇。窗口不是 OLED，也不是功率传感器。[GX601 官方产品](https://rog.asus.com/us/cases/rog-strix-helios-model/)、[用户手册](https://dlcdnets.asus.com/pub/ASUS/ODD/DC/ROG_Strix_Helios/ROG_Strix_Helios_User_Manual.pdf)、[维修手册](https://dlcdnets.asus.com/pub/ASUS/ODD/DC/ROG_Strix_Helios/GX601_R2R_Manual.pdf)

## 可复核的程序入口与最终验收

公开实现入口是 [确切机箱分派／主机锚点](../assembly_case_shrouds052.py)、[NZXT／LIAN LI](../assembly_shroud_nzxt_lianli052.py)、[Fractal](../assembly_shroud_fractal052.py)、[其余六款](../assembly_shroud_other052.py)、[Helios](../assembly_helios_shroud052.py) 及 [整机构建](../assembly_geometry.py)。外盖、托架和可拆板保留独立 `part_id`，材质／外形可以随六版变化，实际物理网格不借换风格改数量或位置。

对应检查包括 [NZXT／LIAN LI](../tests/test_shroud_nzxt_lianli052.py)、[Fractal](../tests/test_shroud_fractal052.py)、[其余六款](../tests/test_shroud_other052.py)、[Helios](../tests/test_helios_shroud052.py)、[North XL](../tests/test_north_shroud052.py)、[真实主机配置](../tests/test_case_layout_hosts052.py)、[MOD5全部材料](../tests/test_mod5_bottom052.py)及[H5底扇接线](../tests/test_h5_fan_route052.py)。这些文件的存在或此前阶段通过不是最终验收凭证；需要最终冻结源下的实际执行记录。

最终至少还要检查：

1. 用新鲜完整配置和实际原生外观描述构建场景，分别数 CPU／单 GPU／各条 RAM／PSU／冷排／风扇／线束与灯区；按硬件部件清单归属，不能把空 `part_id` 的 GPU 接口算第二张卡。检查拒绝、缺件、未知与省略原因，不能以“没有生成”冒充净空。
2. 做实际材料三角与正体积验证，区分薄片、孔、空舱和接触边界；包括后加 PSU／存储／连接件、冷排与软管。未核位置或求解失败要清楚待核，不穿模连管、不移动端口迁就布线。
3. 同一物理配置验证六版实体、线稿、透明遮挡、点选及选择效果，检查拥挤场景的有限边预算；不能只用预览图片遮掉错误，或把软件光栅图称作 Windows 原生像素验收。
4. 内部检视／展示 PSU 使用真实共享绘制和拾取门禁；被隐藏外盖不能截获点击，物理网格仍在，不能因显示开关重烘焙或重新上传全部顶点。[可见性规则](../assembly_visibility048.py)、[渲染消费端](../assembly_viewer.py)
5. 有限拆装仍是参考脱槽与解除演示：源实体、线稿、点选及特效使用一致姿态；结束／取消／关闭／最小化／游戏门禁须停动并释放订阅。不能把 GPU／CPU／RAM／部分机箱风扇的有限动作，称作所有零件都已完成螺钉、扣具、拔线和完整出箱。
6. 对新源做统一回归、候选打包自检和关闭后引用／资源检查。顶点字节、一次构建 CPU、脚本峰值或有限缓存不是整个 Stats 的常驻 RAM／CPU／GPU 占用；真实运行、原生驱动／显存回收与游戏负担仍待测量。

真实接线也不因外壳修复完成：AIO 的工厂内部线束、单／分 PWM 的实际选择、前置 I/O 和每把风扇的转速映射并未普遍取得实机证据。独立冷排与风扇可分选、分部件检视，不代表密封一体水冷能任意拆管；未知 RPM／叶型保持静止，不能借 CPU_FAN、泵速或其他设备读数补动。RAM／PSU 的实际存在、被罩遮住、可选显示和已知灯区静态配色也必须分别说明，不能给无灯零件补通用光圈。

本轮 CPU／GPU 六版小组件的型号、尺寸、停止／过期转速和部分已核风扇门禁，要由实际小组件链另外核对，机箱检查不能替代它。无边框透明命中、屏幕二、同屏游戏不覆盖、CPU 温度重启恢复、顶部栏／设置／详情的真实 Windows 磨砂以及整款资源占用均未完成本轮原生验收。继续遵守游戏中不重启、不安装、不弹管理员授权的要求。

## 许可、来源标识与剩余范围

本文只链接官方资料，不发布厂商照片、下载 CAD 或游戏资产。原创程序化网格和代码遵守既有 [非商业许可](../LICENSE)、[来源声明与第三方例外](../LICENSING.md)；不能撤销 MIT／ISC／LGPL 等既有授权，也不因参考产品就获得厂商商标或图片的授权。

[隐藏来源标识](WATERMARK050.md)只覆盖各次发行清单指定、实际签发验证过的资产。新源码、可选 JSON／SVG 包、实时全库网格或每一个小部件不会自动全部带标；不保证无法移除、权利成立、证据采纳或胜诉。可选数据包和独立模型交付按各自清单与验证范围说明，机箱库尚不能因此宣称已全部迁移为可选包。

截至本文，[29 组要求](REQUIREMENTS.json)仍未全部完成；[当前质量记录](QUALITY052.md)、[持续开发记录](DEVELOPMENT052.md) 与 [PCBS 对照范围](PCBS_GAP_ANALYSIS.md)继续保留缺口。本轮修正的是具体模型与放置错误，不表示全品牌／全型号／全机箱组合完成，也没有达到或超过 PC Building Simulator 1／2 的覆盖和机械交互目标。
