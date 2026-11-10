"""Fixed GX601 front cover and the same bounded physical material representation.

Original reference geometry: PolyForm Noncommercial 1.0.0. Manufacturer source
photos establish part topology/orientation, not CAD dimensions or mounting fit.
No photos are distributed, and no fan selection enters this fixed construction.
Importing performs no native, profile, sensor, Scene or background work.
"""
from dataclasses import dataclass
from fractions import Fraction as F
import math
import struct

CASE_ID='asus-rog-strix-helios-gx601'
PART_ID='case:psu-front-cover'
MESH_NAME='helios-psu-front-cover'
SOURCE_PAGE='https://partshop.asus.com/us/90dc0020-b001jc.html'


@dataclass(frozen=True)
class Drawing:
    """All values are ratios to the local side-fold length, never millimetres."""
    side_height: F = F(8, 25)
    fold_width: F = F(7, 200)
    shoulder_start: F = F(21, 50)
    broad_start: F = F(1, 2)
    broad_width: F = F(41, 50)
    sheet_offset: F = F(3, 500)
    bridge_centres: tuple = (F(33, 50), F(83, 100))
    bridge_width: F = F(9, 500)
    slit_width: F = F(3, 500)
    bridge_start: F = F(4, 25)
    bridge_end: F = F(18, 25)
    bridge_ramp: F = F(3, 50)
    bridge_rise: F = F(3, 100)

REFERENCE = Drawing()

def _validate(d):
    if not isinstance(d, Drawing):
        raise TypeError('Explicit reference Drawing required')
    numbers = (d.side_height, d.fold_width, d.shoulder_start, d.broad_start,
               d.broad_width, d.sheet_offset, d.bridge_width, d.slit_width,
               d.bridge_start, d.bridge_end, d.bridge_ramp, d.bridge_rise,
               *d.bridge_centres)
    if any(type(value) is not F or value <= 0 for value in numbers):
        raise ValueError('Use positive rational reference coordinates')
    if not (d.shoulder_start < d.broad_start < 1 and d.fold_width < d.broad_width
            and d.bridge_start + 2*d.bridge_ramp < d.bridge_end < d.broad_width
            and d.bridge_rise < d.bridge_ramp and d.sheet_offset < d.slit_width*2
            and len(d.bridge_centres) == 2 and d.bridge_centres[0] < d.bridge_centres[1]):
        raise ValueError('Invalid fixed reference sheet topology')
    intervals = []
    for centre in d.bridge_centres:
        half = d.bridge_width/2
        interval = (centre-half-d.slit_width, centre+half+d.slit_width)
        if not d.broad_start < interval[0] < interval[1] < 1:
            raise ValueError('Both strips belong to the broad roof')
        intervals.append(interval)
    if intervals[0][1] >= intervals[1][0]:
        raise ValueError('Reference strips cannot touch')

def roof_width(u, drawing=REFERENCE):
    """Independent roof outline; a long narrow fold survives at the short end."""
    d = drawing
    if not 0 <= u <= 1:
        return F(0)
    if u <= d.shoulder_start:
        return d.fold_width
    if u >= d.broad_start:
        return d.broad_width
    return d.fold_width + (d.broad_width-d.fold_width)*(u-d.shoulder_start)/(d.broad_start-d.shoulder_start)

def _in_slit(u, v, d):
    if not d.bridge_start < v < d.bridge_end:
        return False
    half = d.bridge_width/2
    return any(centre-half-d.slit_width < u < centre-half
               or centre+half < u < centre+half+d.slit_width
               for centre in d.bridge_centres)

def _rise(u, v, d):
    half = d.bridge_width/2
    if not any(centre-half <= u <= centre+half for centre in d.bridge_centres):
        return F(0)
    if not d.bridge_start <= v <= d.bridge_end:
        return F(0)
    return d.bridge_rise*min(F(1), (v-d.bridge_start)/d.bridge_ramp,
                             (d.bridge_end-v)/d.bridge_ramp)

def _clip_roof(poly, slope, intercept):
    """Clip one grid cell against its affine roof boundary, using exact ratios."""
    result = []
    for a, b in zip(poly, (*poly[1:], poly[0])):
        da = slope*a[0] + intercept - a[1]
        db = slope*b[0] + intercept - b[1]
        if da >= 0:
            result.append(a)
        if (da < 0) != (db < 0):
            t = da/(da-db)
            result.append(tuple(a[k] + t*(b[k]-a[k]) for k in (0, 1)))
    # Exact Fraction identity removes only duplicates, never nearby coordinates.
    clean = []
    for point in result:
        if not clean or clean[-1] != point:
            clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    return tuple(clean)

