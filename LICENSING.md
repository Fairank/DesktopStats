# 使用许可 / Licensing

从 **0.19.0-preview.1** 开始，Desktop Stats 的原创应用代码按
[PolyForm Noncommercial 1.0.0](LICENSE) 提供。免费个人使用、学习、试验和
非商业修改、分享须遵守该许可。未经权利人另行书面授权，不授予商业用途许可。
完整条款以英文 LICENSE 为准；NOTICE 中的 Required Notice 须随副本保留。

不能把本应用代码或修改版包装出售、集成到商业产品，或用于其他不属于许可允许
目的的商业活动。教育、公益、公共研究和政府等机构的允许用途按许可证原文确定。
因此这是**源码可见的非商业项目**，不声称符合 OSI 的开源定义。

上述限制同时适用于本版本新增的原创硬件插画、原创风扇图形及对应绘制代码：
未经权利人另行书面授权，**禁止商业使用、商业集成、出售或用于商用盈利**。
切换插画风格不会改变许可。修改、重新配色或重新打包也须遵守许可证；
分享本项目副本或许可允许的修改版时，须保留 LICENSE、NOTICE 及相关来源声明。

原创三维机箱与硬件示意网格、部件外形转换及其渲染代码也属于上述非商业范围。
这些模型由本项目代码生成，不包含厂商 CAD、下载网格或产品照片；目录中的官方
链接只用于核对规格与外观事实，不授予厂商商标或素材使用权。

这一范围仅涉及可受版权保护的原创表达。Lucide/Feather 通用符号及其衍生片段、
既有年糕图标和第三方组件继续适用下文各自的许可，不能用本项目的非商业限制
撤销它们已授予的权利。硬件品牌、产品名称及商标属于各自权利人；这些简化硬件
插画不提供商标授权，不表示硬件厂商参与、认可或背书。参考来源用于核对外观和
规格，厂商产品照片不作为本项目原创插画重新授权或随源码包发布。

公开 GitHub 仓库允许浏览、fork 和下载。许可证约束使用权，不能从技术上阻止
下载、复制或违规使用，也不保证侵权行为不会发生。需要商业授权时，请联系仓库
所有者 Fairank；仓库公开、下载免费或提交 issue 均不构成商业授权。

## Scope and exceptions

The original application code and original contributions in this version are
offered under the unmodified PolyForm Noncommercial License 1.0.0 in LICENSE.
This includes the original Python/QML application, except
for the third-party material identified below. The license is a restriction on
permitted purposes, not download protection or an OSI-approved open-source license.

Original model-specific hardware illustrations, fan drawings and their original
rendering code are included in this scope. Commercial use, commercial integration,
sale and other use for commercial gain require separate written permission.
This includes the original schematic assembly meshes and their generation and
rendering code. They are project-authored illustrations, not manufacturer CAD
files or a license to the referenced manufacturers' product assets.
Third-party or previously licensed symbols and artwork retain their existing
permissions; generic fragments derived from Lucide/Feather are not relicensed.
Hardware product names and trademarks remain with their respective owners.

- **Third-party software:** Qt/PySide/Shiboken, Python, psutil, Lucide/Feather,
  the identified Three r150 noise/lightning algorithm portions,
  the sensor libraries, their embedded resources and other dependencies retain
  their respective licenses. LICENSE does not relicense them, limit their
  independent commercial use or replace their notices. See
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), `assets/lucide/LICENSE`,
  `licenses/`, and `third_party/librehardwaremonitor/0.9.6/NOTICE.md`.
- **Collector wrapper:** `collector/Program.cs` retains its explicit MIT SPDX
  notice and prior MIT permissions; its unchanged build inputs keep their
  existing rights. This narrow exception does not license the new main
  application under MIT.
- **Niangao artwork:** the existing FieldDock identity and previously distributed
  artwork retain the applicable upstream/prior MIT permissions. Adding a status
  curve does not revoke rights in the original face. Provenance is documented in
  [assets/ICON-NOTES.md](assets/ICON-NOTES.md). No exclusive-rights guarantee is made
  for AI-assisted artwork; the application license does not confer trademark rights.
- **LGPL rights:** compatible Qt/PySide/Shiboken libraries remain dynamically
  replaceable. Reverse engineering for debugging modifications to LGPL libraries,
  installing and running a relinked/modified library combination, and the rights
  granted for those libraries are not restricted by the application's license.
  Rebuild instructions and upstream source locations are in the user guide and
  packaged `THIRD_PARTY_LICENSES.txt`.
  The optional 3D assembly view uses Qt Base's QtOpenGL/QtOpenGLWidgets through
  the existing PySide6-Essentials dependency, under the LGPL v3 option. It does
  not add Qt Quick 3D, Qt 3D or PySide6-Addons. The application restrictions do
  not limit the independent permissions granted for those Qt Base libraries.
- **Earlier versions:** copies through 0.18.0-preview.2 were supplied under MIT.
  Their existing permissions are not revoked by deleting an archive, removing
  a release or changing the license of a later version. The original notice is
  retained in [licenses/legacy/DesktopStats-through-0.18-MIT.txt](licenses/legacy/DesktopStats-through-0.18-MIT.txt)
  as a historical notice, not as an alternative license for new original changes.

Only this new snapshot is prepared for publication. Old application snapshots,
installers, personal profiles, local QA records and development logs are not
part of the public source export. A historical license notice is not an old
application release.

## Contributions

Contributions to original application files are offered under the same PolyForm
Noncommercial license. Keep upstream notices and identify any third-party code
you add. Do not submit code that you lack the right to license on these terms.
No contributor copyright assignment or general relicensing permission is implied.
