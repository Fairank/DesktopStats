"""Rebuild the optional hardware-decoration atlases (Pillow, artwork time only).

Noise and recursive midpoint displacement derive from three.js r150, commit
9b274fef1d2b9ba0fc47410d06593e1f34f4df0e: SimplexNoise.noise4d and
LightningStrike.fractalRayRecursive. Original MIT attribution/license are in
licenses/three-r150. No React Bits / Expo implementation is incorporated.
The 2D anchor choreography, branch scheduling, Gaussian light model, atlas and
ten-stage art parameters are authored for DesktopStats. They depict decorative
activity, not an electric waveform, measured discharge or hardware alarm.

The MIT License, Copyright © 2010-2023 three.js authors (derived algorithms).
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageFilter

try:
    from .three_simplex4d import SimplexNoise
except ImportError:
    from three_simplex4d import SimplexNoise

ROOT = Path(__file__).resolve().parents[1]
FRAMES = 48
STAGES = 10
NOISE = tuple(SimplexNoise(seed=n) for n in (39, 81, 113))
SCHEDULES = {
    "warm": (.04,.19,.34,.48,.58,.72,.83,.92),
    "blue": (.11,.32,.03,.62,.45,.82,.69,.94),
}
DURATION_WEIGHTS = (1.00,.86,1.06,.92,.84,1.04,.89,.97)
ATTACKS = (.11,.17,.08,.13,.19,.09,.15,.12)
DECAYS = (.44,.57,.38,.49,.61,.46,.53,.40)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_parameters(stage):
    t = (stage-1)/9
    return dict(stage=stage, activity=stage/10, span=4.5+8.0*t,
                straightness=.74-.66*t, roughness=.82+.12*t,
                branch_count=min(3, int(t*3.5)), burst_budget=3+5*t,
                burst_duration=.055+.045*(stage/10),
                core_width=.65+.28*t, glow=.35+.65*t,
                speed=.82+.36*(stage/10))


def midpoint_ray(start, end, linear_start, linear_end, time, *, straightness,
                 roughness, iterations=5):
    """Adapted Three free XYZ midpoint recursion; no fixed arch or bow.

    Tiny segments use a .01 artwork floor rather than the source's .000001
    degeneracy test. The adaptation also omits prism/radius/up-vector fields.
    """
    def recurse(a, b, la, lb, factor, depth):
        if depth == iterations:
            return [a, b]
        d = tuple(b[i]-a[i] for i in range(3))
        length = max(.01, math.sqrt(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]))
        middle = tuple(a[i]+(b[i]-a[i])*.5 for i in range(3))
        linear = tuple(la[i]+(lb[i]-la[i])*.5 for i in range(3))
        scalar = factor*length
        p = tuple(NOISE[i].noise4d(*linear, time*(2**depth))*scalar+middle[i]
                  for i in range(3))
        left = recurse(a, p, la, linear, factor*roughness, depth+1)
        right = recurse(p, b, linear, lb, factor*roughness, depth+1)
        return left[:-1]+right
    return recurse(start, end, linear_start, linear_end, 1-straightness, 0)


def burst(age, stage, slot, channel):
    params = stage_parameters(stage)
    rng = random.Random(193+slot*101+(707 if channel=="blue" else 0))
    linear = [tuple(rng.random()*1000 for _ in range(3)) for _ in range(2)]
    span = params["span"]
    # Distinct perimeter attachments. Each packet vanishes completely before
    # its anchor/seed is reused; no permanent center-crossing carrier strand.
    anchors = (((3,2),(14,2)),((2,4),(2,13)),((15,3),(15,13)),((3,2),(10,1)),
               ((13,1),(16,8)),((1,11),(7,17)),((5,17),(15,16)),((1,5),(6,1))) if channel=="warm" else (
               ((4,16),(15,16)),((2,6),(2,16)),((16,5),(16,15)),((3,17),(9,13)),
               ((12,17),(17,11)),((1,4),(5,12)),((9,2),(16,8)),((3,3),(12,3)))
    a0, b0 = anchors[slot]
    center = ((a0[0]+b0[0])*.5,(a0[1]+b0[1])*.5)
    ratio=span/12
    ratio_a=ratio*rng.uniform(.84,.98)
    ratio_b=ratio*rng.uniform(1.01,1.12)
    a=tuple(center[i]+(a0[i]-center[i])*ratio_a for i in range(2))+(0,)
    b=tuple(center[i]+(b0[i]-center[i])*ratio_b for i in range(2))+(0,)
    points = midpoint_ray(a, b, *linear, 1.0+age*.8, straightness=params["straightness"],
                          roughness=params["roughness"])
    # Distinct zero-slope attack/hold/decay for each packet, not eight identical
    # sinusoidal pulses. Both ends reach zero before anchors or seeds reset.
    if age<ATTACKS[slot]:
        t=age/ATTACKS[slot]
        envelope=t*t*(3-2*t)
    elif age<DECAYS[slot]:
        envelope=1
    else:
        t=(age-DECAYS[slot])/(1-DECAYS[slot])
        envelope=1-t*t*(3-2*t)
    envelope *= min(1,max(0,params["burst_budget"]-slot))
    # Propagation and vanishing follow actual segment fractions, while a zero
    # endpoint envelope hides the seed/anchor reset at the next burst.
    begin = max(0, (age-.73)/.27)
    end = min(1, age/.13)
    visible = [p for i,p in enumerate(points) if begin <= i/(len(points)-1) <= end]
    result = [(visible, envelope)] if len(visible)>1 else []
    for index in range(params["branch_count"]):
        at = 7+index*7
        anchor = points[at]
        length = (1.3+params["activity"]*2.4)*rng.uniform(.65,1.15)
        angle=rng.uniform(-math.pi,math.pi)
        endpoint = (anchor[0]+math.cos(angle)*length, anchor[1]+math.sin(angle)*length,
                    anchor[2]+rng.uniform(-.5,.7))
        la = tuple(rng.random()*1000 for _ in range(3))
        lb = tuple(rng.random()*1000 for _ in range(3))
        child = midpoint_ray(anchor, endpoint, la, lb, 1.0+age*1.6,
                             straightness=params["straightness"], roughness=params["roughness"], iterations=4)
        branch_start=.12+index*.07+rng.uniform(0,.075)
        branch_life=rng.uniform(.48,.68)
        u = min(1, max(0, (age-branch_start)/branch_life))
        result.append((child, math.sin(math.pi*u)**2*envelope*(.65-index*.12)))
    return result


def frame_paths(phase, stage, channel):
    paths = []
    params=stage_parameters(stage)
    schedule=SCHEDULES[channel]
    for slot,start in enumerate(schedule):
        if params["burst_budget"]<=slot:
            continue
        elapsed=(phase-start)%1
        duration=params["burst_duration"]*DURATION_WEIGHTS[slot]
        if elapsed<duration:
            paths.extend(burst(elapsed/duration,stage,slot,channel))
    return paths


def frame_image(phase, stage, channel, cell):
    scale = cell/32
    params = stage_parameters(stage)
    premult, alpha = Image.new("RGB", (cell,cell)), Image.new("L", (cell,cell))
    # Bright yellow survives at stage10. Only the surrounding warm halo tends red.
    edge = (255, round(171-91*params["activity"]), 13) if channel=="warm" else (15,132,255)
    core = (255,243,112) if channel=="warm" else (179,239,255)
    for points,envelope in frame_paths(phase, stage,channel):
        if envelope<.0001:
            continue
        for width,sigma,opacity,color in ((1.8,1.12,.24*params["glow"],edge),
                                          (1.24,.38,.67,edge),
                                          (params["core_width"],.08,.96,core)):
            mask=Image.new("L",(cell,cell))
            coords=[((p[0]+7)*scale,(p[1]+7)*scale) for p in points]
            ImageDraw.Draw(mask).line(coords,fill=255,width=max(1,round(width*scale)),joint="curve")
            mask=mask.filter(ImageFilter.GaussianBlur(sigma*scale)).point(lambda n:round(n*opacity*envelope))
            layer=Image.merge("RGB",tuple(mask.point(lambda n,c=c:round(n*c/255)) for c in color))
            premult=ImageChops.add(premult,layer)
            alpha=ImageChops.add(alpha,mask)
    a=alpha.tobytes()
    channels=tuple(Image.frombytes("L",(cell,cell),bytes(min(255,round(v*255/k)) if k else 0
                    for v,k in zip(part.tobytes(),a))) for part in premult.split())
    return Image.merge("RGBA",channels+(alpha,))


def generate(output, cell=64):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT) or output.is_symlink():
        raise ValueError("Artwork output must be a normal project directory")
    output.mkdir(parents=True,exist_ok=True)
    if any((output/name).exists() for name in ("arc-warm.png","arc-blue.png","manifest.json")):
        raise FileExistsError("Do not overwrite an existing atlas or receipt")
    textures=[]
    for channel in ("warm","blue"):
        sheet=Image.new("RGBA",(cell*FRAMES,cell*STAGES))
        for stage in range(1,STAGES+1):
            for index in range(FRAMES):
                image=frame_image(index/FRAMES,stage,channel,cell)
                sheet.paste(image,(index*cell,(stage-1)*cell))
        path=output/("arc-"+channel+".png")
        sheet.save(path)
        textures.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),size=list(sheet.size),
                             decoded_bytes=sheet.width*sheet.height*4))
    report=dict(version=1,profile="free-midpoint-discharge",seed=[39,81,113],
                upstream_commit="9b274fef1d2b9ba0fc47410d06593e1f34f4df0e",
                upstream_license="licenses/three-r150/LICENSE.txt",
                generator="tools/generate_metric_motion.py",generator_sha256=sha(Path(__file__)),
                noise="tools/three_simplex4d.py",noise_sha256=sha(ROOT/"tools/three_simplex4d.py"),
                cell_pixels=cell,logical_cell=32,origin=[7,7],frame_count=FRAMES,
                stage_count=STAGES,loop_ms=2400,burst_schedules=SCHEDULES,
                duration_weights=DURATION_WEIGHTS,attack_fractions=ATTACKS,decay_starts=DECAYS,
                artwork_environment=dict(python=sys.version.split()[0],pillow=PIL.__version__),
                stage_parameters=[stage_parameters(i) for i in range(1,11)],
                textures=textures,decoded_bytes=sum(t["decoded_bytes"] for t in textures))
    (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default="assets/metric-motion")
    parser.add_argument("--cell",type=int,choices=(64,128,256),default=64)
    args=parser.parse_args()
    result=generate(ROOT/args.output,args.cell)
    print(json.dumps(dict(textures=result["textures"],decoded_bytes=result["decoded_bytes"])))
