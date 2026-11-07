# 0.45 独立水冷缺口：只读代码审计

范围：当前生产代码与 `docs/PCBS_GAP_ANALYSIS.md`，不联网、不新增类别、不增加风格、不安装或启动 Stats。以下是当前程序能力和下一批数据/接口建议，不是市场全部产品清单、采购建议、CAD 或真实装机验收。

## 当前状态与具体落点

| 类别 | 代码中真正已有的内容 | 当前没有的独立能力 | 下一批必须分开的字段 |
|---|---|---|---|
| CPU 冷头 | `cooling_catalog.py` 的 `custom-loop-360-reference` 是一套明确参考组合；嵌入 XC7 产品名与 87×78×36 外包络。`assembly_cooling._liquid` 给它 `cooler:cpu` part 与可检视外形。 | 没有独立 CPU 冷头目录、冷头选择 ID、扣具/插槽适配表或逐产品口位；不是每个冷头都能从该组合分开选。 | exact ID/修订、外包络、冷板/盖板材料、插槽与原厂扣具 ID、扣具孔距/背板/高度、端口列表与进出口约束、观察到的灯区、逐字段来源与 verified/reference。 |
| GPU 冷头 | `_gpu_block` 用当前 PCB 示意包络的 0.94×宽、0.90×长生成通用全覆盖参考；有透明盖、采样鳍片、端子、两口，`fit_verified=False`。只有明确 GPU PCB 和可用第二冷排/接口时才替换风冷。 | 没有任何零售 GPU 冷头 ID 或对应 PCB 修订匹配；驱动的“RTX 5090”等芯片名不能决定非公冷头。内部微鳍片和接触区域不是制造结构。 | exact block ID、厂商明确的 GPU/PCB/revision 兼容列表、端子/背板选项、装配厚度、螺孔与可用间隙、端口方向/角色；未知 SKU 或 PCB 修订保留原风冷，禁止只按芯片名匹配。 |
| 水泵 | 参考组合里有名为 `cooler-d5-pump` 的静态几何，和水箱合为 `cooler:reservoir`；检视水温/流量/泵 RPM 均为未知。 | 没有独立泵目录、独立泵 part/model ID、泵座/泵盖区别或真实流量/压头模型。 | pump/combo/top/body-only 的产品形态；自身外包络、安装面/孔距、输入/输出口、接口/接线事实、是否含电机、是否有独立 tach/温度通道；不把 D5 类型名称当成任意产品兼容保证。 |
| 水箱 | 参考组合嵌入 TBE 200 D5 的产品名与 60mm/200mm 参考包络；透明筒、盖、夹环、示意液体可见。 | 没有可独立选择的圆筒/扁平水箱/分水板目录；液面不是实测；没有填充/排气/排液口与堵头的逐口选择。 | tank/combo/body-only；外包络、材料、固定方式、口列表/线程/角色、随附与实际安装堵头分开、泵兼容依据、容量（源有才写）；实时液位/水温/流量默认未知。 |
| 接头 | 冷排源口能生成通用空心 hose collar；GPU/CPU 参考冷头也有简单接头图形。没有螺纹齿或压缩接头 SKU 承诺。 | 没有独立接头目录、接头 part ID、旋转角度/延长件、软硬管兼容或压缩圈规格选择。 | straight/angled/rotary/barb/compression/plug/drain/adapter；两端各自 thread/gender 或 tube ID/OD、装配长度/扳手空间、旋转轴/角度、密封与材料来源。G1/4 不能当作管材外径。 |
| 管线 | `_tube` 是开口圆管表面；`_liquid` 用固定参考半径 6.2 与有限 Bézier 采样连接端点。缺已观察冷排口会省略对应连管并显示 issue。 | 没有管材型号、ID/OD、软/硬材质、最小弯曲半径、接头规则或可编辑连接图；不是流体/压力/泄漏/热模拟。 | tubing ID、材质、内外径、类型、弯曲半径/温度等级（有源才写）；edge(from part+port,to part+port)、路线点及 reference 状态。路线只是可缓存的有限示意；未知两端不补造连接。 |
| 机箱风扇/冷排组合 | 主/第二冷排独立型号/扇型；single/push_pull/none；冷排风扇独立 front/rear part ID。机箱扇独立选择、拒绝与冷排同面重复。已核孔距不一致是 review，未拿 0.05mm 差直接证明无法安装。 | 机箱只有面级位置与参考 2D 边界；一面至多一组且组至多 4 把，不能表达真正双列 8 把。没有普遍三维堆叠干涉、螺钉长度/螺纹深度、偏置支架或全几何碰撞解。 | mount-zone/array/row/column、面内方向与孔距双轴、支架偏置、冷排+前/后扇实际厚度、已核可用深度、盖板/内存/GPU 干涉状态、螺钉/垫片来源。未知深度保持 review，不自动缩放硬件。 |

## 需要避免复用错语义的现有字段

