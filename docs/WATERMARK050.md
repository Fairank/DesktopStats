# 隐形水印、转载与来源验证 · 0.50

**状态：六项正式密钥副本的签发候选已完成验证，验签、提取、固定数据入口及最终 r2 相关回归均已核对。**
原版 GLB 的四视图 CPU 软件对照已完成。最终上传／安装结果以候选最终提交说明为准；本轮未安装或做 Windows 原生验收。
原有应用与 0.49 预览文件保留；本轮不安装、重启 Stats，不采集硬件，也不做 Windows 原生验收。

目标是为原创发行资产加入平常观看难以察觉、可以离线提取的来源标记，便于在疑似复制时对照原件。
它不是可见角标或仅存在于文件属性中的 metadata。非商用范围仍以原 [LICENSE](../LICENSE)、
[LICENSING.md](../LICENSING.md) 和第三方例外为准，六版外观与原版无笑脸的约束不变。

## 本轮范围

本地已标记一份指定参考整机 GLB，以及以下五项原始预览的**另存副本**。
GLB 是原创程序化参考网格，不是厂商 CAD，不表示实际电脑的硬件清单或完整装配验收。

| 类型 | 原件输入 | 本地已验证的 0.50 签发候选 |
| --- | --- | --- |
| GLB | 指定 North XL 参考整机，含独立部件身份 | [north-xl-independent-protected050.glb（ZIP 内）](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/DesktopStats-protected-reference050.zip) |
| PNG | `assembly-six-depth049.png` | [assembly-six-depth050-protected.png](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/assembly-six-depth050-protected.png) |
| PNG | `gpu-six-depth049.png` | [gpu-six-depth050-protected.png](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/gpu-six-depth050-protected.png) |
| PNG | `assembly-depth-review049.png` | [assembly-depth-review050-protected.png](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/assembly-depth-review050-protected.png) |
| GIF | `gpu-insertion049.gif` | [gpu-insertion050-protected.gif](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/gpu-insertion050-protected.gif) |
| GIF | `gpu-insertion-six049.gif` | [gpu-insertion-six050-protected.gif](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/gpu-insertion-six050-protected.gif) |

五项图像原件位于 `assets/showcase/`；它们是 0.49 的未标记输入，不能因为 0.50 后续另存就追称旧发布已标记。
新的模型、标记预览和来源清单放在独立数据提交，供用户按需下载；文件和链接已准备好，最终发布结果见候选最终提交说明。
这些资产不加入 Stats 主程序，也不改变现有运行时 `.dspack` 的型号数或安装规则。

以下仍**未覆盖**：SVG、JSON 扩展包、程序实时生成的全库网格、其他照片或历史图片。
标记 GLB 不意味着同一场景截图会带有可提取的几何标记，标记图片也不意味着所有压缩、裁剪或截图后仍能提取。
Lucide／Feather、第三方库、厂商照片及既有授权素材不作为我们的原创标记载体。

## 固定下载入口（签发候选）

以下链接固定到数据提交 `7319224c4999d59a9eebbae654dc5db452ece498`，对应数据分支
`codex/invisible-watermark-data-v050`。上传成功前它们可能无法访问，不能仅凭本说明认定已公开。

