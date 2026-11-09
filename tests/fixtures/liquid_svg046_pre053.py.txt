"""On-demand SVG projections of the same optional loop component meshes.

No second catalog/mesh/SVG cache is kept here: accessory_art's existing bounded
cache owns the resulting card. Source photos, CAD, fonts, logos and telemetry
are never loaded or embedded. Original artwork: PolyForm Noncommercial 1.0.0.
"""
import hashlib
import math
import re
import struct
from collections import deque
from accessory_cancel047 import checkpoint

KINDS=('cpu_block','pump','reservoir','pump_reservoir','fitting','tubing','gpu_block')
STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut',
        'inkwash','classic','outline','solid','soft','sketch','notebook_smile')
MAX_TRIANGLES=2600
MAX_EDGES=4096
MAX_SVG_BYTES=750000
MAX_CLIP_WORK=600000
MAX_FACE_PIECES=512
MAX_VISIBLE_POLYGONS=16000
_ID=re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z',re.ASCII)


def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _unit(v):
    size=math.sqrt(_dot(v,v));return tuple(x/size for x in v)
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
_EYE=_unit((.56,.35,-.75))
_RIGHT=_unit(_cross(_EYE,(0.,1.,0.)))
_UP=_cross(_RIGHT,_EYE)
_LIGHT=_unit((.35,.7,-.65))


def _n(value):
    result=f'{value:.3f}'.rstrip('0').rstrip('.')
    return '0' if result in ('','-0') else result


def _svg(content):
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" fill="none" stroke-linecap="round" stroke-linejoin="round">'+content+'</svg>'


def _rgb(tone,factor=1.):
    return '#'+''.join(f'{max(0,min(255,round(v*factor*255))):02x}' for v in tone[:3])


def choices():
    """One detached lightweight optional-pack index; never fetch all models."""
    from liquid_component_runtime046 import grouped_choices
    return grouped_choices()


def cache_info():return dict(entries=0,max_entries=0,cache_owner='accessory_art')
def clear_cache():
    """No local resources survive a call; the outer gallery clears its cache."""
    return None


def _area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,(*poly[1:],poly[0])))/2
def _bounds(poly):
    points=iter(poly);first=next(points);left=right=first[0];top=bottom=first[1]
    for point in points:
        x,y=point[:2]
        if x<left:left=x
        if x>right:right=x
        if y<top:top=y
        if y>bottom:bottom=y
    return left,top,right,bottom
def _plane(triangle):
    a,b,c=triangle;u,v=b[0]-a[0],b[1]-a[1];x,y=c[0]-a[0],c[1]-a[1];det=u*y-x*v
    if abs(det)<1e-10:return None
    aa=((b[2]-a[2])*y-(c[2]-a[2])*v)/det
    bb=(u*(c[2]-a[2])-x*(b[2]-a[2]))/det
    return aa,bb,a[2]-aa*a[0]-bb*a[1]


def _cut(poly,plane):
    """Keep a convex polygon's half-plane with positive camera depth."""
    if not poly:return ()
    values=tuple(plane[0]*p[0]+plane[1]*p[1]+plane[2] for p in poly)
    if min(values)>=0:return poly
    if max(values)<0:return ()
    old=poly[-1];before=values[-1];out=[]
    for point,now in zip(poly,values):
        if (before>=0)!=(now>=0):
            ratio=before/(before-now);out.append(tuple(old[k]+ratio*(point[k]-old[k]) for k in (0,1)))
        if now>=0:out.append(point)
        old,before=point,now
    return tuple(out) if len(out)>=3 and abs(_area(out))>1e-7 else ()


def _overlaps(a,b):
    # Bounding boxes overlap even for many disjoint clipped fan triangles.
    # SAT avoids needlessly fragmenting a face along an absent occluder's
    # extended edge planes. Both inputs are convex and counter-clockwise.
    for polygon,other in ((a,b),(b,a)):
        for p,q in zip(polygon,(*polygon[1:],polygon[0])):
            dx,dy=q[0]-p[0],q[1]-p[1]
            if not any(dx*(r[1]-p[1])-dy*(r[0]-p[0])>1e-8 for r in other):return False
    return True


