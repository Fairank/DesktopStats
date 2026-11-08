"""Check/render the complete user requirement ledger inside README, offline."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BEGIN='<!-- REQUIREMENTS:BEGIN -->'
END='<!-- REQUIREMENTS:END -->'
GROUP_IDS=('topbar_history','screen_two','game_hide','crash_recovery','cpu_temperature_restart',
    'glass_three_surfaces','low_overhead','top_five_processes','style_versions','same_model_all_styles',
    'fan_motion','all_gpu_brands_series','cpu_memory_variants','hardware_auto_match','model_widget_layout',
    'model_widget_animation','desktop_3d_inspection','case_library','motherboard_detail',
    'cooler_fan_brand_library','all_other_parts','free_mixed_assembly','liquid_radiator_fan_split',
    'lighting','github_optional_packs','copyright_noncommercial','github_publish_merge_install',
    'pcbs_benchmark','readme_full_requirements_ledger')
SHOWCASE_IDS=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def validate(data,root):
    """Check the ledger against small offline manifests, never live catalogs."""
    if tuple(row['id'] for row in data['items'])!=GROUP_IDS:
        raise ValueError('Full requirement ledger must retain the29 original ordered group IDs')
    if (data['all_requirements_complete'] is not False or data.get('native_045_accepted') is not False or
            data.get('native_046_accepted') is not False):
        raise ValueError('This0.46 candidate has outstanding requirements and no installed native acceptance')
    policy=data['style_policy']
    if (tuple(row['id'] for row in policy['showcase'])!=SHOWCASE_IDS or
            tuple(row['number'] for row in policy['showcase'])!=tuple(range(1,7)) or
            policy['saved_options']!=13 or policy['original_has_face'] is not False or
            policy['new_styles_enabled'] is not False):
        raise ValueError('Fixed six showcase IDs,13 retained options and faceless original must remain explicit')
    coverage=data['coverage_045'];cooling=coverage['optional_cooling_by_kind']
    if (sum(cooling.values())!=coverage['optional_cooling_products'] or
            coverage['optional_cpu_products']+coverage['optional_cooling_products']!=coverage['optional_products'] or
            coverage['base_products']+coverage['optional_products']!=coverage['total_products'] or
            coverage['installed_by_default'] is not False):
        raise ValueError('Product counts must exclude the reference combination and overlapping pack groupings')
    packs=json.loads((root/'docs/COOLING_PACKS_INDEX.json').read_text(encoding='utf8'))
    groups=Counter(row['group'] for row in packs['packs'])
    if (packs['by_kind']!=cooling or packs['unique_products']!=coverage['optional_cooling_products'] or
            len(packs['packs'])!=coverage['cooling_package_artifacts'] or
            groups['collection']!=coverage['cooling_collection_packages'] or
            groups['brand']!=coverage['cooling_brand_category_packages']):
        raise ValueError('Cooling package manifest and requirement count scopes differ')
    cpu=json.loads((root/'docs/HARDWARE_PACKS_INDEX.json').read_text(encoding='utf8'))
    if cpu['optional_cpu_products']!=coverage['optional_cpu_products']:
        raise ValueError('CPU package count differs from the requirement scope')
    current=data['coverage_046'];loops=json.loads((root/'docs/LOOP_PACKS_INDEX.json').read_text(encoding='utf8'))
    loop_counts=current['optional_loop_by_kind'];loop_groups=Counter(row['group'] for row in loops['packs'])
    if (sum(loop_counts.values())!=current['optional_loop_products'] or loops['by_kind']!=loop_counts or
            loops['unique_products']!=current['optional_loop_products'] or loops['installed_by_default'] is not False or
            len(loops['packs'])!=current['loop_package_artifacts'] or
            loop_groups['collection']!=current['loop_collection_packages'] or
            loop_groups['category']!=current['loop_category_packages'] or loop_groups['brand']!=current['loop_brand_packages']):
        raise ValueError('Loop package manifest and current requirement counts differ')
    identities=set()
    for item in loops['packs']:
        path=(root/item['file']).resolve()
        if not path.is_relative_to((root/'model-packs/v046').resolve()) or path.suffix!='.dspack':
            raise ValueError('Loop package path is not in its data-only release directory')
        raw=path.read_bytes()
        if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('Loop package data does not match its actual hash/size index')
        identities.update(item['model_ids'])
    if (len(identities)!=current['optional_loop_products'] or
            current['optional_cpu_products']+current['optional_cooling_products']+current['optional_loop_products']!=current['optional_products'] or
            current['base_products']+current['optional_products']!=current['total_products'] or current['installed_by_default'] is not False):
        raise ValueError('Current counts must de-duplicate overlapping package groups and exclude the reference assembly')
    inventory=json.loads((root/'docs/ASSEMBLY_CATALOG.json').read_text(encoding='utf8'))
    if (inventory['optional_summary']['loop_products']!=current['optional_loop_products'] or
            inventory['optional_summary']['total_named_products']!=current['total_products']):
        raise ValueError('Current requirement scope differs from the assembly product inventory')
    measured=data['scoped_performance_046']
    performance=json.loads((root/measured['source']).read_text(encoding='utf8'))
    for key in ('measurement_type','median_picker_cpu_reduction_percent','retained_index_python_bytes','retained_selected_python_bytes'):
        if performance[key]!=measured[key]:raise ValueError('Scoped performance ledger differs from its actual report')
    if (performance['native_application_acceptance'] is not False or performance['installed_app_changed'] is not False or
            measured['whole_application_memory_measured'] is not False):
        raise ValueError('An isolated picker benchmark cannot become native or whole-application acceptance')
    sizes=json.loads((root/'docs/SIZE_COVERAGE.json').read_text(encoding='utf8'))
    if any(sizes[key]!=value for key,value in data['size_coverage_045'].items()):
        raise ValueError('Size/form-factor matrix differs from its source manifest')
    if sum(sizes['board_form_counts'].values())!=coverage['motherboard_products']:
        raise ValueError('Motherboard form-factor matrix must match the catalog count')
    pcbs=data['pcbs_comparison_scope']
    if (pcbs['strict_name_matches']+pcbs['unmatched_or_pending']!=pcbs['entries'] or
            pcbs['complete_opponent_catalog'] is not False or pcbs['confirmed_missing_skus'] is not False):
        raise ValueError('Partial PCBS name comparison cannot become a complete market gap')
    comparison=json.loads((root/'docs/PCBS_COMPARISON.json').read_text(encoding='utf8'))
    for source,key in (('reference_entries','entries'),('grouped_variants','grouped_variant_entries'),
                       ('name_exact_matches','strict_name_matches'),('unmatched_or_review','unmatched_or_pending')):
        if comparison[source]!=pcbs[key]:raise ValueError('PCBS ledger differs from its scoped comparison record')
    gpu=json.loads((root/'docs/GPU_RESEARCH043.json').read_text(encoding='utf8'))
    if sum(row['status']!='confirmed_this_round' for row in gpu['rows'])!=data['open_detail_counts_046']['gpu_leaf_profiles_pending']:
        raise ValueError('GPU leaf gap count differs from the existing source audit')


def render(root=ROOT):
    data=json.loads((root/'docs/REQUIREMENTS.json').read_text(encoding='utf8'))
    validate(data,root);items=data['items'];coverage=data['coverage_046'];style=data['style_policy']
    rows=[BEGIN,'## 全文需求逐项核对与未完成清单','',
        f"核对日期：{data['reviewed']}；当前 {data['target_version']} 源码候选。重复要求合并为 29 项，原有组 ID、核心约束和后续补充全部保留。",
        '**当前没有达到“全部做完”的交付条件。** 源码存在、离屏测试通过、旧版实测与当前新版原生验收分别记录；不能用候选包生成或旧版温度读数给新版打勾。',
        '用户要求逐项核对、报告问题与缺项；未完成项继续保留，不因本轮上传或文档更新而关闭。',
        '0.46 尚未安装。游戏期间只做代码、后台和离屏检查，不重启 Stats，不弹出系统授权或可见测试窗；原生验收等待后续允许的桌面时段。','',
        '**外观顺序约束：** '+ '、'.join(f"{row['number']} {row['label']}（`{row['id']}`）" for row in style['showcase'])+'。原版无笑脸；13 个旧保存选项继续保留。**先完成现有类别、型号与六版一致性缺口，不新增外观。**','',
        f"**0.46 统计口径：** 本体 {coverage['base_products']} 个具名产品＋{coverage['reference_combinations']} 套参考组合；可选 {coverage['optional_products']} 个产品＝{coverage['optional_cpu_products']} CPU＋{coverage['optional_cooling_products']} 冷却（{coverage['optional_cooling_by_kind']['radiator']} 冷排／{coverage['optional_cooling_by_kind']['fan']} 风扇／{coverage['optional_cooling_by_kind']['cooler']} 散热器）＋{coverage['optional_loop_products']} 独立水路，合计 **{coverage['total_products']} 个具名产品**。不按风格或下载分组重复计数；共壳 SKU 不等于独立高精度外壳，参考组合不计为产品。",
        f"冷却包共 {coverage['cooling_package_artifacts']} 个候选数据文件：{coverage['cooling_collection_packages']} 类集合包或 {coverage['cooling_brand_category_packages']} 个按品牌、类别划分的小包，分组可能重叠，**同一型号不可重复安装**。未装目录默认不加载，不预载全库网格，不新增后台查询；其它品类尚不能全部按包选装。",'',
        f"独立水路可选包收录 {coverage['optional_loop_by_kind']['cpu_block']} 冷头／{coverage['optional_loop_by_kind']['pump']} 泵／{coverage['optional_loop_by_kind']['reservoir']} 纯水箱／{coverage['optional_loop_by_kind']['pump_reservoir']} 泵箱组合／{coverage['optional_loop_by_kind']['fitting']} 接头／{coverage['optional_loop_by_kind']['tubing']} 管材。{coverage['loop_package_artifacts']} 个集合、类别和品牌文件为重叠替代分组，以 [实际包索引](docs/LOOP_PACKS_INDEX.json) 的字节数与 SHA256 为准，不重复计产品。端口姿态、网格与连接路线是原创参考；未知螺纹、插槽或接合保留待核，未通过原生或实物装配验收。",'',
        '| 编号 | 原始重点／验收要求 | 当前状态 | 实现与证据 | 问题、缺项或下一步 |',
        '| --- | --- | --- | --- | --- |']
    clean=lambda v:str(v).replace('|','／').replace('\n',' ')
    for n,item in enumerate(items,1):
        paths=item['source_files']+item['test_files']
        for path in paths:
            p=Path(path)
            if p.is_absolute() or '..' in p.parts or not (root/p).is_file():raise ValueError('Invalid requirement evidence: '+path)
        evidence=' / '.join(f'[{Path(p).name}]({p})' for p in item['source_files'][:2])
        cells=(str(n),item['requirement'],item['status_label'],item['implementation']+'<br>'+evidence,'<br>'.join(item['gaps']))
        rows.append('| '+' | '.join(map(clean,cells))+' |')
    sizes=data['size_coverage_045']
    rows+=['','**尺寸与板型矩阵（已收录记录，不是全市场覆盖或实物兼容保证）：**','',
        '| 名义散热等级 | 独立冷排记录（本体＋可选） | AIO 记录（本体＋可选） |',
        '| --- | ---: | ---: |']
    for nominal in ('120','140','240','280','360','420','480','560'):
        rows.append(f"| {nominal} | {sizes['radiator_nominal_counts'].get(nominal,0)} | {sizes['aio_nominal_counts'].get(nominal,'未收录')} |")
    rows+=['','| 主板板型 | 具名记录 |','| --- | ---: |']
    for key,label in (('itx','ITX'),('matx','mATX'),('atx','ATX'),('eatx','E-ATX')):
        rows.append(f"| {label} | {sizes['board_form_counts'][key]} |")
    pcbs=data['pcbs_comparison_scope'];pending=data['open_detail_counts_046']
    rows+=['','120／140 等名义等级不等于实际长度、孔距或安装间隙；每个品牌／系列的尺寸空档、原始来源和未核项见 [尺寸覆盖表](docs/SIZE_COVERAGE.json)。',
        f"**PCBS 对照范围：** 当前只比较局部官方公告的 {pcbs['entries']} 个列表出现条目（含 {pcbs['grouped_variant_entries']} 个合并变体），{pcbs['strict_name_matches']} 项严格名称匹配、{pcbs['unmatched_or_pending']} 项未匹配／待核。不是完整游戏数据库，也不是确认缺少 {pcbs['unmatched_or_pending']} 个 SKU；不据此算完成百分比。见 [PCBS 差距与来源](docs/PCBS_GAP_ANALYSIS.md)。",'',
        f"**硬件覆盖与质量未完成项：** 原账仍有 {pending['gpu_leaf_profiles_pending']} 个 GPU 叶型待核，本轮没有新增完整叶型核实；新增风扇中 {pending['new_fan_leaf_evidence_pending']} 款叶片证据未完整；{pending['motherboard_finish_pending']} 款主板 finish 仍待官方来源。两款板载小风扇仅有 MSI 无叶片风扇槽与 ASUS 网罩参考，另 {pending['unplaced_onboard_heatsink_fans']} 款内部位置未知；两款叶片、方向和 RPM 都未知。",
        '全品牌全系列、全部旧代非公显卡、机箱／主板／散热器仍未覆盖；新增63条没有补齐全部水路产品。零售 GPU 冷头的 exact PCB 匹配、更多接头／管材规格、线材与外围设备类别仍缺。',
        '参考组合不等于已有独立零售 SKU；水路部件需要拆开的身份、尺寸、端口与验收字段见 [独立水冷缺口](docs/LIQUID_COMPONENT_GAPS.md)。',
        '机箱／GPU／内存／主板／电源／存储等运行时可选包，以及网络逐进程 Top5、真实单盘进程归因仍未完成；进程总读写 I/O 已实现，不能冒称当前物理盘占用。',
        '现有冷排、机箱与硬件都保留未核孔位、内部 PCB、细小封装或安装间隙标记。不得把“有这个型号”写成“所有细节已核”。',
        '**原生验收未完成项：** 0.46 重启后的 CPU 温度授权恢复、顶部栏／设置／详情真实磨砂、屏幕二定位、游戏隐藏与恢复、关闭资源释放及整款程序 CPU／RAM／GPU 占用。0.43／0.44／0.45 历史图层、模块和离屏测量保留原范围，不能替代本轮实测。',
        '具体源码、测试路径和逐项缺口以 [结构化需求清单](docs/REQUIREMENTS.json) 为准；逐产品进度见 [覆盖清单](docs/ASSEMBLY_CATALOG.json)。',
        END]
    return '\n'.join(rows),dict(Counter(r['status'] for r in items))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    path=ROOT/'README.md';section,counts=render()
    # Other release prose may be edited independently. Read it only after all
    # manifest validation, immediately before replacing this one marked region.
    text=path.read_text(encoding='utf8')
    if text.count(BEGIN)!=1 or text.count(END)!=1:raise SystemExit('README requirement section markers are missing or duplicated')
    start=text.index(BEGIN);end=text.index(END)+len(END);updated=text[:start]+section+text[end:]
    if args.check:
        if text!=updated:raise SystemExit('Requirement ledger is stale; run tools/export_requirements.py')
    else:path.write_text(updated,encoding='utf8',newline='\n')
    print(json.dumps(dict(checked=args.check,requirements=29,statuses=counts),ensure_ascii=False))


if __name__=='__main__':main()
