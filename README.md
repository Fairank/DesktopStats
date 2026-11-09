# 第三方硬件 GLB 参考资料（七件）

这里提供 CPU、RTX3080、RAM、双扇水冷、120mm 风扇、PSU、M.2 SSD 的原样第三方模型文件和来源资料，合计3,540,424B模型数据。用于独立模型评估，不是已完成装机的新版软件。

**当前 Stats 不能把此目录作为 `.dspack` 导入。原生预览、六版表现、真实尺寸、固定安装位、接线和装配净空都未验收；不会默认加载。**

## 文件

- `models/`：七个固定版本原样 GLB，完整大小、SHA256、Git blob SHA1见 MODEL_SOURCES053.json。
- `ATTRIBUTION053.md` / `MODEL_SOURCES053.json`：逐原作者、作品、原URL、CC BY4.0、固定镜像与未修改说明。
- `LICENSE-CC-BY-4.0.txt`：Creative Commons 官方完整许可文本。
- `MODEL_QUALITY053.json`：实际离线解码检查及原模型已发现的几何问题。
- `UPSTREAM-MODEL-CREDITS.md`：固定镜像完整署名原文；其中包含本包未收录文件的历史上下文。
- `MANIFEST053.json`：目录逐文件大小和SHA256；不等于发布签名或已上传证明。

## 使用边界

这些作品使用 CC BY4.0，而非 DesktopStats 自有素材的非商用许可。保留原作者署名与许可，修改时注明修改。这里没有以 DesktopStats 著作权名义添加任何模型水印、追踪或权利限制，也不包含本项目既有 D1 数据发行件。

七件已完成实际压缩网格解码、有限值和索引范围检查，但原始缺陷保留：GPU37退化/共线三角与84强反向法线观察；RAM570与573；冷却器70退化及546局部/108世界强反向观察；PSU19与5；SSD4与1。CPU与风扇在该有限判据下为0，不等于制造或装机认证。完整数字、判据与不可解读为全绿的限制见 MODEL_QUALITY053.json。

全部原模型单位与厂家毫米尺寸仍未校准。镜像项目中为画面手调的300mm显卡、142mm内存、100mmSSD、80mm电源高度未被使用，不能据此安装。GPU动画标签也存在采样混叠，不能当真实转速；本包没有新动画或现场监测数据。

GLB 需要 EXT_meshopt_compression、KHR_mesh_quantization，部分还需要 WebP；这说明查看器需要相应功能，不表示 Stats 现已支持。纹理像素、PBR显示及原生视效尚未检查。本资料包不包含 JavaScript/Three/WebView 运行时、安装器或后台采集器，不会安装、重启软件或自动运行模型代码。
