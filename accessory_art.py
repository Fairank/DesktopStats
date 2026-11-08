"""Small, on-demand original SVG references for the manual accessory gallery.

Product names identify their owners. No photographs, logos, manufacturer CAD,
fonts, network access, Qt or hardware discovery are used. Dimensions and named
features come from the source-linked catalogs; curves, spacing, unseen detail
and every animation direction remain explicitly schematic reference artwork.
Original code/art: PolyForm Noncommercial 1.0.0; see LICENSE/LICENSING.md.
"""
from collections import OrderedDict
from copy import deepcopy
from html import escape
import math
import re
import sys

import chassis_catalog
import component_catalog
import cooling_catalog


# Kept local to avoid pulling the settings/sensor graph into this art module.
STYLES = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker',
          'papercut', 'inkwash', 'classic', 'outline', 'solid', 'soft', 'sketch',
          'notebook_smile')
_LOOP_KINDS = ('cpu_block','pump','reservoir','pump_reservoir','fitting','tubing','gpu_block')
_LOOP_KEYS = ('cpu_blocks','loop_pumps','loop_reservoirs','loop_combos','loop_fittings','loop_tubing','gpu_blocks')
_KINDS = ('case', 'cooler', 'psu', 'fan', *_LOOP_KINDS)
_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z', re.ASCII)
_MAX_ENTRIES = 16
_CACHE = OrderedDict()
_CHOICES = None
_CHOICES_GENERATION = -1


def _n(value):
    return format(float(value), '.8f').rstrip('0').rstrip('.') or '0'


def _shade(value, factor):
    if not isinstance(value,str) or not re.fullmatch('#[0-9a-fA-F]{6}',value):
        return '#303a42'
    return '#'+''.join(format(max(0,min(255,round(int(value[n:n+2],16)*factor))),'02x') for n in (1,3,5))


def _svg(content, rotor=False):
    bounds = '0 0 100 100' if rotor else '0 0 120 100'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + bounds +
            '" fill="none">' + content + '</svg>')


class _Pen:
    """Deterministic linework; notebook styles change contours, not just color."""
    def __init__(self, style):
        self.style = style
        self.hand = style in ('notebook_color', 'notebook_line', 'sketch', 'notebook_smile', 'inkwash')
        self.line = style in ('notebook_line', 'outline', 'sketch')
        self.paper = '#fbf8ed' if style in ('notebook_line','sketch') else '#edf2f4'
        self.cute = style in ('cartoon', 'notebook_smile')
        self.ink = '#394250' if self.hand else '#253544'
        self.width = 1.05 if self.hand else (.85 if style == 'miniature' else 1.25)
        if style == 'sticker':
            self.width = 1.65
        elif style == 'soft':
            self.width = .65
        elif style == 'solid':
            self.width = .5
        self.body = '#d7e0e6'
        self.dark = '#495864'
        self.light = '#f2f6f7'
        self.glass = '#bddce2'
        self.accent = '#68acb0'
        if style in ('cartoon', 'sticker', 'notebook_smile'):
            self.body, self.dark, self.glass, self.accent = '#b9d7dc', '#637891', '#e0f1eb', '#e3aa84'
        elif style in ('notebook_color', 'papercut', 'inkwash'):
            self.body, self.dark, self.glass, self.accent = '#bfcbd0', '#626c7b', '#dce9db', '#d4a17f'
        elif style == 'solid':
            self.body, self.dark, self.glass, self.accent = '#596b7c', '#273746', '#91bdc9', '#96cad0'
        elif style == 'soft':
            self.body, self.dark, self.glass, self.accent = '#d7e2e9', '#708699', '#dbedf0', '#9ecac3'
        self.parts = []
        self.index = 0

    def _attrs(self, fill, width=None, opacity=1):
        if self.line and fill!='none':
            # Opaque, uncolored entities hide rear linework. Glass and real
            # apertures stay transparent, as does everything outside the part.
            fill='none' if fill==self.glass else self.paper
        width = self.width if width is None else width
        stroke = self.ink
        if self.style == 'papercut' and fill != 'none':
            stroke, width = fill, .5
        return (' fill="' + escape(fill, quote=True) + '" stroke="' + stroke +
                '" stroke-width="' + _n(width) + '" stroke-linecap="round" stroke-linejoin="round"' +
                (' opacity="' + _n(opacity) + '"' if opacity != 1 else ''))

    def path(self, data, fill='none', width=None, opacity=1):
        if self.style == 'sticker' and fill != 'none':
            self.parts.append('<path d="'+data+'" fill="none" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"/>')
        self.parts.append('<path d="' + data + '"' + self._attrs(fill, width, opacity) + '/>')

    def poly(self, points, fill='none', width=None, close=True, opacity=1, retrace=True):
        if not points:
            return
        self.index += 1
        data = 'M' + _n(points[0][0]) + ' ' + _n(points[0][1])
        perimeter = 0.
        for i, (x, y) in enumerate(points[1:] + ([points[0]] if close else [])):
            last = points[i]
            length = math.hypot(x-last[0], y-last[1]) if self.hand else 0.
            perimeter += length
            if self.hand:
                # The pen drifts gently to either side of a long stroke. Exact
                # shared endpoints keep joints closed; tiny ports stay legible.
                amount = min(.78 if self.style != 'sketch' else 1.05, length*.035)
                sign = -1 if (self.index+i) % 2 else 1
                nx,ny = ((last[1]-y)/length, (x-last[0])/length) if length else (0.,0.)
                a = amount*sign
                b = -a*(.42 if (self.index+i)%3 else .64)
                data += (' C'+_n(last[0]+(x-last[0])/3+nx*a)+' '+_n(last[1]+(y-last[1])/3+ny*a)
                         +' '+_n(last[0]+(x-last[0])*2/3+nx*b)+' '+_n(last[1]+(y-last[1])*2/3+ny*b)
                         +' '+_n(x)+' '+_n(y))
            else:
                data += ' L' + _n(x) + ' ' + _n(y)
        if close:
            data += ' Z'
        pressure = (.94+(self.index*7%9)*.022) if self.hand else 1.
        self.path(data, fill, (self.width*pressure if width is None and self.hand else width), opacity)
        # Retrace a few long outlines, never every tiny grille cell. This reads
        # as drawn linework while keeping fine openings clean and bounded.
        if retrace and self.hand and self.style in ('notebook_color','notebook_line','notebook_smile','sketch') and close and perimeter>=45:
            self.parts.append('<path d="' + data + '" transform="translate(.32 -.22)"' + self._attrs('none', .28, .45) + '/>')

    def rect(self, x, y, w, h, fill='none', radius=0, width=None, opacity=1):
        if self.hand:
            self.poly([(x+.25,y),(x+w,y+.2),(x+w-.2,y+h),(x,y+h-.2)], fill, width, opacity=opacity)
        else:
            if self.style in ('cartoon', 'sticker', 'soft'):
                radius = max(radius, min(w, h)*.08)
            self.parts.append('<rect x="'+_n(x)+'" y="'+_n(y)+'" width="'+_n(w)+'" height="'+_n(h)+'" rx="'+_n(radius)+'"'+self._attrs(fill,width,opacity)+'/>')

    def ellipse(self, cx, cy, rx, ry, fill='none', width=None, opacity=1):
        if self.hand:
            k = .552285
            self.path('M'+_n(cx+rx)+' '+_n(cy)+' C'+_n(cx+rx)+' '+_n(cy+ry*k+.23)+' '+_n(cx+rx*k)+' '+_n(cy+ry)+' '+_n(cx)+' '+_n(cy+ry)+' C'+_n(cx-rx*k-.15)+' '+_n(cy+ry)+' '+_n(cx-rx)+' '+_n(cy+ry*k)+' '+_n(cx-rx)+' '+_n(cy)+' C'+_n(cx-rx)+' '+_n(cy-ry*k)+' '+_n(cx-rx*k)+' '+_n(cy-ry-.18)+' '+_n(cx)+' '+_n(cy-ry)+' C'+_n(cx+rx*k)+' '+_n(cy-ry)+' '+_n(cx+rx)+' '+_n(cy-ry*k)+' '+_n(cx+rx)+' '+_n(cy)+' Z',fill,width,opacity)
        else:
            self.parts.append('<ellipse cx="'+_n(cx)+'" cy="'+_n(cy)+'" rx="'+_n(rx)+'" ry="'+_n(ry)+'"'+self._attrs(fill,width,opacity)+'/>')

    def line_to(self, x1, y1, x2, y2, width=None, opacity=1):
        self.poly([(x1,y1),(x2,y2)], width=width, close=False, opacity=opacity)

    def face(self, cx, cy, size):
        if self.cute:
            self.parts.append('<g data-art-face="smile">')
            self.ellipse(cx-size*.3,cy,size*.07,size*.12,self.ink,.3)
            self.ellipse(cx+size*.3,cy,size*.07,size*.12,self.ink,.3)
            self.path('M'+_n(cx-size*.18)+' '+_n(cy+size*.25)+' Q'+_n(cx)+' '+_n(cy+size*.48)+' '+_n(cx+size*.18)+' '+_n(cy+size*.25),width=.8)
            self.parts.append('</g>')

    def finish(self):
        content = ''.join(self.parts)
        if self.style == 'inkwash':
            return '<g opacity=".84">'+content+'</g>'
        return content


