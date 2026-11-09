"""Original 0.40 case linework using the caller's existing illustration pen.

No raster/vendor assets, logo tracing, backgrounds, installed devices or sensor
readings. Repeated vents, tray-frame construction and edge positions are bounded
references. Outer proportions come from reviewed catalog dimensions. This
module does not import accessory_art, Qt, hardware libraries or start workers.
"""
class _View:
    def __init__(self, pen, row):
        self.p = pen
        dims = row['dimensions_mm']
        self.w,self.h,self.d = (dims[key] for key in ('width','height','depth'))
        self.s = min(102/(.86*self.w+.58*self.d),82/(self.h+.24*self.d))

    def point(self, p):
        x,y,z=p
        # View from -X/+Y/+Z: the -X side and +Z front share visible edges.
        return 60+self.s*(.86*x+.58*z),50+self.s*(-y+.24*z)

    def poly(self, points, tone, width=.75, opacity=1):
        self.p.poly([self.point(p) for p in points],tone,width,opacity=opacity)

    def line(self,a,b,width=.7,opacity=1):
        self.p.line_to(*self.point(a),*self.point(b),width,opacity)

    def side(self, points_zy, x, tone, width=.75, opacity=1, pose=None):
        points=[(x,y,z) for z,y in points_zy]
        self.poly([pose(p) for p in points] if pose else points,tone,width,opacity)

    def front(self,x0,x1,y0,y1,z,tone,width=.7,opacity=1):
        self.poly([(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)],tone,width,opacity)

    def cube(self,w,h,d,center,tone,side=None,top=None,width=.7):
        x,y,z=center;a,b,c=w/2,h/2,d/2
        self.poly([(x-a,y+b,z-c),(x+a,y+b,z-c),(x+a,y+b,z+c),(x-a,y+b,z+c)],top or self.p.light,width)
        self.poly([(x-a,y-b,z-c),(x-a,y-b,z+c),(x-a,y+b,z+c),(x-a,y+b,z-c)],side or self.p.dark,width)
        self.front(x-a,x+a,y-b,y+b,z+c,tone,width)

    def face(self,point,size=7):
        self.p.face(*self.point(point),size)


def _marker(p,name):
    p.parts.append('<g data-case-structure="'+name+'" data-detail-status="original-reference">')


def _close(p):
    p.parts.append('</g>')
    return True


