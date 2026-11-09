"""Flatten trusted catalog paths for original three-dimensional meshes on demand."""
import copy
import json
import math
import re

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPainterPath, QTransform
from PySide6.QtQml import QQmlComponent, QQmlExpression, qmlContext

from stats_config import ASSETS

_TOKENS = re.compile(r"[MmLlHhVvCcQqZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[Ee][-+]?\d+)?")
_COUNTS = dict(M=2,L=2,H=1,V=1,C=6,Q=4)


def _path_contours(shape):
    """Flatten bounded trusted paths while retaining their individual subpaths."""
    if not isinstance(shape, dict) or not isinstance(shape.get("d"), str) or len(shape["d"]) > 20000:
        return []
    source=shape["d"]
    if _TOKENS.sub("",source).strip(" ,\t\r\n"):
        return []
    tokens=_TOKENS.findall(source)
    if len(tokens)>4096:return []
    path=QPainterPath();index=0;command="";current=(0.,0.);start=(0.,0.)
    try:
        while index<len(tokens):
            if tokens[index].isalpha():
                command=tokens[index];index+=1
                if command.upper()=="Z":
                    path.closeSubpath();current=start;command="";continue
            kind=command.upper();count=_COUNTS[kind]
            values=[float(v) for v in tokens[index:index+count]]
            if len(values)!=count or not all(math.isfinite(v) and abs(v)<100000 for v in values):return []
            index+=count;relative=command.islower();x,y=current
            def point(at):return (values[at]+(x if relative else 0),values[at+1]+(y if relative else 0))
            if kind=="M":
                current=point(0);path.moveTo(*current);start=current;command="l" if relative else "L"
            elif kind=="L":current=point(0);path.lineTo(*current)
            elif kind=="H":current=(values[0]+(x if relative else 0),y);path.lineTo(*current)
            elif kind=="V":current=(x,values[0]+(y if relative else 0));path.lineTo(*current)
            elif kind=="C":
                a,b,current=point(0),point(2),point(4);path.cubicTo(*a,*b,*current)
            elif kind=="Q":a,current=point(0),point(2);path.quadTo(*a,*current)
    except (ValueError,KeyError,IndexError):return []
    matrix=shape.get("m",[1,0,0,1,0,0])
    if (not isinstance(matrix,list) or len(matrix)!=6
            or not all(type(v) in (int,float) and math.isfinite(v) and abs(v)<10000 for v in matrix)):
        return []
    path=QTransform(*matrix).map(path)
    return path.toSubpathPolygons(QTransform(8,0,0,8,0,0))


def _contour_points(polygon):
    points=[[round(p.x()/8,6),round(p.y()/8,6)] for p in polygon]
    if len(points)>1 and points[0]==points[-1]:points.pop()
    return points if 3<=len(points)<=1024 else []


def path_polygon(shape):
    """Return the previous outer silhouette, without changing its sampling."""
    polygons=_path_contours(shape)
    if not polygons:return []
    polygon=max(polygons,key=lambda p:p.boundingRect().width()*p.boundingRect().height())
    return _contour_points(polygon)


def _shell_holes(shape):
    """Keep explicitly evenodd, fully contained simple shell openings only.

    Disconnected paths are not openings. Nested islands/intersecting contours
    require a more general surface representation, so they are not inferred.
    The reviewed shell currently has one simple internal rectangular opening.
    """
    if not isinstance(shape,dict) or shape.get('fill_rule')!='evenodd':return []
    polygons=_path_contours(shape)
    if not 2<=len(polygons)<=32:return []
    outer=max(polygons,key=lambda p:p.boundingRect().width()*p.boundingRect().height())
    if not _contour_points(outer):return []
    outline=QPainterPath();outline.addPolygon(outer);outline.closeSubpath()
    candidates=[]
    for polygon in polygons:
        if polygon is outer:continue
        points=_contour_points(polygon)
        if not points:return []
        path=QPainterPath();path.addPolygon(polygon);path.closeSubpath()
        if outline.contains(path):candidates.append((points,path))
    if any(a.intersects(b) for i,(_,a) in enumerate(candidates) for _,b in candidates[i+1:]):return []
    return [points for points,_ in candidates]


def bounds(points):
    if not points:return (0,0,1,1)
    xs,ys=zip(*points);return min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)


def normalized(points,box=None):
    x,y,w,h=box or bounds(points)
    return [[round((a-x)/w,6),round((b-y)/h,6)] for a,b in points] if w>0 and h>0 else []


def _dimension(value,low,high):
    return float(value) if type(value) in (int,float) and math.isfinite(value) and low<=value<=high else None


def _fan_radius(uv,previous,length,width,count):
    """Match the builder's bounded, circular fit to both illustration axes.

    These are reference drawing proportions, not measured retail fan diameters.
    When either physical axis is unknown the previous scalar remains a fallback;
    radius_uv is authoritative once the builder resolves its reference envelope.
    """
    if length is None or width is None:return previous
    fallback=min(width*.41,length/max(1,count)*.42)
    base=_dimension(previous,5,75)
    base=fallback if base is None else base
    return min((_dimension(uv[0],.005,.5) or base/length)*length,
               (_dimension(uv[1],.005,.5) or base/width)*width)