def _rotor(row, style, x, y, width, height):
    pen = _Pen(style)
    blades = int(row.get('blades', 7))
    hub = float(row.get('hub_ratio', .25))*45
    family = row.get('family','reference')
    leaf = row.get('blade_color', '#617482')
    if family=='bequiet-grooved' and style in ('miniature','classic','solid'):
        # Keep black leaves readable without recoloring the hardware body.
        pen.ink='#75818a'
    if style in ('cartoon','notebook_color','notebook_smile','sticker','papercut','inkwash','soft'):
        leaf = pen.accent
    # A featureless aperture under the leaves gives overlapping fan planes a
    # consistent background. Its circular symmetry is unchanged by rotation.
    if not row.get('open_back'):
        pen.ellipse(50,50,44,44,row.get('aperture_color',pen.dark),.2)
    # Wide pressure leaves, narrower multi-leaf rotors and known joined-tip
    # outlines are different original curves, never sampled manufacturer CAD.
    broad = blades <= 5 or family == 'cm-silencio'
    bend = .65 if pen.hand else 0
    if broad:
        contour = ('M47 '+_n(50-hub)+' C16 35 15 11 37 6 C60 1 82 13 85 29 '
                   'C66 25 67 43 54 '+_n(50-hub+3)+' Z')
    elif family=='noctua-a':
        # Broad swept pressure leaves with a straighter tip, rather than a
        # round flower petal. This remains an original qualitative contour.
        contour = ('M47 '+_n(50-hub)+' C32 30 25 20 30 12 L39 7 '
                   'C52 3 66 8 75 18 L71 23 C59 25 60 36 54 '+_n(50-hub+3)+' Z')
    elif family in ('noctua-sterrox','noctua-g2','msi-lcp','thermaltake-toughfan'):
        contour = ('M48 '+_n(50-hub)+' C31 27 26 14 38 7 C49 3 65 5 74 16 '
                   'C59 18 61 32 55 '+_n(50-hub+4)+' Z')
    elif family in ('bequiet-grooved','fractal-notched','phanteks-t30','phanteks-d30'):
        contour = ('M47 '+_n(50-hub)+' C24 30 26 11 42 7 C58 3 74 10 80 22 '
                   'L74 25 C60 25 61 39 54 '+_n(50-hub+4)+' Z')
    else:
        contour = ('M48 '+_n(50-hub)+' C'+_n(27+bend)+' 30 28 '+_n(11-bend)+' 42 7 '
                   'C59 3 74 12 78 23 C63 24 62 40 54 '+_n(50-hub+3)+' Z')
    if row.get('foil_profile'):
        # Reuse the exact same sampled outline as the 3D leaf; style only paints.
        from assembly_geometry import blade_polygon
        points=blade_polygon(row)
        contour=('M'+' L'.join(_n(50+px*45*1.07/3)+' '+_n(50+py*45*1.07/3) for px,py in points)+' Z') if points else ''
    if pen.hand:
        contour = contour.replace(' 7 C',' 7.35 C').replace(' 23 C',' 22.65 C')
    pen.parts.append('<g data-blade-count="'+str(blades)+'" data-contour="original-reference">')
    if row.get('reverse_blade'):
        pen.parts.append('<g data-foil="reverse-pitch" transform="translate(100 0) scale(-1 1)">')
    for i in range(blades):
        pen.parts.append('<g data-leaf="'+str(i+1)+'" transform="rotate('+_n(i*360/blades)+' 50 50)">')
        if style=='papercut':
            # Cut edges keep overlapping paper leaves legible and rotation
            # visible. Do not let equal fill/stroke merge the rotor into a disc.
            attrs=pen._attrs(leaf,.65).replace('stroke="'+leaf+'"','stroke="'+pen.ink+'"',1)
            pen.parts.append('<path d="'+contour+'"'+attrs+' data-cut-edge="visible"/>')
        else:
            pen.path(contour,leaf,.65)
        if row.get('foil_profile'):
            pass # Legacy decorative strokes are not reused at unrelated coordinates.
        elif family=='noctua-a':
            for offset in (0,3,6):
                pen.path('M'+_n(54+offset)+' 11 Q'+_n(51+offset)+' 15 '+_n(51+offset)+' 20',width=.35,opacity=.6)
        elif family in ('noctua-sterrox','noctua-g2'):
            for offset in (0,3,6):
                pen.path('M'+_n(48+offset)+' 12 Q'+_n(42+offset)+' 23 '+_n(48+offset*.7)+' 31',width=.45,opacity=.55)
        elif family=='bequiet-grooved':
            for offset in range(0,12,3):
                pen.path('M'+_n(35+offset)+' 12 Q'+_n(27+offset)+' 24 '+_n(42+offset*.7)+' 32',width=.45,opacity=.65)
        elif family=='fractal-notched':
            pen.path('M52 33 L48 30 L49 35',width=.65)
        pen.parts.append('</g>')
    if row.get('reverse_blade'):
        pen.parts.append('</g>')
    if row.get('outer_ring'):
        pen.ellipse(50,50,43,43,'none',2.7)
    pen.ellipse(50,50,hub,hub,leaf,.8)
    if row.get('id')=='noctua-nf-a12x15-pwm' and style in ('miniature','classic','solid'):
        pen.ellipse(50,50,hub*.58,hub*.58,'#b8bfc0',.28)
    if family=='noctua-g2':
        for a in range(0,360,60):
            angle=math.radians(a)
            pen.ellipse(50+hub*.52*math.cos(angle),50+hub*.52*math.sin(angle),.65,.65,pen.dark,.25)
    pen.face(50,48,hub)
    pen.parts.append('</g>')
    return dict(x=x,y=y,width=width,height=height,svg=_svg(pen.finish(),True),direction=1)


def _fan_holes(row):
    axes=row.get('mount_pitch_axes_mm')
    if row.get('mount_pitch_axes_verified') and isinstance(axes,(list,tuple)) and len(axes)==2:
        return tuple((.5+sx*axes[0]/row.get('width_mm',row['size_mm'])/2,.5+sy*axes[1]/row['size_mm']/2) for sx in (-1,1) for sy in (-1,1))
    pitch=row.get('mount_pitch_mm')
    if row.get('mount_pitch_verified') and type(pitch) in (int,float) and math.isfinite(pitch):
        return tuple((.5+sx*pitch/row.get('width_mm',row['size_mm'])/2,.5+sy*pitch/row['size_mm']/2) for sx in (-1,1) for sy in (-1,1))
    return ((.085,.085),(.915,.085),(.085,.915),(.915,.915))


def _fan_frame(pen, x, y, size, row):
    if row.get('open_back'):
        _fan_foreground(pen,x,y,size,row)
        return
    from accessory_fan_frame045 import draw_frame
    if draw_frame(pen,x,y,size,row):return
    frame_color=row.get('frame_color',pen.body) if pen.style in ('miniature','classic','solid') else pen.body
    pad_color=('#725549' if row.get('family','').startswith('noctua') else '#35434c') if pen.style in ('miniature','classic','solid') else pen.accent
    if row.get('frame') == 'round':
        # The round Noctua frame still has four projecting mounting ears.
        for dx,dy in ((0,0),(1,0),(0,1),(1,1)):
            pen.rect(x+dx*size*.83,y+dy*size*.83,size*.17,size*.17,frame_color,size*.035,.6)
        pen.ellipse(x+size/2,y+size/2,size*.49,size*.49,frame_color)
    elif row.get('family') in ('corsair-airguide','phanteks-d30','lian-li-sl','lian-li-infinity'):
        cut=size*.1
        pen.poly([(x+cut,y),(x+size-cut,y),(x+size,y+cut),(x+size,y+size-cut),
                  (x+size-cut,y+size),(x+cut,y+size),(x,y+size-cut),(x,y+cut)],frame_color)
    else:
        pen.rect(x,y,size,size,frame_color,size*.06)
    pen.ellipse(x+size/2,y+size/2,size*.437,size*.437,pen.dark,.65)
    if row.get('rgb') and not row.get('frame_rgb_polygon'):
        pen.ellipse(x+size/2,y+size/2,size*.418,size*.418,'none',size*.022,.8)
    if row.get('frame_rgb_ring'):
        pen.ellipse(x+size/2,y+size/2,size*.473,size*.473,'none',size*.025)
    if row.get('frame_rgb_sides') or row.get('family') in ('lian-li-sl','lian-li-infinity','phanteks-d30'):
        for yy in (y+size*.04,y+size*.96):
            pen.line_to(x+size*.19,yy,x+size*.81,yy,size*.022)
        # Interlocking side connectors, kept on the stationary frame.
        pen.rect(x+size*.99,y+size*.39,size*.025,size*.19,pen.accent,.3,.4)
    for dx, dy in _fan_holes(row):
        if row.get('pads'):
            if row.get('pad_style')=='round':pen.ellipse(x+dx*size,y+dy*size,size*.052,size*.052,pad_color,.5)
            else:pen.rect(x+dx*size-size*.045,y+dy*size-size*.045,size*.09,size*.09,pad_color,1,.5)
        pen.ellipse(x+dx*size,y+dy*size,size*.018,size*.018,pen.light,.5)


