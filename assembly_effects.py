"""Finite selection feedback for thirteen artwork styles, with no clock or I/O.

The host advances this state using its existing shared 34 ms animation clock.
Effects change light/ink only: model positions, fan angles and picking geometry
remain unchanged. No effect runs at rest or invents a sensor measurement.
"""
import math

from top_bar_config import HARDWARE_ICON_STYLES

_POLICIES = {
    "miniature":(1,620,"金属斜向掠光","A narrow diagonal reflection crosses brushed metal."),
    "cartoon":(2,650,"软轮廓双脉冲","Two rounded Fresnel rim pulses soften the selected shape."),
    "notebook_color":(3,820,"彩铅落色","Stippled pigment dabs reveal across the selected surface."),
    "notebook_line":(4,850,"线稿描绘","A moving pen front progressively traces selected crease ink."),
    "sticker":(5,620,"贴纸压印环","An expanding die-cut ring flashes over the selected sticker."),
    "papercut":(6,780,"剪纸分层显影","Six staggered paper bands reveal with offset seams."),
    "inkwash":(7,850,"墨色晕染","An irregular radial wash grows with a soft pigment tide line."),
    "classic":(8,400,"精简扫描线","A single clean vertical scan sweeps the selected component."),
    "outline":(9,650,"轮廓游线","Short bright dashes travel along the retained crease ink."),
    "solid":(10,540,"硬边金属高光","A tight metallic glint follows view-facing hard edges."),
    "soft":(11,720,"柔和羽化光","A broad feathered light moves through the selected surface."),
    "sketch":(12,850,"铅笔交叉排线","Fine crossed pencil hatches reveal in an uneven drawn sweep."),
    "notebook_smile":(13,720,"手账双圈印记","A small double-ring ink stamp settles without changing the model."),
}
COMPONENTS = ("case","gpu","cpu","memory","board","cooler","fans","psu","storage","expansion","cables")


def component_family(value):
    return value.split(':',1)[0] if isinstance(value,str) else ''


def effect_for(style):
    style=style if isinstance(style,str) and style in _POLICIES else "miniature"
    kind,duration,label,mechanism=_POLICIES[style]
    return dict(style=style,kind=kind,duration_ms=duration,label=label,mechanism=mechanism,
                event="selection",geometry_transform=False,continuous=False)


def effect_sample(style,elapsed_ms,component="gpu"):
    policy=effect_for(style)
    valid=type(elapsed_ms) in (int,float) and math.isfinite(elapsed_ms)
    elapsed=max(0.,float(elapsed_ms)) if valid else float(policy['duration_ms'])
    progress=min(1.,elapsed/policy['duration_ms'])
    known=component_family(component) in COMPONENTS
    active=known and valid and elapsed<policy['duration_ms']
    return dict(style=policy['style'],component=component if known else '',
                kind=policy['kind'],progress=progress,amount=math.sin(math.pi*progress) if active else 0.,
                active=active,elapsed_ms=elapsed)


class SelectionEffect:
    """One bounded transient; completion cannot restart itself."""
    def __init__(self):
        self.style='miniature';self.component='';self.elapsed_ms=0.;self.active=False

    def start(self,style,component):
        if component_family(component) not in COMPONENTS:return False
        self.style=effect_for(style)['style'];self.component=component
        self.elapsed_ms=0.;self.active=True;return True

    def cancel(self):
        changed=self.active;self.active=False;return changed

    def advance(self,elapsed_ms):
        if not self.active or type(elapsed_ms) not in (int,float) or not math.isfinite(elapsed_ms):return False
        elapsed=max(0.,min(136.,elapsed_ms))
        if not elapsed:return False
        self.elapsed_ms=min(effect_for(self.style)['duration_ms'],self.elapsed_ms+elapsed)
        if self.elapsed_ms>=effect_for(self.style)['duration_ms']:self.active=False
        return True

    def sample(self):
        state=effect_sample(self.style,self.elapsed_ms,self.component)
        if not self.active:state.update(active=False,amount=0.)
        return state


def policies():
    return tuple(effect_for(style) for style in HARDWARE_ICON_STYLES)
