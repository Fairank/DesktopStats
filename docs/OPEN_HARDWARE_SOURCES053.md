# 开源机箱原始零件下载

三项作者机箱设计、46 个独立 STL／3MF 文件，合计 **5,798,677 B**。这些是已实际下载并核对的原件；本页把逐文件入口公开，方便选择和继续加工。它们不是 46 款机箱，也不是已经装进 Stats 的完整整机。

**手动下载，不预载。** 点击下表文件名，从原作者固定版本直接下载。Stats 不在启动或后台读取本索引、下载这些文件或生成网格；这些文件目前不能当作 `.dspack` 导入。已有可直接导入的数据包另见[硬件扩展包](HARDWARE_PACKS.md)。

[机器可读索引、逐文件 SHA-256 与 Git blob](OPEN_HARDWARE_SOURCES053.json)记录同一批原件。检查只涵盖原始字节与有限容器结构；STL 单位、安装姿态、孔位、净空、打印可用性、六版外观与原生占用尚未验收。

各作者许可和署名单独保留；本项目原创内容的非商用声明和自有水印不适用于这些上游原件。下载、修改或转载时请保留相应作者通知，并按其完整许可处理。

## Parametric Mini-ITX Case

作者：Nirav Patel。[原项目与说明](https://github.com/eclecticc/ParametricCase/blob/b5f1ee43c1db93cac7657c52bcc5a97baa5df7c4/README.md) · [BSD-2-Clause 完整许可](https://raw.githubusercontent.com/eclecticc/ParametricCase/b5f1ee43c1db93cac7657c52bcc5a97baa5df7c4/LICENSE)。

包括机身、盖板和脚。作者的示范针对 NH-L12S／Zotac 1080 Mini／SFX；作者也记录了显卡支架／高度和盖板刚性方面的问题。不是零售整机或已验兼容配置。

| 原作者文件（点击下载） | 大小 | 格式 |
| --- | ---: | --- |
| [mini-itx.stl](https://raw.githubusercontent.com/eclecticc/ParametricCase/b5f1ee43c1db93cac7657c52bcc5a97baa5df7c4/mini-itx.stl) | 2,398,134 B | ASCII-STL |
| [mini-itx-lid.stl](https://raw.githubusercontent.com/eclecticc/ParametricCase/b5f1ee43c1db93cac7657c52bcc5a97baa5df7c4/mini-itx-lid.stl) | 6,728 B | ASCII-STL |
| [feet.stl](https://raw.githubusercontent.com/eclecticc/ParametricCase/b5f1ee43c1db93cac7657c52bcc5a97baa5df7c4/feet.stl) | 348,875 B | ASCII-STL |

## Space Case: Makers Edition

作者：Circle Studio (CircleTect repository)。[原项目与说明](https://github.com/CircleTect/space-case/blob/0a2ad693beb7d466181df6cb1feff788df1aa3df/README.md) · [GPL-3.0 完整许可](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/LICENSE)。

作者明确标注此设计仍在 beta 测试阶段，可能需要自行调整。21 个 3MF 的 XML 明确写有毫米单位；这不代表制造尺寸或组合净空已验收。包括主板支座、电源架、GPU 支座、冷排／风扇支架、脚和把手；3／4 槽等互斥变体不能全部同时安装。还需金属管、五金、I/O 和侧板，21 件不是完整装配 CAD。完整可修改源与装配资料继续从上方原项目取得。

| 原作者文件（点击下载） | 大小 | 格式 |
| --- | ---: | --- |
| [02_3D PRINT FILES/01_X4_PIPE_JOINT_V14_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/01_X4_PIPE_JOINT_V14_BLK.3mf) | 75,076 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/03_X1_MOBO_SUPPORT_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/03_X1_MOBO_SUPPORT_V3_BLK.3mf) | 23,465 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/04_X1_HANDLE_V4_BLU.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/04_X1_HANDLE_V4_BLU.3mf) | 33,921 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/05_X4_FOOT_V2_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/05_X4_FOOT_V2_BLK.3mf) | 20,070 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/07_X2_MOBO_BRACKET_SHORT_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/07_X2_MOBO_BRACKET_SHORT_V3_BLK.3mf) | 16,386 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/08_X1_PSU_BRACKET_LOWER_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/08_X1_PSU_BRACKET_LOWER_V3_BLK.3mf) | 21,714 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/09_X1_PSU_BRACKET_UPPER_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/09_X1_PSU_BRACKET_UPPER_V3_BLK.3mf) | 21,907 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/10_X2_PLATE_CLIP_V1_BLU.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/10_X2_PLATE_CLIP_V1_BLU.3mf) | 10,638 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/11_X8_PANEL_PIN_V1_BLU.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/11_X8_PANEL_PIN_V1_BLU.3mf) | 20,745 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/3-Slot Build/02_X1_3-SLOT_GPU_SUPPORT_V6_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/3-Slot%20Build/02_X1_3-SLOT_GPU_SUPPORT_V6_BLK.3mf) | 48,397 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/3-Slot Build/06_X2_3-SLOT_MOBO_BRACKET_LONG_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/3-Slot%20Build/06_X2_3-SLOT_MOBO_BRACKET_LONG_V3_BLK.3mf) | 14,471 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/4-Slot Build/01B_X8_4-SLOT_PIPE_EXTENSION_V1.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/4-Slot%20Build/01B_X8_4-SLOT_PIPE_EXTENSION_V1.3mf) | 12,137 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/4-Slot Build/02_X1_4-SLOT_GPU_SUPPORT_V6_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/4-Slot%20Build/02_X1_4-SLOT_GPU_SUPPORT_V6_BLK.3mf) | 47,359 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/4-Slot Build/06_X2_4-SLOT_MOBO_BRACKET_LONG_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/4-Slot%20Build/06_X2_4-SLOT_MOBO_BRACKET_LONG_V3_BLK.3mf) | 13,997 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/IO Panels/Cheap_Ebay-1_IO_PANEL_V6_12MM_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/IO%20Panels/Cheap_Ebay-1_IO_PANEL_V6_12MM_BLK.3mf) | 32,310 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/IO Panels/Cheap_Ebay-1_IO_PANEL_V6_16MM_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/IO%20Panels/Cheap_Ebay-1_IO_PANEL_V6_16MM_BLK.3mf) | 32,540 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/OPTIONAL_X2_2.5_DRIVE_SUPPORT_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/OPTIONAL_X2_2.5_DRIVE_SUPPORT_V3_BLK.3mf) | 18,089 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/OPTIONAL_X2_3.5_DRIVE_SUPPORT_V4_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/OPTIONAL_X2_3.5_DRIVE_SUPPORT_V4_BLK.3mf) | 25,217 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/OPTIONAL_X2_CABLE_COMB_V2_BLU.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/OPTIONAL_X2_CABLE_COMB_V2_BLU.3mf) | 8,910 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/OPTIONAL_X2_FAN_BRACKET_V3_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/OPTIONAL_X2_FAN_BRACKET_V3_BLK.3mf) | 15,612 B | 3MF-ZIP/XML |
| [02_3D PRINT FILES/OPTIONAL_X2_RAD_BRACKET_V1_BLK.3mf](https://raw.githubusercontent.com/CircleTect/space-case/0a2ad693beb7d466181df6cb1feff788df1aa3df/02_3D%20PRINT%20FILES/OPTIONAL_X2_RAD_BRACKET_V1_BLK.3mf) | 16,531 B | 3MF-ZIP/XML |

## JKASE D3 V1.0

作者：JKASE Design / repository owner absonbbg。[原项目与说明](https://github.com/absonbbg/Jkase-D3/blob/9842073feeb0ddf03729c04a5213c19fe236a983/README_en.md) · [CERN-OHL-S-2.0 完整许可](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/LICENCE.txt)。

包含金属板、亚克力板、立柱和打印支架，需区分加工方式。不同外形的显卡／散热限高不能合并成一张兼容上限；有文件被作者标记为无需生产。完整设计源、BOM 和加工资料继续从上方原项目取得。

| 原作者文件（点击下载） | 大小 | 格式 |
| --- | ---: | --- |
| [3D_FIles_Format/STL/(No_need_to_produce)L_Shape_Fastener.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/%28No_need_to_produce%29L_Shape_Fastener.STL) | 15,884 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_Acrylic_120mm_fan_2.5_drive_bracket.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_Acrylic_120mm_fan_2.5_drive_bracket.STL) | 84,884 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_Acrylic_120mm_fan_bracket.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_Acrylic_120mm_fan_bracket.STL) | 78,884 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_Acrylic_280_to_240_bracket.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_Acrylic_280_to_240_bracket.STL) | 64,284 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_Acrylic_92mm_fan_2.5_drive_bracket.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_Acrylic_92mm_fan_2.5_drive_bracket.STL) | 77,684 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_Acrylic_92mm_fan_bracket.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_Acrylic_92mm_fan_bracket.STL) | 78,884 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_GPU_fastener_head.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_GPU_fastener_head.STL) | 71,884 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_GPU_fastener_tail.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_GPU_fastener_tail.STL) | 67,084 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_foot.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_foot.STL) | 43,484 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_nameplate_D3.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_nameplate_D3.STL) | 7,084 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_nameplate_JK.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_nameplate_JK.STL) | 82,484 B | binary-STL |
| [3D_FIles_Format/STL/3Dprint_nameplate_fastener.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/3Dprint_nameplate_fastener.STL) | 9,684 B | binary-STL |
| [3D_FIles_Format/STL/Acrylic_Panel_360AIO+drive.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Acrylic_Panel_360AIO%2Bdrive.STL) | 200,284 B | binary-STL |
| [3D_FIles_Format/STL/Acrylic_Panel_Decorative.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Acrylic_Panel_Decorative.STL) | 199,884 B | binary-STL |
| [3D_FIles_Format/STL/Acrylic_Panel_Decorative_2.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Acrylic_Panel_Decorative_2.STL) | 68,284 B | binary-STL |
| [3D_FIles_Format/STL/Acrylic_Panel_GPU_AIO.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Acrylic_Panel_GPU_AIO.STL) | 145,884 B | binary-STL |
| [3D_FIles_Format/STL/Acrylic_Panel_drive.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Acrylic_Panel_drive.STL) | 234,484 B | binary-STL |
| [3D_FIles_Format/STL/Metal_Column.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Metal_Column.STL) | 80,484 B | binary-STL |
| [3D_FIles_Format/STL/Metal_Column_with_front_panel.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Metal_Column_with_front_panel.STL) | 119,884 B | binary-STL |
| [3D_FIles_Format/STL/Metal_Panel_Bottom.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Metal_Panel_Bottom.STL) | 356,584 B | binary-STL |
| [3D_FIles_Format/STL/Metal_Panel_Top.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Metal_Panel_Top.STL) | 208,184 B | binary-STL |
| [3D_FIles_Format/STL/Metal_Panel_motherboard+PSU.STL](https://raw.githubusercontent.com/absonbbg/Jkase-D3/9842073feeb0ddf03729c04a5213c19fe236a983/3D_FIles_Format/STL/Metal_Panel_motherboard%2BPSU.STL) | 219,284 B | binary-STL |