def _fan_foreground(pen, x, y, size, row):
    """A stationary frame with a real transparent aperture above moving leaves."""
    cx,cy=x+size/2,y+size/2
    radius=size*.437
    color=row.get('frame_color',pen.body) if pen.style in ('miniature','classic','solid') else pen.body
    pad_color=('#725549' if row.get('family','').startswith('noctua') else '#35434c') if pen.style in ('miniature','classic','solid') else pen.accent
    from accessory_fan_frame045 import draw_frame
    if not draw_frame(pen,x,y,size,row):
        if row.get('frame')=='round':
            outer='M'+_n(cx+size*.49)+' '+_n(cy)+' A'+_n(size*.49)+' '+_n(size*.49)+' 0 1 0 '+_n(cx-size*.49)+' '+_n(cy)+' A'+_n(size*.49)+' '+_n(size*.49)+' 0 1 0 '+_n(cx+size*.49)+' '+_n(cy)+' Z'
        else:
            cut=size*.1 if row.get('family') in ('corsair-airguide','phanteks-d30','lian-li-sl','lian-li-infinity') else size*.025
            outer='M'+_n(x+cut)+' '+_n(y)+' L'+_n(x+size-cut)+' '+_n(y)+' L'+_n(x+size)+' '+_n(y+cut)+' L'+_n(x+size)+' '+_n(y+size-cut)+' L'+_n(x+size-cut)+' '+_n(y+size)+' L'+_n(x+cut)+' '+_n(y+size)+' L'+_n(x)+' '+_n(y+size-cut)+' L'+_n(x)+' '+_n(y+cut)+' Z'
        hole=' M'+_n(cx+radius)+' '+_n(cy)+' A'+_n(radius)+' '+_n(radius)+' 0 1 0 '+_n(cx-radius)+' '+_n(cy)+' A'+_n(radius)+' '+_n(radius)+' 0 1 0 '+_n(cx+radius)+' '+_n(cy)+' Z'
        pen.parts.append('<path d="'+outer+hole+'" fill-rule="evenodd"'+pen._attrs(color,.6)+'/>')
        for dx,dy in _fan_holes(row):
            if row.get('pads'):
                if row.get('pad_style')=='round':pen.ellipse(x+dx*size,y+dy*size,size*.052,size*.052,pad_color,.5)
                else:pen.rect(x+dx*size-size*.045,y+dy*size-size*.045,size*.09,size*.09,pad_color,1,.5)
            pen.ellipse(x+dx*size,y+dy*size,size*.018,size*.018,pen.light,.45)
    if row.get('fixed_white_hub_window') and row.get('hub_window_face')=='front':
        pen.parts.append('<g data-window="stationary-front-bearing-reference" data-light="fixed-white">')
        pen.ellipse(cx,cy,size*.104,size*.104,pen.dark,.4)
        ink=pen.ink;pen.ink='#f4f1dc'
        pen.ellipse(cx,cy,size*.096,size*.096,'none',size*.012)
        pen.ink=ink
        for index in range(8):
            angle=index*math.tau/8
            pen.ellipse(cx+size*.06*math.cos(angle),cy+size*.06*math.sin(angle),size*.013,size*.018,'#ad844d' if pen.style in ('miniature','classic','solid') else pen.accent,.2)
        pen.ellipse(cx,cy,size*.03,size*.03,pen.light,.3)
        pen.parts.append('</g>')
    if row.get('hub_display'):
        pen.parts.append('<g data-display="stationary-blank-lcd">')
        pen.ellipse(cx,cy,size*.182,size*.182,pen.light,.7)
        pen.ellipse(cx,cy,size*.164,size*.164,pen.dark,.5)
        pen.parts.append('</g>')
    elif row.get('metal_hub'):
        tone='#b6c5cd' if pen.style in ('miniature','classic','solid') else pen.light
        pen.ellipse(cx,cy,size*.095,size*.095,tone,.6)
    if row.get('frame_rgb_polygon') in (6,12):
        sides=row['frame_rgb_polygon']
        pen.parts.append('<g data-frame-light="stationary-'+str(sides)+'-sided-reference">')
        pen.poly([(cx+size*.472*math.cos(i*math.tau/sides+math.pi/6),cy+size*.472*math.sin(i*math.tau/sides+math.pi/6)) for i in range(sides)],'none',size*.018)
        pen.parts.append('</g>')
    if row.get('directional_grille'):
        pen.parts.append('<g data-grille="stationary-reference">')
        for i in range(12):
            a=i*math.tau/12
            pen.path('M'+_n(cx+radius*.27*math.cos(a))+' '+_n(cy+radius*.27*math.sin(a))+
                     ' Q'+_n(cx+radius*.65*math.cos(a+.2))+' '+_n(cy+radius*.65*math.sin(a+.2))+
                     ' '+_n(cx+radius*math.cos(a+.28))+' '+_n(cy+radius*math.sin(a+.28)),width=.85)
        pen.parts.append('</g>')


def _distinct_case(p, row):
    """Bounded original outlines for documented structures, shared by all styles."""
    from accessory_case_details040 import draw_case
    if draw_case(p,row):return True
    features=set(row.get('features',()))
    if 'tubular_open_frame' in features:
        p.parts.append('<g data-case-structure="tubular-open-frame">')
        for x in (31,74):
            p.path('M'+str(x)+' 88 L'+str(x)+' 20 Q'+str(x)+' 13 '+str(x+6)+' 13 L'+str(x+15)+' 13 Q'+str(x+21)+' 13 '+str(x+21)+' 20 L'+str(x+21)+' 80',width=3.1)
        p.poly([(39,28),(76,23),(76,77),(39,82)],p.dark,.7)
        for yy in (32,66):p.line_to(33,yy+7,90,yy-3,2)
        for yy in (23,81):p.line_to(33,yy+8,74,yy,2.9)
        p.rect(48,38,20,25,p.body,1,.6)
        p.face(58,50,8)
        p.parts.append('</g>')
    elif 'horizontal_test_bench' in features:
        p.parts.append('<g data-case-structure="horizontal-test-bench">')
        for xx,yy in ((24,45),(77,30),(101,51),(47,66)):
            p.rect(xx-2,yy,4,20,p.dark,1,.6)
            p.ellipse(xx,yy+20,3.5,1.4,p.body,.6)
        outline=[(22,43),(77,27),(103,49),(47,66)]
        p.poly([(xx,yy+3) for xx,yy in outline],p.dark,.7)
        p.poly(outline,p.body,.9)
        for xx,yy in ((37,43),(62,36),(61,54),(85,46)):
            p.ellipse(xx,yy,2,1.1,p.dark,.45)
            p.line_to(xx,yy,xx,yy-5,1.2)
        p.poly([(30,44),(42,40),(47,44),(35,48)],p.dark,.5)
        p.face(67,48,6)
        p.parts.append('</g>')
    elif 'passive_finned_cube' in features:
        p.parts.append('<g data-case-structure="passive-finned-cube">')
        p.poly([(26,29),(47,16),(96,26),(75,39)],p.light,.8)
        p.poly([(75,39),(96,26),(96,77),(75,90)],p.dark,.8)
        p.poly([(26,29),(75,39),(75,90),(26,80)],p.body,.8)
        for i in range(11):
            xx=29+i*4.2
            p.line_to(xx,31+i*.86,xx,79+i*.86,1)
        for i in range(6):
            xx=78+i*3
            p.line_to(xx,38-i*1.85,xx,87-i*1.85,.9)
        p.poly([(33,81),(71,89),(89,79),(89,83),(71,94),(33,86)],p.dark,.7)
        p.face(52,59,8)
        p.parts.append('</g>')
    elif 'fabric_column' in features:
        p.parts.append('<g data-case-structure="fabric-rounded-column">')
        p.rect(41,12,38,76,p.body,8,.9)
        p.ellipse(60,17,18,6,p.dark,.75)
        for i in range(10):
            xx=44+i*3.5
            p.line_to(xx,27,xx,79,.38,.55)
        for yy in range(30,79,7):p.line_to(44,yy,76,yy,.3,.42)
        for yy in (14,17,20):p.line_to(47,yy,73,yy,.55)
        p.rect(44,83,32,6,p.dark,2,.6)
        p.face(60,53,8)
        p.parts.append('</g>')
    elif 'front_gpu_chamber' in features:
        p.parts.append('<g data-case-structure="front-gpu-chamber">')
        p.poly([(30,17),(48,9),(89,9),(71,17)],p.dark,.8)
        p.poly([(71,17),(89,9),(89,82),(71,90)],p.glass,.8)
        p.rect(30,17,41,73,p.body,1,.8)
        p.rect(33,23,15,59,p.dark,1,.6)
        for xx in (36,45):p.line_to(xx,25,xx,80,.7)
        for yy in range(28,81,4):p.line_to(34,yy,47,yy,.45)
        p.rect(51,24,17,57,p.glass,1,.65)
        p.poly([(31,89),(73,89),(87,83),(87,89),(73,95),(31,95)],p.dark,.7)
        p.face(60,53,6)
        p.parts.append('</g>')
    elif 'origami_vent_tabs' in features:
        p.parts.append('<g data-case-structure="folded-vent-tabs">')
        p.poly([(32,17),(49,8),(89,16),(72,25)],p.light,.8)
        p.poly([(72,25),(89,16),(89,80),(72,90)],p.dark,.8)
        p.poly([(32,17),(72,25),(72,90),(32,82)],p.body,.8)
        for yy in range(30,75,13):
            for xx in (39,54):
                p.poly([(xx,yy),(xx+10,yy+2),(xx+5,yy+12)],p.dark,.5)
                p.poly([(xx,yy),(xx+5,yy+4),(xx+5,yy+12)],p.accent,.4)
        p.face(61,80,5)
        p.parts.append('</g>')
    elif 'reversible_u_frame' in features:
        p.parts.append('<g data-case-structure="u-frame-feet-down">')
        p.rect(29,19,53,64,p.dark,2,.8)
        p.rect(32,23,47,55,p.glass,2,.7)
        p.path('M24 13 L24 82 Q24 91 33 91 L80 91 Q89 91 89 82 L89 13',width=3.3)
        for yy in range(30,77,6):p.line_to(33,yy,44,yy,.55)
        p.face(61,53,9)
        p.parts.append('</g>')
    else:return False
    return True


