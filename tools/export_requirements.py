"""Check/render the complete user requirement ledger inside README, offline."""
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BEGIN='<!-- REQUIREMENTS:BEGIN -->'
END='<!-- REQUIREMENTS:END -->'


def render(root=ROOT):
    data=json.loads((root/'docs/REQUIREMENTS.json').read_text(encoding='utf8'))
    items=data['items'];ids=[r['id'] for r in items]
    if len(items)!=29 or len(ids)!=len(set(ids)):raise ValueError('Full requirement ledger must retain29 unique groups')
    rows=[BEGIN,'## 全文需求逐项核对与未完成清单','',
        '核对日期：2026-11-08。重复要求已合并为 29 项，核心约束和后续补充全部保留。',
        '**当前没有达到“全部做完”的交付条件。** 源码存在、离屏测试通过、旧版实测与当前新版原生验收分别记录；不能用候选包生成或旧版温度读数给新版打勾。',
        '用户要求逐项核对、报告问题与缺项；未完成项继续保留，不因本轮上传或文档更新而关闭。',
        '游戏期间只做代码、后台和离屏检查，不安装、不重启 Stats，不弹出系统授权或可见测试窗。需要这些操作的验收等待之后明确允许的桌面时段。','',
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
    rows+=['','**硬件覆盖与质量未完成项：** 全品牌全系列、完整旧代非公显卡、全部机箱／主板／散热器仍未覆盖；',
        '部分显卡叶型／独立 RPM、非 CPU 运行时扩展包、磁盘与网络 Top5、逐品牌零售冷头／泵／水箱／接头目录仍缺。',
        '现有冷排、机箱与硬件都保留未核孔位、内部 PCB、细小封装或安装间隙标记。不得把“有这个型号”写成“所有细节已核”。',
        '**原生验收未完成项：** 新版重启后的 CPU 温度授权恢复、顶部栏／设置／详情真实磨砂、屏幕二定位、游戏隐藏与恢复、关闭资源释放及整款程序 CPU／RAM／GPU 占用。',
        '具体源码、测试路径和逐项缺口以 [结构化需求清单](docs/REQUIREMENTS.json) 为准；逐产品进度见 [覆盖清单](docs/ASSEMBLY_CATALOG.json)。',
        END]
    return '\n'.join(rows),dict(Counter(r['status'] for r in items))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    path=ROOT/'README.md';text=path.read_text(encoding='utf8');section,counts=render()
    if text.count(BEGIN)!=1 or text.count(END)!=1:raise SystemExit('README requirement section markers are missing or duplicated')
    start=text.index(BEGIN);end=text.index(END)+len(END);updated=text[:start]+section+text[end:]
    if args.check:
        if text!=updated:raise SystemExit('Requirement ledger is stale; run tools/export_requirements.py')
    else:path.write_bytes(updated.replace('\n','\r\n').encode('utf8'))
    print(json.dumps(dict(checked=args.check,requirements=29,statuses=counts),ensure_ascii=False))


if __name__=='__main__':main()
