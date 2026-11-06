"""Export a self-contained, offline icon review gallery from the actual QML code.

No sampler, desktop window, browser, network, driver query or installed profile.
Only the selected cards/style/theme are attached to the gallery's DOM.
"""

import argparse
import base64
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>硬件造型图鉴</title><style>
:root{font-family:"Segoe UI","Microsoft YaHei UI",sans-serif;color:#293544;background:var(--page);--page:#edf1f5;--card:#fff;--line:#dce3eb;--muted:#65758a;--field:#f5f7fa}
:root[data-theme=dark]{color:#e4ebf4;--page:#1c222b;--card:#252e3a;--line:#3c4858;--muted:#aab7c9;--field:#303c4a;color-scheme:dark}
*{box-sizing:border-box}body{max-width:1560px;margin:auto;padding:36px 28px 60px}h1{font-size:28px;letter-spacing:-.5px;margin:0 0 9px}header p{margin:0;color:var(--muted);line-height:1.65}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;position:sticky;top:0;background:var(--page);padding:22px 0 18px;z-index:2}select,input{font:inherit;font-size:14px;min-height:40px;border:1px solid var(--line);border-radius:9px;padding:8px 11px;color:inherit;background:var(--card)}input{flex:1;min-width:210px}select:focus,input:focus{outline:2px solid #6b91c0;outline-offset:2px}
#count{font-size:13px;color:var(--muted);margin:0 0 16px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(265px,1fr));gap:16px}.card{border:1px solid var(--line);border-radius:15px;background:var(--card);padding:19px 19px 16px;min-width:0}.brand{font-size:11px;letter-spacing:.7px;color:var(--muted);margin-bottom:7px}.card h2{font-size:17px;margin:0 0 5px}.model{font-size:11px;line-height:1.5;color:var(--muted);min-height:34px}.art{height:129px;display:flex;align-items:center;justify-content:center}.art img{width:128px;height:128px}.actual{display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid var(--line);padding-top:12px;margin-top:2px}.small{display:flex;align-items:center;gap:8px;background:var(--field);border-radius:7px;padding:6px 10px;font-size:12px}.small img{width:18px;height:18px}.facts{font-size:11px;text-align:right;color:var(--muted);line-height:1.55}.features{font-size:12px;color:var(--muted);line-height:1.65;margin:12px 0;min-height:20px}.link{font-size:12px;color:inherit;text-decoration-color:var(--muted);text-underline-offset:3px}.badge{font-size:10px;border:1px solid var(--line);border-radius:5px;padding:2px 4px;margin-left:5px;color:var(--muted)}footer{margin-top:24px;line-height:1.7;color:var(--muted);font-size:12px}button{font:inherit;cursor:pointer}#empty{padding:30px;color:var(--muted)}
</style><body><header><h1>硬件造型图鉴</h1><p id="summary"></p><p>按代际、品牌和系列比较外观。入门、主流、旗舰指板卡产品线定位，不代表芯片性能排名。每张卡都保留 18px 顶部栏实际大小。</p></header>
<div class="toolbar"><select id="kind" aria-label="硬件类型"><option value="all">全部硬件</option><option value="gpu">显卡</option><option value="memory">内存条</option></select><select id="brand" aria-label="品牌"><option value="all">全部品牌</option></select><select id="vendor" aria-label="芯片厂商"><option value="all">全部芯片厂商</option><option value="nvidia">NVIDIA 显卡</option><option value="amd">AMD 显卡</option><option value="intel">Intel 显卡</option></select><select id="era" aria-label="代际"><option value="all">全部代际</option></select><select id="tier" aria-label="产品线"><option value="all">全部产品线</option><option value="entry">入门非公</option><option value="mainstream">主流非公</option><option value="flagship">旗舰非公</option><option value="creator">创作系列</option><option value="reference">公版 / 参考设计</option></select><select id="style" aria-label="图标版本"><option value="solid">精简实物</option><option value="miniature">微型实物</option><option value="soft">柔和双色</option><option value="outline">结构线稿 · 旧版</option><option value="classic">经典通用</option></select><select id="theme" aria-label="背景"><option value="light">浅色背景</option><option value="dark">深色背景</option></select><input id="search" type="search" placeholder="搜索系列或代表型号" aria-label="搜索系列或代表型号"></div>
<p id="count" role="status"></p><main id="grid" class="grid"></main><p id="empty" hidden>没有匹配的系列。</p>
<footer>图形是依据代表产品特征绘制的简化插画，不是产品照片或厂商标志。具体型号、不同代际及特别版分别核实；未确认的风扇不会被猜成零、双扇或三扇。经典通用和旧线稿保留原先表现方式。页面与图标均已内嵌，筛选和切换无需联网；“官方型号资料”由你点击后打开。</footer>
<script>const DATA=__DATA__;
const controls=Object.fromEntries(['kind','brand','vendor','era','tier','style','theme','search'].map(id=>[id,document.getElementById(id)]));
const {kind,brand,vendor,era,tier,style,theme,search}=controls,grid=document.querySelector('#grid');
document.querySelector('#summary').textContent=DATA.brands.length+' 个品牌 · '+DATA.cards.length+' 项代表设计 · '+DATA.cards.filter(row=>row.kind==='gpu').length+' 项显卡 / '+DATA.cards.filter(row=>row.kind==='memory').length+' 项内存';
for(const row of DATA.brands){const option=document.createElement('option');option.value=row.id;option.textContent=row.label+' · '+row.count;brand.append(option)}
for(const row of DATA.eras){const option=document.createElement('option');option.value=row.id;option.textContent=row.label;era.append(option)}
function text(tag,value,cls){const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e}
function render(){document.documentElement.dataset.theme=theme.value;const query=search.value.trim().toLocaleLowerCase();const rows=DATA.cards.filter(row=>(kind.value==='all'||row.kind===kind.value)&&(brand.value==='all'||row.brand===brand.value)&&(vendor.value==='all'||row.vendor===vendor.value)&&(era.value==='all'||row.era===era.value)&&(tier.value==='all'||row.tier===tier.value)&&(!query||(row.label+' '+row.model+' '+row.brandLabel).toLocaleLowerCase().includes(query)));const fragment=document.createDocumentFragment();
for(const row of rows){const card=document.createElement('article');card.className='card';card.append(text('div',row.brandLabel,'brand'));const title=text('h2',row.label);if(row.legacy)title.append(text('span','历史型号','badge'));card.append(title,text('div',row.model,'model'));const uri=row.art[style.value][theme.value];const art=document.createElement('div');art.className='art';const large=new Image(128,128);large.src=uri;large.alt=row.label+' 外观';large.loading='lazy';art.append(large);card.append(art);const actual=document.createElement('div');actual.className='actual';const small=document.createElement('div');small.className='small';const icon=new Image(18,18);icon.src=uri;icon.alt='';icon.loading='lazy';small.append(icon,text('span','36%'));actual.append(small,text('div',row.fans,'facts'));card.append(actual,text('div',style.value==='classic'?'通用符号，不表达具体风扇布局':row.features.join(' · '),'features'));const link=text('a','官方型号资料','link');link.href=row.source;link.target='_blank';link.rel='noopener noreferrer';card.append(link);fragment.append(card)}
grid.replaceChildren(fragment);document.querySelector('#count').textContent='显示 '+rows.length+' / '+DATA.cards.length+' 个系列';document.querySelector('#empty').hidden=rows.length>0}
for(const control of Object.values(controls))control.addEventListener(control===search?'input':'change',render);render();
</script></body></html>'''


def export_gallery(output):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext

    from hardware_appearance import BRANDS, CATALOG, appearance_for
    from hardware_series import SERIES_CATALOG
    from memory_appearance import BRANDS as MEMORY_BRANDS, CATALOG as MEMORY_MODELS
    from memory_appearance import SERIES_CATALOG as MEMORY_SERIES, appearance_for_memory

    app = QCoreApplication.instance() or QCoreApplication([])
    engine, warnings = QQmlEngine(), []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    component = QQmlComponent(engine)
    component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/IconData.js" as Icons
QtObject { function svgFor(value,ink) {
    if(value.icon_set === "classic") return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+ink+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+Icons.fragment(value.kind==='memory'?'memory':'gpu')+'</svg>'
    return decodeURIComponent(Shapes.source(Shapes.key(value,ink)).split(',')[1])
} }''', QUrl.fromLocalFile(str(ROOT / "tools/hardware-gallery.qml")))
    renderer = component.create()
    if renderer is None:
        raise RuntimeError([error.toString() for error in component.errors()])
    representatives = {}
    for row in CATALOG:
        value = appearance_for(row[1], row[-1][0])
        if row[1] == "gpu" and value["series_id"]:
            representatives.setdefault(value["series_id"], value)
    for row in MEMORY_MODELS:
        value = appearance_for_memory(model=row["aliases"][0])
        representatives.setdefault(value["series_id"], value)
    cards, counts = [], {}
    all_brands = dict(BRANDS, **MEMORY_BRANDS)
    for series in (*SERIES_CATALOG, *MEMORY_SERIES):
        value = representatives[series["id"]]
        brand = value["board_vendor"]
        counts[brand] = counts.get(brand, 0) + 1
        total, visible = value["fan_count"], value["visible_fan_count"]
        fans = f"总数 {total} 扇" if type(total) is int else "风扇总数未确认"
        if type(visible) is int and visible != total:
            fans += f" · 正面 {visible} 扇"
        if value["kind"] == "memory":
            fans = {"dimm": "DIMM 长条", "sodimm": "SO-DIMM 短条"}.get(value["style"], "形态未确认")
        elif total == 0:
            fans = "被动散热 · 无风扇"
        art = {}
        for style in ("classic", "outline", "solid", "miniature", "soft"):
            art[style] = {}
            for theme, ink in (("light", "#303a48"), ("dark", "#e8edf4")):
                expression = QQmlExpression(qmlContext(renderer), renderer,
                    "svgFor(" + json.dumps(dict(value, icon_set=style)) + "," + json.dumps(ink) + ")")
                svg = expression.evaluate()
                if isinstance(svg, tuple):
                    svg = svg[0]
                if expression.hasError() or not isinstance(svg, str) or not svg.startswith("<svg"):
                    raise RuntimeError(expression.error().toString())
                art[style][theme] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        cards.append(dict(brand=brand, brandLabel=all_brands[brand][0], label=series["label"],
                          model=value["label"], fans=fans, features=value["features"],
                          source=value["source_url"], legacy=bool(series.get("legacy")), art=art,
                          kind=value["kind"], vendor=value["vendor"] if value["kind"]=="gpu" else "memory",
                          era=value.get("era", "memory"), tier=value.get("tier", "unspecified")))
    if warnings:
        raise RuntimeError(warnings)
    era_labels = dict(memory="内存条", gtx10="GTX / GT 10 系列", gtx900="GTX 900", gtx700="GTX 700",
                      gtx600="GTX 600", gtx500="GTX 500", gtx400="GTX 400", gtx200="GTX 200", pre_gtx="GeForce 8 / FX",
                      radeon_hd="Radeon HD", r9="Radeon R9", rx500="Radeon RX 500", rx400="Radeon RX 400",
                      vega="Radeon Vega", rdna1="Radeon RX 5000", rdna2="Radeon RX 6000", rdna3="Radeon RX 7000", rdna4="Radeon RX 9000",
                      arc_a="Intel Arc A", arc_b="Intel Arc B", unspecified="代际未分组")
    era_labels.update({"rtx"+digit+"0": "GeForce RTX "+digit+"0 系列" for digit in "2345"})
    era_labels.update({"rx"+digit+"000": "Radeon RX "+digit+"000" for digit in "56789"})
    data = dict(cards=cards, brands=[dict(id=brand, label=all_brands[brand][0], count=count)
                                    for brand, count in sorted(counts.items())],
                eras=[dict(id=era, label=era_labels.get(era, era.upper())) for era in sorted({row["era"] for row in cards})])
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    output.write_text(PAGE.replace("__DATA__", encoded), encoding="utf-8")
    renderer.deleteLater()
    engine.deleteLater()
    app.processEvents()
    return dict(path=str(output), brands=len(counts), series=len(cards), glyph_variants=len(cards)*10,
                bytes=output.stat().st_size, warnings=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "qa-private/hardware-gallery.html")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        parser.error("Choose a new output or use --overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    with patch.object(ctypes, "WinDLL", side_effect=AssertionError("No hardware API")), \
         patch.object(subprocess, "Popen", side_effect=AssertionError("No process")), \
         patch("threading.Thread.start", side_effect=AssertionError("No thread")):
        print(json.dumps(export_gallery(output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
