# 可选三维模型

只下载你想看的模型，在含本轮改动的 DesktopStats 开发版中打开 **硬件型号图鉴 → 开源 3D → 载入模型 ZIP…**。无需解压；这些包不会自动安装、扫描或预载，也不会替换本机的硬件设置。

| 模型 | 下载 | 大小 | 可点选结构 |
| --- | --- | ---: | --- |
| 通用风扇 | [风扇 ZIP](pc-anatomy053/DesktopStats-open-fan-reference053.zip) | 166,183 B | 框架、叶轮、轮毂 |
| 风冷散热器 | [风冷 ZIP](pc-anatomy054/DesktopStats-MIT-air-cooler054.zip) | 564,932 B | 冷板、热管、鳍片、顶盖、风扇、扣具 |
| 一体水冷 | [水冷 ZIP](pc-anatomy054/DesktopStats-MIT-liquid-cooler054.zip) | 787,376 B | 冷排、风扇、泵、冷板、管路、接头 |
| 通用整机 | [整机 ZIP](whole-pc054/DesktopStats-MIT-whole-PC054.zip) | 1,395,020 B | 机箱、主板、CPU、显卡、内存、电源、线缆与存储等25部件 |
| CPU，作者参考 | [CPU ZIP](ccby-components054/DesktopStats-CCBY-CPU054.zip) | 494,297 B | 两个源部件 |
| RTX 3080，作者参考 | [显卡 ZIP](ccby-components054/DesktopStats-CCBY-RTX3080-compact054.zip) | 3,164,655 B | 27个源分区，沿用已核精简LOD |
| Samsung 990 PRO 1TB，作者标注参考 | [SSD ZIP](ccby-components055/DesktopStats-CCBY-Samsung990PRO-SSD055.zip) | 888,683 B | 两个源分区 |
| 通用电源 | [电源 ZIP](ccby-components055/DesktopStats-CCBY-generic-PSU055.zip) | 357,252 B | 43个源分区；未指认为某款零售电源 |

这些是八件通用结构或作者参考，不是八套已完成的厂家精模。同一模型可以切换原版、可爱笑脸、彩色手绘、纯线条、奶油贴纸、拼色剪纸；切换风格共用几何，关闭检视后释放模型。原有13个风格保存值仍保留。

第三方参考目前的风格切换以配色与线条规则为主，不等于每件的六套手绘、表情与细节均已完成。“部件／分区”指可选择的源对象，不等于已辨明的物理零件数量；例如电源源文件还保留用途未注明的游离Cone_45对象。

当前支持旋转、缩放、点选、聚焦和隐藏／恢复部件。参考模型暂不自动匹配本机型号，不自动装到机箱固定孔位，不把演示旋转当作真实风扇转速。源贴图与材质保留，当前检视未完整还原贴图和PBR；模型单位、制造孔位、完整拆装仍需继续适配。薄板SSD等依赖贴图的细节尤其尚未完整显示。

内存参考的转换检查发现新增表面退化和方向错误，保持待修，未列入可用下载清单；没有通过删除三角形或放宽门槛冒充完成。

风扇／风冷／水冷来自 [Yoseph / PC Anatomy](https://github.com/Yoosseph/pc-anatomy)，整机来自 [PC Components Manual](https://github.com/mdrayyanhussain2006/pc-components-manual)，保留各自MIT声明与完整通知。CPU、显卡、SSD和电源分别沿用各作者CC BY 4.0；作者、固定来源、修改说明与校验值随各包保留。

本项目原创应用代码和原创硬件插画按非商业许可提供；本页第三方模型数据继续按原MIT／CC BY许可，不叠加本项目非商业限制，不加入本项目独占水印。品牌与商标属于各自权利人，参考模型不表示厂商认证或背书。

[完整适配范围与已核记录](https://github.com/Fairank/DesktopStats/blob/codex/fixed-mount-fit-v053/docs/OPEN_REFERENCE_MODELS054.md) · [SSD／电源包与校验值](ccby-components055/README.md)