def _case(row, style):
    p = _Pen(style)
    if _distinct_case(p,row):return p.finish(),[],''
    dims = row['dimensions_mm']
    features = set(row.get('features',()))
    height = 72
    width = max(25,min(66,height*dims['width']/dims['height']))
    if row['layout'] in ('horizontal','compact'):
        width = min(72,max(39,width))
        height = min(59,width*dims['height']/dims['width'])
    if 'slim_itx' in features:
        width,height=24,63
    x,y = (120-width-17)/2,(94-height)/2
    side = 17
    wood = '#aa815d' if not p.line else 'none'
    if row['layout'] == 'open_frame':
        # A plate, glass standoffs and feet replace the closed tower envelope.
        if 'winged_open_frame' in features:
            p.poly([(38,21),(28,12),(10,25),(18,78),(38,75)],p.dark)
            p.poly([(82,21),(92,12),(110,25),(102,78),(82,75)],p.dark)
            for xx in (20,91):
                p.rect(xx,29,9,37,p.body,1)
                for yy in range(33,65,5):
                    p.line_to(xx+1,yy,xx+8,yy,.5)
            p.rect(37,16,46,65,p.glass,1)
        else:
            p.rect(28,16,57,67,p.dark,1)
            p.rect(22,20,57,65,p.glass,1,.7,.75)
            for xx,yy in ((24,23),(77,23),(24,82),(77,82)):
                p.ellipse(xx,yy,1.5,1.5,p.light,.6)
                p.line_to(xx,yy,xx+5,yy-4,.65)
        for xx in (32,76):
            p.poly([(xx,79),(xx+8,79),(xx+12,91),(xx-3,91)],p.dark)
        p.rect(46,31,24,32,p.body,1,.55)
        for yy in (67,72):
            p.rect(42,yy,33,3,p.dark,.4,.5)
        p.face(58,47,10)
        return p.finish(),[],''
    if 'octagonal_front' in features:
        # Faceted glass and clipped front corners are characteristic of The Tower.
        bevel=width*.19
        p.poly([(x+bevel,y),(x+width-bevel,y),(x+width,y+7),(x+width,y+height-7),
                (x+width-bevel,y+height),(x+bevel,y+height),(x,y+height-7),(x,y+7)],p.dark)
        p.poly([(x+bevel+1,y+9),(x+width-bevel-1,y+9),(x+width-3,y+14),
                (x+width-3,y+height-15),(x+width-bevel-1,y+height-9),
                (x+bevel+1,y+height-9),(x+3,y+height-15),(x+3,y+14)],p.glass)
        for xx in (x+bevel,x+width-bevel):
            p.line_to(xx,y+9,xx,y+height-9,.8)
        for yy in (y+4,y+height-5):
            p.line_to(x+bevel+2,yy,x+width-bevel-2,yy,.6)
        p.face(x+width/2,y+height*.56,11)
        return p.finish(),[],''
    if 'angular_glass_corner' in features:
        # The front glass, chamfer glass and side glass occupy three separate
        # planes. A five-sided top and a clipped base expose the actual corner
        # facet rather than decorating an otherwise rectangular tower.
        bevel=min(12,width*.23)
        edge=x+width-bevel
        corner=x+width+3
        right=x+width+side
        p.parts.append('<g data-case-facet="angular-glass-corner">')
        p.poly([(x,y),(x+side,y-7),(right,y-7),(corner,y-4),(edge,y)],p.dark)
        p.poly([(corner,y-4),(right,y-7),(right,y+height-7),(corner,y+height-4)],p.dark)
        p.rect(x,y,edge-x,height,p.body,1)
        p.rect(x+2,y+5,edge-x-4,height-11,p.glass,1,.65)
        p.poly([(edge,y),(corner,y-4),(corner,y+height-4),(edge,y+height)],p.body,.9)
        p.poly([(edge+1,y+5),(corner-1,y+1),(corner-1,y+height-10),(edge+1,y+height-6)],p.glass,.7)
        p.poly([(corner+1,y+2),(right-3,y-1),(right-3,y+height-14),(corner+1,y+height-10)],p.glass,.65)
        # The rear hardware chamber remains a dark, distinctly separate strip.
        p.poly([(right-5,y-2),(right-1,y-3),(right-1,y+height-9),(right-5,y+height-8)],p.body,.6)
        p.poly([(x,y+height-7),(edge,y+height-7),(corner,y+height-11),
                (right,y+height-14),(right,y+height-7),(corner,y+height-4),(edge,y+height),(x,y+height)],p.dark,.7)
        p.line_to(x+6,y+10,edge-5,y+height-17,.45,.65)
        p.line_to(edge+3,y+10,corner-3,y+height-18,.35,.55)
        for xx in range(5,int(width)-4,5):
            p.line_to(x+xx,y-1,x+xx+8,y-5,.4)
        for foot in (x+4,edge-8):
            p.rect(foot,y+height,6,3,p.dark,.6)
        p.ellipse(x+7,y+2,1,1,p.accent,.5)
        p.face(x+(edge-x)/2,y+height*.59,11)
        p.parts.append('</g>')
        return p.finish(),[],''
    p.poly([(x,y),(x+side,y-7),(x+width+side,y-7),(x+width,y)],p.light)
    p.poly([(x+width,y),(x+width+side,y-7),(x+width+side,y+height-7),(x+width,y+height)],p.dark)
    if 'curved_front_glass' in features:
        p.path('M'+_n(x+4)+' '+_n(y)+' Q'+_n(x-1)+' '+_n(y)+' '+_n(x)+' '+_n(y+8)+
               ' L'+_n(x)+' '+_n(y+height-7)+' Q'+_n(x)+' '+_n(y+height)+' '+_n(x+7)+' '+_n(y+height)+
               ' L'+_n(x+width)+' '+_n(y+height)+' L'+_n(x+width)+' '+_n(y)+' Z',p.body)
    else:
        p.rect(x,y,width,height,p.body,1)
    panels = row['panels']
    inset=3
    if 'front_wood_frame' in features:
        p.rect(x+1,y+2,width-2,height-4,wood,1)
        p.rect(x+4,y+5,width-8,height-10,p.dark,1,.6)
        inset=5
    if panels['front'] in ('glass','angled_glass'):
        p.rect(x+3,y+4,width-6,height-9,p.glass,1)
        p.line_to(x+5,y+8,x+width-6,y+height-15,.45,.6)
        p.line_to(x+5,y+13,x+width-10,y+height-17,.35,.45)
        if 'angular_glass_corner' in features:
            p.line_to(x+width-9,y+4,x+width-9,y+height-5,.8)
            p.poly([(x+width-9,y+4),(x+width-3,y+4),(x+width-3,y+height-5),(x+width-9,y+height-5)],p.light,.45,opacity=.35)
        elif 'curved_front_glass' in features:
            p.path('M'+_n(x+6)+' '+_n(y+5)+' Q'+_n(x+1)+' '+_n(y+height*.45)+' '+_n(x+7)+' '+_n(y+height-7),width=.65)
    elif panels['front'] in ('mesh','slotted','wood'):
        p.rect(x+inset,y+4,width-inset*2,height-9,p.dark,.5,.55)
        if panels['front']=='wood':
            for offset in range(5,int(width)-3,4):
                p.line_to(x+offset,y+5,x+offset,y+height-6,2.1)
                if not p.line:
                    p.parts.append('<path d="M'+_n(x+offset)+' '+_n(y+5)+' L'+_n(x+offset)+' '+_n(y+height-6)+'" stroke="'+wood+'" stroke-width="1.5"/>')
        elif any(f in features for f in ('triangular_front_mesh','front_triangle_grid')):
            for yy in range(7,int(height)-5,7):
                for xx in range(5,int(width)-7,7):
                    p.poly([(x+xx,y+yy+5),(x+xx+3,y+yy),(x+xx+6,y+yy+5)],p.body,.35)
        elif 'front_square_grid' in features:
            for yy in range(7,int(height)-6,6):
                for xx in range(6,int(width)-6,6):
                    p.rect(x+xx,y+yy,2.5,2.5,p.body,.25,.35)
        elif panels['front']=='slotted':
            spacing=5 if 'wide_front_grille' in features else 4
            for offset in range(5,int(width)-3,spacing):
                if 'open_front_grille' in features:
                    p.poly([(x+offset,y+6),(x+width/2+(offset-width/2)*.55,y+height*.48),
                            (x+offset,y+height-6)],width=1.3,close=False)
                else:
                    p.line_to(x+offset,y+5,x+offset,y+height-6,1.1)
        else:
            # A simple open mesh field is deliberately not a precise hole count.
            for yy in range(8,int(height)-5,5):
                p.line_to(x+inset+2,y+yy,x+width-inset-2,y+yy,.45,.75)
            for xx in range(inset+3,int(width)-inset-2,5):
                p.line_to(x+xx,y+6,x+xx,y+height-7,.35,.6)
        if 'front_diagonal_rails' in features:
            for start,end in ((.18,.74),(.74,.4),(.4,.92)):
                p.line_to(x+width*start,y+6,x+width*end,y+height-7,1.6)
    if panels['left'] == 'glass':
        p.poly([(x+width+2,y+3),(x+width+side-3,y-2),(x+width+side-3,y+height-10),(x+width+2,y+height-5)],p.glass,.6)
        if 'bottom_psu_shroud' in features:
            p.poly([(x+width+2,y+height-17),(x+width+side-3,y+height-22),
                    (x+width+side-3,y+height-10),(x+width+2,y+height-5)],p.body,.5)
        elif 'top_psu_shroud' in features:
            p.poly([(x+width+2,y+3),(x+width+side-3,y-2),(x+width+side-3,y+10),(x+width+2,y+15)],p.body,.5)
    elif panels['left'] in ('mesh','slotted','vented'):
        for yy in range(6,int(height)-9,4):
            p.line_to(x+width+3,y+yy,x+width+side-3,y+yy-4,.55)
    if 'side_ventilation' in features:
        for yy in range(int(height*.33),int(height*.75),3):
            p.line_to(x+width+4,y+yy,x+width+side-3,y+yy-4,.65)
    if 'perforated_psu_shroud' in features:
        for yy in (height-15,height-11):
            for xx in range(4,side-2,4):
                p.line_to(x+width+xx,y+yy-xx*.3,x+width+xx+1.5,y+yy-xx*.3-.5,.55)
    if 'angled_front_right_intake' in features:
        p.poly([(x+width-5,y+5),(x+width+8,y),(x+width+8,y+height-10),(x+width-5,y+height-5)],p.dark,.7)
        for yy in range(10,int(height)-9,4):
            p.line_to(x+width-3,y+yy,x+width+6,y+yy-3,.6)
    if panels['top']=='glass':
        p.poly([(x+4,y-1),(x+side,y-5),(x+width+side-4,y-5),(x+width,y-1)],p.glass,.5)
    elif panels['top']=='mesh':
        for xx in range(6,int(width)-2,5):
            p.line_to(x+xx,y-1,x+xx+9,y-5,.45)
    if 'front_wood_strip' in features:
        p.rect(x+1,y+height-9,width-2,6,wood,.5,.5)
    if 'front_wood_io_trim' in features:
        p.rect(x+width-7,y+4,4,height-9,wood,.5,.5)
    if 'front_wood_panel' in features:
        p.rect(x+3,y+4,width-6,height*.42,wood,.5,.6)
        p.line_to(x+width*.5,y+height*.5,x+width*.5,y+height-5,.7)
    if 'side_bottom_mesh_band' in features:
        for yy in (height-11,height-8):
            p.line_to(x+width+2,y+yy,x+width+side-3,y+yy-4,.65)
    if 'front_round_display' in features:
        p.ellipse(x+width/2,y+height*.44,width*.19,width*.19,p.glass,.8)
        p.ellipse(x+width/2,y+height*.44,width*.12,width*.12,'none',.5)
    if 'side_status_screen' in features:
        p.poly([(x+width+4,y+height-18),(x+width+12,y+height-21),
                (x+width+12,y+height-13),(x+width+4,y+height-10)],p.dark,.6)
        p.line_to(x+width+6,y+height-14,x+width+10,y+height-15,.7)
    if 'external_exoskeleton' in features or 'diagonal_frame_rails' in features:
        for a,b in ((0,1),(1,0)):
            p.line_to(x+width*a,y+7,x+width*b,y+height-7,2.7)
    if 'wide_external_frame' in features:
        for xx in (x-2,x+width+2):
            p.line_to(xx,y+5,xx,y+height-5,2.8)
    if 'carry_handle' in features:
        p.poly([(x+width*.24,y-2),(x+width*.24,y-9),(x+width*.71,y-9),(x+width*.71,y-2)],width=2.4,close=False)
    if 'fabric_carry_straps' in features:
        for xx in (x+width*.2,x+width*.75):
            p.path('M'+_n(xx)+' '+_n(y-1)+' Q'+_n(xx+4)+' '+_n(y-11)+' '+_n(xx+11)+' '+_n(y-5),width=2.8)
    if 'vertical_front_light_strips' in features:
        for xx in (x+2,x+width-2):
            p.line_to(xx,y+7,xx,y+height-7,1.5)
    if 'top_bottom_light_strips' in features:
        for yy in (y+1.5,y+height-2):
            p.line_to(x+3,yy,x+width-3,yy,1.2)
    if 'translucent_base' in features:
        p.rect(x-2,y+height-1,width+5,5,p.glass,1,.7)
    if 'front_psu_mount' in features:
        p.rect(x+width+5,y+3,7,14,p.body,.5,.5)
    if 'wood_top_panel' in features:
        top_tone='#aa815d' if style in ('miniature','classic','solid') else p.accent
        p.parts.append('<g data-case-detail="vented-wood-top">')
        p.poly([(x+1,y-1),(x+side,y-7),(x+width+side-2,y-7),(x+width-1,y-1)],top_tone,.7)
        for index in range(6):
            xx=x+6+index*(width-12)/6
            p.line_to(xx,y-2,xx+9,y-5,.65)
        p.parts.append('</g>')
    for foot in (x+4,x+width-10):
        p.rect(foot,y+height,6,3,p.dark,.6)
    p.ellipse(x+width-6,y+2,1,1,p.accent,.5)
    if 'top_io' in features:
        for xx in (x+width*.35,x+width*.48):
            p.line_to(xx,y-2,xx+2,y-3,.8)
    p.face(x+width/2,y+height*.62,12)
    return p.finish(),[],''


