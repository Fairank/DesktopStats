# 显卡模型逐项细化清单

本清单对应 0.43 开发候选的现有目录，不表示覆盖全部市售型号。
全部 147 项共享 13 个外观保存值、相同设备身份与风扇布局；当前编号 1–6 与其余保留方案见 [README](../README.md#硬件外观清单六版沿革与现有选项)。
147 项均补入具体前面板、折梁、切面或风道的来源轮廓；两项 BIOSTAR 经本轮官方原图复核后分别绘制基础款与 OC 款。
已有的尺寸、颜色、接口种类和数量继续从各自 Board profile 取得；没有新造内部 PCB、电路、插座次序或隐藏风扇。
风扇列独立记录叶型状态：资料未完整核实时保持现有静态开孔／轴心，不画猜测叶片，也不因零转速推断风扇数量。
图形为原创比例示意；OC／非 OC 经来源确认共壳时使用同一结构。面板间距、笔迹、材质效果不当作 CAD 尺寸。

状态“已补轮廓”指已接入模型视图及全部风格，并非该产品所有细节都已核实。来源链接沿用已收录厂商资料。

| 型号／版本 | 稳定 ID | 前壳进度 | 总／正面风扇 | 叶型与动效前提 | 结构配方 |
| --- | --- | --- | --- | --- | --- |
| [ASUS Dual RTX 4060 OC](https://www.asus.com/motherboards-components/graphics-cards/dual/dual-rtx4060-o8g/) | `asus-dual-4060-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `asus_dual` |
| [ASUS TUF RTX 4070 Ti SUPER OC](https://www.asus.com/motherboards-components/graphics-cards/tuf-gaming/tuf-rtx4070tis-o16g-gaming/) | `asus-tuf-4070tis-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_tuf` |
| [MSI RTX 4060 VENTUS 2X BLACK OC](https://us.msi.com/Graphics-Card/GeForce-RTX-4060-VENTUS-2X-BLACK-8G-OC) | `msi-ventus-4060-2x-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_ventus` |
| [GIGABYTE RTX 4060 WINDFORCE OC](https://www.gigabyte.com/press/news/2096) | `gigabyte-windforce-4060-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `gigabyte_windforce` |
| [ZOTAC RTX 4060 SOLO](https://marketplace.nvidia.com/en-us/consumer/graphics-cards/zotac-nvidia-geforce-rtx-4060-solo-single-fan-8gb-gddr6-pcie-4-0-graphics-card/) | `zotac-solo-4060` | 已补轮廓（3 组） | 1／1 | 已核；仅有效 RPM 转动 | `zotac_solo` |
| [SAPPHIRE PULSE RX 7600](https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7600-8g-gddr6) | `sapphire-pulse-7600` | 已补轮廓（5 组） | 2／2 | 已核；仅有效 RPM 转动 | `sapphire_pulse` |
| [ASUS ROG Strix GeForce RTX 4090 OC Edition 24GB GDDR6X](https://rog.asus.com/graphics-cards/graphics-cards/rog-strix/rog-strix-rtx4090-o24g-gaming-model/) | `asus-rog-strix-4090-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_rog_strix` |
| [MSI GeForce RTX 4090 SUPRIM X 24G](https://www.msi.com/Graphics-Card/GeForce-RTX-4090-SUPRIM-X-24G/Overview) | `msi-suprim-x-4090-24g` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_suprim` |
| [MSI GeForce RTX 5080 16G GAMING TRIO](https://www.msi.com/Graphics-Card/GeForce-RTX-5080-16G-GAMING-TRIO/Specification) | `msi-gaming-trio-5080-16g` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_gaming` |
| [GIGABYTE AORUS GeForce RTX 4090 MASTER 24G](https://www.gigabyte.com/Graphics-Card/GV-N4090AORUS-M-24GD) | `gigabyte-aorus-4090-master` | 已补轮廓（4 组） | 3／3 | 叶型待核；保持静止 | `gigabyte_aorus` |
| [GIGABYTE GeForce RTX 4090 AERO OC 24G](https://www.gigabyte.com/Graphics-Card/GV-N4090AERO-OC-24GD) | `gigabyte-aero-4090-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `gigabyte_aero` |
| [SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC 16GB GDDR6](https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-16g-gddr6) | `sapphire-nitro-9070xt-oc` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `sapphire_nitro` |
| [PowerColor Hellhound AMD Radeon RX 7800 XT 16GB GDDR6](https://www.powercolor.com/product-detail31.htm) | `powercolor-hellhound-7800xt-oc` | 已补轮廓（2 组） | 3／3 | 已核；仅有效 RPM 转动 | `powercolor_hellhound` |
| [PowerColor Red Devil AMD Radeon RX 7800 XT 16GB GDDR6](https://www.powercolor.com/product-detail32.htm) | `powercolor-red-devil-7800xt-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `powercolor_red_devil` |
| [ASRock AMD Radeon RX 7900 XTX Phantom Gaming 24GB OC](https://pg.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Phantom%20Gaming%2024GB%20OC/) | `asrock-phantom-7900xtx-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asrock_phantom` |
| [ASRock AMD Radeon RX 7800 XT Steel Legend 16GB OC](https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207800%20XT%20Steel%20Legend%2016GB%20OC/) | `asrock-steel-legend-7800xt-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asrock_steel_legend` |
| [ASRock AMD Radeon RX 7600 Challenger 8GB OC](https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207600%20Challenger%208GB%20OC/) | `asrock-challenger-7600-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `asrock_challenger` |
| [ASRock AMD Radeon RX 7900 XTX Taichi 24GB OC](https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Taichi%2024GB%20OC/) | `asrock-taichi-7900xtx-oc` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `asrock_taichi` |
| [XFX Speedster MERC 310 AMD Radeon RX 7900 XTX Black Edition 24GB](https://www.xfxforce.com/shop/xfx-speedster-merc-310-7900xtx-black-edition) | `xfx-merc310-7900xtx-black` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `xfx_merc` |
| [XFX Speedster QICK 319 AMD Radeon RX 6750 XT CORE 12GB](https://www.xfxforce.com/shop/xfx-speedster-qick-319-amd-radeon-tm-rx-6750-xt-core-2) | `xfx-qick319-6750xt-core-jfdr` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `xfx_qick` |
| [XFX Speedster SWFT 210 AMD Radeon RX 6600 CORE 8GB](https://www.xfxforce.com/shop/xfx-speedster-swft-210-amd-radeon-tm-rx-6600-core) | `xfx-swft210-6600-core-lfdq` | 已补轮廓（3 组） | 2／2 | 已核；仅有效 RPM 转动 | `xfx_swft` |
| [PNY GeForce RTX 4070 12GB XLR8 Gaming VERTO EPIC-X RGB Overclocked Triple Fan](https://www.pny.com/pny-geforce-rtx-4070-12gb-xlr8-gaming-verto-epic-x-rgb-oc) | `pny-xlr8-4070-epicx-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `pny_xlr8` |
| [PNY GeForce RTX 4070 12GB VERTO Dual Fan](https://www.pny.com/geforce-rtx-4070-12gb-verto-dual-fan) | `pny-verto-4070-dual` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `pny_verto` |
| [EVGA GeForce RTX 3080 FTW3 GAMING 10GB](https://www.nvidia.com/en-us/geforce/news/rtx-3080-3090-custom-card-roundup/) | `evga-ftw3-3080-gaming-kr` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `evga_ftw3` |
| [EVGA GeForce RTX 3080 XC3 BLACK GAMING 10GB](https://www.nvidia.com/en-us/geforce/news/rtx-3080-3090-custom-card-roundup/) | `evga-xc3-3080-black-kr` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `evga_xc3` |
| [Leadtek WinFast GeForce RTX 4090 HURRICANE 24GB](https://www.leadtek.com/eng/news/product_news_detail/1693) | `leadtek-hurricane-4090-24g` | 已补轮廓（4 组） | 3／3 | 叶型待核；保持静止 | `leadtek_hurricane` |
| [Palit GeForce RTX 4090 GameRock OC](https://www.palit.com/palit/vgapro.php?id=4578&lang=en) | `palit-gamerock-4090-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `palit_gamerock` |
| [Palit GeForce RTX 4070 Ti JetStream](https://www.palit.com/palit/vgapro.php?id=4818&lang=en) | `palit-jetstream-4070ti` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `palit_jetstream` |
| [Palit GeForce RTX 4070 Ti GamingPro OC](https://www.palit.com/palit/vgapro.php?id=4698&lang=en) | `palit-gamingpro-4070ti-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `palit_gamingpro` |
| [Gainward GeForce RTX 4090 Phantom](https://www.gainward.com/main/vgapro.php?id=1163&lang=en) | `gainward-phantom-4090` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `gainward_phantom` |
| [Gainward GeForce RTX 4080 SUPER Phoenix](https://www.gainward.com/main/vgapro.php?id=1210&lang=en) | `gainward-phoenix-4080super` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `gainward_phoenix` |
| [Gainward GeForce RTX 4060 Ghost](https://www.gainward.com/main/vgapro.php?id=1191&lang=en) | `gainward-ghost-4060` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `gainward_ghost` |
| [GALAX GeForce RTX 5080 HOF Extreme](https://galax.com/en/news/press-release-5080-hof-extreme/) | `galax-hof-5080-extreme` | 已补轮廓（4 组） | 4／3 | 已核；仅有效 RPM 转动 | `galax_hof` |
| [GALAX GeForce RTX 4070 EX Gamer 1-Click OC D6](https://galax.com/en/product/geforce-rtx-4070-ex-gamer-d6/) | `galax-ex-gamer-4070-d6` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `galax_ex_gamer` |
| [GALAX GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC](https://galax.com/en/product/geforce-rtx-4070ti-super-sg-plus-1-click-oc/) | `galax-sg-plus-4070tis` | 已补轮廓（6 组） | 未知／3 | 已核；仅有效 RPM 转动 | `galax_sg` |
| [INNO3D GeForce RTX 4070 iCHILL X3](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-ichill-x3) | `inno3d-ichill-x3-4070` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `inno3d_ichill_x3` |
| [INNO3D GeForce RTX 3080 iCHILL X4](https://inno3d.com/product/inno3d-geforce-rtx-3080-ichill-x4) | `inno3d-ichill-x4-3080` | 已补轮廓（4 组） | 4／3 | 叶型待核；保持静止 | `inno3d_ichill_x4` |
| [INNO3D GeForce RTX 4070 TWIN X2](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2) | `inno3d-twin-x2-4070` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `inno3d_twin_x2` |
| [INNO3D GeForce RTX 4070 X3 OC](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-x3-oc) | `inno3d-x3-4070-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `inno3d_x3` |
| [Colorful iGame GeForce RTX 4070 Ti Vulcan OC-V](https://test.colorful.cn/en/home/product?id=89dc18fc-c42b-4bea-8e6b-11ad5e8400bc&mid=102) | `colorful-vulcan-4070ti-oc-v` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `colorful_vulcan` |
| [Colorful iGame GeForce RTX 4070 Ti SUPER Ultra W OC 16GB-V](https://www.colorfulgroup.com/en/home/product?id=c619c9ae-b48e-4618-b9b4-225e23c83140&mid=102) | `colorful-ultra-4070ti-super-w-oc-16g-v` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `colorful_ultra` |
| [Colorful iGame GeForce RTX 4070 Ti Advanced OC-V](https://test.colorful.cn/en/home/product?id=455a7ef6-46de-4fb5-9400-c11884c02991&mid=102) | `colorful-advanced-4070ti-oc-v` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `colorful_advanced` |
| [Maxsun MS-RTX5060 iCraft GT OC8G AIGA](https://www.maxsun.com/products/ms-rtx5060-icraft-gt-oc8g-aiga) | `maxsun-icraft-5060-gt-oc8g-aiga` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `maxsun_icraft` |
| [Maxsun MS-RTX5060Ti TerminatorX3 16G](https://www.maxsun.com/products/ms-rtx5060ti-trbx3-16g) | `maxsun-terminator-5060ti-x3-16g` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `maxsun_terminator` |
| [Yeston Sakura Atlantis Radeon RX 9070 XT 16G GDDR6 256bit](https://yestonstore.com/products/yeston-sakura-atlantis-radeon-rx-9070-xt-16g-gddr6-256bit-4nm-video-cards-desktop-computer-pc-graphics-card) | `yeston-atlantis-rx9070xt-16g` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `yeston_atlantis` |
| [Yeston Sakura Radeon RX 7800 XT 16G GDDR6 256bit](https://yestonstore.com/products/yeston-sakura-radeon-rx-7800-xt-16g-gddr6-256bit-desktop-computer-graphics-card) | `yeston-sakura-rx7800xt-16g` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `yeston_sakura` |
| [BIOSTAR Radeon RX 7600 VA7606RM81](https://www.biostar.com.tw/app/en/vga/introduction.php?S_ID=316) | `biostar-radeon-rx7600-va7606rm81` | 已补轮廓（2 组） | 2／2 | 已核；仅有效 RPM 转动 | `b_biostar7600_base` |
| [NVIDIA GeForce RTX 5090 Founders Edition 32GB](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/) | `nvidia-founders-rtx5090-32g` | 已补轮廓（3 组） | 2／2 | 已核；仅有效 RPM 转动 | `nvidia_founders` |
| [AMD Radeon RX 7900 XTX Reference 24GB](https://www.amd.com/en/products/graphics/desktops/radeon/7000-series/amd-radeon-rx-7900xtx.html) | `amd-reference-rx7900xtx-24g` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `amd_reference` |
| [Intel Arc A770 Limited Edition 16GB](https://game.intel.com/stories/intel-arc-graphics-overclocking-101/) | `intel-limited-arc-a770-16g` | 已补轮廓（3 组） | 2／2 | 已核；仅有效 RPM 转动 | `intel_limited` |
| [ASUS ROG Astral GeForce RTX 5080 OC Edition 16GB GDDR7](https://rog.asus.com/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5080-o16g-gaming/) | `asus-astral-5080-oc` | 已补轮廓（4 组） | 4／3 | 已核；仅有效 RPM 转动 | `asus_astral` |
| [ASUS Prime GeForce RTX 5080 OC Edition 16GB GDDR7](https://www.asus.com/motherboards-components/graphics-cards/prime/prime-rtx5080-o16g/) | `asus-prime-5080-oc` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_prime` |
| [ASUS ProArt GeForce RTX 5080 OC Edition 16GB GDDR7](https://press.asus.com/news/press-releases/asus-proart-geforce-rtx-50-series/) | `asus-proart-5080-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_proart` |
| [MSI GeForce RTX 4080 SUPER 16G EXPERT](https://www.msi.com/Graphics-Card/GeForce-RTX-4080-SUPER-16G-EXPERT) | `msi-expert-4080super` | 已补轮廓（4 组） | 2／1 | 已核；仅有效 RPM 转动 | `msi_expert` |
| [MSI GeForce RTX 5080 16G VANGUARD SOC](https://storage-asset.msi.com/datasheet/vga/cn/GeForce-RTX-5080-16G-VANGUARD-SOC.pdf) | `msi-vanguard-5080soc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_vanguard` |
| [MSI GeForce RTX 5080 16G INSPIRE 3X OC](https://www.msi.com/Graphics-Card/GeForce-RTX-5080-16G-INSPIRE-3X-OC/Overview) | `msi-inspire-5080oc` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_inspire` |
| [MSI GeForce RTX 5080 16G SHADOW 3X OC](https://storage-asset.msi.com/datasheet/vga/sg/GeForce-RTX-5080-16G-SHADOW-3X-OC.pdf) | `msi-shadow-5080oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_shadow` |
| [GIGABYTE GeForce RTX 5070 GAMING OC 12G](https://www.gigabyte.com/Graphics-Card/GV-N5070GAMING-OC-12GD) | `gigabyte-gaming-5070oc` | 已补轮廓（4 组） | 3／3 | 叶型待核；保持静止 | `gigabyte_gaming_oc` |
| [GIGABYTE GeForce RTX 5070 EAGLE OC SFF 12G](https://www.gigabyte.com/Graphics-Card/GV-N5070EAGLE-OC-12GD) | `gigabyte-eagle-5070oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `gigabyte_eagle` |
| [ZOTAC GAMING GeForce RTX 4060 Ti 8GB Twin Edge](https://mktportal.zotac.com/uploadPath/ZT-D40610E-10M-brochure_4.pdf) | `zotac-twin-4060ti` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `zotac_twin_edge` |
| [ZOTAC GAMING GeForce RTX 5080 SOLID](https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5080/Brochure/ZT-B50800D-10P-brochure.pdf) | `zotac-solid-5080` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `zotac_solid` |
| [ZOTAC GAMING GeForce RTX 5080 AMP Extreme INFINITY](https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5080/Brochure/ZT-B50800B-10P-brochure.pdf) | `zotac-infinity-5080` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `zotac_amp_infinity` |
| [ZOTAC GAMING GeForce RTX 4080 SUPER AMP Extreme AIRO](https://www.zotac.com/us/news/zotac-gaming-announces-geforce-rtx-40-super-series?l=en) | `zotac-airo-4080super` | 已补轮廓（3 组） | 3／3 | 叶型待核；保持静止 | `zotac_amp_airo` |
| [ZOTAC GAMING GeForce RTX 4080 SUPER Trinity Black Edition](https://www.zotac.com/us/news/zotac-gaming-announces-geforce-rtx-40-super-series?l=en) | `zotac-trinity-4080super` | 已补轮廓（3 组） | 3／3 | 叶型待核；保持静止 | `zotac_trinity` |
| [SAPPHIRE PURE AMD Radeon RX 7800 XT 16G GDDR6](https://www.sapphiretech.com/en/consumer/pure-radeon-rx-7800-xt-16g-gddr6) | `sapphire-pure-7800xt` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `sapphire_pure` |
| [PowerColor Fighter AMD Radeon RX 7800 XT 16GB GDDR6](https://www.powercolor.com/product-detail33.htm) | `powercolor-fighter-7800xt` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `powercolor_fighter` |
| [PowerColor Reaper AMD Radeon RX 9070 XT 16GB GDDR6](https://www.powercolor.com/product-detail212.htm) | `powercolor-reaper-9070xt` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `powercolor_reaper` |
| [NVIDIA GeForce GTX 1080 Founders Edition](https://www.nvidia.com/en-us/geforce/news/geforce-gtx-1080-founders-edition/) | `nvidia-gtx1080-founders` | 已补轮廓（5 组） | 1／1 | 已核；仅有效 RPM 转动 | `nvidia_founders_pascal` |
| [MSI GeForce GTX 1050 AERO ITX 2G OC](https://storage-asset.msi.com/datasheet/vga/global/GeForce-GTX-1050-AERO-ITX-2G-OC.pdf) | `msi-gtx1050-aero-itx-2g-oc` | 已补轮廓（4 组） | 1／1 | 已核；仅有效 RPM 转动 | `msi_aero_itx_pascal` |
| [MSI GeForce GTX 1050 Ti 4GT LP](https://storage-asset.msi.com/datasheet/vga/global/GeForce-GTX-1050-Ti-4GT-LP.pdf) | `msi-gtx1050ti-4gt-lp` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_low_profile_pascal` |
| [MSI GeForce GTX 1080 Ti GAMING X 11G](https://storage-asset.msi.com/datasheet/vga/global/GeForce-GTX-1080-Ti-GAMING-X-11G.pdf) | `msi-gtx1080ti-gaming-x-11g` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_gaming_pascal` |
| [MSI GeForce GTX 1080 Ti LIGHTNING Z](https://storage-asset.msi.com/datasheet/vga/global/GeForce-GTX-1080-Ti-LIGHTNING-Z.pdf) | `msi-gtx1080ti-lightning-z` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_lightning_pascal` |
| [GIGABYTE GeForce GT 1030 Silent Low Profile 2G](https://www.gigabyte.com/Graphics-Card/GV-N1030SL-2GL) | `gigabyte-gt1030-silent-lp-2g` | 已补轮廓（5 组） | 0／0 | 无风扇 | `gigabyte_silent_pascal` |
| [MSI GeForce GTX 980 Ti GAMING 6G](https://storage-asset.msi.com/datasheet/vga/global/GTX-980-Ti-GAMING-6G.pdf) | `msi-gtx980ti-gaming-6g` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_gaming_maxwell` |
| [NVIDIA GeForce GTX 780 Ti Reference](https://nvidianews.nvidia.com/news/nvidia-unveils-geforce-gtx-780-ti-the-best-gaming-gpu-on-the-planet-6622622) | `nvidia-gtx780ti-reference` | 已补轮廓（6 组） | 1／1 | 叶型待核；保持静止 | `nvidia_reference_kepler` |
| [MSI N680GTX Lightning](https://storage-asset.msi.com/datasheet/vga/global/N680GTX_Lightning.pdf) | `msi-n680gtx-lightning` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_lightning_kepler` |
| [MSI N660 TF 2GD5/OC](https://storage-asset.msi.com/datasheet/vga/global/N660_TF_2GD5OC.pdf) | `msi-n660-tf-2gd5-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_twinfrozr_kepler` |
| [MSI N580GTX Lightning](https://storage-asset.msi.com/datasheet/vga/global/N580GTX_Lightning.pdf) | `msi-n580gtx-lightning` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_lightning_fermi` |
| [MSI N480GTX-M2D15](https://storage-asset.msi.com/datasheet/vga/global/N480GTXM2D15.pdf) | `msi-n480gtx-m2d15` | 已补轮廓（6 组） | 1／1 | 叶型待核；保持静止 | `msi_blower_fermi` |
| [GIGABYTE GV-N460OC-1GI Rev. 1.0](https://www.gigabyte.com/Graphics-Card/GV-N460OC-1GI) | `gigabyte-gtx460-oc-1g-rev1` | 已补轮廓（4 组） | 2／2 | 叶型待核；保持静止 | `gigabyte_windforce_fermi` |
| [MSI N260GTX Lightning](https://storage-asset.msi.com/datasheet/vga/global/N260GTX_Lightning.pdf) | `msi-n260gtx-lightning` | 已补轮廓（4 组） | 2／2 | 叶型待核；保持静止 | `msi_lightning_tesla` |
| [MSI NX8800GTS-T2D320E-HD-OC](https://storage-asset.msi.com/datasheet/vga/global/NX8800GTST2D320EHDOC.pdf) | `msi-nx8800gts-320-oc` | 已补轮廓（4 组） | 1／1 | 叶型待核；保持静止 | `msi_blower_g80` |
| [GIGABYTE GV-N52128D GeForce FX 5200](https://www.gigabyte.com/Graphics-Card/GV-N52128D) | `gigabyte-fx5200-n52128d` | 已补轮廓（4 组） | 1／1 | 叶型待核；保持静止 | `gigabyte_fx5200` |
| [MSI Radeon HD 4870 R4870-T2D512-OC Reference](https://storage-asset.msi.com/datasheet/vga/global/R4870T2D512OC.pdf) | `msi-hd4870-t2d512-oc-reference` | 已补轮廓（3 组） | 1／1 | 叶型待核；保持静止 | `msi_hd4870_reference` |
| [MSI Radeon HD 5450 R5450-MD1GD3H/LP](https://storage-asset.msi.com/datasheet/vga/my/R5450-MD1GD3HLP.pdf) | `msi-hd5450-md1gd3h-lp` | 已补轮廓（5 组） | 0／0 | 无风扇 | `msi_hd5450_passive` |
| [MSI Radeon HD 5870 R5870-PM2D1G Reference](https://storage-asset.msi.com/datasheet/vga/ua/R5870PM2D1G.pdf) | `msi-hd5870-pm2d1g-reference` | 已补轮廓（5 组） | 1／1 | 叶型待核；保持静止 | `msi_hd5870_reference` |
| [MSI Radeon HD 7970 R7970 TF 3GD5/OC BE](https://storage-asset.msi.com/datasheet/vga/global/R7970_TF_3GD5OC_BE.pdf) | `msi-hd7970-tf-3gd5-oc-be` | 已补轮廓（5 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_twin_frozr_hd7970` |
| [MSI Radeon R9 290X 4GD5 Reference](https://storage-asset.msi.com/datasheet/vga/global/R9-290X-4GD5.pdf) | `msi-r9-290x-4gd5-reference` | 已补轮廓（3 组） | 1／1 | 已核；仅有效 RPM 转动 | `msi_r9_290x_reference` |
| [ASUS STRIX Radeon R9 Fury DC3 4G GAMING](https://www.asus.com/it/news/ohcitiw9wqe49eh8/) | `asus-strix-r9fury-dc3-4g` | 已补轮廓（5 组） | 3／3 | 叶型待核；保持静止 | `asus_strix_fury` |
| [MSI Radeon RX 480 8G Reference](https://storage-asset.msi.com/datasheet/vga/global/AMD-Radeon-RX-480-8G.pdf) | `msi-rx480-8g-reference` | 已补轮廓（4 组） | 1／1 | 叶型待核；保持静止 | `msi_rx480_reference` |
| [SAPPHIRE NITRO+ Radeon RX 580 8G G5 11265-01-20G](https://www.sapphiretech.com/en/consumer/nitro-rx-580-8g-g5) | `sapphire-nitro-rx580-8g-01` | 已补轮廓（5 组） | 2／2 | 已核；仅有效 RPM 转动 | `sapphire_nitro_polaris` |
| [MSI Radeon RX Vega 64 8G Reference](https://storage-asset.msi.com/datasheet/vga/global/Radeon-RX-Vega-64-8G.pdf) | `msi-vega64-8g-reference` | 已补轮廓（5 组） | 1／1 | 已核；仅有效 RPM 转动 | `msi_vega64_reference` |
| [ASRock Radeon RX 5500 XT Challenger D 8G OC](https://asrock.com/Graphics-Card/AMD/Radeon%20RX%205500%20XT%20Challenger%20D%208G%20OC/) | `asrock-rx5500xt-challenger-d-8g` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `asrock_challenger_rdna1` |
| [MSI Radeon RX 5700 XT 8G Reference](https://storage-asset.msi.com/datasheet/vga/global/Radeon-RX-5700-XT-8G.pdf) | `msi-rx5700xt-8g-reference` | 已补轮廓（5 组） | 1／1 | 已核；仅有效 RPM 转动 | `msi_rx5700xt_reference` |
| [SAPPHIRE PULSE Radeon RX 6400 4GB 11315-01-20G](https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-6400-4g-gddr6) | `sapphire-pulse-rx6400-4g-lp` | 已补轮廓（4 组） | 1／1 | 已核；仅有效 RPM 转动 | `sapphire_pulse_rdna2_lp` |
| [ASUS TUF Gaming Radeon RX 6800 XT OC 16GB](https://www.asus.com/motherboards-components/graphics-cards/tuf-gaming/tuf-rx6800xt-o16g-gaming/) | `asus-tuf-rx6800xt-o16g` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_tuf_rdna2` |
| [SAPPHIRE PULSE Radeon RX 7900 XT 20GB 11323-02-20G](https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7900-xt-20g-gddr6) | `sapphire-pulse-rx7900xt-20g` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `sapphire_pulse_rdna3` |
| [ASRock AMD Radeon RX 9070 XT Taichi 16GB OC](https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%209070%20XT%20Taichi%2016GB%20OC/) | `asrock-taichi-rx9070xt-16g-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asrock_taichi_rdna4` |
| [ASRock Intel Arc A380 Challenger ITX 6GB OC](https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20A380%20Challenger%20ITX%206GB%20OC/index.asp) | `asrock-a380-challenger-itx-6g` | 已补轮廓（6 组） | 1／1 | 已核；仅有效 RPM 转动 | `asrock_challenger_arc_a380` |
| [SPARKLE Intel Arc A750 TITAN OC Edition 8GB](https://www.sparkle.com.tw/files/20240202122437352.pdf) | `sparkle-a750-titan-8g-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `sparkle_titan_arc_a750` |
| [Acer Predator BiFrost Intel Arc A770 OC 16GB](https://www.acer.com/us-en/predator/desktops-and-all-in-ones/components/predator-bifrost-intel-arc-a770-oc) | `acer-bifrost-a770-16g-oc` | 已补轮廓（4 组） | 2／2 | 叶型待核；保持静止 | `acer_bifrost_arc_a770` |
| [ASRock Intel Arc B570 Challenger 10GB OC](https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20B570%20Challenger%2010GB%20OC/) | `asrock-b570-challenger-10g-oc` | 已补轮廓（5 组） | 2／2 | 已核；仅有效 RPM 转动 | `asrock_challenger_arc_b570` |
| [SPARKLE Intel Arc B580 TITAN OC Edition 12GB](https://www.sparkle.com.tw/files/20241203213858182.pdf) | `sparkle-b580-titan-12g-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `sparkle_titan_arc_b580` |
| [ASUS Dual RTX 4060 8GB](https://www.asus.com/motherboards-components/graphics-cards/dual/dual-rtx4060-8g/techspec/) | `asus-dual-4060` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `asus_dual` |
| [ASUS Dual RTX 4060 OC White](https://www.asus.com/motherboards-components/graphics-cards/dual/dual-rtx4060-o8g-white/techspec/) | `asus-dual-4060-oc-white` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `a_asus_dual_white` |
| [ASUS TUF RTX 4070 Ti SUPER 16GB](https://www.asus.com/motherboards-components/graphics-cards/tuf-gaming/tuf-rtx4070tis-16g-gaming/techspec/) | `asus-tuf-4070tis` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_tuf` |
| [ASUS ROG Strix RTX 4090 24GB](https://rog.asus.com/graphics-cards/graphics-cards/rog-strix/rog-strix-rtx4090-24g-gaming-model/spec/) | `asus-rog-strix-4090` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_rog_strix` |
| [ASUS ROG Strix RTX 4090 OC White](https://rog.asus.com/graphics-cards/graphics-cards/rog-strix/rog-strix-rtx4090-o24g-white-model/spec/) | `asus-rog-strix-4090-oc-white` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `a_asus_strix_white` |
| [ASUS Prime RTX 5080 16GB](https://www.asus.com/motherboards-components/graphics-cards/prime/prime-rtx5080-16g/techspec/) | `asus-prime-5080` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_prime` |
| [ASUS ProArt RTX 5080 16GB](https://www.asus.com/us/motherboards-components/graphics-cards/proart/proart-rtx5080-16g/techspec/) | `asus-proart-5080` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `asus_proart` |
| [ASUS ROG Astral RTX 5080 16GB](https://rog.asus.com/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5080-16g-gaming/spec/) | `asus-astral-5080` | 已补轮廓（4 组） | 4／3 | 已核；仅有效 RPM 转动 | `asus_astral` |
| [ASUS ROG Astral RTX 5080 OC White](https://rog.asus.com/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5080-o16g-white/spec/) | `asus-astral-5080-oc-white` | 已补轮廓（4 组） | 4／3 | 已核；仅有效 RPM 转动 | `a_asus_astral_white` |
| [ASUS ROG Astral RTX 5090 OC 32GB](https://rog.asus.com/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5090-o32g-gaming/spec/) | `asus-astral-5090-oc` | 已补轮廓（4 组） | 4／3 | 已核；仅有效 RPM 转动 | `asus_astral` |
| [ASUS ROG Astral RTX 5090 32GB](https://rog.asus.com/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5090-32g-gaming/spec/) | `asus-astral-5090` | 已补轮廓（4 组） | 4／3 | 已核；仅有效 RPM 转动 | `asus_astral` |
| [MSI RTX 4060 VENTUS 2X BLACK 8G](https://www.msi.com/Graphics-Card/GeForce-RTX-4060-VENTUS-2X-BLACK-8G/Specification) | `msi-ventus-4060-2x` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_ventus` |
| [MSI GeForce GTX 1080 Ti GAMING 11G](https://storage-asset.msi.com/datasheet/vga/id/GeForce-GTX-1080-Ti-GAMING-11G.pdf) | `msi-gtx1080ti-gaming-11g` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_gaming_pascal` |
| [MSI GeForce GTX 1080 Ti LIGHTNING X](https://www.msi.com/Graphics-Card/GeForce-GTX-1080-Ti-LIGHTNING-X/Specification) | `msi-gtx1080ti-lightning-x` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `msi_lightning_pascal` |
| [MSI GeForce GTX 980 Ti GAMING 6G LE](https://storage-asset.msi.com/datasheet/vga/global/GTX-980-Ti-GAMING-6G-LE.pdf) | `msi-gtx980ti-gaming-6g-le` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `msi_gaming_maxwell` |
| [MSI GeForce GTX 980 Ti GAMING 6G GOLDEN EDITION](https://www.msi.com/Graphics-Card/GTX-980-Ti-GAMING-6G-GOLDEN-EDITION/Specification) | `msi-gtx980ti-gaming-6g-golden` | 已补轮廓（5 组） | 2／2 | 已核；仅有效 RPM 转动 | `a_msi_golden980ti` |
| [ZOTAC RTX 4060 Ti 8GB Twin Edge OC](https://www.zotac.com/download/mediadrivers/External/GraphicsCard/4060Ti/Brochure/ZT-D40610H-10M-brochure.pdf) | `zotac-twin-4060ti-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `a_zotac_twin_oc` |
| [ZOTAC RTX 4060 Ti 8GB Twin Edge OC White](https://www.zotac.com/download/mediadrivers/External/GraphicsCard/4060Ti/Brochure/ZT-D40610Q-10M-brochure.pdf) | `zotac-twin-4060ti-oc-white` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `a_zotac_twin_white` |
| [ZOTAC RTX 5080 SOLID OC](https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5080/Brochure/ZT-B50800J-10P-brochure.pdf) | `zotac-solid-5080-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `zotac_solid` |
| [ZOTAC RTX 5080 AMP Extreme INFINITY (10A)](https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5080/Brochure/ZT-B50800B-10A-brochure.pdf) | `zotac-infinity-5080-10a` | 已补轮廓（4 组） | 3／3 | 叶型待核；保持静止 | `a_zotac_infinity_10a` |
| [GIGABYTE GV-N460OC-1GI Rev.2.0](https://www.gigabyte.com/Graphics-Card/GV-N460OC-1GI-rev-20) | `gigabyte-gtx460-oc-1g-rev2` | 已补轮廓（4 组） | 2／2 | 叶型待核；保持静止 | `a_gigabyte_460_rev2` |
| [GIGABYTE GV-N460OC-1GI Rev.3.0](https://www.gigabyte.com/Graphics-Card/GV-N460OC-1GI-rev-30) | `gigabyte-gtx460-oc-1g-rev3` | 已补轮廓（4 组） | 2／2 | 叶型待核；保持静止 | `a_gigabyte_460_rev3` |
| [MSI GeForce RTX 5090 32G SUPRIM SOC](https://www.msi.com/Graphics-Card/GeForce-RTX-5090-32G-SUPRIM-SOC/Specification) | `msi-suprim-5090-32g-soc` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `suprim_blackwell` |
| [MSI GeForce RTX 5090 32G SUPRIM OC](https://www.msi.com/Graphics-Card/GeForce-RTX-5090-32G-SUPRIM-OC/Specification) | `msi-suprim-5090-32g-oc` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `suprim_blackwell` |
| [ASRock AMD Radeon RX 7900 XTX Taichi White 24GB OC](https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Taichi%20White%2024GB%20OC/index.asp) | `asrock-taichi-7900xtx-white-oc` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `b_taichi7900_white` |
| [ASRock AMD Radeon RX 9070 XT Taichi White 16GB OC](https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%209070%20XT%20Taichi%20White%2016GB%20OC/index.asp) | `asrock-taichi-rx9070xt-white-16g-oc` | 已补轮廓（6 组） | 3／3 | 已核；仅有效 RPM 转动 | `b_taichi9070_white_lcd` |
| [INNO3D GeForce RTX 4070 TWIN X2 OC](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2-oc) | `inno3d-twin-x2-4070-oc` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `inno3d_twin_x2` |
| [INNO3D GeForce RTX 4070 GDDR6 TWIN X2](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-gddr6-twin-x2) | `inno3d-twin-x2-4070-gddr6` | 已补轮廓（4 组） | 2／2 | 已核；仅有效 RPM 转动 | `inno3d_twin_x2` |
| [INNO3D GeForce RTX 4070 TWIN X2 OC WHITE](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2-oc-white) | `inno3d-twin-x2-4070-oc-white` | 已补轮廓（3 组） | 2／2 | 已核；仅有效 RPM 转动 | `b_inno4070_white` |
| [INNO3D GeForce RTX 4070 TWIN X2 OC WHITE STEALTH](https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2-oc-white-stealth) | `inno3d-twin-x2-4070-oc-white-stealth` | 已补轮廓（3 组） | 2／2 | 已核；仅有效 RPM 转动 | `b_inno4070_white_stealth` |
| [BIOSTAR Radeon RX 7600 OC VA76S6RM81](https://www.biostar.com.tw/app/en/vga/introduction.php?S_ID=334) | `biostar-radeon-rx7600-oc-va76s6rm81` | 已补轮廓（5 组） | 2／2 | 已核；仅有效 RPM 转动 | `b_biostar7600_oc` |
| [SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC PhantomLink Edition GPU](https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-ple-16g-gddr6) | `sapphire-nitro-9070xt-phantomlink` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_nitro_phantom` |
| [SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC PhantomLink Polar Edition GPU](https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-ple-polar-16g-gddr6) | `sapphire-nitro-9070xt-phantomlink-polar` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_nitro_polar` |
| [SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC Valor Mortis Edition GPU](https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-vme-16g-gddr6) | `sapphire-nitro-9070xt-valor-mortis` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_nitro_valor` |
| [SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC Crimson Desert Edition GPU](https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-cde-16g-gddr6) | `sapphire-nitro-9070xt-crimson-desert` | 已补轮廓（3 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_nitro_crimson` |
| [PowerColor Hellhound Sakura RX 7800 XT Limited Edition](https://powercolor.com/product-detail34.htm) | `powercolor-hellhound-7800xt-sakura-limited` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_hellhound_sakura_limited` |
| [PowerColor Hellhound Sakura RX 7800 XT](https://powercolor.com/product-detail35.htm) | `powercolor-hellhound-7800xt-sakura` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_hellhound_sakura` |
| [PowerColor Hellhound Spectral White RX 7800 XT](https://powercolor.com/product-detail36.htm) | `powercolor-hellhound-7800xt-white` | 已补轮廓（2 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_hellhound_white` |
| [PowerColor Red Devil RX 7800 XT Limited Edition](https://powercolor.com/product-detail39.htm) | `powercolor-red-devil-7800xt-limited` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_devil_limited` |
| [PowerColor Red Devil RX 7800 XT BP Edition](https://powercolor.com/product-detail256.htm) | `powercolor-red-devil-7800xt-bp` | 已补轮廓（5 组） | 3／3 | 已核；仅有效 RPM 转动 | `c_devil_bp` |
| [PowerColor Fighter Mini RX 7800 XT](https://powercolor.com/cn/product-detail37.htm) | `powercolor-fighter-7800xt-mini` | 已补轮廓（2 组） | 2／2 | 已核；仅有效 RPM 转动 | `c_fighter_mini` |
| [SPARKLE Intel Arc A770 TITAN OC Edition 16GB](https://www.sparkle.com.tw/files/20240507153541749.pdf) | `sparkle-a770-titan-16g-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `sparkle_titan_arc_a750` |
| [SPARKLE Intel Arc B580 TITAN Luna OC 12GB](https://www.sparkle.com.tw/files/20250116155909862.pdf) | `sparkle-b580-titan-luna-12g-oc` | 已补轮廓（4 组） | 3／3 | 已核；仅有效 RPM 转动 | `sparkle_titan_arc_b580` |
| [SPARKLE Intel Arc B580 ROC Luna OC Ultra 12GB](https://www.sparkle.com.tw/files/20250519101812700.pdf) | `sparkle-b580-roc-luna-12g-oc-ultra` | 已补轮廓（3 组） | 2／2 | 已核；仅有效 RPM 转动 | `c_roc_luna` |

不完整项的后续工作：先补可靠的该型号实物资料，再更新外壳或逐扇叶型；不把静态图鉴的演示转动当作已安装设备转速。
本轮没有重启、替换当前安装或改变温度桥接。Windows 桌面玻璃与真实游戏占用仍需之后独立验收。