def _cells(d):
    us = {F(0), F(1), d.shoulder_start, d.broad_start}
    half = d.bridge_width/2
    for centre in d.bridge_centres:
        us.update((centre-half-d.slit_width, centre-half, centre+half,
                   centre+half+d.slit_width))
    vs = sorted({-d.side_height, F(0), d.fold_width, d.broad_width,
                 d.bridge_start, d.bridge_start+d.bridge_ramp,
                 d.bridge_end-d.bridge_ramp, d.bridge_end})
    us = sorted(us)
    result = []
    for u0, u1 in zip(us, us[1:]):
        width0, width1 = roof_width(u0, d), roof_width(u1, d)
        slope = (width1-width0)/(u1-u0)
        intercept = width0-slope*u0
        for v0, v1 in zip(vs, vs[1:]):
            if _in_slit((u0+u1)/2, (v0+v1)/2, d):
                continue
            cell = _clip_roof(((u0,v0),(u1,v0),(u1,v1),(u0,v1)), slope, intercept)
            if len(cell) >= 3:
                area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(cell,(*cell[1:],cell[0])))
                if area > 0:
                    result.append(cell)
    return tuple(result)

def sub(a,b):return tuple(a[k]-b[k]for k in range(3))

def dot(a,b):return sum(a[k]*b[k]for k in range(3))

def cross(a,b):return(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])

def signed6(a,b,c,d):return dot(cross(sub(b,a),sub(c,a)),sub(d,a))

def bounds(points):
    points=tuple(points)
    if not points:raise ValueError('Nonempty geometry required')
    return(tuple(min(p[k]for p in points)for k in range(3)),tuple(max(p[k]for p in points)for k in range(3)))

def overlaps(a,b):return all(a[0][k]<=b[1][k]and b[0][k]<=a[1][k]for k in range(3))

@dataclass(frozen=True)
class WorldCover:
    points:tuple
    tetrahedra:tuple
    boundary:tuple
    vertices:tuple
    datum:dict
    part_id:str=PART_ID
    mesh_name:str=MESH_NAME
    dimensions_verified:bool=False
    mounting_fit_verified:bool=False
    fixing_ears_placed:bool=False

def reference_datum(dimensions=(250.,591.,565.)):
    if len(dimensions)!=3 or any(type(v)not in(int,float)or not math.isfinite(v)for v in dimensions):
        raise ValueError('Finite fixed case dimensions required')
    w,h,d=map(float,dimensions)
    if not(200<=w<=330 and 500<=h<=700 and 480<=d<=700):raise ValueError('GX601 reference envelope out of scope')
    half=(w-12)/2;front=(d-12)/2;bottom=-h*.49;top=-h*.32
    split_bottom=-front+2*front*.340;split_top=-front+2*front*.557
    return dict(width=w,height=h,depth=d,half=half,front=front,bottom=bottom,top=top,
        split_bottom=split_bottom,split_top=split_top,seam_slope=(split_top-split_bottom)/(top-bottom),
        thickness_reference_mm=1.2,bridge_height_reference_mm=2.5,
        dimensions_verified=False,installation_axes_source='official user step5/6 + detached front printed side',
        narrow_end_world_axis='+Z',wide_end='rear diagonal seam',roof_inward_world_axis='+X')