def _fan(row, style):
    p=_Pen(style)
    _fan_frame(p,23,13,74,row)
    extra=max(0,row.get('width_mm',row['size_mm'])/row['size_mm']-1)*37
    if extra:
        for xx in (23-extra,97):p.rect(xx,18,extra,64,p.body,.4,.5)
    fg=_Pen(style)
    if row.get('stator_vanes'):
        # Air-guide stators are stationary, behind the impeller in this front view.
        for i in range(row['stator_vanes']):
            a=math.radians(i*360/row['stator_vanes'])
            p.line_to(60+12*math.cos(a),50+12*math.sin(a),60+30*math.cos(a+.18),50+30*math.sin(a+.18),.8,.65)
    _fan_foreground(fg,23,13,74,row)
    return p.finish(),[_rotor(row,style,28,18,64,64)],fg.finish()


def _cooler_fan(row):
    from cooling_pack_runtime045 import bundled_fan
    fan=bundled_fan(row) or cooling_catalog.get_fan(row.get('fan_model'))
    if not fan:
        # Explicit bundled/reference leaf layout, not an invented retail identity.
        size=row.get('fan_reference_mm',120)
        fan=dict(size_mm=size,width_mm=size,depth_mm=row.get('fan_reference_depth_mm',25 if size>=100 else 15),
                 family=row.get('fan_family','bundled-reference'),blades=row.get('fan_reference_blades',7),
                 hub_ratio=.25,blade_count_verified=row.get('fan_blade_count_verified',False),frame='square',outer_ring=row.get('fan_outer_ring',False),
                 frame_color='#35434d',blade_color='#60727d',
                 rgb=bool(row.get('fan_reference_rgb')),reference_details=True)
    fan['open_back']=True
    return fan