def draw_case(p,row):
    """Append one recognised 0.40 outline, or return False without touching pen."""
    flags=set(row.get('features',()))
    recognised={'angular_modular_shell','forward_tilted_open_frame','striker_open_frame',
                'expandable_itx_shell','nas_twelve_bay','split_glass_mesh_side',
                'elevated_glass_shell','cosmos_wrap_handles','fabric_front_insert'}
    if not flags&recognised:
        return False
    v=_View(p,row);w,h,d=v.w,v.h,v.d
    original=p.style in ('miniature','classic','solid')

    if 'angular_modular_shell' in flags:
        _marker(p,'mod5-separated-angular-armour')
        upper=[(-d*.48,h*.31),(-d*.22,h*.49),(d*.22,h*.43),(d*.48,h*.17),
               (d*.37,h*.12),(d*.12,h*.32),(-d*.26,h*.36)]
        lower=[(-d*.45,-h*.26),(-d*.22,-h*.49),(d*.29,-h*.43),(d*.47,-h*.24),
               (d*.29,-h*.21),(d*.12,-h*.34),(-d*.24,-h*.35)]
        pane=[(-d*.34,-h*.24),(-d*.38,h*.18),(-d*.20,h*.32),(d*.22,h*.28),
              (d*.36,h*.10),(d*.30,-h*.23)]
        v.side(upper,w*.48,p.dark,.8)
        v.side(lower,w*.48,p.dark,.8)
        for y in (-h*.36,h*.36):
            v.line((-w*.46,y,-d*.26),(w*.46,y,-d*.26),1.35)
            v.line((-w*.46,y,d*.15),(w*.46,y,d*.15),1.35)
        v.side(pane,-w*.49,p.glass,.7,.72)
        v.side(upper,-w*.50,p.body,.9)
        v.side(lower,-w*.50,p.dark,.9)
        for z in (-d*.27,d*.29):
            v.cube(w*.82,10,42,(0,-h*.49,z),p.dark,width=.6)
        v.face((-w*.50,-h*.33,d*.15),7)
        return _close(p)

    if 'forward_tilted_open_frame' in flags:
        from assembly_case_exteriors040 import torque_pose
        _marker(p,'torque-forward-tilted-reference')
        alloy=[(-d*.38,-h*.30),(-d*.34,h*.30),(-d*.18,h*.41),(d*.28,h*.37),
               (d*.38,h*.16),(d*.29,h*.12),(d*.20,h*.29),(-d*.22,h*.31),(-d*.27,-h*.28)]
        crimson=[(-d*.32,-h*.30),(-d*.20,-h*.40),(d*.29,-h*.33),(d*.36,-h*.12),
                 (d*.29,-h*.08),(d*.22,-h*.23)]
        glass=[(-d*.29,-h*.25),(-d*.29,h*.24),(-d*.15,h*.32),(d*.25,h*.28),(d*.30,-h*.20)]
        red='#a84852' if original else p.accent
        v.side(alloy,w*.42,p.dark,.8,pose=torque_pose)
        v.side(crimson,w*.42,red,.75,pose=torque_pose)
        for y in (-h*.27,h*.27):
            v.line(torque_pose((-w*.42,y,-d*.24)),torque_pose((w*.42,y,-d*.24)),1.3)
        v.side(glass,-w*.445,p.glass,.7,.68,torque_pose)
        v.side(alloy,-w*.42,p.body,.85,pose=torque_pose)
        v.side(crimson,-w*.42,red,.8,pose=torque_pose)
        for z in (-d*.30,d*.31):
            v.cube(w*.83,12,d*.16,(0,-h*.46,z),p.dark,width=.65)
        v.face(torque_pose((-w*.43,-h*.30,d*.18)),6)
        return _close(p)

    if 'striker_open_frame' in flags:
        _marker(p,'striker-empty-front-gpu-fork')
        fork=[(-d*.40,-h*.40),(-d*.43,h*.28),(-d*.25,h*.44),(-d*.12,h*.40),
              (-d*.28,h*.22),(-d*.25,-h*.27),(d*.31,-h*.29),(d*.35,h*.37),
              (d*.44,h*.40),(d*.43,-h*.40)]
        pane=[(-d*.32,-h*.24),(-d*.33,h*.20),(-d*.20,h*.34),(d*.23,h*.27),(d*.26,-h*.25)]
        v.side(fork,w*.43,p.dark,.8)
        v.side(pane,-w*.41,p.glass,.65,.66)
        v.side(fork,-w*.43,p.light,.95)
        z=d/2-min(96.,d*.24)
        for x in (-w*.39,w*.39):
            v.line((x,-h*.35,z),(x,h*.415,z),1.25)
        for y in (-h*.35,h*.415):
            v.line((-w*.40,y,z),(w*.40,y,z),1.25)
        for z in (-d*.31,d*.31):
            v.cube(w*.88,13,32,(0,-h*.47,z),p.dark,width=.65)
        v.face((-w*.43,-h*.31,d*.13),6)
        return _close(p)

    if 'expandable_itx_shell' in flags:
        _marker(p,'shiftxt-air-boost-static-infinity-mirror')
        low,high=-h/2+9.,h/2-38.
        v.cube(w,high-low,d,(0,(high+low)/2,0),p.body,side=p.dark,width=.8)
        # The lifted roof leaves a visible mid-height expansion band.
        for x in (-w*.43,w*.43):
            for z in (-d*.43,d*.43):
                v.line((x,high,z),(x,h/2-3,z),1.1)
        v.cube(w-6,4,d-6,(0,h/2-2,0),p.body,side=p.dark,top=p.light,width=.75)
        for i in range(13):
            z=-d*.42+i*d*.84/12
            v.line((-w*.43,h/2+.1,z),(w*.43,h/2+.1,z),.45,.65)
        v.front(-w*.36,w*.36,(low+high)/2-(high-low)*.29+4,
                (low+high)/2+(high-low)*.29+4,d/2+1,p.dark,.65)
        for scale in (.9,.72,.54):
            y=(low+high)/2+4;hh=(high-low)*.25*scale
            v.front(-w*.32*scale,w*.32*scale,y-hh,y+hh,d/2+2,'none',.6,.75)
        for i in range(11):
            z=-d*.42+i*d*.84/10
            v.line((-w/2-1,low+8,z),(-w/2-1,high-8,z),.4,.65)
        v.face((0,(low+high)/2+4,d/2+3),6)
        return _close(p)

    if 'nas_twelve_bay' in flags:
        _marker(p,'nas-twelve-empty-tray-frames')
        v.cube(w,h-6,d,(0,3,0),p.body,side=p.dark,width=.8)
        v.front(-w*.46,w*.46,h*.03,h*.43,d/2+1,p.dark,.65)
        wood='#a78966' if original else p.accent
        for i in range(12):
            x=-w*.42+i*w*.84/11
            v.line((x,h*.06,d/2+2),(x,h*.40,d/2+2),1.0,.85)
        # Wood inlay and a separate lower empty tray bank, never fake HDD LEDs.
        v.front(-w*.46,w*.46,-h*.015,h*.025,d/2+3,wood,.55)
        for row_index in range(4):
            y=-h*.38+row_index*h*.09
            for column in range(3):
                x=(column-1)*w*.29
                v.front(x-w*.13,x+w*.13,y-h*.034,y+h*.034,d/2+2,p.dark,.45)
                v.line((x-w*.10,y,d/2+3),(x+w*.10,y,d/2+3),.45,.75)
        v.face((0,h*.22,d/2+4),6)
        return _close(p)

    if 'split_glass_mesh_side' in flags:
        _marker(p,'q58-four-half-panels-sfx-reference')
        v.cube(w,h,d,(0,0,0),p.body,side=p.dark,width=.75)
        # The matching far half-panels are occluded in this fixed exterior view.
        # Drawing them last would incorrectly paste them over the opaque front.
        x=-w/2-1
        v.side([(-d*.46,h*.03),(-d*.46,h*.47),(d*.46,h*.47),(d*.46,h*.03)],x,p.glass,.6,.75)
        v.side([(-d*.46,-h*.43),(-d*.46,-h*.03),(d*.46,-h*.03),(d*.46,-h*.43)],x,p.body,.6)
        for i in range(13):
            z=-d*.43+i*d*.86/12
            v.line((-w/2-2,-h*.40,z),(-w/2-2,-h*.05,z),.42,.72)
        for i in range(6):
            y=-h*.40+i*h*.35/5
            v.line((-w/2-2,y,-d*.43),(-w/2-2,y,d*.43),.38,.65)
        v.face((0,h*.05,d/2+2),6)
        return _close(p)

    if 'elevated_glass_shell' in flags:
        _marker(p,'evolvx2-floating-glass-shell')
        v.cube(w*.93,8,d*.93,(0,-h/2+4,0),p.dark,width=.65)
        for x in (-w*.39,w*.39):
            for z in (-d*.39,d*.39):
                v.line((x,-h/2+8,z),(x,-h/2+32,z),1.1)
        v.cube(w-8,h-40,d-8,(0,20,0),p.glass,side=p.glass,top=p.body,width=.8)
        for z in (-d*.46,d*.46):
            v.line((-w*.47,-h/2+33,z),(-w*.47,h/2-4,z),.7)
            v.line((w*.47,-h/2+33,z),(w*.47,h/2-4,z),.7)
        for i in range(10):
            z=-d*.40+i*d*.80/9
            v.line((-w*.39,h/2+1,z),(w*.39,h/2+1,z),.4,.6)
        v.face((0,-h*.32,d/2-2),7)
        return _close(p)

    if 'cosmos_wrap_handles' in flags:
        _marker(p,'cosmos-silver-wraps-and-curved-side-glass')
        bw,bh,bd=w*.88,h*.88,d*.94
        v.cube(bw,bh,bd,(0,0,0),p.body,side=p.glass,width=.8)
        # Explicit side glazing curve; the front remains brushed aluminium.
        a=v.point((-bw/2,-bh*.44,bd*.28));b=v.point((-bw/2,-bh*.44,bd/2))
        c=v.point((-bw/2,bh*.44,bd/2));e=v.point((-bw/2,bh*.44,bd*.28))
        p.path('M'+str(a[0])+' '+str(a[1])+' Q'+str(b[0]-3)+' '+str(b[1])+' '+str(b[0])+' '+str(b[1])+
               ' L'+str(c[0])+' '+str(c[1])+' Q'+str(c[0]-3)+' '+str(c[1])+' '+str(e[0])+' '+str(e[1]),width=.65)
        for x in (-w*.46,w*.46):
            for sign in (-1,1):
                y=sign*(h/2-8)
                points=[(x,sign*bh*.40,-d*.45),(x,y-sign*9,-d*.46),(x,y,-d*.40),
                        (x,y,d*.40),(x,y-sign*9,d*.46),(x,sign*bh*.40,d*.45)]
                for a,b in zip(points,points[1:]):v.line(a,b,2.2)
        v.face((0,-h*.21,bd/2+2),7)
        return _close(p)

    if 'fabric_front_insert' in flags:
        _marker(p,'ridge-vertical-fabric-front')
        v.cube(w*.92,7,d*.74,(0,-h/2+3.5,0),p.dark,width=.65)
        v.cube(w*.86,h*.92,d*.98,(0,h*.02,0),p.body,side=p.dark,width=.8)
        v.front(-w*.36,w*.36,-h*.38,h*.42,d/2+1,p.glass,.65)
        for i in range(14):
            y=-h*.35+i*h*.74/13
            v.line((-w*.32,y,d/2+2),(w*.32,y,d/2+2),.37,.65)
        for i in range(5):
            x=-w*.32+i*w*.64/4
            v.line((x,-h*.35,d/2+2),(x,h*.39,d/2+2),.32,.55)
        for i in range(14):
            z=-d*.42+i*d*.84/13
            v.line((-w*.44,-h*.38,z),(-w*.44,h*.40,z),.33,.55)
        v.face((0,h*.03,d/2+3),6)
        return _close(p)
    return False