def build_cover(dimensions=(250.,591.,565.)):
    """One fixed cover. All choices are independent of mounted hardware/style.

    Triangular sheet cells use a consistent ordered 3-tetra decomposition.
    The returned visible boundary is extracted from these SAME material cells,
    so collision logic cannot silently keep the obsolete full-roof prism.
    """
    d=REFERENCE;_validate(d);r=reference_datum(dimensions)
    cells=_cells(d)
    points=[];point_ids={};tetra=[];faces={}
    def point_id(uv,inside):
        key=(uv[0],uv[1],inside)
        if key in point_ids:return point_ids[key]
        u,v=map(float,uv)
        local_height=float(_rise(*uv,d))if v>=0 else v
        height=(local_height/float(d.bridge_rise)*r['bridge_height_reference_mm']if local_height>0
                else local_height/float(d.side_height)*(r['top']-r['bottom']-r['thickness_reference_mm']))
        x=-r['half']+max(0.,v)/float(d.broad_width)*(2*r['half']-r['thickness_reference_mm'])
        y=r['top']+height
        z=r['front']-u*((r['front']-r['split_top'])-r['seam_slope']*height)
        if inside:
            x+=r['thickness_reference_mm'];y-=r['thickness_reference_mm']
            z-=u*r['seam_slope']*r['thickness_reference_mm']
        if not all(math.isfinite(v)for v in(x,y,z)):raise ValueError('Nonfinite mapped point')
        # This is the renderer's actual float32 position representation, not
        # rounded welding. Collapsed cells are rejected, never silently fixed.
        mapped=struct.unpack('<fff',struct.pack('<fff',x,y,z))
        result=len(points);point_ids[key]=result;points.append(mapped);return result
    def add_tetra(ids):
        a,b,c,e=(points[i]for i in ids);volume=signed6(a,b,c,e)
        if not volume or not math.isfinite(volume):raise ValueError('Collapsed world material cell')
        if volume<0:ids=(ids[0],ids[2],ids[1],ids[3])
        tetra.append(ids)
        for face,opposite in(((ids[0],ids[1],ids[2]),ids[3]),((ids[0],ids[3],ids[1]),ids[2]),
                              ((ids[0],ids[2],ids[3]),ids[1]),((ids[1],ids[3],ids[2]),ids[0])):
            a,b,c=(points[i]for i in face)
            if dot(cross(sub(b,a),sub(c,a)),sub(points[opposite],a))>0:face=tuple(reversed(face))
            key=tuple(sorted(face))
            if key in faces:
                previous=faces.pop(key)
                reverse=tuple(reversed(previous))
                if not any(face==reverse[i:]+reverse[:i]for i in range(3)):
                    raise ValueError('Two material cells use a face on the same side')
                # Keep a tombstone separately below to reject a third reuse.
                cancelled.add(key)
            elif key in cancelled:raise ValueError('Nonmanifold shared material face')
            else:faces[key]=face
    cancelled=set()
    for cell in cells:
        for at in range(1,len(cell)-1):
            # Global UV ordering chooses the same side-quad diagonal for either
            # adjacent triangle; no rounding or independent seam welding.
            a,b,c=sorted((cell[0],cell[at],cell[at+1]))
            aa,bb,cc=(point_id(p,False)for p in(a,b,c))
            ai,bi,ci=(point_id(p,True)for p in(a,b,c))
            for ids in((aa,bb,cc,ai),(bb,cc,ai,bi),(cc,ai,bi,ci)):add_tetra(ids)
    boundary=tuple(faces.values());vertices=[]
    for face in boundary:
        a,b,c=(points[i]for i in face);normal=cross(sub(b,a),sub(c,a));length=math.hypot(*normal)
        if not length:raise ValueError('Degenerate world boundary')
        normal=tuple(n/length for n in normal)
        for p in(a,b,c):vertices.extend((*p,*normal))
    return WorldCover(tuple(points),tuple(tetra),boundary,tuple(vertices),r)

def material_planes(cover,tet):
    """Actual tetra faces, normalized inward halfspaces n·p+c >= 0."""
    result=[]
    for indices,other in(((0,1,2),3),((0,3,1),2),((0,2,3),1),((1,3,2),0)):
        a,b,c=(cover.points[tet[i]]for i in indices)
        normal=cross(sub(b,a),sub(c,a));length=math.hypot(*normal)
        normal=tuple(n/length for n in normal)
        if dot(normal,sub(cover.points[tet[other]],a))<0:normal=tuple(-n for n in normal)
        result.append((*normal,-dot(normal,a)))
    return tuple(result)

def distance_triangle(point,a,b,c):
    ab,ac=sub(b,a),sub(c,a);normal=cross(ab,ac);length=math.hypot(*normal)
    if not length:raise ValueError('Degenerate boundary triangle')
    normal=tuple(n/length for n in normal);height=dot(normal,sub(point,a))
    projected=tuple(point[k]-height*normal[k]for k in range(3))
    if all(dot(cross(sub(y,x),sub(projected,x)),normal)>=-1e-10
           for x,y in((a,b),(b,c),(c,a))):return abs(height)
    result=[]
    for x,y in((a,b),(b,c),(c,a)):
        edge=sub(y,x);t=max(0.,min(1.,dot(sub(point,x),edge)/dot(edge,edge)))
        result.append(math.dist(point,tuple(x[k]+t*edge[k]for k in range(3))))
    return min(result)