def _pump(p, fg, row, cx, cy, scale=1):
    """Draw documented exterior family; internal pump/VRM impellers stay hidden."""
    family=row.get('pump_style','round')
    w,h=32*scale,25*scale
    if row.get('pump_dimensions_verified'):
        dims=row['pump_reference_mm']
        h=max(20,min(33,32*dims['depth']/dims['width']))*scale
    if family=='tryx_panorama':
        p.poly([(cx-w*.6,cy-h*.55),(cx-w*.32,cy-h*.8),(cx+w*.6,cy-h*.45),(cx+w*.6,cy+h*.43),(cx-w*.3,cy+h*.64),(cx-w*.6,cy+h*.35)],p.dark,.9)
        p.path('M'+_n(cx-w*.55)+' '+_n(cy-h*.50)+' Q'+_n(cx-w*.4)+' '+_n(cy-h*.66)+' '+_n(cx-w*.28)+' '+_n(cy-h*.51)+' L'+_n(cx+w*.53)+' '+_n(cy-h*.28)+' L'+_n(cx+w*.53)+' '+_n(cy+h*.35)+' L'+_n(cx-w*.28)+' '+_n(cy+h*.55)+' Q'+_n(cx-w*.47)+' '+_n(cy+h*.57)+' '+_n(cx-w*.55)+' '+_n(cy+h*.3)+' Z',p.glass,.7)
        p.line_to(cx-w*.28,cy-h*.48,cx-w*.28,cy+h*.49,.55)
    elif family=='ek_nucleus':
        p.rect(cx-w/2,cy-h/2,w,h,p.dark,3)
        p.ellipse(cx+1,cy,w*.43,h*.49,p.body,.8)
        p.ellipse(cx+1,cy,w*.35,h*.40,'none',1.4)
    elif family in ('xpg_infinity','deepcool_lt_mirror'):
        p.poly([(cx-w/2,cy-h/2),(cx-w*.28,cy-h*.76),(cx+w*.63,cy-h*.55),(cx+w/2,cy-h/2)],p.light,.7)
        p.poly([(cx+w/2,cy-h/2),(cx+w*.63,cy-h*.55),(cx+w*.63,cy+h*.3),(cx+w/2,cy+h/2)],p.dark,.7)
        p.rect(cx-w/2,cy-h/2,w,h,p.dark,2,.8)
        for ratio in (.36,.25,.14):p.rect(cx-w*ratio,cy-h*ratio,w*ratio*2,h*ratio*2,'none',1,.65)
        if family=='deepcool_lt_mirror':
            p.poly([(cx+w*.51,cy-h*.36),(cx+w*.61,cy-h*.41),(cx+w*.61,cy+h*.24),(cx+w*.51,cy+h*.38)],p.glass,.5)
    elif family in ('nzxt_lcd','nzxt_infinity','aorus_round_lcd','lianli_infinity','thermaltake_mirror','id_white_ring','arctic_vrm','cm_dual_chamber','fractal_lumen'):
        p.ellipse(cx,cy+3*scale,w*.51,h*.5,p.dark)
        p.ellipse(cx,cy,w*.51,h*.5,p.body)
        if family=='arctic_vrm':
            # LF III has an exterior radial vent crown. Its visible crown is
            # stationary; the documented internal VRM fan is not guessed here.
            for i in range(20):
                a=math.radians(i*18)
                p.line_to(cx+w*.33*math.cos(a),cy+h*.33*math.sin(a),
                          cx+w*.48*math.cos(a),cy+h*.47*math.sin(a),.8)
            p.ellipse(cx,cy,w*.29,h*.29,p.dark,.6)
            for xx in (cx-w*.22,cx+w*.22):
                p.path('M'+_n(xx)+' '+_n(cy-h*.4)+' Q'+_n(xx-5*scale)+' '+_n(cy-h*.77)+' '+_n(xx-9*scale)+' '+_n(cy-h*.67),width=2.2)
        else:
            p.ellipse(cx,cy,w*.36,h*.36,p.dark if family in ('nzxt_lcd','aorus_round_lcd') else p.glass,.7)
            if family in ('lianli_infinity','nzxt_infinity'):
                for ratio in (.28,.2):
                    p.ellipse(cx,cy,w*ratio,h*ratio,'none',.55)
    elif family=='corsair_lcd':
        p.rect(cx-w*.49,cy-h*.33,w*.98,h*.78,p.dark,3,.7)
        p.rect(cx-w*.49,cy-h*.43,w*.98,h*.73,p.body,3,.7)
        p.ellipse(cx,cy-h*.08,w*.47,h*.50,p.dark,.7)
        p.ellipse(cx,cy-h*.08,w*.43,h*.46,p.accent,.5)
        p.ellipse(cx,cy-h*.08,w*.39,h*.42,p.dark,.6)
    elif family in ('corsair_octagon','asus_tuf_hex'):
        cut=w*(.18 if family=='corsair_octagon' else .25)
        p.poly([(cx-w/2+cut,cy-h/2),(cx+w/2-cut,cy-h/2),(cx+w/2,cy-h/2+cut*.7),
                (cx+w/2,cy+h/2-cut*.7),(cx+w/2-cut,cy+h/2),(cx-w/2+cut,cy+h/2),
                (cx-w/2,cy+h/2-cut*.7),(cx-w/2,cy-h/2+cut*.7)],p.body)
        p.rect(cx-w*.3,cy-h*.3,w*.6,h*.6,p.glass,1,.6)
    else:
        tall=family in ('asus_lcd','msi_lcd','deepcool_lcd')
        if tall:
            p.poly([(cx-w/2,cy-h/2),(cx-w/2+5*scale,cy-h/2-6*scale),
                    (cx+w/2+5*scale,cy-h/2-6*scale),(cx+w/2,cy-h/2)],p.light,.7)
        p.rect(cx-w/2,cy-h/2,w,h,p.body,3)
        p.rect(cx-w*.37,cy-h*.34,w*.74,h*.68,p.glass,2,.6)
        if 'mirror' in family or family=='xc7_block':
            for ratio in (.27,.18):
                p.rect(cx-w*ratio,cy-h*ratio,w*ratio*2,h*ratio*2,'none',1,.5)
        elif tall:
            # Abstract display strokes, no invented telemetry, digits or logos.
            p.path('M'+_n(cx-w*.27)+' '+_n(cy+h*.12)+' L'+_n(cx-w*.12)+' '+_n(cy-h*.12)+
                   ' L'+_n(cx+w*.04)+' '+_n(cy+h*.06)+' L'+_n(cx+w*.27)+' '+_n(cy-h*.18),width=.8)
        if family=='phanteks_bridge':
            p.rect(cx-w*.45,cy-h*.2,w*.9,h*.4,p.accent,2,.65)
        if family=='alphacool_square':
            for dx in (-.36,.36):
                for dy in (-.34,.34):p.ellipse(cx+w*dx,cy+h*dy,.8,.8,p.light,.4)
    if row.get('pump_fixed_white'):
        ink=p.ink;p.ink='#f4f1dc'
        p.line_to(cx-w*.12,cy,cx+w*.12,cy,.9)
        p.ink=ink
    if family=='msi_radiator_pump':
        # Here the remote piece is a CPU block; the pump is in the radiator.
        p.rect(cx-7*scale,cy-5*scale,14*scale,10*scale,p.dark,1,.5)
    if row.get('vrm_fan') and family!='arctic_vrm':
        for i in range(5):
            fg.line_to(cx-w*.3+i*w*.15,cy+h*.37,cx-w*.3+i*w*.15,cy+h*.47,.6)
    p.face(cx,cy-1*scale,9*scale)


def _cooler(row, style):
    p=_Pen(style)
    fg=_Pen(style)
    rotors=[]
    from accessory_cooling_details040 import draw_air
    from accessory_cooling_details045 import draw_center,draw_low_profile
    custom=draw_center(p,fg,row,style,_cooler_fan,_rotor)
    if custom is None:custom=draw_low_profile(p,fg,row,style,_cooler_fan,_rotor)
    if custom is None:custom=draw_air(p,fg,row,style,_cooler_fan,_rotor)
    if custom is not None:return p.finish(),custom,fg.finish()
    fan=_cooler_fan(row)
    count=row.get('fan_count',1)
    if row['kind']=='passive_tower':
        p.parts.append('<g data-cooler-structure="thirteen-passive-fins">')
        original=style in ('miniature','classic','solid')
        tone=row.get('fin_color',p.body) if original else p.body
        for index in range(row['documented_fin_count']):
            xx=24+index*4.0;yy=28-index*.85
            p.poly([(xx,yy),(xx+17,yy-8),(xx+17,yy+45),(xx,yy+54)],tone,.55)
            for yy_hole in (yy+8,yy+23,yy+38):p.ellipse(xx+8.5,yy_hole,1.7,2.4,p.dark,.35)
        for index in range(row.get('heatpipes',0)):
            xx=34+index*6
            p.path('M'+str(xx)+' 78 Q'+str(xx)+' 87 61 88',width=1)
        p.rect(47,87,28,4,p.light,1,.7)
        p.face(72,47,6)
        p.parts.append('</g>')
        return p.finish(),[],''
    if row['kind'] in ('aio','custom_loop'):
        radiator=row['radiator_mm']
        radiator_width=min(98,45+53*(radiator['length']-156)/(458-156))
        scale=radiator_width/radiator['length']
        size=row.get('fan_reference_mm',120)*scale
        if row['kind']=='custom_loop':
            radiator_width=77
            scale=radiator_width/radiator['length']
            size=120*scale
        left=(120-radiator_width)/2
        top=12
        rh=radiator['width']*scale+4
        # Visible end tanks and thickness distinguish 120/240/280/360/420.
        p.rect(left,top,radiator_width,rh,p.dark,2)
        p.rect(left,top+rh,radiator_width,max(2,radiator['thickness']*scale*.42),p.body,.5,.7)
        first=left+(radiator_width-size*count)/2
        for i in range(count):
            fx=first+i*size;fy=top+2
            _fan_frame(p,fx,fy,size,fan)
            inset=size*.07
            rotors.append(_rotor(fan,style,fx+inset,fy+inset,size-2*inset,size-2*inset))
            _fan_foreground(fg,fx,fy,size,fan)
        pipe_x=left+radiator_width-3
        pipe_y=top+rh
        if row['kind']=='custom_loop':
            p.path('M'+_n(left+2)+' '+_n(pipe_y)+' C13 56 17 83 39 79',width=2.6)
            p.path('M58 78 C67 88 90 91 91 77 L91 57',width=2.6)
            p.path('M91 56 C104 55 108 48 '+_n(pipe_x)+' '+_n(pipe_y),width=2.6)
            # Explicit referenced D5 reservoir combo, not an all-in-one pump.
            p.rect(82,49,19,28,p.glass,2,.7)
            p.ellipse(91.5,49,9.5,3,p.light,.7)
            p.rect(81,76,21,10,p.dark,2,.7)
            p.ellipse(91.5,76,9.5,3,p.body,.65)
            p.line_to(86,56,86,69,.65)
            _pump(p,fg,row,45,73,.77)
        else:
            # Tube routing is illustrative and does not claim measured bends.
            p.path('M'+_n(pipe_x)+' '+_n(pipe_y)+' C111 49 109 76 77 73',width=3.1)
            p.path('M'+_n(pipe_x-5)+' '+_n(pipe_y)+' C102 47 104 66 77 67',width=3.1)
            if row.get('pump_location')=='radiator':
                p.rect(left+radiator_width*.45,top+rh-3,10,4,p.body,.6,.65)
            _pump(p,fg,row,59,71)
    else:
        towers=2 if row['kind']=='dual_tower' else 1
        low=row['kind'].startswith('stock') or row['kind']=='low_profile'
        original=style in ('miniature','classic','solid')
        fin=row.get('fin_color',p.body) if original else p.body
        copper=row.get('pipe_color','#b89a77') if original else p.accent
        if low:
            if row.get('fin_style')=='radial':
                p.ellipse(60,55,34,28,fin,.7)
                for i in range(24):
                    a=math.radians(i*15)
                    p.line_to(60+20*math.cos(a),55+17*math.sin(a),60+33*math.cos(a),55+27*math.sin(a),.55)
                p.ellipse(60,43,30,25,p.dark,.8)
                # Top-down rotor plane remains an ellipse, never a 3-D shear.
                rotors.append(_rotor(fan,style,32,20,56,46))
                fg.ellipse(60,43,29,24,'none',1)
                if row['kind']=='stock_intel':
                    fg.ellipse(60,43,29.7,24.7,'none',1)
                for xx,yy in ((27,27),(89,27),(27,67),(89,67)):
                    p.rect(xx,yy,5,8,p.dark,1,.6)
            else:
                p.rect(26,30,68,45,fin,1)
                for yy in range(39,75,3):
                    p.line_to(28,yy,92,yy,.5)
                for offset in range(max(0,int(row.get('heatpipes',0)))):
                    xx=34+offset*7
                    p.path('M'+_n(xx)+' 71 Q'+_n(xx-7)+' 81 '+_n(xx+4)+' 82 L'+_n(xx+8)+' 82',copper,.7)
                _fan_frame(p,30,17,60,fan)
                rotors.append(_rotor(fan,style,34,21,52,52))
                _fan_foreground(fg,30,17,60,fan)
            p.rect(46,83,28,4,copper,1,.7)
        else:
            total=61 if towers==2 else 52
            left=29
            top=20 if row.get('dimensions_mm',{}).get('height',160)>160 else 24
            bottom=78
            tw=42 if towers==2 else total
            for i in range(towers):
                # Towers occupy depth: the rear stack rises to the right in the
                # same compact perspective as the rear fan, never side by side.
                xx=left+(towers-1-i)*17
                yy=top+i*11
                if row.get('asymmetric'):
                    xx+=i*2
                p.rect(xx,yy,tw,bottom-yy-i*2,fin,1)
                for line_y in range(int(yy)+4,bottom-i*2-1,3):
                    p.line_to(xx+1,line_y,xx+tw-1,line_y,.45)
                if row.get('fin_style')=='checker_cut':
                    for dx in range(5,int(tw)-4,8):
                        p.line_to(xx+dx,yy+2,xx+dx,yy+10,.5)
            pipes=int(row.get('heatpipes',0))
            for i in range(pipes):
                xx=left+7+i*(total-14)/max(1,pipes-1)
                p.path('M'+_n(xx)+' 77 Q'+_n(xx)+' 85 59 85',width=1.4)
                if row.get('top_style') in ('exposed_caps','asymmetric_caps',None):
                    p.ellipse(xx,top-1,1.2,1.4,copper,.45)
            top_style=row.get('top_style','')
            if top_style not in ('exposed_caps','asymmetric_caps',''):
                p.rect(left-1,top-3,total+2,10,fin,1,.8)
                if top_style in ('matrix_caps','mesh_bridge','mesh_bridge_rgb','stealth_caps'):
                    for xx in range(int(left)+4,int(left+total)-2,5):
                        p.line_to(xx,top-1,xx,top+4,.5)
                if top_style=='mesh_bridge_rgb':
                    p.rect(left+6,top-2,total-12,3,p.accent,1,.6)
                if top_style=='assassin_shell':
                    p.rect(left-3,top-4,total+6,13,fin,2,.8)
                    p.line_to(left+4,top+2,left+total-4,top+2,.6)
            # Front/rear fans overlap in depth; two 140 mm fans must not appear
            # beside each other across a 150 mm wide dual-tower cooler.
            fan_sizes=row.get('fan_sizes',[row.get('fan_reference_mm',120)]*count)
            base_size=43 if count==2 else 46
            starts=[(48,26),(29,38)] if count==2 else [(33,34)]
            for i in range(count):
                # Listed sizes identify front then centre on mixed-fan coolers;
                # the visible rear plane is rendered first for correct overlap.
                size_index=count-1-i
                fan_models=row.get('fan_models',[])
                if size_index<len(fan_models):fan=_cooler_fan(dict(row,fan_model=fan_models[size_index]))
                size=base_size*fan_sizes[size_index]/max(fan_sizes)
                xx=starts[i][0]+(base_size-size)/2
                yy=starts[i][1]+(base_size-size)/2
                _fan_frame(p,xx,yy,size,fan)
                inset=size*.07
                rotors.append(_rotor(fan,style,xx+inset,yy+inset,size-2*inset,size-2*inset))
                relative=row.get('fan_relative_directions',[]) if row.get('relative_rotation_verified') else []
                if size_index<len(relative):rotors[-1]['direction']=-1 if relative[size_index]==-1 else 1
                if i==count-1:
                    _fan_foreground(fg,xx,yy,size,fan)
            p.rect(47,84,25,4,copper,1,.65)
    return p.finish(),rotors,fg.finish()