def _clean_polygon(points):
    result=[]
    for point in points:
        if not result or math.dist(point,result[-1])>1e-7:result.append(point)
    if len(result)>1 and math.dist(result[0],result[-1])<1e-7:result.pop()
    return tuple(result) if len(result)>=3 and abs(_area(result))>1e-7 else ()


def _split_polygon(poly,edge):
    """Classify one edge plane once for both complementary clipping pieces."""
    dx,dy,ax,ay=edge
    values=[dx*(p[1]-ay)-dy*(p[0]-ax) for p in poly]
    # Face inputs and prior split results are clean convex polygons. An edge
    # that does not cross one need not rebuild/clean two identical point lists.
    if min(values)>1e-8:return poly,()
    if max(values)<-1e-8:return (),poly
    inside=[];outside=[];previous=poly[-1];old=values[-1]
    for point,value in zip(poly,values):
        was_in,now_in=old>=-1e-8,value>=-1e-8
        was_out,now_out=old<=1e-8,value<=1e-8
        if was_in!=now_in or was_out!=now_out:
            ratio=old/(old-value)
            crossing=(previous[0]+ratio*(point[0]-previous[0]),previous[1]+ratio*(point[1]-previous[1]))
            if was_in!=now_in:inside.append(crossing)
            if was_out!=now_out:outside.append(crossing)
        if now_in:inside.append(point)
        if now_out:outside.append(point)
        previous,old=point,value
    return _clean_polygon(inside),_clean_polygon(outside)


def _subtract_cover(poly,edges):
    # The caller has already rejected disjoint bounding boxes and polygons.
    # Precomputed planes are shared by every remaining piece of this cover.
    result=[];remaining=poly
    for edge in edges:
        remaining,outside=_split_polygon(remaining,edge)
        if outside:result.append(outside)
        if not remaining:break
    return result


def _merge_faces(faces,cancel=None):
    """Join exact adjacent coplanar convex faces, preserving every bore.

    Concave unions and material/plane changes are rejected. This removes the
    source tessellation's redundant triangles before exact visibility work.
    """
    rows=dict(enumerate(faces));edges={};pending=deque();work=0
    point=lambda p:tuple(round(v,6) for v in p)
    def edge_keys(face):
        poly=face['polygon']
        for a,b in zip(poly,(*poly[1:],poly[0])):yield tuple(sorted((point(a),point(b))))
    def insert(index):
        for edge in edge_keys(rows[index]):
            ids=edges.setdefault(edge,set());ids.add(index)
            if len(ids)==2:pending.append(edge)
    for index in rows:
        if index%64==0:checkpoint(cancel)
        insert(index)
    while pending and work<40000:
        if work%64==0:checkpoint(cancel)
        edge=pending.popleft();work+=1;ids=edges.get(edge)
        if not ids or len(ids)!=2:continue
        a_id,b_id=sorted(ids);a,b=rows[a_id],rows[b_id]
        if a['material']!=b['material'] or any(abs(x-y)>1e-6 for x,y in zip(a['plane'],b['plane'])):continue
        aa,bb=a['polygon'],b['polygon']
        ai=next(i for i,(p,q) in enumerate(zip(aa,(*aa[1:],aa[0]))) if tuple(sorted((point(p),point(q))))==edge)
        bi=next(i for i,(p,q) in enumerate(zip(bb,(*bb[1:],bb[0]))) if tuple(sorted((point(p),point(q))))==edge)
        if point(aa[ai])!=point(bb[(bi+1)%len(bb)]):continue
        pa=aa[ai+1:]+aa[:ai+1];pb=bb[bi+1:]+bb[:bi+1];poly=pa+pb[1:-1]
        simplified=[]
        for i,p in enumerate(poly):
            previous,following=poly[i-1],poly[(i+1)%len(poly)]
            cross=(p[0]-previous[0])*(following[1]-p[1])-(p[1]-previous[1])*(following[0]-p[0])
            if cross < -1e-7:break
            if abs(cross)>1e-7:simplified.append(p)
        else:
            if not 3<=len(simplified)<=64:continue
            for index in (a_id,b_id):
                for key in edge_keys(rows[index]):
                    edges[key].discard(index)
                    if not edges[key]:del edges[key]
            polygon=tuple(simplified);rows[a_id]=dict(a,polygon=polygon,bounds=_bounds(polygon),
                near=max(a['plane'][0]*p[0]+a['plane'][1]*p[1]+a['plane'][2] for p in polygon),
                far=min(a['plane'][0]*p[0]+a['plane'][1]*p[1]+a['plane'][2] for p in polygon))
            del rows[b_id];insert(a_id)
    return list(rows.values()),work