def contains_material(cover,point,margin=1e-5):
    if not 0<=margin<=.01:raise ValueError('Fixed strict material margin out of scope')
    # Internal tetra faces are inclusive. Shrinking every tetra separately
    # would invent cracks and could miss a fan surface on an internal face.
    present=any(all(dot(plane[:3],point)+plane[3]>=-1e-9 for plane in material_planes(cover,tet))
                for tet in cover.tetrahedra if overlaps(bounds(cover.points[i]for i in tet),(point,point)))
    return present and min(distance_triangle(point,*(cover.points[i]for i in face))for face in cover.boundary)>margin

def triangle_material_witness(cover,triangles,margin=1e-5,max_triangles=60000):
    """Strict actual fan-surface area inside actual cover tetrahedra.

    This replaces the legacy full-roof analytic prism for the limited private
    consumer. It does not claim a complete two-closed-solid containment test.
    Caller must also retain verified closed-solid containment controls before
    declaring a full assembly fit; unknown input remains a failed review.
    """
    if not 0<=margin<=.01:raise ValueError('Fixed strict material margin out of scope')
    material=[(bounds(cover.points[i]for i in tet),material_planes(cover,tet))for tet in cover.tetrahedra]
    for index,tri in enumerate(triangles):
        if index>=max_triangles:return dict(reference_review='bounded_check_exhausted',clear=False)
        if len(tri)!=3 or any(len(p)!=3 or not all(math.isfinite(v)for v in p)for p in tri):
            raise ValueError('Finite actual triangle coordinates required')
        original_area=math.hypot(*cross(sub(tri[1],tri[0]),sub(tri[2],tri[0])))/2
        if not original_area:return dict(clear=False,reference_review='degenerate_or_underflow_input_triangle',triangle_index=index)
        tri_bounds=bounds(tri)
        for cell,(box,planes)in enumerate(material):
            if not overlaps(box,tri_bounds):continue
            poly=tuple(tri)
            for plane in planes:
                out=[]
                for a,b in zip(poly,(*poly[1:],poly[0])):
                    # Inclusive numerical guard on internal partitions only;
                    # actual external boundary distance below remains strict.
                    da=dot(plane[:3],a)+plane[3]+1e-9;db=dot(plane[:3],b)+plane[3]+1e-9
                    if da>=0:out.append(a)
                    if(da<0)!=(db<0):
                        t=da/(da-db);out.append(tuple(a[k]+t*(b[k]-a[k])for k in range(3)))
                poly=tuple(out)
                if not poly:break
            area=sum(math.hypot(*cross(sub(poly[i],poly[0]),sub(poly[i+1],poly[0])))/2
                     for i in range(1,len(poly)-1))
            centre=tuple(sum(p[k]for p in poly)/len(poly)for k in range(3))if poly else None
            if centre is not None and contains_material(cover,centre,margin):
                if not area:
                    return dict(clear=False,reference_review='intersection_area_underflow',
                                triangle_index=index,material_tetrahedron=cell)
                # A tiny nonzero face wholly inside material is still a real
                # intersection. An absolute area cutoff cannot prove clear.
                return dict(clear=False,triangle_index=index,material_tetrahedron=cell,
                            strict_interior_surface_mm2=area,witness_polygon_world_mm=poly)
    return dict(clear=True,scope='actual triangle surfaces only; full closed-solid containment not covered')

def _ray_inside(triangles,point,direction):
    hits=[]
    for a,b,c in triangles:
        e1,e2=sub(b,a),sub(c,a);h=cross(direction,e2);det=dot(e1,h)
        if abs(det)<1e-12:continue
        s=sub(point,a);u=dot(s,h)/det
        if not 0<=u<=1:continue
        q=cross(s,e1);v=dot(direction,q)/det
        if v<0 or u+v>1:continue
        t=dot(e2,q)/det
        if t>1e-9:hits.append(t)
    hits.sort();unique=[]
    for value in hits:
        if not unique or abs(value-unique[-1])>1e-8:unique.append(value)
    return bool(len(unique)%2)