def _psu(row, style):
    p=_Pen(style)
    fg=_Pen(style)
    if style in ('miniature','classic','solid'):
        p.body,p.dark,p.light,p.ink='#303a42','#182229','#667781','#9babb5'
        fg.ink='#9babb5'
        if row.get('housing_color'):
            p.body=row['housing_color'];p.dark=_shade(p.body,.65);p.light=_shade(p.body,1.25)
            p.ink='#536471' if sum(int(p.body[n:n+2],16) for n in (1,3,5))>560 else '#afbdc8'
            fg.ink=p.ink
    dims=row['dimensions_mm']
    # SFX is visibly shorter, SF-L has its documented longer fan face; ATX
    # length differences remain visible rather than using one generic box.
    width=dims['length']*.39
    height=width*dims['width']/dims['length']*.65
    side=16
    x,y=(120-width-side)/2,32-height*.14
    p.poly([(x,y),(x+15,y-9),(x+width+15,y-9),(x+width,y)],p.light)
    p.poly([(x+width,y),(x+width+15,y-9),(x+width+15,y+height-9),(x+width,y+height)],p.dark)
    p.rect(x,y,width,height,p.body,1)
    rotors=[]
    pattern=row.get('grille_pattern','reference')
    if row['fan_count']:
        diameter=row['fan_diameter_mm']
        fw=min(width-5,width*diameter/dims['length'])
        fh=min(height-4,height*diameter/dims['width'])
        fx=x+(width-fw)/2;fy=y+(height-fh)/2
        cx,cy=fx+fw/2,fy+fh/2
        p.ellipse(cx,cy,fw/2,fh/2,p.dark,.6)
        if row.get('funnel_inlet'):
            p.parts.append('<g data-fan-inlet="funnel-reference">')
            p.ellipse(cx,cy,fw*.51,fh*.51,p.light,1.1)
            p.ellipse(cx,cy,fw*.47,fh*.47,p.dark,.65)
            p.parts.append('</g>')
        if row.get('frameless_fan'):
            p.parts.append('<g data-fan-support="frameless-reference">')
            for index in range(3):
                angle=index*math.tau/3
                p.line_to(cx+fw*.42*math.cos(angle),cy+fh*.42*math.sin(angle),cx,cy,1.5)
            p.ellipse(cx,cy,fw*.1,fh*.1,p.dark,.6)
            p.parts.append('</g>')
        rotor=_rotor(dict(blades=row.get('fan_blades',7),blade_color='#a8d0d6' if row.get('rgb_fan') else '#455660',
                          aperture_color='#182229',hub_ratio=.27,outer_ring=row.get('outer_ring') is True),style,fx,fy,fw,fh)
        rotors.append(rotor)
        fg.parts.append('<g data-grille="'+escape(pattern,quote=True)+'">')
        if pattern=='rounded_y':
            # Original rounded Y apertures from the RMx 2024 family, not a
            # concentric wire grille or an imported product image.
            for gy in range(5,int(height)-3,6):
                for gx in range(5,int(width)-3,7):
                    xx,yy=x+gx,y+gy
                    if ((xx-cx)/(fw*.48))**2+((yy-cy)/(fh*.48))**2<.9:
                        fg.path('M'+_n(xx)+' '+_n(yy+2)+' L'+_n(xx)+' '+_n(yy)+' M'+_n(xx-2)+' '+_n(yy-2)+' Q'+_n(xx)+' '+_n(yy+1)+' '+_n(xx+2)+' '+_n(yy-2),width=1.05)
        elif pattern=='triangle':
            for gy in range(5,int(height)-3,5):
                for gx in range(5,int(width)-3,6):
                    xx,yy=x+gx,y+gy
                    if ((xx-cx)/(fw*.48))**2+((yy-cy)/(fh*.48))**2<.8:
                        fg.poly([(xx-1.7,yy+1.3),(xx,yy-1.3),(xx+1.7,yy+1.3)],width=.65)
        elif pattern=='quadrant_slots':
            for signx,signy in ((1,1),(-1,1),(-1,-1),(1,-1)):
                for ratio in (.34,.55,.77,.94):
                    sx=fw*.48*ratio;sy=fh*.48*ratio
                    fg.path('M'+_n(cx+signx*2)+' '+_n(cy+signy*sy)+' Q'+_n(cx+signx*sx)+' '+_n(cy+signy*sy)+' '+_n(cx+signx*sx)+' '+_n(cy+signy*1.6),width=1.1)
            fg.line_to(cx-fw*.46,cy,cx+fw*.46,cy,1.4)
            fg.line_to(cx,cy-fh*.46,cx,cy+fh*.46,1.4)
        else:
            for ratio in (.22,.34,.46):
                fg.ellipse(cx,cy,fw*ratio,fh*ratio,'none',.65)
        fg.ellipse(cx,cy,fw*.49,fh*.49,'none',.75)
        fg.ellipse(cx,cy,fw*.07,fh*.07,p.body,.65)
        fg.parts.append('</g>')
    else:
        p.parts.append('<g data-grille="honeycomb" data-fanless="true">')
        for iy in range(5,int(height)-3,4):
            for ix in range(4,int(width)-3,5):
                xx=x+ix+(2.5 if iy%8 else 0);yy=y+iy
                p.poly([(xx-1.6,yy),(xx-.8,yy-1.1),(xx+.8,yy-1.1),
                        (xx+1.6,yy),(xx+.8,yy+1.1),(xx-.8,yy+1.1)],p.dark,.35)
        p.parts.append('</g>')
    # The small end face shows only schematic connector positions and counts.
    # IEC/socket and switch form are retained without copying a pin layout.
    p.poly([(x+width+3,y+height-13),(x+width+11,y+height-17),
            (x+width+11,y+height-11),(x+width+3,y+height-7)],p.light,.6)
    p.poly([(x+width+5,y+height-12),(x+width+9,y+height-14),
            (x+width+9,y+height-12),(x+width+5,y+height-10)],p.dark,.45)
    p.rect(x+width+6,y+height-24,4,5,p.body,.3,.5)
    if row.get('manual_fan_knob'):
        p.ellipse(x+width+10,y+height-28,1.8,2.4,p.light,.55)
    if row['modular']:
        # Modular end is represented along the upper rear lip, spatially separate
        # from the IEC end. Socket groups are explicitly illustrative detail.
        for i in range(4):
            xx=x+11+i*(width-18)/4
            p.poly([(xx,y-3),(xx+5,y-5),(xx+8,y-5),(xx+3,y-3)],p.dark,.4)
    if not row['modular'] or row.get('semi_modular'):
        p.parts.append('<g data-cable-attachment="fixed-harness-reference">')
        hx=x+width*.3;hy=y-4
        p.ellipse(hx,hy,3,1.4,p.dark,.5)
        for i in range(3):
            p.path('M'+_n(hx+i*.7)+' '+_n(hy)+' C'+_n(hx-6+i)+' '+_n(hy-8)+' '
                   +_n(hx+3+i)+' '+_n(hy-12)+' '+_n(hx-3+i*2)+' '+_n(hy-17),width=1.2)
        p.parts.append('</g>')
    if row.get('oled_display'):
        p.parts.append('<g data-oled="unread-blank-reference">')
        sx=x+width*.16
        p.poly([(sx,y-1),(sx+11,y-7),(sx+29,y-7),(sx+18,y-1)],p.dark,.55)
        p.poly([(sx+3,y-1.7),(sx+11.5,y-6),(sx+25,y-6),(sx+17,y-1.7)],'#142c36',.35)
        p.parts.append('</g>')
    if row.get('accent_color'):
        accent=row['accent_color'] if style in ('miniature','classic','solid') else p.accent
        p.line_to(x+width*.22,y-2,x+width*.68,y-2,.9)
        p.parts.append('<path d="M'+_n(x+width*.22)+' '+_n(y-2)+' L'+_n(x+width*.68)+' '+_n(y-2)+'" stroke="'+escape(accent,quote=True)+'" stroke-width="1.1"/>')
    for xx,yy in ((x+2,y+2),(x+width-2,y+2),(x+2,y+height-2),(x+width-2,y+height-2)):
        fg.ellipse(xx,yy,.7,.55,p.light,.35)
    fg.face(x+width*.5,y+height*.53,7)
    return p.finish(),rotors,fg.finish()