class _Visibility:
    """Bounded exact convex depth clipping; no per-pixel buffers or workers."""
    def __init__(self,faces,cancel=None):
        self.faces=faces;self.grid={};self.work=0;self.cancel=cancel
        for index,face in enumerate(faces):
            poly=face['polygon']
            face['edge_terms']=tuple((q[0]-p[0],q[1]-p[1],p[0],p[1]) for p,q in zip(poly,(*poly[1:],poly[0])))
            face['plane_key']=tuple(round(v,5) for v in face['plane'])
            if face['alpha']<.999:continue
            for cell in self.cells(face['bounds']):self.grid.setdefault(cell,[]).append(index)
        for values in self.grid.values():values.sort(key=lambda i:-faces[i]['near'])
    def cells(self,bounds):
        a,b,c,d=bounds
        return ((x,y) for x in range(max(0,int(a/6)),min(19,int(c/6))+1)
                      for y in range(max(0,int(b/6.25)),min(15,int(d/6.25))+1))
    def candidates(self,bounds):
        cells=tuple(self.cells(bounds))
        if len(cells)==1:return self.grid.get(cells[0],())
        indices=set()
        for cell in cells:indices.update(self.grid.get(cell,()))
        return sorted(indices,key=lambda i:-self.faces[i]['near'])
    def tick(self):
        self.work+=1
        if self.work%64==0:checkpoint(self.cancel)
        if self.work>MAX_CLIP_WORK:raise ValueError('SVG occlusion work limit')
    def visible_face(self,index):
        face=self.faces[index];pieces=[(face['polygon'],face['bounds'])];a,b,c,d=face['bounds']
        for other in self.candidates(face['bounds']):
            if other==index:continue
            self.tick();cover=self.faces[other];aa,bb,cc,dd=cover['bounds']
            if cover['near']<=face['far']+1e-5:break
            if cc<a or aa>c or dd<b or bb>d:continue
            delta=tuple(cover['plane'][n]-face['plane'][n] for n in range(3));delta=(*delta[:2],delta[2]-1e-5)
            if max(delta[0]*p[0]+delta[1]*p[1]+delta[2] for p in face['polygon'])<=0:continue
            hole=_cut(cover['polygon'],delta)
            if not hole:continue
            updated=[]
            if hole is cover['polygon']:
                hx,hy,hxx,hyy=cover['bounds'];edges=cover['edge_terms']
            else:
                hx,hy,hxx,hyy=_bounds(hole)
                edges=tuple((q[0]-p[0],q[1]-p[1],p[0],p[1]) for p,q in zip(hole,(*hole[1:],hole[0])))
            for piece,bounds in pieces:
                if bounds[2]<=hx or bounds[0]>=hxx or bounds[3]<=hy or bounds[1]>=hyy or not _overlaps(piece,hole):
                    updated.append((piece,bounds));continue
                updated.extend((result,_bounds(result)) for result in _subtract_cover(piece,edges))
            pieces=updated
            if len(pieces)>MAX_FACE_PIECES:raise ValueError('SVG face partition limit')
            if not pieces:break
        return [poly for poly,_ in pieces]
    def visible_line(self,a,b):
        intervals=[(0.,1.)];delta=tuple(b[n]-a[n] for n in range(3));bounds=_bounds((a,b))
        for index in self.candidates(bounds):
            self.tick();face=self.faces[index];near,far=0.,1.;plane=face['plane']
            if face['near']<=min(a[2],b[2])+1e-5:break
            box=face['bounds']
            if box[2]<bounds[0] or box[0]>bounds[2] or box[3]<bounds[1] or box[1]>bounds[3]:continue
            for dx,dy,px,py in face['edge_terms']:
                value=dx*(a[1]-py)-dy*(a[0]-px);slope=dx*delta[1]-dy*delta[0]
                if abs(slope)<1e-12:
                    if value<0:near=1.;far=0.;break
                elif slope>0:near=max(near,-value/slope)
                else:far=min(far,-value/slope)
                if far-near<1e-7:break
            if far-near<1e-7:continue
            value=plane[0]*a[0]+plane[1]*a[1]+plane[2]-a[2]-1e-5
            slope=plane[0]*delta[0]+plane[1]*delta[1]-delta[2]
            if abs(slope)<1e-12:
                if value<0:continue
            elif slope>0:near=max(near,-value/slope)
            else:far=min(far,-value/slope)
            if far-near<1e-7:continue
            kept=[]
            for left,right in intervals:
                if right<=near or left>=far:kept.append((left,right));continue
                if left<near:kept.append((left,near))
                if right>far:kept.append((far,right))
            intervals=kept
            if len(intervals)>MAX_FACE_PIECES:raise ValueError('SVG edge partition limit')
            if not intervals:break
        return [(tuple(a[n]+delta[n]*left for n in range(3)),tuple(a[n]+delta[n]*right for n in range(3)))
                for left,right in intervals if right-left>1e-6]
    def partition_edge(self,a,b,material=None):
        """Discard only one mesh's triangulation, preserving real part joins."""
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<1e-8:return True
        mid=tuple((a[n]+b[n])/2 for n in range(3));offset=(-dy/length*.018,dx/length*.018)
        probes=((mid[0]+offset[0],mid[1]+offset[1]),(mid[0]-offset[0],mid[1]-offset[1]))
        found={}
        bounds=_bounds(probes)
        for index in self.candidates(bounds):
            self.tick();face=self.faces[index];plane=face['plane']
            if material is not None and face['material']!=material:continue
            if abs(plane[0]*mid[0]+plane[1]*mid[1]+plane[2]-mid[2])>1e-4:continue
            key=face['plane_key'];sides=found.setdefault(key,set())
            for side,p in enumerate(probes):
                if all((q[0]-r[0])*(p[1]-r[1])-(q[1]-r[1])*(p[0]-r[0])>=-1e-9
                       for r,q in zip(face['polygon'],(*face['polygon'][1:],face['polygon'][0]))):sides.add(side)
            if len(sides)==2:return True
        return False


