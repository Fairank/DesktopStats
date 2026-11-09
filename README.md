# 第三方硬件GLB参考资料（九件候选）

提供CPU、RTX3080、RAM、双扇水冷、120mm风扇、PSU、M.2 SSD，以及Fractal Meshify C机箱与ASUS Strix B550-F主板的作者模型原样GLB。九文件共23,873,776B。它们是独立参考资料，不是已完成装机的新版软件，也不是厂家官方CAD。

**当前Stats不能把此目录作为`.dspack`导入。原生预览、六版表现、厂家毫米尺寸、固定安装位、接线和装配净空未验收，不会默认加载。**

## 文件与来源

- `models/`：九个固定版本原样GLB，逐文件bytes/SHA256/Git blob SHA1、作者与原URL见MODEL_SOURCES053.json。
- `ATTRIBUTION053.md`：逐原作者、作品和CC BY4.0署名；完整许可见LICENSE-CC-BY-4.0.txt。
- `MODEL_QUALITY053.json`：七件已解码与新增两件仅容器检查分开记录，不能合并成九件几何全绿。
- `UPSTREAM-MODEL-CREDITS.md`：固定镜像原始credit说明，含其自身历史上下文；fan-white不在此候选内。
- `MANIFEST053.json`：十五个payload文件的大小/SHA256，不包含自身；不是签名或上传证明。

## 检查范围：七件已解码，两件仅查容器

原七件CPU/GPU/RAM/cooler/fan/PSU/storage完成离线压缩网格解码、有限值和索引范围检查，仍保留原始缺陷：GPU37退化/共线三角与84强反向法线观察；RAM570与573；冷却器70退化及546局部/108世界强反向观察；PSU19与5；SSD4与1。CPU与风扇在该有限判据下为0，不代表制造、闭合外法线或装机认证。

新增case.glb与motherboard.glb只完成GLB容器/JSON/声明布局/引用/层级检查，**没有做实际顶点、法线或索引样本扫描**，因此几何缺陷统计为unknown而非0。Meshify C声明136nodes/67mesh/223920triangles，未使用meshopt；B550-F声明31nodes/31mesh/583847triangles，需要meshopt/quantization并含27WebP。源层级分组不等于已核可拆板件或机械动作。统计依据与旧七件不同，不能直接汇总。

## 使用边界

九个原模型的单位和厂家毫米尺寸均未校准。镜像项目为画面手调的300mm显卡、142mm内存、100mmSSD、80mm电源高度未被采用；不得拿这些数值或镜像hideNodes自动安装、缩放、删除源件。GPU原动画标签还有采样混叠，不是实际转速；本资料没有现场监测数据。

全部纹理像素/PBR显示未验收。部分文件需EXT_meshopt_compression/KHR_mesh_quantization/WebP等查看器功能，但这不表示Stats现在支持，也不表示未压缩的case已完成几何质量检查。高面数模型需要另行有界预算评估，不能静默丢件或减面后仍称原件相同。

模型使用原作者CC BY4.0，而非DesktopStats自有素材的非商用许可。保留署名、原URL、许可和更改说明，原有商用等权利不被收窄。本候选不包含DIY项目的GPL/CERN文件、程序源码、旧自有素材包或签名，也没有我方版权水印、运行时JS/Three/WebView、安装器或后台采集器；不自动安装或运行任何上游模型代码。

九件参考资料与稳定软件分开提供。原七个GLB保持相同字节，同一独立资料分支保留版本历史；不能混入程序或自有NC素材树。清单只能校验目录内容，不能单独证明远端上传状态；实际资料提交与远端读回回执另列。
