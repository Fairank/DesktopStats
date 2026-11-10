# 可直接载入开发版的 MIT 三维参考

已接入[DesktopStats 开发源码的“开源 3D”入口](https://github.com/Fairank/DesktopStats/blob/codex/fixed-mount-fit-v053/docs/OPEN_REFERENCE_MODELS054.md)。在包含本次改动的版本中打开“硬件型号图鉴 → 开源 3D → 载入模型 ZIP…”，无需解压。当前本机安装版未因此自动升级。

| 下载 | 大小 | 结构 |
| --- | ---: | --- |
| [风冷散热器](DesktopStats-MIT-air-cooler054.zip) | 564,932 B | 冷板、热管、鳍片、风扇、顶盖、卡扣与扣具等8组 |
| [一体水冷](DesktopStats-MIT-liquid-cooler054.zip) | 787,376 B | 冷排、风扇、泵、冷板、管路与接头等8组 |

另可载入[此前的通用风扇包](https://github.com/Fairank/DesktopStats/blob/861420f4b2457cd2a661e99fd73cc4dd47349b20/additional/pc-anatomy053/DesktopStats-open-fan-reference053.zip)。这是同一风扇的原始／法线修订两份文件，不按两款产品计数。

两份新ZIP均已实际走应用加载代码检查，CRC、成员字节、实体数量、部件归属和只读几何匹配，关闭后引用释放。支持旋转、点选、聚焦、隐藏／恢复及六版风格；当前原生驱动画面仍待桌面验收。包内有完整原始材质数据，但检视暂用简化材质；没有绑定本机温度或转速，也没有把通用结构当作经过厂家认证的零售精模、制造CAD或完整机械拆装。

原作者：[Yoseph / PC Anatomy](https://github.com/Yoosseph/pc-anatomy/tree/9ca9c9635a19abd189cd9978396d26be7a5d0858)。固定源版本 `9ca9c9635a19abd189cd9978396d26be7a5d0858`。本轮只修正叶片绕序和法线，保留原坐标、表面、其他配件、实例、材质和光源；衍生说明及顶点对应表在包内。

保留 PC Anatomy、Three.js、Canvas 的完整 MIT 许可与署名；不叠加本项目原创代码的非商用限制，不加本项目独占水印。此为数据参考ZIP，区别于旧JSON型号 `.dspack`，不自动安装或预载，不含可执行程序。文件 SHA-256 与范围见 [PACKAGES054.json](PACKAGES054.json)。