def art(kind,model_id,style='miniature'):
    """Project one validated optional model; missing/uninstalled IDs stay empty."""
    if (type(kind) is not str or kind not in KINDS or type(model_id) is not str
            or not 1<=len(model_id)<=64 or not _ID.fullmatch(model_id)
            or type(style) is not str or style not in STYLES):return {}
    from liquid_component_runtime046 import get_component
    row=get_component(kind,model_id)
    if not row:return {}
    return art_from_reference(row,style)


def art_from_reference(row,style='miniature',cancel=None):
    """Project one detached validated row; no store, catalog or shared cache.

    Optional callers resolve/validate the reference before dispatching it. A
    cancellation exception is intentionally not converted to an unknown model.
    """
    if not isinstance(row,dict) or row.get('part_kind') not in KINDS or style not in STYLES:return {}
    kind=row['part_kind'];model_id=row.get('id')
    if not isinstance(model_id,str) or not _ID.fullmatch(model_id) or len(model_id)>64:return {}
    checkpoint(cancel)
    from liquid_geometry046 import build_component
    from assembly_style import apply_colors,edge_batches,style_for
    from liquid_silhouette046 import clip_edge
    try:meshes,physical=build_component(row,'eco')
    except ValueError:return {}
    checkpoint(cancel)
    count=sum(len(mesh.vertices)//18 for mesh in meshes)
    if not meshes or count>MAX_TRIANGLES:return {}
    digest=hashlib.sha256();low_x=low_y=math.inf;high_x=high_y=-math.inf
    for mesh in meshes:
        checkpoint(cancel)
        digest.update(mesh.name.encode('utf8'));digest.update(struct.pack('<3d',*mesh.position))
        for at in range(0,len(mesh.vertices),6):
            chunk=mesh.vertices[at:at+6]
            if not all(math.isfinite(v) for v in chunk):return {}
            digest.update(struct.pack('<6d',*chunk))
            point=tuple(chunk[k]+mesh.position[k] for k in range(3))
            x,y=_dot(point,_RIGHT),-_dot(point,_UP)
            if x<low_x:low_x=x
            if x>high_x:high_x=x
            if y<low_y:low_y=y
            if y>high_y:high_y=y
    low=(low_x,low_y);high=(high_x,high_y)
    scale=min(108./max(high[0]-low[0],1e-8),88./max(high[1]-low[1],1e-8))
    center=tuple((low[k]+high[k])/2 for k in (0,1))
    def project(point):
        return (60.+(_dot(point,_RIGHT)-center[0])*scale,
                50.+(-_dot(point,_UP)-center[1])*scale,_dot(point,_EYE))
    styled=apply_colors(meshes,style);policy=style_for(style);draw=[];shape=hashlib.sha256();faces=[]
    # Triangle cap holes remain real holes. No rectangle/silhouette replacement,
    # copied logo, separate invented OEM port or source-image trace is used.
    for mesh_index,mesh in enumerate(styled):
        checkpoint(cancel)
        for at in range(0,len(mesh.vertices),18):
            if at%1152==0:checkpoint(cancel)
            normal=mesh.vertices[at+3:at+6]
            # The actual native/software renderer draws both sides of its
            # thin walls and inner channels. Back-face culling here would
            # remove real occluders and let rear grip samples leak through.
            triangle=[project(tuple(mesh.vertices[at+j+k]+mesh.position[k] for k in range(3))) for j in (0,6,12)]
            plane=_plane(triangle)
            if plane is None:continue
            polygon=tuple(p[:2] for p in triangle)
            if _area(polygon)<0:polygon=tuple(reversed(polygon))
            lighting=1.-policy['shading']*(.40-.40*max(0.,_dot(normal,_LIGHT)))
            fill='#ffffff' if policy['line_only'] else _rgb(mesh.color,lighting)
            faces.append(dict(polygon=polygon,plane=plane,bounds=_bounds(polygon),near=max(p[2] for p in triangle),far=min(p[2] for p in triangle),
                              depth=sum(p[2] for p in triangle)/3,fill=fill,alpha=mesh.color[3],material=mesh_index))
    front_count=len(faces);faces,merge_work=_merge_faces(faces,cancel)
    visibility=_Visibility(faces,cancel);visible_polygons=0
    try:
        for index,face in enumerate(faces):
            if index%64==0:checkpoint(cancel)
            for polygon in visibility.visible_face(index):
                visible_polygons+=1
                if visible_polygons>MAX_VISIBLE_POLYGONS:return {}
                path='M'+' L'.join(_n(p[0])+' '+_n(p[1]) for p in polygon)+'Z';shape.update(path.encode('ascii'))
                draw.append((int(face['alpha']<.999)*100000.+face['depth'],0,path,face['fill'],face['alpha']))
    except ValueError:return {}
    edge_count=0;view_tags={};filtered_edges=0
    if policy['edges']:
        materials={id(mesh):index for index,mesh in enumerate(styled)}
        for mesh,vertices in edge_batches(styled,style):
            checkpoint(cancel)
            for at in range(0,len(vertices),12):
                if at%768==0:checkpoint(cancel)
                if edge_count>=MAX_EDGES:break
                world_a=tuple(vertices[at+k]+mesh.position[k] for k in range(3))
                world_b=tuple(vertices[at+6+k]+mesh.position[k] for k in range(3))
                tag=tuple(vertices[at+3:at+6])
                if tag[2]==-2.:
                    # For this fixed orthographic camera the shared normal
                    # gate depends on the tag, never on phase or position.
                    keep=view_tags.get(tag)
                    if keep is None:
                        keep=bool(clip_edge(world_a,world_b,tag,direction=_EYE))
                        if len(view_tags)<512:view_tags[tag]=keep
                    if not keep:filtered_edges+=1;continue
                a,b=project(world_a),project(world_b)
                try:
                    if visibility.partition_edge(a,b,materials.get(id(mesh))):continue
                    segments=visibility.visible_line(a,b)
                except ValueError:return {}
                for a,b in segments:
                    if edge_count>=MAX_EDGES:break
                    distance=math.hypot(b[0]-a[0],b[1]-a[1])
                    if distance<.025:continue
                    wobble=policy['wobble']*.16
                    if wobble:
                        seed=math.sin((a[0]+b[0])*12.3+(a[1]+b[1])*7.1)
                        control=((a[0]+b[0])/2-(b[1]-a[1])/distance*wobble*seed,
                                 (a[1]+b[1])/2+(b[0]-a[0])/distance*wobble*seed)
                        path='M'+_n(a[0])+' '+_n(a[1])+' Q'+_n(control[0])+' '+_n(control[1])+' '+_n(b[0])+' '+_n(b[1])
                    else:path='M'+_n(a[0])+' '+_n(a[1])+' L'+_n(b[0])+' '+_n(b[1])
                    draw.append((200000.,1,path,_rgb(policy['ink']),1.));edge_count+=1
            if edge_count>=MAX_EDGES:break
    draw.sort(key=lambda item:(item[0],item[1]))
    # Exact visibility has already removed opaque overlaps. Fill equal-colored
    # opaque fragments as one compound path, so rasterizers do not antialias
    # source tessellation boundaries into pale seams. Transparent layers keep
    # their own ordering/opacity; holes remain the same excluded polygons.
    opaque={};layered=[]
    for item in draw:
        if item[1]==0 and item[4]>=.999:opaque.setdefault(item[3],[]).append(item[2])
        else:layered.append(item)
    draw=[(0.,0,''.join(paths),tone,1.) for tone,paths in opaque.items()]+layered
    opaque.clear()
    fragments=[];pending=[];last=None
    def flush():
        if not pending:return
        mode,tone,alpha=last
        paint=('fill="'+tone+'" fill-opacity="'+_n(alpha)+'"' if mode==0 else
               'stroke="'+tone+'" stroke-width="'+_n(.30 if style=='soft' else .44 if policy['line_only'] else .38)+'"')
        fragments.append('<path d="'+''.join(pending)+'" '+paint+'/>');pending.clear()
    for _,mode,path,tone,alpha in draw:
        key=(mode,tone,alpha)
        if key!=last:flush();last=key
        pending.append(path)
    flush();checkpoint(cancel);body=_svg(''.join(fragments))
    if len(body.encode('utf8'))>MAX_SVG_BYTES:return {}
    # Meshes and reference records are local variables, never retained in a
    # module cache. The outer gallery's existing 16-item cache owns SVG only.
    return dict(id=model_id,kind=kind,label=row['label'],brand=row['brand'],style=style,
        svg=body,body_svg=body,foreground_svg='',rotors=[],reference_details=True,
        sources=list(row['sources']),fidelity='actual_mesh_projection_reference',
        motion_source='static_reference_mesh',rotation_direction_verified=False,original_face='none',
        reference_notes='The same bounded component mesh as the 3D reference. Fine contours, unverified dimensions, '
                        'contacts and mounting details remain schematic. No live water temperature, flow or pump speed.',
        art_details=dict(geometry_source='liquid_geometry046.build_component',detail_level='eco',
            geometry_family=row['geometry_family'],form=row['form'],triangle_count=count,
            projected_triangle_count=front_count,merged_face_count=len(faces),merge_work=merge_work,
            visible_face_polygons=visible_polygons,crease_edge_count=edge_count,
            view_filtered_smooth_edges=filtered_edges,smooth_tag_memo_entries=len(view_tags),
            occlusion_work=visibility.work,occlusion_clipping=True,
            geometry_digest=digest.hexdigest(),shape_path_digest=shape.hexdigest(),
            dimensions_mm=physical['dimensions_mm'],reference_envelope_mm=physical['reference_envelope_mm'],
            dimensions_verified=row['dimensions_verified'],coordinates_verified=False,
            physical_shape_shared_across_styles=True,telemetry_bound=False,reference_camera=True))