class ProfileReader:
    """A temporary object in the existing QML engine; destroyed after use."""
    def __init__(self,engine):
        self.component=QQmlComponent(engine)
        self.component.setData(b'import QtQml\nimport "AssemblyProfiles.js" as Profiles\nQtObject {function profile(v){return JSON.stringify(Profiles.profile(v))}}',
            QUrl.fromLocalFile(str(ASSETS/'native/AssemblyProfilesBridge.qml')))
        self.object=self.component.create()
        if self.object is None:raise RuntimeError("Hardware mesh profiles could not be loaded")

    def read(self,appearance):
        expression=QQmlExpression(qmlContext(self.object),self.object,"profile("+json.dumps(appearance)+")")
        result=expression.evaluate()
        if expression.hasError():raise RuntimeError("Hardware mesh profile could not be read")
        return json.loads(result[0] if isinstance(result,tuple) else result)

    def close(self):
        self.object.deleteLater();self.component.deleteLater()


def bake_profiles(spec,engine):
    value=copy.deepcopy(spec);reader=ProfileReader(engine)
    try:
        gpu=value['gpu'];appearance=gpu['appearance'];profile=reader.read(appearance)
        shell_shape=profile.get('shell')
        shell=path_polygon(shell_shape);box=profile.get('bounds') or {}
        gpu.pop('shell_holes',None)
        gpu['shell_polygon']=normalized(shell) if shell else []
        # Fan positions refer to the reviewed face coordinates, including unequal hybrids.
        face_box=bounds(shell) if shell else (box.get('x',0),box.get('y',0),box.get('width',24),box.get('height',24))
        holes=_shell_holes(shell_shape)
        if holes:gpu['shell_holes']=[normalized(hole,face_box) for hole in holes]
        gx,gy,gw,gh=face_box;physical_width=gpu.get('width_mm') or 135
        nominal=appearance.get('board_details',{}).get('dimensions_mm') or {}
        physical_length=_dimension(gpu.get('length_mm'),80,450) or _dimension(nominal.get('length'),80,450)
        physical_height=_dimension(gpu.get('width_mm'),50,190) or _dimension(nominal.get('height'),50,190)
        gpu['detail_polygons']=[]
        for detail in profile.get('details',[]):
            polygon=path_polygon(detail)
            if polygon:
                gpu['detail_polygons'].append(dict(points=normalized(polygon,face_box),color=detail.get('color')))
        gpu['fans']=[]
        front_fans=profile.get('fans',[])
        for fan in front_fans:
            polygons=[]
            for leaf in fan.get('blade_paths',[]):
                raw=path_polygon(dict(d=leaf['d'],m=[1,0,0,1,0,0]))
                angle=math.radians(leaf['rotation']);co,si=math.cos(angle),math.sin(angle)
                raw=[[co*x-si*y,si*x+co*y] for x,y in raw]
                if leaf.get('mirror'):raw=[[-x,y] for x,y in raw]
                if raw:polygons.append(raw)
            radius_uv=[fan['radius']/gw,fan['radius']/gh]
            radius_mm=_fan_radius(radius_uv,fan['radius']/gh*physical_width,physical_length,physical_height,len(front_fans))
            gpu['fans'].append(dict(center_uv=[(fan['cx']-gx)/gw,(fan['cy']-gy)/gh],
                x_ratio=(fan['cx']-gx)/gw,radius_mm=radius_mm,radius_uv=radius_uv,
                blade_polygons=polygons,profile=fan['profile'],direction=fan['direction'],
                blades=fan['profile'].get('blades'),shape=fan['profile'].get('shape'),
                hub_ratio=fan['hub_ratio'],outer_ring=fan['outer_ring'],group_size=fan['group_size'],face='front',
                colors=fan.get('colors',{}),
                blade_geometry_mirrored=fan['direction']==-1))
        gpu['physical_fan_count']=profile.get('physical_fan_count')
        gpu['colors']=profile.get('colors',{})
        cpu=value['cpu'];profile=reader.read(cpu['appearance'])
        package=path_polygon(profile.get('package'));lid=path_polygon(profile.get('lid'))
        cpu['lid_polygon']=normalized(lid,bounds(package)) if lid else []
        for module in value['memory'].get('modules',[]):
            profile=reader.read(module['appearance']);pcb=path_polygon(profile.get('pcb'))
            covers=[path_polygon(s) for s in profile.get('covers',[])]
            covers=[p for p in covers if p]
            cover=max(covers,key=lambda p:bounds(p)[2]*bounds(p)[3],default=[])
            module.update(pcb_polygon=normalized(pcb),case_polygon=normalized(cover,bounds(pcb)) if cover else [],
                          short_form=profile.get('short_form',False),colors=profile.get('colors',{}),
                          diffuser=bool(module['appearance'].get('board_details',{}).get('diffuser')))
        if value['memory'].get('modules'):
            first=value['memory']['modules'][0]
            value['memory'].update({k:first[k] for k in ('pcb_polygon','case_polygon','short_form','diffuser')})
        return value
    finally:reader.close()
