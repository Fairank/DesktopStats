# 0.47 独立显卡冷头参考库

这批增加 **12 款零售显卡冷头参考模型**，来自 Alphacool 8 款、Watercool 2 款、Corsair 2 款，覆盖 NVIDIA 9 款、AMD 3 款。它们属于独立检视阶段，不替换整卡散热器，不自动安装到显卡或连接水路，也不推断本机已改水冷。厂商资料、实际安装坐标和制造 CAD 是不同层次的证据。

完整列表、实际包字节与 SHA256 以 [GPU_BLOCK_PACKS047_INDEX.json](GPU_BLOCK_PACKS047_INDEX.json) 为准。包有集合 1 个、按品牌分组 3 个，共 4 个替代下载；品牌包与集合包重叠，产品只计 12 次。它们不默认加载，0.46 原有 15 个 loop 包与索引保持独立。

## 首批产品

|品牌|产品|厂商料号|
|---|---|---|
|Alphacool|Core RTX 5090 ROG Astral|10270|
|Alphacool|ES RTX 5090 Reference 1-slot|10262|
|Alphacool|Core RTX 4090 Founders Edition|13470|
|Alphacool|Eisblock Aurora RX 7900 XTX Reference|13547|
|Alphacool|Core RX 9070 / 9070 XT TUF + Prime|14779|
|Alphacool|Core RX 9070 XT Swift + Quicksilver|14799|
|Alphacool|Core RTX 5090 Suprim + Vanguard + Gaming Trio|10268|
|Alphacool|Core RTX 5090 TUF Gaming|10269|
|Watercool|HEATKILLER V ULTRA RTX 5090 ASUS TUF ACRYL Ni aRGB|15688|
|Watercool|HEATKILLER V PRO RTX 4090 FE ACRYL Ni aRGB|15661|
|Corsair|Hydro X XG7 RGB RTX 4090 STRIX/TUF|CX-9020020-WW|
|Corsair|Hydro X XG7 RGB RTX 3080 Ti / 3080 FE|CX-9020011-WW|

Watercool RTX 5090 Palit/Gainward 与 Corsair RX 7900 XTX 两款研究记录没有进入本包：当前取得的页面未给出足够具体的板卡/PCB 白名单。本批未取得可用的 Intel 零售冷头兼容主源，保留缺口；这不表示市面上不存在。

## 兼容边界

- `liquid_gpu_schema047.compatibility()` 只比较厂商列出的完整板卡名称、完整产品码与必要 PCB 版本，不做同芯片、相似名称或型号前缀扩展。相互矛盾的名称和产品码不能通过一个宽松的“或”匹配。
- XFX 14799 的正文限定 V2.0、排除 A.0，Swift 条目却另列 V3.0。V3.0 保持来源冲突状态；没有确认版本的 White 条目保持待确认，不能自动放行。
- MSI 10268 只有 SUPRIM SOC 和 SUPRIM LIQUID SOC 明确 MS-V530 Ver:2.1。该版本不转移给 Gaming Trio/Vanguard；SUPRIM OC 也不等同 SOC。
- Corsair CX-9020020-WW 不使用另一款 iCUE LINK CX-9020027-WW 的规格。RX 7900 XTX 冷头和 Palit/Gainward 5090 的宽范围说法没有借给这 12 款。
- 即使返回 `manufacturer_listed`，仍然是来源名单匹配，`assembly_supported=False`。现有资料不足以提供精确的 GPU 芯片、显存接触面、安装孔、垫片与板上安装姿态。

## 端子、背板与尺寸

冷头本体、标准端子、被动背板以及每个已观察接口分别有几何/观察组。接口观察组可以单独选择，并不宣称螺纹嵌件可由用户拆卸。没有泵、转子、虚构转速、流量、液温或液晶屏。

Watercool 5090 TUF 的标准总包络为 259.5 × 130 × 27.5 mm，另购 Sideport 配置为 249.5 × 130 × 27.5 mm，两者单独记录。Sideport 的具体口数/口位本批未核，保留空接口清单；不能把标准端子的六口转移过去。

Alphacool 的 cooler 总尺寸表与 backplate 表分开保存。它们没有统一明确总尺寸是否已包含背板；Corsair 的产品 L/W/H 表也未统一说明总装范围。因此对应整件 `dimensions_mm` 保留未知，单独的 `published_envelopes` 保存已发表数值。参考绘图包络不用于安装验证，也不把两张表的厚度直接相加。Corsair 3080 FE 本批没有取得已发表外形尺寸，保持参考默认与未知标记。

接口总数与口位观察是两回事。Watercool 5090 TUF 标准端子有厂商给出的六口总数，本模型只放了已观察的两口；其他四口的位置不从总数推造。G1/4 是管螺纹标准，不是管材外径。

Corsair 3080 适用手册明确四口分成两液压柱：同一柱正反面的两个口不能作为进出水，否则旁通冷头。`port_pair_status()` 保留这个禁配；其他产品未核的内部水路分组不被当作任意两口均可用。本阶段不生成 GPU 冷头连管。

## 外观证据与尚未完成的细节

本轮真实生产网格的软件离屏图鉴：[1 原版](../assets/showcase/gpu-blocks047-style-1-twelve-r4.png) · [2 可爱笑脸](../assets/showcase/gpu-blocks047-style-2-twelve-r4.png) · [3 彩色手绘](../assets/showcase/gpu-blocks047-style-3-twelve-r4.png) · [4 纯线条](../assets/showcase/gpu-blocks047-style-4-twelve-r4.png) · [5 奶油贴纸](../assets/showcase/gpu-blocks047-style-5-twelve-r4.png) · [6 拼色剪纸](../assets/showcase/gpu-blocks047-style-6-twelve-r4.png) · [原版正面](../assets/showcase/gpu-blocks047-original-front-twelve-r4.png)。十二款都按相同的六种风格输出；这些是独立参考模型，不是完整装机或实测读数。

六个主风格和其他保留风格复用同一物理几何。外壳类别包括透明 Core、透明 Aurora 端子、薄型不透明 Carbon ES、金属多边形窗 HEATKILLER、双侧肋纹 XG7。每条记录的 `exterior_observations` 保存官方实物图中可观察的盖板、端子、肩部、边层和背板特征。

外部类别与已有尺寸有来源；**数值化孔位、支柱采样分布、肋纹重复、层厚和内部沟槽仍是原创示意**。沟槽没有被称为真实 CNC 水路，也不用于流体仿真或制造。前代 Core、不同型号右侧平整金属区、上端子轮廓和 ES 短端接口会分别处理；没有为增加差异而绘制未见的电容、PCB 电路或额外接口。

这不是“每款全细节完成”或“达到装机模拟器覆盖”的承诺。仍缺精确安装姿态、完整内部水路、全部接口位置、未见背面细节、部分附送挡板的独立摆放，以及更多零售产品。图鉴软件投影与纯 CPU 几何测试不代替 Windows 原生透明/三维视图、本机温度或游戏中实际验收。

原创代码和程序化模型继续适用仓库的 PolyForm Noncommercial 1.0.0 及已有条款。产品名、商标与第三方素材权利属于各自权利人；厂商照片和 PDF 只在私有来源核对中使用，不随这些数据包分发。