- [参考整机 GLB 下载包](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/DesktopStats-protected-reference050.zip)：1190244 字节，SHA-256 为 `25f585d6f2cc4f239219813adfd4c580f60cd3d06f6a6c975621be8d5c915793`。
- [数据提交与五项预览](https://github.com/Fairank/DesktopStats/tree/7319224c4999d59a9eebbae654dc5db452ece498)：PNG／GIF 与其同名 `.watermark.json` 另存于此，GLB 和其清单在上述 ZIP 内。
- [签名发行清单](https://raw.githubusercontent.com/Fairank/DesktopStats/7319224c4999d59a9eebbae654dc5db452ece498/RELEASE_INDEX.json)及[本地发行索引](WATERMARK050_INDEX.json)：列出原件、标记件、清单和文件哈希，不包含秘密密钥。
- [离线发布工具源码](https://github.com/Fairank/DesktopStats/tree/codex/invisible-watermark-v050)：源码链接指向工作分支，具体冻结及上传结果见候选最终提交说明。

## 隐藏信息如何进入资产

几何方案在离线导出时把随机的 **96 bit 发行 ID** 编入 GLB 的 f32 位置低位，并按部件记录覆盖情况。
约束是不新增节点、三角形或动画，不更改法线，并保持共享几何点的一致性；位置数值会有极小变化，
因此不能称为原顶点字节完全不变。正式副本的世界位置最大改变量为 **0.000065185575 mm**，包络差为零；
由新位置推导的几何面方向最大角差约 **0.00658161°**，没有翻面或新增／消失的退化三角形。
存储的法线、索引、材质、节点值与有限动画保持原样；这是数值比较，不是实物 CAD 精度或原生像素验收。

PNG 在不透明像素的蓝色通道低位嵌入标记，GIF 修改最终调色板低位；正式副本的 RGB 通道最大改变量为 **1**，
alpha 不变，GIF 索引、时长与 loop 不变。GIF 编码器本身不解码每项调色板的索引使用情况；
独立图像测试对两段真实输入动画各 **62 帧** 进行软件解码对照；两张正式保护 PNG 也已抽看，未见可识别的水印标志。
这不是对全部图片、GIF 每帧、显示器和缩放的人工验收；不能只因写入 metadata 或数值变化小就冒称完成原生视觉验收。

上述 **RGB 变化不超过 1** 只适用于 PNG／GIF 文件标记，不适用于“重新渲染标记后的 GLB”。
正式 GLB 已用其实际 f32 位置，与原始 GLB 在相同相机、材质和法线下做原版四视图 CPU 软件比较，
没有把先前 f64 转 f32 的导出舍入误差算作水印变化。最大投影差约 **0.0001831 px**，但仍有实际栅格差异：

| 原版软件视图 | RGB 改变像素／总像素 | 最大 RGB 差（0—255） | RGB 平均绝对差（0—255） |
| --- | ---: | ---: | ---: |
| 整机 | 1003／705600 | 35（差值至少 32 的仅 3 点） | 0.00416053 |
| GPU | 412／520000 | 23 | 0.00137949 |
| CPU | 16／490000 | 3 | 0.00004082 |
| 单条 RAM | 0／490000 | 0 | 0 |

实际对照未见可识别的水印文字或标志，但不能称为零像素差异。微小坐标变化可能跨过软件抗锯齿或深度采样边界，
所以个别像素的色差可大于 1；差异图完整保留，没有过滤这些点。
此结果仅覆盖原版四个 CPU 软件视图，不代表六版、任意缩放或原生 Windows GL 的像素等价验收。

ID 标识这次发行资产，不识别用户或设备，不按下载者生成个人指纹。
嵌入与提取是离线发布工具，不向 Stats 增加采样、线程、动画时钟或后台检查。
未测整款应用的 CPU、RAM、显存或总绘制调用，不据此宣称占用降低。

## 签名、原件与离线核对

正式本地副本已将原件、标记件及清单的哈希与各自发行 ID 绑定，并用 **Ed25519** 为清单签名。
签名只能在信任所用公钥的前提下确认清单来源和字节完整性；不能仅凭文件自带一把公钥就认定发布者。

本次项目公钥见 [WATERMARK050_PUBLIC_KEY.json](WATERMARK050_PUBLIC_KEY.json)，SPKI SHA-256 指纹为
`7055a716d2763fc595eb150e4d2a1c07a965d8ca8a053d3255f93812ee7ef0f7`。这是项目发布密钥标识，
不是外部机构的作者身份认证或可信时间戳。

签名与水印使用两个独立随机秘密，按用途分离：签名私钥用于 Ed25519 发行签名；水印 master 为每项资产
派生 32 byte 的提取密钥，不把签名私钥复用为水印密钥。两项秘密共同保存在一份 `owner-key.dpapi` bundle 中，
由 Windows DPAPI `CurrentUser` 加密，并放在仓库外的 `%LOCALAPPDATA%\DesktopStatsPublisher` 下；
这不是两份物理隔离的密钥存储。这些秘密及派生密钥不进入 Git、模型包或主程序。
公开的只有公钥、签名与清单。
**公钥不能提取隐藏水印**，只能核验发行签名及清单所绑定的精确文件哈希。
所有下载者取得相同的发行资产，不嵌入下载者或设备身份。

权利人可离线核对疑似副本；如需第三方专家独立提取，应经授权提供相关的每资产密钥，
不提供 master 或签名私钥。密钥备份设计为用口令经 scrypt 与 AES-256-GCM 加密，属于另行手动操作，
当前不会弹出窗口或要求游戏中的用户执行备份。合成测试密钥的备份、恢复、坏口令和篡改拒绝已有测试，
**正式权利人密钥尚未备份，也未做正式密钥恢复演练。**
现有 Node 24 的内置加密功能只用于离线签名和验签工具，不成为 Stats 的运行依赖，也不增加新安装依赖。
本地签发使用仓库外的权利人密钥；相关软件检查与尚未完成项分列在下方，不以文字说明代替验证。

核对流程是：

1. 保存收到的疑似副本原始字节，另存工作副本，不直接修改待核文件。
2. 按公开公钥的可信来源核对指纹，再验证签名清单和文件哈希。
3. 权利人使用对应资产的秘密密钥离线提取隐藏 ID，与清单中的发行 ID、原件和生成版本比对。
4. 记录提取器版本、输入哈希、输出结果、失败情况和所做变换，保留完整工作记录。

哈希只比对内容；本地时间、Git 时间或自制签名不自动成为司法时间戳。
检出相同 ID 是来源核对线索，不能单独证明创作时间、权利归属、侵权、可获赔或法院一定采纳。
公开共享的识别信息也可能被仿造；没有检出则可能是未覆盖或发生不支持的转换，不能反推没有复制。
本轮没有在线追踪、用户 ID、联网 DRM、自动举报或向他人发送消息。

离线发布工具提供 `key-init`、`key-public`、`key-backup`、`key-restore`、`mark`、`verify`、`detect`，
标记时另存 `{name}.watermark.json` 清单。
`verify` 的公钥验签与 `detect` 的秘密密钥提取是两种不同能力。

取得上述文件和同名清单后，可在项目源码目录离线核对精确发行件：

```powershell
python tools/watermark_assets050.py verify --input north-xl-independent-protected050.glb --receipt north-xl-independent-protected050.glb.watermark.json --public-key docs/WATERMARK050_PUBLIC_KEY.json
```

`verify` 不需要秘密密钥，也不执行水印提取；当前文件与已签哈希不同会报告不匹配并返回非零状态。
`detect` 需要权利人的本地密钥，分别报告原发行清单签名、当前哈希是否相同与隐藏标记是否匹配。

## 转载与非商用要求

原创代码、原创插画和程序化示意模型继续适用 PolyForm Noncommercial 1.0.0。
商业使用须有相关权利人另行授权；许可规定的允许用途、第三方与旧版许可权利不变。

转载副本应给接收者提供许可条款或官方许可 URL，并完整保留 [NOTICE](../NOTICE) 中所有
`Required Notice:` 行，里面包含 Fairank、Desktop Stats 贡献者及原仓库地址。
随副本一起提供 LICENSE、NOTICE 和适用第三方许可文件，是直接的履行方式。
转载页面也建议说明版本、来源及修改，便于分清原作和修改版。

水印不替代公开署名，不新增原许可证以外的使用条件，不撤销 MIT、ISC、LGPL 等许可已授予的权利。
它也不赋予厂商品牌、照片、CAD 或机器生成作品原本没有的专有权。

## 实际验证记录：本地通过项与待办分列

以下是正式权利人密钥的六件本地副本验证，和另行使用合成密钥的编码器测试。
两类结果不混用；本地签发不代表 GitHub 已上传、源码已冻结或 Windows 原生验收。

| 检查 | 当前结果 |
| --- | --- |
| 六项正式本地副本 | 均已验签、精确哈希匹配、提取标记匹配；0 误码，原件未修改 |
| GLB 物理数据 | 363 Mesh／107662 三角形／393 节点；法线、索引、材质、有限动画和共享点关系保持；误差见上文 |
| GLB 分组覆盖 | 21 个源父组（18 个非空 `part_id`＋3 个明确组件回退组）均支持，对应 20 种几何身份；不是新增 21 个真实硬件 ID。两条同形 RAM 保留各自节点，共用几何身份。CPU 独立提取有 76 次重复，两条 RAM 各 8 次，均为 96 bit、0 误码；不承诺每个小 Mesh 或任意剪出片段均有完整标记 |
| 正式副本阴性检查 | 六项未标记原件及错误秘密密钥均不匹配 |
| 受测无损改动 | GLB 删除 name／extras／generator／copyright；PNG 增加 metadata；GIF 增加 comment 后，六项仍检出且 0 误码；这些是各自具体变换，不能合称所有格式均已验证“删除 metadata” |
| 修改件的签名语义 | 原发行清单签名仍有效，但修改件哈希不同；原签名不覆盖修改后的文件，不给法律结论 |
| 图像编码器独立检查 | 12 项阶段测试通过；合成密钥操作真实五项输入，PNG／GIF 的 RGB 差不超过 1、alpha 不变，两 GIF 各 62 帧的时长／loop／索引不变；不是正式签发密钥记录 |
| 几何编码器独立检查 | 10 项阶段测试通过，含部件独立提取、重排、索引重建和保留节点 TRS 的变换；不能据此承诺坐标被重写后的提取 |
| 最终 r2 相关回归 | 9 模块运行 88 项，1 项原有符号链接权限跳过，结果通过，墙钟 34.687 秒；代码 568 文件与公钥／LICENSE／NOTICE／INDEX 四项信任输入前后稳定。前一轮与本轮不相加成 176 项 |
| 运行路径边界 | 静态导入检查中，主程序对新增离线模块的直接导入为 0；Node 仅用于离线发布工具，不新增 Stats 时钟、采集或联网行为。这不是应用 CPU／RAM／GPU 实测 |
| 正式密钥备份／恢复 | 尚未做；已有备份测试只使用合成密钥 |
| 正常观看对照 | 正式 GLB 原版四个 CPU 软件视图与两张正式保护 PNG 已查看，未见可识别水印标志；真实像素差异如上，不能写成像素相同、全部 GIF 逐帧目测或六版原生验收 |
| GitHub 数据分支与完整在线索引 | 固定数据提交及入口已准备；发布结果以候选最终提交说明为准，不以本地准备替代远端确认 |

正式标记件的 SHA-256 如下；原件哈希和签名在各自同名 `.watermark.json` 清单中。

| 文件 | 字节 | 本地正式标记件 SHA-256 |
| --- | ---: | --- |
| `north-xl-independent-protected050.glb` | 8186188 | `b45805ffdcd19b699626f8dd0d916e8203b54269809f0393f28c0baceca1c096` |
| `assembly-six-depth050-protected.png` | 1621440 | `5ae6d497e488f2ca8a038dcfdd77e627ac7b3fc37a5aa98bf4923755801f2ad9` |
| `gpu-six-depth050-protected.png` | 790857 | `bd9d6e2f9d438f2cebb5ed1a8338c639cd3c62d0cec1b8d8b2df9fe7fc901aec` |
| `assembly-depth-review050-protected.png` | 343989 | `9f08df9c2af0f14682c5a3c59f5d9ddf34aed2687c889cd4e48d239faddc4900` |
| `gpu-insertion050-protected.gif` | 2908594 | `338345625499b5e4ee8f64773160d9b7d6b927c524d157b823b2122a29cb27c1` |
| `gpu-insertion-six050-protected.gif` | 9168985 | `0379168569e69ef9920f43ee6dcb5e226a604f8c432851269ec8a0d5870d10f4` |

**已知失败边界：** 不承诺跨 JPEG、有损重编码、GIF 调色板重新量化、几何重建／量化、
将毫米换成 f32 米后重写坐标、烘焙旋转或按 0.01 精度重新导出仍可提取。
它们已有相应阴性或失败样本，不能把低位标记说成抗任意处理。SVG、JSON 扩展及程序实时全库仍未加入本轮标记。

## 官方依据与法律边界

PolyForm 的 Notices 条款要求保留条款或许可 URL，以及提供的 Required Notice 行；
本文没有改写该许可或另加使用限制。[PolyForm Noncommercial 1.0.0 官方原文](https://polyformproject.org/licenses/noncommercial/1.0.0)

WIPO 将版权声明、时间信息与隐形水印列为不同的来源保护工具，并强调受保护的是原创表达。
本文将水印作为来源与取证辅助，不把嵌入或签名当作版权登记或诉讼保证。[WIPO：版权保护与数字作品](https://www.wipo.int/en/web/copyright/protection)

EUIPO 区分可见／不可见、脆弱／鲁棒水印，并说明需要检测流程。
这里的几何与图像方案只能声称实际测试过的提取能力；不作特定司法辖区的采纳或裁判结论。
[EUIPO：Digital Watermarks](https://euipo.europa.eu/anti-counterfeiting-and-anti-piracy-technology-guide/technologies-digital-media/digital-watermarks)
