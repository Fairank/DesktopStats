"""Export a self-contained, offline icon review gallery from the actual QML code.

No sampler, desktop window, browser, network, driver query or installed profile.
Only the selected cards/style/theme are attached to the gallery's DOM.
"""

import argparse
import base64
import ctypes
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STYLES = ("classic", "outline", "solid", "miniature", "soft", "cartoon", "sketch", "notebook_line", "notebook_color", "notebook_smile")
MODERN = ("solid", "miniature", "soft", "cartoon", "sketch", "notebook_line", "notebook_color", "notebook_smile")
THEMES = (("light", "#303a48"), ("dark", "#e8edf4"))
SIMULATED_RPMS = (0, 600, 1200, 1800, 2400, 3000)
FAN_SLOWDOWN = 120

PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>硬件造型图鉴</title><style>
:root{font-family:"Segoe UI","Microsoft YaHei UI",sans-serif;color:#293544;background:var(--page);--page:#edf1f5;--card:#fff;--line:#dce3eb;--muted:#65758a;--field:#f4f7fa;--accent:#4777a4}
:root[data-theme=dark]{color:#e4ebf4;--page:#1c222b;--card:#252e3a;--line:#3c4858;--muted:#aab7c9;--field:#303c4a;--accent:#a6c9ec;color-scheme:dark}
*{box-sizing:border-box}[hidden]{display:none!important}body{max-width:1560px;margin:auto;padding:36px 28px 60px}h1{font-size:28px;letter-spacing:-.5px;margin:0 0 9px}header p{margin:0;color:var(--muted);line-height:1.65}
.toolbar{display:flex;flex-wrap:wrap;gap:9px;position:sticky;top:0;background:var(--page);padding:20px 0 10px;z-index:2}select,input,button{font:inherit}select,input[type=search],button{font-size:13px;min-height:38px;border:1px solid var(--line);border-radius:9px;padding:8px 10px;color:inherit;background:var(--card)}input[type=search]{flex:1;min-width:205px}button{cursor:pointer}button:disabled{opacity:.45;cursor:default}select:focus-visible,input:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.preview-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:3px 0 17px;font-size:12px;color:var(--muted)}.preview-controls label{display:flex;gap:7px;align-items:center;cursor:pointer;color:var(--accent)}input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px}#count{font-size:13px;color:var(--muted);margin:0 0 16px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(265px,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:15px;background:var(--card);padding:19px 19px 16px;min-width:0}.brand{font-size:11px;letter-spacing:.7px;color:var(--muted);margin-bottom:7px}.card h2{font-size:17px;margin:0 0 5px}.model{font-size:11px;line-height:1.5;color:var(--muted);min-height:34px;overflow-wrap:anywhere}.art{height:137px;display:flex;align-items:center;justify-content:center}.art-open{border:0;background:none;padding:0;width:100%;border-radius:8px}.stage{position:relative;display:block;width:128px;height:128px;flex:none}.stage>.still,.layer-view,.layer-view>.base{position:absolute;inset:0;width:100%;height:100%}.stage.playing>.still{visibility:hidden}.layer-view{pointer-events:none}.rotor{position:absolute;transform-origin:50% 50%;animation:none}.playing .rotor{animation:rotor-turn var(--rotor-duration,6s) linear infinite;animation-direction:var(--rotor-direction,normal)}@keyframes rotor-turn{to{transform:rotate(1turn)}}
.actual{display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid var(--line);padding-top:12px;margin-top:2px}.small{display:flex;align-items:center;gap:8px;background:var(--field);border-radius:7px;padding:6px 9px;font-size:11px;white-space:nowrap}.small img{width:18px;height:18px}.facts{font-size:11px;text-align:right;color:var(--muted);line-height:1.55}.features,.fan-profile{font-size:12px;color:var(--muted);line-height:1.65;margin:12px 0;min-height:20px}.fan-profile{padding-top:10px;border-top:1px solid var(--line)}.card-links,.source-links{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.link{font-size:12px;color:inherit;text-decoration-color:var(--muted);text-underline-offset:3px}.view-button{border:0;background:none;min-height:30px;padding:4px 0;color:var(--accent);font-size:12px}.badge{font-size:10px;border:1px solid var(--line);border-radius:5px;padding:2px 4px;margin-left:5px;color:var(--muted)}footer{margin-top:24px;line-height:1.7;color:var(--muted);font-size:12px}#empty{padding:30px;color:var(--muted)}
dialog{color:inherit;background:var(--card);border:1px solid var(--line);border-radius:20px;width:min(720px,calc(100vw - 32px));max-height:92vh;padding:25px;overflow:auto;box-shadow:0 25px 100px #0004}dialog::backdrop{background:#101c2b99}dialog:not([open]){display:none}.focus-top{display:flex;justify-content:space-between;align-items:center;gap:12px}.focus-top p{margin:0;color:var(--muted);font-size:12px}#focus-title{font-size:23px;line-height:1.35;margin:16px 0 6px}#focus-model{font-size:13px;line-height:1.65;color:var(--muted);overflow-wrap:anywhere}.focus-art{display:flex;justify-content:center;padding:12px 0}.focus-art .stage{width:min(350px,64vw);height:min(350px,64vw)}.focus-details{border-top:1px solid var(--line);padding-top:15px;display:flex;align-items:center;justify-content:space-between;gap:16px}.focus-actions{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:22px}.focus-actions span{font-size:12px;color:var(--muted)}
@media(max-width:600px){body{padding:24px 16px 40px}.toolbar{position:relative}.toolbar select{flex:1;min-width:135px}.toolbar input[type=search]{flex-basis:100%}.focus-actions span{max-width:105px}}
@media(prefers-reduced-motion:reduce){.playing .rotor{animation:none!important}}
</style><body><header><h1>硬件造型图鉴</h1><p id="summary"></p><p>全部已设计作品都在这里。点击单项放大，或用上一项、下一项逐个比较。每项保留 18px 顶部栏实际尺寸。</p></header>
<div class="toolbar"><select id="kind" aria-label="硬件类型"><option value="all">全部硬件</option><option value="cpu">处理器</option><option value="gpu">显卡</option><option value="memory">内存条</option></select><select id="brand" aria-label="品牌"><option value="all">全部品牌</option></select><select id="vendor" aria-label="芯片厂商"><option value="all">全部芯片厂商</option><option value="nvidia">NVIDIA</option><option value="amd">AMD</option><option value="intel">Intel</option></select><select id="era" aria-label="代际"><option value="all">全部代际</option></select><select id="tier" aria-label="产品线"><option value="all">全部产品线</option><option value="entry">入门非公</option><option value="mainstream">主流非公</option><option value="flagship">旗舰非公</option><option value="creator">创作系列</option><option value="reference">公版 / 参考设计</option><option value="processor">处理器封装</option></select><select id="style" aria-label="图标版本"><option value="solid">精简实物</option><option value="miniature">微型实物</option><option value="soft">柔和双色</option><option value="cartoon">可爱卡通</option><option value="sketch">手绘线稿</option><option value="notebook_line">随手线条</option><option value="notebook_color">手涂淡彩</option><option value="notebook_smile">笑脸手绘</option><option value="outline">结构线稿 · 旧版</option><option value="classic">经典通用</option></select><select id="theme" aria-label="背景"><option value="light">浅色背景</option><option value="dark">深色背景</option></select><input id="search" type="search" placeholder="搜索系列或代表型号" aria-label="搜索系列或代表型号"></div>
<div class="preview-controls"><label><input id="motion" type="checkbox">动效预览</label><label for="simulated-rpm">模拟 RPM <select id="simulated-rpm" aria-label="模拟转速 RPM"><option value="0">0 · 停止</option><option value="600">600</option><option value="1200" selected>1200</option><option value="1800">1800</option><option value="2400">2400</option><option value="3000">3000</option></select></label><span>固定 120 倍慢放 · 非实时测量</span><span id="motion-status">默认静态；模拟转速只用于预览。</span></div>
<p id="count" role="status"></p><main id="grid" class="grid"></main><p id="empty" hidden>没有匹配的作品。</p>
<dialog id="focus-dialog" aria-labelledby="focus-title"><div class="focus-top"><p id="focus-position"></p><button id="focus-close" type="button">关闭</button></div><h2 id="focus-title"></h2><div id="focus-model"></div><div id="focus-art" class="focus-art"></div><div class="focus-details"><div id="focus-small" class="small"></div><div id="focus-facts" class="facts"></div></div><p id="focus-features" class="features"></p><p id="focus-profile" class="fan-profile" hidden></p><p id="focus-board" class="features" hidden></p><div id="focus-structure" hidden></div><div class="source-links"><a id="focus-source" class="link" target="_blank" rel="noopener noreferrer">官方型号资料</a><a id="focus-fan-source" class="link" target="_blank" rel="noopener noreferrer" hidden>官方风扇资料</a></div><div class="focus-actions"><button id="focus-prev" type="button">← 上一项</button><span>键盘 ← / → 浏览<br>Home / End 首尾</span><button id="focus-next" type="button">下一项 →</button></div></dialog>
<footer>图形是依据代表产品特征绘制的简化插画，不是照片、厂商标志或精确尺寸图。未确认的风扇不会被猜成零或固定扇数；外置冷排和附加风扇另行说明。内存扩散罩不表示灯效已开启。产品线定位不代表芯片性能排名。叶片数量只在官方文字或图片足够明确时确认，未知部分不补猜；轮毂与叶片轮廓是插画估计。模拟 RPM 固定 120 倍慢放，保留已核相对转向，不代表真实读数。动效默认关闭，0 RPM 停止，只在当前视口、页面可见且系统未要求减少动态时播放；放大时暂停后方卡片。页面、静态图及叶轮均已内嵌，无需联网；官方资料链接仅在你点击后打开。</footer>
<script>const DATA=__DATA__;
const $=id=>document.getElementById(id),controls=Object.fromEntries(['kind','brand','vendor','era','tier','style','theme','search'].map(id=>[id,$(id)]));
const {kind,brand,vendor,era,tier,style,theme,search}=controls,grid=$('grid'),dialog=$('focus-dialog'),motion=$('motion'),rpmControl=$('simulated-rpm');
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)'),modern=new Set(['solid','miniature','soft','cartoon','sketch','notebook_line','notebook_color','notebook_smile']),stages=new Set();
let observer=null,filtered=[],focusedId=null,returnFocus=null,pageSuspended=false;
function simulatedRpm(){const value=Number(rpmControl.value);return DATA.simulation.rpmOptions.includes(value)?value:0}
function updateDuration(){const rpm=simulatedRpm();document.documentElement.style.setProperty('--rotor-duration',(rpm>0?60*DATA.simulation.slowdown/rpm:6)+'s')}
const counts=Object.fromEntries(['cpu','gpu','memory'].map(k=>[k,DATA.cards.filter(row=>row.kind===k).length]));
$('summary').textContent=DATA.brands.length+' 个品牌 · '+DATA.cards.length+' 项代表设计 · '+counts.cpu+' 处理器 / '+counts.gpu+' 显卡 / '+counts.memory+' 内存';
for(const row of DATA.brands){const option=document.createElement('option');option.value=row.id;option.textContent=row.label+' · '+row.count;brand.append(option)}
for(const row of DATA.eras){const option=document.createElement('option');option.value=row.id;option.textContent=row.label;era.append(option)}
function text(tag,value,cls){const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e}
function stopStage(stage){stage.classList.remove('playing');if(stage._overlay)stage._overlay.hidden=true}
function clearStages(focus){for(const stage of [...stages])if(stage._focus===focus){stopStage(stage);stages.delete(stage);if(observer)observer.unobserve(stage)}}
function localImage(uri,alt,loading='lazy'){const image=new Image();image.loading=loading;image.decoding='async';image.alt=alt;image.src=uri;return image}
function setupStage(row,focus=false){const stage=document.createElement('span');stage.className='stage';stage._row=row;stage._focus=focus;stage._view=false;stage._style=style.value;stage._theme=theme.value;stage._layers=row.motion[style.value]?.[theme.value];const image=localImage(row.art[style.value][theme.value],row.label+' 外观',focus?'eager':'lazy');image.className='still';stage.append(image);stages.add(stage);return stage}
function decoded(image){if(image.complete)return Promise.resolve(image.naturalWidth>0);return new Promise(resolve=>{image.addEventListener('load',()=>resolve(true),{once:true});image.addEventListener('error',()=>resolve(false),{once:true})})}
function prepareLayers(stage){if(stage._preparing||stage._ready||stage._failed||!stage._layers?.rotors.length)return;stage._preparing=true;const box=document.createElement('span');box.className='layer-view';box.hidden=true;box.setAttribute('aria-hidden','true');const base=localImage(DATA.motionAssets[stage._layers.baseSource],'','eager');base.className='base';box.append(base);const images=[base];for(const rotor of stage._layers.rotors){const image=localImage(DATA.motionAssets[rotor.source],'','eager');image.className='rotor';image.style.left=((rotor.cx-rotor.radius)/24*100)+'%';image.style.top=((rotor.cy-rotor.radius)/24*100)+'%';image.style.width=(rotor.radius*2/24*100)+'%';image.style.height=(rotor.radius*2/24*100)+'%';image.style.setProperty('--rotor-direction',rotor.direction===-1?'reverse':'normal');box.append(image);images.push(image)}stage._overlay=box;stage.append(box);Promise.all(images.map(decoded)).then(ready=>{stage._ready=ready.every(Boolean);stage._failed=!stage._ready;stage._preparing=false;if(stages.has(stage)&&stage.isConnected)syncStage(stage)})}
function canRun(){return motion.checked&&simulatedRpm()>0&&modern.has(style.value)&&!reduced.matches&&!document.hidden&&!pageSuspended&&typeof IntersectionObserver==='function'}
function syncStage(stage){const eligible=canRun()&&stage._view&&stage.isConnected&&(dialog.open?stage._focus:!stage._focus)&&stage._layers?.rotors.length>0;if(!eligible){stopStage(stage);return}prepareLayers(stage);if(stage._ready){stage._overlay.hidden=false;stage.classList.add('playing')}}
function syncAll(){
 for(const stage of stages)syncStage(stage);
 let status='默认静态；模拟转速只用于预览。';
 if(reduced.matches)status='系统已开启减少动态，保持静态展示。';
 else if(typeof IntersectionObserver!=='function')status='当前浏览器无法按视口暂停，保持静态展示。';
 else if(motion.checked&&!modern.has(style.value))status='此版本保留静态造型；三个实物版本支持叶轮预览。';
 else if(motion.checked&&simulatedRpm()===0)status='模拟 0 RPM：叶轮保持静止。';
 else if(motion.checked)status='模拟 '+simulatedRpm()+' RPM · 120 倍慢放；只播放视口内已确认叶轮，离屏或页面隐藏即停止。';
 $('motion-status').textContent=status;motion.disabled=reduced.matches||typeof IntersectionObserver!=='function';
}
function resetObservation(){if(observer)observer.disconnect();for(const stage of stages){stage._view=false;stopStage(stage)}if(canRun()){if(!observer)observer=new IntersectionObserver(entries=>{for(const entry of entries)if(stages.has(entry.target)){entry.target._view=entry.isIntersecting&&entry.intersectionRatio>0;syncStage(entry.target)}},{threshold:0});for(const stage of stages)if(dialog.open?stage._focus:!stage._focus)observer.observe(stage)}syncAll()}
function actualSample(row){const small=document.createElement('div');small.className='small';const image=localImage(row.art[style.value][theme.value],'');image.width=18;image.height=18;small.append(image,text('span','18px 实际尺寸'));return small}
function shownFeatures(row){return style.value==='classic'?'通用符号，不表达具体型号布局':row.features.join(' · ')}
function focusIndex(){return filtered.findIndex(row=>row.id===focusedId)}
function boardText(row){const facts=row.boardDetails||{};return [facts.ports_text,facts.power_text,facts.host_text,facts.kind==='memory'?[facts.generation?.toUpperCase(),facts.pins?facts.pins+' pin':''].filter(Boolean).join(' · '):''].filter(Boolean).join(' · ')}
function structurePanel(row){const host=$('focus-structure');host.replaceChildren();host.hidden=!Object.keys(row.structures||{}).length;if(host.hidden)return;const controls=document.createElement('div');controls.className='source-links';const body=document.createElement('div');const labels={ports:'视频接口',power:'供电插座',backplate:'原厂背板',accessory:'附送配件背板'};for(const [kind,uri] of Object.entries(row.structures)){const button=text('button',labels[kind],'view-button');button.type='button';button.addEventListener('click',()=>{const image=localImage(uri,row.model+' '+button.textContent,'eager');image.style.width='100%';image.style.maxWidth='420px';image.style.height='auto';const note=kind==='accessory'?'附送背板外观，未确认实际安装。':kind==='backplate'?'原厂背板简化外观。':'类型与数量示意；排列和位置未核实。';body.replaceChildren(image,text('p',note,'features'))});controls.append(button)}host.append(controls,body)}
function updateFocus(){const index=focusIndex();if(index<0){if(dialog.open)dialog.close();return}const row=filtered[index];clearStages(true);$('focus-title').textContent=row.label;$('focus-model').textContent=row.model;$('focus-position').textContent=(index+1)+' / '+filtered.length+' · '+row.brandLabel;$('focus-facts').textContent=row.fans;$('focus-features').textContent=shownFeatures(row);$('focus-profile').textContent=row.fanProfileText;$('focus-profile').hidden=!row.fanProfileText;$('focus-board').textContent=boardText(row);$('focus-board').hidden=!$('focus-board').textContent;structurePanel(row);$('focus-fan-source').hidden=!row.fanProfile?.source_url;if(row.fanProfile?.source_url)$('focus-fan-source').href=row.fanProfile.source_url;$('focus-source').href=row.source;$('focus-art').replaceChildren(setupStage(row,true));const sample=actualSample(row);$('focus-small').replaceChildren(...sample.childNodes);$('focus-prev').disabled=filtered.length<2;$('focus-next').disabled=filtered.length<2;resetObservation()}
function openFocus(row,button){focusedId=row.id;returnFocus=button;if(!dialog.open)dialog.showModal();updateFocus()}
function browse(direction){if(!filtered.length)return;const index=focusIndex();focusedId=filtered[(index+direction+filtered.length)%filtered.length].id;updateFocus()}
function buildCard(row){const card=document.createElement('article');card.className='card';card.dataset.id=row.id;card.append(text('div',row.brandLabel+' · '+({cpu:'处理器',gpu:'显卡',memory:'内存条'}[row.kind]),'brand'));const title=text('h2',row.label);if(row.legacy)title.append(text('span','历史型号','badge'));card.append(title,text('div',row.model,'model'));const art=document.createElement('button');art.type='button';art.className='art art-open';art.setAttribute('aria-label','放大查看 '+row.label);art.append(setupStage(row));art.addEventListener('click',()=>openFocus(row,art));card.append(art);const actual=document.createElement('div');actual.className='actual';actual.append(actualSample(row),text('div',row.fans,'facts'));card.append(actual,text('div',shownFeatures(row),'features'));if(row.fanProfileText)card.append(text('p',row.fanProfileText,'fan-profile'));const links=document.createElement('div');links.className='card-links';const link=text('a','官方型号资料','link');link.href=row.source;link.target='_blank';link.rel='noopener noreferrer';const view=text('button','放大查看 →','view-button');view.type='button';view.addEventListener('click',()=>openFocus(row,view));links.append(link);if(row.fanProfile?.source_url){const fanLink=text('a','风扇资料','link');fanLink.href=row.fanProfile.source_url;fanLink.target='_blank';fanLink.rel='noopener noreferrer';links.append(fanLink)}links.append(view);card.append(links);return card}
function render(){document.documentElement.dataset.theme=theme.value;const query=search.value.trim().toLocaleLowerCase();filtered=DATA.cards.filter(row=>(kind.value==='all'||row.kind===kind.value)&&(brand.value==='all'||row.brand===brand.value)&&(vendor.value==='all'||row.vendor===vendor.value)&&(era.value==='all'||row.era===era.value)&&(tier.value==='all'||row.tier===tier.value)&&(!query||(row.label+' '+row.model+' '+row.brandLabel+' '+row.features.join(' ')+' '+row.fanProfileText).toLocaleLowerCase().includes(query)));if(observer)observer.disconnect();clearStages(false);const fragment=document.createDocumentFragment();for(const row of filtered)fragment.append(buildCard(row));grid.replaceChildren(fragment);$('count').textContent='显示 '+filtered.length+' / '+DATA.cards.length+' 项作品';$('empty').hidden=filtered.length>0;if(dialog.open)updateFocus();else resetObservation()}
for(const control of Object.values(controls))control.addEventListener(control===search?'input':'change',render);motion.addEventListener('change',resetObservation);rpmControl.addEventListener('change',()=>{updateDuration();resetObservation()});$('focus-close').addEventListener('click',()=>dialog.close());$('focus-prev').addEventListener('click',()=>browse(-1));$('focus-next').addEventListener('click',()=>browse(1));dialog.addEventListener('close',()=>{clearStages(true);$('focus-art').replaceChildren();focusedId=null;resetObservation();if(returnFocus?.isConnected)returnFocus.focus();returnFocus=null});dialog.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();if(event.key==='Home'||event.key==='End'){focusedId=filtered[event.key==='Home'?0:filtered.length-1]?.id;updateFocus()}else browse(event.key==='ArrowLeft'?-1:1)}});document.addEventListener('visibilitychange',resetObservation);window.addEventListener('pagehide',()=>{pageSuspended=true;resetObservation()});window.addEventListener('pageshow',()=>{pageSuspended=false;resetObservation()});if(reduced.addEventListener)reduced.addEventListener('change',resetObservation);else reduced.addListener(resetObservation);updateDuration();render();
</script></body></html>
'''


def fan_profile_text(appearance):
    """Separate the reviewed blade count from the number of physical fans."""
    if appearance.get("kind") != "gpu":
        return "", "not_applicable"
    if appearance.get("fan_count") == 0:
        return "被动散热 · 无叶轮", "not_applicable"
    profile = appearance.get("fan_profile") or {}
    label = profile.get("label") or "风扇结构未确认"
    counts = profile.get("blade_counts") or []
    count = profile.get("blades")
    if not counts and type(count) is int and count > 0:
        counts = [count]
    confirmed = [type(value) is int and value > 0 for value in counts]
    if counts and all(confirmed):
        if len(set(counts)) == 1:
            detail = f"正面叶轮：每扇 {counts[0]} 叶 · 已确认"
        else:
            detail = "正面从左到右：" + " / ".join(map(str, counts)) + " 叶 · 已确认"
        return label + " · " + detail, "confirmed"
    if any(confirmed):
        detail = " / ".join(str(value) if valid else "未确认"
                            for value, valid in zip(counts, confirmed))
        return label + " · 正面从左到右：" + detail + " 叶 · 部分已确认", "partial"
    return label + " · 风扇外观待核实（简化占位）", "unknown"


def export_gallery(output):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext

    from hardware_appearance import BRANDS, CATALOG, appearance_for
    from hardware_series import SERIES_CATALOG
    from hardware_variants import READY, RECORDS
    from memory_appearance import BRANDS as MEMORY_BRANDS, CATALOG as MEMORY_MODELS
    from memory_appearance import SERIES_CATALOG as MEMORY_SERIES, appearance_for_memory

    app = QCoreApplication.instance() or QCoreApplication([])
    engine, warnings = QQmlEngine(), []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    component = QQmlComponent(engine)
    component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/IconData.js" as Icons
import "../native/HardwareBoardDesigns.js" as Boards
QtObject { function svgFor(value,ink) {
    if(value.icon_set === "classic") return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+ink+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+Icons.fragment(value.kind==='memory'?'memory':value.kind==='cpu'?'cpu':'gpu')+'</svg>'
    return decodeURIComponent(Shapes.source(Shapes.key(value,ink)).split(',')[1])
}
function layersFor(value,ink) { return JSON.stringify(Shapes.layers(Shapes.key(value,ink))) }
function structureFor(value,view) { return Boards.technicalSource(Boards.modelKey(value),view) }
}''', QUrl.fromLocalFile(str(ROOT / "tools/hardware-gallery.qml")))
    renderer = component.create()
    if renderer is None:
        raise RuntimeError([error.toString() for error in component.errors()])
    def evaluate(name, value, ink):
        expression = QQmlExpression(qmlContext(renderer), renderer,
                                   name + "(" + json.dumps(value) + "," + json.dumps(ink) + ")")
        result = expression.evaluate()
        result = result[0] if isinstance(result, tuple) else result
        if expression.hasError() or not isinstance(result, str):
            raise RuntimeError(expression.error().toString())
        return result

    representatives, entries = {}, []
    for row in CATALOG:
        value = appearance_for(row[1], row[-1][0])
        if row[1] == "cpu":
            entries.append((dict(id="cpu-" + value["id"], label=value["label"]), value))
        elif value["series_id"]:
            representatives.setdefault(value["series_id"], value)
    for row in MEMORY_MODELS:
        value = appearance_for_memory(model=row["aliases"][0])
        representatives.setdefault(value["series_id"], value)
    entries.extend((series, representatives[series["id"]]) for series in (*SERIES_CATALOG, *MEMORY_SERIES))
    series_by_id={row['id']:row for row in (*SERIES_CATALOG,*MEMORY_SERIES)}
    for row in CATALOG:
        if row[0] in READY:
            value=appearance_for(row[1],row[-1][0])
            entries.append((dict(series_by_id[value['series_id']],id='variant-'+row[0],label=value['label'],variant=True),value))
    for row in MEMORY_MODELS:
        if row['id'] in READY:
            value=appearance_for_memory(model=row['aliases'][0])
            entries.append((dict(series_by_id[value['series_id']],id='variant-'+row['id'],label=value['label'],variant=True),value))
    cards, counts, assets, asset_ids = [], {}, [], {}
    all_brands = dict(BRANDS, **MEMORY_BRANDS)

    def asset(uri):
        if not isinstance(uri, str) or not uri.startswith("data:image/svg+xml"):
            raise ValueError("Every animation layer must be an embedded SVG")
        if uri not in asset_ids:
            asset_ids[uri] = len(assets)
            assets.append(uri)
        return asset_ids[uri]

    for series, value in entries:
        brand = value["vendor"] if value["kind"] == "cpu" else value["board_vendor"]
        counts[brand] = counts.get(brand, 0) + 1
        total, visible = value["fan_count"], value["visible_fan_count"]
        fans = f"物理总数 {total} 扇" if type(total) is int else "风扇总数未确认"
        if type(visible) is int and visible != total:
            fans += f" · 图示 {visible} 扇"
        if value["kind"] == "memory":
            fans = {"dimm": "DIMM 长条", "sodimm": "SO-DIMM 短条"}.get(value["style"], "形态未确认")
        elif value["kind"] == "cpu":
            fans = {"lga_rect": "长方形顶盖", "am5": "带缺口顶盖"}.get(value["style"], "处理器封装")
        elif value["style"] == "gpu_hybrid":
            fans += " · 含外置冷排"
        elif total == 0:
            fans = "被动散热 · 无风扇"
        profile_text, profile_state = fan_profile_text(value)
        facts=value.get('board_details') or {}
        structures={}
        if value['kind']=='gpu':
            for view,field in (('ports','ports'),('power','power_connectors'),
                               ('backplate','backplate_recipe'),('accessory','accessory_backplate_recipe')):
                if facts.get(field) or view=='power' and facts.get('extra_power_interface'):
                    structures[view]=evaluate('structureFor',value,view)
        art, motion = {}, {}
        for style in STYLES:
            art[style] = {}
            for theme, ink in THEMES:
                selected = dict(value, icon_set=style)
                svg = evaluate("svgFor", selected, ink)
                if not svg.startswith("<svg"):
                    raise ValueError("Invalid static SVG for " + value["id"])
                art[style][theme] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
                if value["kind"] != "gpu" or style not in MODERN or not value.get("fan_profile", {}).get("render_ready"):
                    continue
                layers = json.loads(evaluate("layersFor", selected, ink))
                if not layers.get("rotors"):
                    continue
                exported = []
                for rotor in layers["rotors"]:
                    numbers = [rotor.get(key) for key in ("cx", "cy", "radius")]
                    if any(type(number) not in (int, float) or not math.isfinite(number) for number in numbers):
                        raise ValueError("Invalid rotor geometry for " + value["id"])
                    cx, cy, radius = numbers
                    if radius <= 0 or min(cx-radius, cy-radius) < 0 or max(cx+radius, cy+radius) > 24:
                        raise ValueError("Rotor is outside the icon: " + value["id"])
                    if rotor.get("kind") not in ("axial", "blower"):
                        raise ValueError("Unreviewed rotor type")
                    direction = rotor.get("direction", 1)
                    if type(direction) is not int or direction not in (-1, 1):
                        raise ValueError("Invalid relative fan direction")
                    exported.append(dict(cx=cx, cy=cy, radius=radius, kind=rotor["kind"],
                                         direction=direction, source=asset(rotor["source"])))
                motion.setdefault(style, {})[theme] = dict(baseSource=asset(layers["baseSource"]), rotors=exported)
        cards.append(dict(id=series["id"], brand=brand, brandLabel=all_brands[brand][0], label=series["label"],
                          model=value["label"], fans=fans, features=value["features"],
                          fanProfile=value.get("fan_profile") or {},
                          fanProfileText=profile_text, fanProfileState=profile_state,
                          boardDetails=facts,structures=structures,variant=bool(series.get('variant')),
                          source=value["source_url"], legacy=bool(series.get("legacy")), art=art, motion=motion,
                          kind=value["kind"], vendor=value["vendor"] if value["kind"]!="memory" else "memory",
                          era="cpu" if value["kind"]=="cpu" else value.get("era", "memory"),
                          tier="processor" if value["kind"]=="cpu" else value.get("tier", "unspecified")))
    if warnings:
        raise RuntimeError(warnings)
    era_labels = dict(cpu="处理器", memory="内存条", gtx10="GTX / GT 10 系列", gtx900="GTX 900", gtx700="GTX 700",
                      gtx600="GTX 600", gtx500="GTX 500", gtx400="GTX 400", gtx200="GTX 200", pre_gtx="GeForce 8 / FX",
                      radeon_hd="Radeon HD", r9="Radeon R9", rx500="Radeon RX 500", rx400="Radeon RX 400",
                      vega="Radeon Vega", rdna1="Radeon RX 5000", rdna2="Radeon RX 6000", rdna3="Radeon RX 7000", rdna4="Radeon RX 9000",
                      arc_a="Intel Arc A", arc_b="Intel Arc B", unspecified="代际未分组")
    era_labels.update({"rtx"+digit+"0": "GeForce RTX "+digit+"0 系列" for digit in "2345"})
    era_labels.update({"rx"+digit+"000": "Radeon RX "+digit+"000" for digit in "56789"})
    data = dict(cards=cards, motionAssets=assets, versionInventory=list(RECORDS.values()),
                simulation=dict(rpmOptions=SIMULATED_RPMS, slowdown=FAN_SLOWDOWN, source="simulation"),
                brands=[dict(id=brand, label=all_brands[brand][0], count=count)
                                    for brand, count in sorted(counts.items())],
                eras=[dict(id=era, label=era_labels.get(era, era.upper())) for era in sorted({row["era"] for row in cards})])
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    output.write_text(PAGE.replace("__DATA__", encoded), encoding="utf-8")
    renderer.deleteLater()
    engine.deleteLater()
    app.processEvents()
    return dict(path=str(output), brands=len(counts), series=len(cards), glyph_variants=len(cards)*len(STYLES)*len(THEMES),
                kinds={kind:sum(card["kind"]==kind for card in cards) for kind in ("cpu","gpu","memory")},
                motion_assets=len(assets), animated_cards=sum(bool(card["motion"]) for card in cards),
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