def closed_pair_review(cover,triangles,*,other_closed_verified=False,margin=1e-5):
    """Private fixed consumer: real surfaces plus the reverse-containment case.

    A caller cannot silently treat an arbitrary/open fan surface as a solid.
    Positive witnesses are useful even for unknown inputs, but clear requires
    independent closed-material verification of the input component.
    """
    triangles=tuple(triangles)
    if not triangles or len(triangles)>60000:return dict(clear=False,reference_review='missing_or_unbounded_component')
    result=triangle_material_witness(cover,triangles,margin)
    if not result['clear']:return result
    other_bounds=bounds(p for tri in triangles for p in tri)
    if not any(overlaps(bounds(cover.points[i]for i in tet),other_bounds)for tet in cover.tetrahedra):
        return dict(clear=True,proof='all_actual_material_cell_bounds_disjoint',
                    scope='bounded represented geometry; not manufacturing clearance')
    if other_closed_verified is not True:return dict(clear=False,reference_review='other_closed_material_unverified')
    directions=((1.,.173,.317),(.317,1.,.173),(.173,.317,1.))
    for index,tet in enumerate(cover.tetrahedra):
        points=tuple(cover.points[i]for i in tet)
        if not overlaps(bounds(points),other_bounds):continue
        centre=tuple(sum(p[k]for p in points)/4 for k in range(3))
        if not contains_material(cover,centre,margin):continue
        inside=tuple(_ray_inside(triangles,centre,d)for d in directions)
        if len(set(inside))!=1:return dict(clear=False,reference_review='ray_parity_ambiguous',material_tetrahedron=index)
        distance=min(distance_triangle(centre,*tri)for tri in triangles)
        if all(inside)and distance>margin:
            return dict(clear=False,material_tetrahedron=index,witness_world_mm=centre,
                        other_boundary_distance_mm=distance,proof='cover_material_inside_closed_other')
    return dict(clear=True,scope='bounded actual fixed mesh pair, surface and reverse containment; reference dimensions only')

def replacement_mesh(cover,tone,mesh_factory):
    """Explicit consumer seam; no lazy Scene import or special drawing mask."""
    return mesh_factory(MESH_NAME,cover.vertices,tuple(tone),component='case',part_id=PART_ID)

def collision_query(cover,*,closed_verifier=None):
    """Private replacement for the legacy _front_fan_intersection callback.

    Meshes are inspected independently: overlapping closed decoration pieces
    must not cancel each other through XOR parity on one combined triangle soup.
    Positive/unknown results retain public finish()'s conservative withdrawal.
    A None result means all the included represented meshes were actually clear.
    """
    def query(meshes,meta):
        if cover is None:return dict(reference_review='front_material_missing')
        if meta.get('case_id')!=CASE_ID:return dict(reference_review='wrong_case_material')
        seen=0;represented=0
        for mesh in meshes:
            if any(word in mesh.name for word in('wire','lead','connector')):continue
            values=mesh.vertices;position=mesh.position
            if len(values)%18:return dict(reference_review='incomplete_triangle_mesh',mesh_name=mesh.name)
            triangles=[]
            for at in range(0,len(values),18):
                seen+=1
                if seen>60000:return dict(reference_review='bounded_check_exhausted',mesh_name=mesh.name)
                triangles.append(tuple(tuple(values[at+j+k]+position[k]for k in range(3))for j in(0,6,12)))
            if not triangles:continue
            represented+=1
            closed=closed_verifier(mesh)if closed_verifier is not None else False
            proof=closed_pair_review(cover,triangles,other_closed_verified=closed)
            if not proof['clear']:return dict(proof,mesh_name=mesh.name)
        return None if represented else dict(reference_review='missing_front_fan_material_meshes')
    return query

def make_front(dimensions,tone):
    """One owner-scoped collision sidecar; the ordinary Mesh holds only PN."""
    from assembly_geometry import Mesh
    cover=build_cover(dimensions)
    return replacement_mesh(cover,tone,Mesh),cover


def material_identity_problem(front,material):
    """The visible fixed part must own exactly this material's PN representation."""
    if not isinstance(material,WorldCover):return 'front_material_missing_or_wrong_type'
    if material.part_id!=PART_ID or material.mesh_name!=MESH_NAME:return 'front_material_identity_mismatch'
    if (getattr(front,'part_id',None)!=PART_ID or getattr(front,'name',None)!=MESH_NAME
            or getattr(front,'component',None)!='case'):return 'front_part_identity_mismatch'
    if getattr(front,'vertices',None)is not material.vertices:return 'front_visible_material_mismatch'
    if getattr(front,'position',None)!=(0.,0.,0.)or getattr(front,'rotor',True)is not False:
        return 'front_fixed_pose_unverified'
    return None


def query_front_fans(meshes,meta,material,*,identity_issue=None):
    """Only the paired actual material may review a new front; never a prism."""
    if identity_issue is not None:return dict(reference_review=identity_issue)
    if not isinstance(material,WorldCover):return dict(reference_review='front_material_missing_or_wrong_type')
    return collision_query(material)(meshes,meta)
