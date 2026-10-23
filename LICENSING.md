# 使用许可 / Licensing

从 **0.19.0-preview.1** 开始，Desktop Stats 的原创应用代码按
[PolyForm Noncommercial 1.0.0](LICENSE) 提供。免费个人使用、学习、试验和
非商业修改、分享须遵守该许可。未经权利人另行书面授权，不授予商业用途许可。
完整条款以英文 LICENSE 为准；NOTICE 中的 Required Notice 须随副本保留。

不能把本应用代码或修改版包装出售、集成到商业产品，或用于其他不属于许可允许
目的的商业活动。教育、公益、公共研究和政府等机构的允许用途按许可证原文确定。
因此这是**源码可见的非商业项目**，不声称符合 OSI 的开源定义。

公开 GitHub 仓库允许浏览、fork 和下载。许可证约束使用权，不能从技术上阻止
下载、复制或违规使用，也不保证侵权行为不会发生。需要商业授权时，请联系仓库
所有者 Fairank；仓库公开、下载免费或提交 issue 均不构成商业授权。

## Scope and exceptions

The original application code and original contributions in this version are
offered under the unmodified PolyForm Noncommercial License 1.0.0 in LICENSE.
This includes the original Python/QML application, except
for the third-party material identified below. The license is a restriction on
permitted purposes, not download protection or an OSI-approved open-source license.

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