- 参考组合的 `pump_reference_mm` 在 `pump_style='xc7_block'` 时其实描述 CPU 冷头，不是 D5 电机尺寸。下一批必须拆成 CPU block、pump、reservoir 各自的外包络，不能直接把这个字段喂给独立水泵目录。
- `reservoir_model` / `cpu_block_model` 当前是参考组合里的标签字符串，不能当作已经存在的独立零售模型记录或独立 source ledger。
- `gpu_waterblock` 当前只是明确启用通用 GPU 参考的开关，不是零售冷头的兼容 ID。`secondary_radiator_mount` 仍由程序从 side/top 选择；不是任意数量冷排的连接图。
- `ports_geometry_complete=True` 表示参考图已覆盖总孔数，不等于毫米坐标已核。现有冷排的 `port_positions_verified=False` 需要保留这种区分。
- `pump_reservoir` 检视已经正确保留未知水温、流量和泵转速；新产品条目也不能借 CPU 温度、CPU_FAN 或同机箱另一把风扇的读数补数。
- 封闭 AIO 冷排不可替换的现有规则要保留；添加零售冷头/冷排不代表支持现实改造 AIO。

## 可落地的下一批顺序

1. **先统一独立端口/连接合同**：产品事实和参考几何分层；端口 ID、角色、线程、方向、口位依据、堵头实际安装状态、管材 ID/OD。以少量具名 CPU 冷头、泵水箱组合、直通/弯头、软管闭合一套真实选择流程。没有主源的字段留空。
2. **拆开泵与水箱身份**：明确 body-only、带泵组合、独立泵、泵盖、支架。允许组合包装引用其子件，避免同一电机重复安装或把无泵水箱画出泵。
3. **再做 exact GPU 冷头**：先取得厂商 PCB 兼容表和 exact 修订，之后才替换对应风冷外壳；未知型号/修订/间隙保留原 GPU 与明确原因。不能拿通用冷头缩放冒充更多零售 SKU。
4. **补机械组合验证**：孔距双轴、端口/接头占位、软管最小弯曲、双面风扇厚度与机箱/内存/GPU 干涉，区分 supported / unsupported / review；再扩双列、多安装区或第三冷排。
5. **最后进入新的 data-only 可选包类别**：当前 pack 顶层只允许 cpu/fan/cooler/radiator，冷却规则没有独立 block/pump/tank/fitting/tubing。需显式新 kind 或带严格 discriminator 的 loop-component schema，同时接选择器、保存迁移、装配 part ID、检视和 cache。不要给零售无风扇冷头伪造 `fan_count=1` 来挤进现有 cooler schema（当前 fan_count=0 只允许 passive_tower）。

每批都复用现有 13 风格与共享 clock；静态模型只在选择变化构建，保留 selected-record LRU 与关闭释放。增加类别不需要新增采集轮询或产品时钟。

## 下一批可直接执行的验收用例

- 冷头 ID 与 CPU 插槽/扣具组合：明确不支持完整拒绝；未知不自动变成支持；标签、实际选择与 mesh ID 相同。
- 显卡芯片名相同但 PCB 修订不同：不得匹配零售 GPU 冷头，保持原风冷；有来源的 exact 匹配才允许替换。
- body-only 与完整泵水箱组合：只有带泵条目能生成电机；组合/子件不能重复；所有读数默认未知直到显式独立绑定。
- 压缩接头与软/硬管 ID/OD 不合：拒绝或 review，不能仅因都是 G1/4 就接通。
- fill/drain/auxiliary/capped 口不能被默认挑作普通水路连接；未知坐标不画假管；连通图不得出现悬空半管。
- 最小弯曲与接头外包络不满足：不能穿过机箱/内存/GPU；未核间隙不能显示已验收；不预言流量或温度。
- 冷排+两面不同厚度扇的总厚度按实际记录相加；同安装区重复、双列位、偏置支架有独立状态与可解释结果。
- 13 风格复用同一型号/物理数组；不为细节新增后台线程/clock；未知 RPM 不动；卸载包后 picker、SVG、mesh cache 失效且退回明确缺失状态。

## 代码证据

`cooling_catalog.py:197`（唯一自定义参考组合）；`assembly_cooling.py:41`（管表面）、`:530`（独立冷排/风扇/源口）、`:592`（通用 GPU 冷头）、`:777`（参考 CPU/水箱/管线）、`:846`（选择与安装边界）；`assembly_config.py:7` / `:106`（可保存选项/组边界）；`assembly_parts.py:22` / `:53`（选择器/保存字段）；`assembly_inspection.py:169`（独立读数未知）；`liquid_selection044.py:10`（AIO保护/独立扇型/孔距review）；`cooling_pack_schema045.py:12`（允许类别）；`docs/PCBS_GAP_ANALYSIS.md:124`（已有互动与缺口）。

本轮新增的导出回归仅在 `tests/test_cooling_pack_export045.py`，没有实现上述新类别或修改生产导出工具；PCBS 整体覆盖目标仍未达到。