def _picker_choices(catalogs):
    return {key:[dict(id=r['id'],label=r['label'],brand=r['brand'],fidelity='schematic_reference')
                 for r in rows] for key,rows in zip(('cases','coolers','psus','fans'),catalogs)}


def builtin_choices():
    """Detached bundled-only artwork inventory, without profile/pack access."""
    # Cooling's application pickers also read installed optional packs. Export
    # only its immutable bundled rows so another user's profile cannot alter it.
    return _picker_choices((chassis_catalog.choices(),cooling_catalog._COOLERS,
                            component_catalog.choices('psu'),cooling_catalog._FANS))


def _library_generation():
    # An unopened pack library has the same generation0 as library_generation.
    # Pure bundled artwork must not import pack/profile/network-URL machinery.
    module=sys.modules.get('hardware_packs')
    return module.library_generation() if module is not None else 0


def choices():
    """Return detached app picker records, including installed optional packs."""
    global _CHOICES,_CHOICES_GENERATION
    generation=_library_generation()
    if _CHOICES is None or _CHOICES_GENERATION!=generation:
        _CHOICES=_picker_choices((chassis_catalog.choices(),cooling_catalog.choices_coolers(),
                                  component_catalog.choices('psu'),cooling_catalog.choices_fans()))
        from liquid_component_runtime046 import grouped_choices
        loop=grouped_choices()
        _CHOICES.update({key:[dict(r,fidelity='schematic_reference') for r in loop[kind]]
                         for kind,key in zip(_LOOP_KINDS,_LOOP_KEYS)})
        _CHOICES_GENERATION=_library_generation()
    return deepcopy(_CHOICES)


def model_key(kind,model_id,style):
    """Validate a small GUI request without looking up any selected record."""
    if (not isinstance(kind,str) or kind not in _KINDS or not isinstance(model_id,str)
            or len(model_id)>64 or not _ID.fullmatch(model_id)
            or not isinstance(style,str) or style not in STYLES):return None
    return (kind,model_id,style,_library_generation())


def has_cached(key):return key in _CACHE


def cached_art(key):
    """GUI-only cache lookup; a cold miss never generates a mesh."""
    if key not in _CACHE:return {}
    _CACHE.move_to_end(key)
    return deepcopy(_CACHE[key])


def publish_art(key,result):
    """GUI-only commit of a current completed data result, not worker state."""
    if (key[3]!=_library_generation() or not result
            or any(result.get(field)!=value for field,value in zip(('kind','id','style'),key[:3]))):return
    _CACHE[key]=result
    _CACHE.move_to_end(key)
    while len(_CACHE)>_MAX_ENTRIES:_CACHE.popitem(last=False)


def art(kind, model_id, style='miniature'):
    """Render one bounded, detached reference; unknown input returns an empty map."""
    key=model_key(kind,model_id,style)
    if key is None:return {}
    if key in _CACHE:return cached_art(key)
    if kind in _LOOP_KINDS:
        from liquid_svg046 import art as loop_art
        result=loop_art(kind,model_id,style)
        if not result:return {}
        _CACHE[key]=result
        while len(_CACHE)>_MAX_ENTRIES:_CACHE.popitem(last=False)
        return deepcopy(result)
    getters=dict(case=chassis_catalog.get_case,cooler=cooling_catalog.get_cooler,
                 psu=component_catalog.get_component,fan=cooling_catalog.get_fan)
    row=getters[kind](model_id)
    if not row or (kind=='psu' and row.get('category')!='psu'):
        return {}
    body,rotors,foreground=dict(case=_case,cooler=_cooler,psu=_psu,fan=_fan)[kind](row,style)
    combined=body
    for rotor in rotors:
        inner=rotor['svg'].split('>',1)[1].rsplit('</svg>',1)[0]
        if rotor.get('affine'):
            transform='matrix('+' '.join(_n(v) for v in rotor['affine'])+')'
        else:transform='translate('+_n(rotor['x'])+' '+_n(rotor['y'])+') scale('+_n(rotor['width']/100)+' '+_n(rotor['height']/100)+')'
        combined+='<g transform="'+transform+'">'+inner+'</g>'
        if rotor.get('after_svg'):
            combined+=rotor['after_svg'].split('>',1)[1].rsplit('</svg>',1)[0]
    combined+=foreground
    fan_source=_cooler_fan(row) if kind=='cooler' else {}
    sources=list(dict.fromkeys([*row.get('sources',[]),*row.get('appearance_sources',[]),
                               *fan_source.get('sources',[])]))
    details=dict(silhouette=row.get('layout',row.get('kind',row.get('form_factor',row.get('frame','reference')))),
                 features=list(row.get('features',[])))
    if kind=='cooler':
        details.update(fan_count=row.get('fan_count',0),heatpipes=row.get('heatpipes',0),
                       heatpipe_count_verified=bool(row.get('heatpipe_count_verified',False)),
                       fan_placement=row.get('fan_placement','reference'),
                       relative_rotation_verified=bool(row.get('relative_rotation_verified')),
                       top_style=row.get('top_style','reference'),pump_style=row.get('pump_style','none'))
    elif kind=='psu':
        details.update(grille=row.get('grille_pattern','reference'),fan_count=row['fan_count'],
                       form_factor=row['form_factor'],port_positions_reference=True,
                       modular=bool(row['modular']),semi_modular=bool(row.get('semi_modular')),
                       fixed_harness=not row['modular'] or bool(row.get('semi_modular')),
                       oled_display=bool(row.get('oled_display')),oled_live_reading=None,
                       rgb_fan=bool(row.get('rgb_fan')),rgb_lighting_live=False,
                       blade_tip_ring=bool(row.get('outer_ring')),frameless_fan=bool(row.get('frameless_fan')),
                       fan_inlet_profile='funnel_reference' if row.get('funnel_inlet') else 'reference')
    elif kind=='fan':
        details.update(family=row.get('family','reference'),blade_count=row['blades'],
                       blade_count_verified=bool(row.get('blade_count_verified')),
                       leaf_contour=row.get('leaf_contour_accuracy','original_reference'),
                       reverse_pitch=bool(row.get('reverse_blade')),stationary_lcd=bool(row.get('hub_display')),
                       stationary_directional_grille=bool(row.get('directional_grille')),
                       stationary_light_polygon=row.get('frame_rgb_polygon'),
                       marketed_separately_verified=row.get('marketed_separately_verified'))
    result=dict(id=model_id,kind=kind,label=row['label'],brand=row['brand'],style=style,
                svg=_svg(combined),body_svg=_svg(body),foreground_svg=_svg(foreground) if foreground else '',
                rotors=rotors,reference_details=True,sources=sources,
                fidelity='schematic_reference',motion_source='reference_demo',rotation_direction_verified=False,
                original_face='smile' if style in ('cartoon','notebook_smile') else 'none',
                art_details=details,reference_notes='Original schematic illustration. Fine contours, spacing, mesh/grille repetition, '
                'unverified leaves, socket positions and tube routing are references; no exact CAD, installed case-fan count '
                'or measured rotation direction is claimed.')
    _CACHE[key]=result
    while len(_CACHE)>_MAX_ENTRIES:
        _CACHE.popitem(last=False)
    return deepcopy(result)


def clear_cache():
    """Release generated images and picker copies when the gallery closes."""
    global _CHOICES
    _CACHE.clear()
    _CHOICES=None


def cache_info():
    return dict(entries=len(_CACHE),max_entries=_MAX_ENTRIES)
