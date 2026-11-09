"""On-demand native OpenGL assembly viewport using existing Qtbase libraries.

Import this module only when the user opens the assembly viewer. There is no
Quick3D, external asset loader, hardware access, polling or animation timer.
Original code/art: PolyForm Noncommercial 1.0.0, see LICENSE and LICENSING.md.
"""
import math
import struct
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMatrix4x4, QVector2D, QVector3D, QVector4D, QSurfaceFormat
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLFunctions_3_3_Core, QOpenGLShader,
                             QOpenGLShaderProgram, QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from assembly_geometry import Scene,build_scene, number, vertex_bytes
from assembly_style import edge_batches,material_for,style_for
from assembly_effects import SelectionEffect,component_family,effect_for,effect_sample
from assembly_scene_cache import SceneCache
from assembly_visibility048 import hidden_mesh_ids,psu_cover_mesh_ids
from assembly_gpu_insertion049 import GpuInsertion,insertion_plan
from assembly_pose052 import (valid_offsets,valid_hidden,hidden as pose_hidden,
                             offset_for,posed_bounds,sphere as box_sphere)
from assembly_part_motion052 import PartMotion,hidden_connections
from assembly_inspection import part_family
from top_bar_feedback import GPU_FAN_MAX_AGE

GL_FLOAT=0x1406
GL_TRIANGLES=0x0004
GL_LINES=0x0001
GL_DEPTH_TEST=0x0B71
GL_POLYGON_OFFSET_FILL=0x8037
GL_LESS=0x0201
GL_LEQUAL=0x0203
GL_BLEND=0x0BE2
GL_SRC_ALPHA=0x0302
GL_ONE_MINUS_SRC_ALPHA=0x0303
GL_ONE=1
GL_COLOR_BUFFER_BIT=0x4000
GL_DEPTH_BUFFER_BIT=0x0100


def ink_depth_bias(distance,radius):
    """Conservative NDC lift: at most .025 scene-mm at the farthest surface.

    This covers surface-line raster precision while preserving real opaque
    layers, including CPU contacts behind the substrate. It is not an x-ray
    pass: depth testing stays enabled, and all triangle positions stay intact.
    """
    near=max(.1,distance-radius*1.5);far=distance+radius*2.
    derivative=2*far*near/max(1e-9,far-near)/max(1.,distance+radius)**2
    return max(0.,min(.00015,derivative*.025))


def ray_box(origin,direction,low,high):
    """Nearest nonnegative ray/AABB distance; pure click-time broad phase."""
    near,far=0.,float('inf')
    for axis in range(3):
        if abs(direction[axis])<1e-12:
            if not low[axis]<=origin[axis]<=high[axis]:return None
            continue
        a=(low[axis]-origin[axis])/direction[axis];b=(high[axis]-origin[axis])/direction[axis]
        near=max(near,min(a,b));far=min(far,max(a,b))
        if near>far:return None
    return near if far>=0 else None


def ray_triangle(origin,direction,a,b,c):
    """Two-sided Möller–Trumbore hit; no GL query or sensor work."""
    def cross(x,y):return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    def dot(x,y):return sum(a*b for a,b in zip(x,y))
    e1=tuple(b[n]-a[n] for n in range(3));e2=tuple(c[n]-a[n] for n in range(3))
    p=cross(direction,e2);det=dot(e1,p)
    if abs(det)<1e-10:return None
    t=tuple(origin[n]-a[n] for n in range(3));u=dot(t,p)/det
    if not -1e-8<=u<=1+1e-8:return None
    q=cross(t,e1);v=dot(direction,q)/det
    if v< -1e-8 or u+v>1+1e-8:return None
    distance=dot(e2,q)/det
    return distance if distance>=0 else None


def mesh_phase(mesh,phase):
    value=phase.get(getattr(mesh,'part_id',''),phase.get(mesh.component,0.)) if isinstance(phase,dict) else phase
    return float(value) if type(value) in (int,float) and math.isfinite(value) else 0.


ASSEMBLY_COMPONENTS=('all','gpu','cpu','memory','board','case','cooler','fans','psu','storage','expansion','cables')


def scene_bounds(scene,selected,shift):
    """Build the same focus/part bounds with one local scan per mesh.

    Styles share physical arrays. Compute their local extrema once for this
    upload, then translate the small bounds for normal/exploded poses. No
    vertex copies or cache survive the call; rotors keep their existing
    conservative, unposed bounds and picking still tests real triangles.
    """
    local=[]
    for mesh in scene.meshes:
        low=[];high=[]
        for axis in range(3):
            values=mesh.vertices[axis::6]
            low.append(min(values));high.append(max(values))
        local.append((mesh,low,high))
    bounds={};pick_bounds={}
    targets=(*ASSEMBLY_COMPONENTS,*dict.fromkeys(getattr(mesh,'part_id','') for mesh in scene.meshes if getattr(mesh,'part_id','')))
    for focus in targets:
        rows=[row for row in local if selected(row[0],focus)]
        if not rows:continue
        for exploded in (False,True):
            low=[float('inf')]*3;high=[float('-inf')]*3
            for mesh,local_low,local_high in rows:
                offset=shift(mesh,exploded)
                for axis in range(3):
                    low[axis]=min(low[axis],local_low[axis]+mesh.position[axis]+offset[axis])
                    high[axis]=max(high[axis],local_high[axis]+mesh.position[axis]+offset[axis])
            center=tuple((low[i]+high[i])/2 for i in range(3))
            radius=math.sqrt(sum((high[i]-low[i])**2 for i in range(3)))/2
            bounds[(focus,exploded)]=(center,max(1.,radius))
            pick_bounds[(focus,exploded)]=(tuple(low),tuple(high))
    return bounds,pick_bounds


def posed_point(mesh,point,shift=(0.,0.,0.),phase=0.):
    phase=mesh_phase(mesh,phase)
    if mesh.rotor and phase:
        x,y,z=point;axis=mesh.axis;length=math.sqrt(sum(v*v for v in axis))
        if length:
            a,b,c=(v/length for v in axis);angle=math.radians(phase*mesh.direction)
            co,si=math.cos(angle),math.sin(angle);dot=a*x+b*y+c*z
            point=(x*co+(b*z-c*y)*si+a*dot*(1-co),
                   y*co+(c*x-a*z)*si+b*dot*(1-co),
                   z*co+(a*y-b*x)*si+c*dot*(1-co))
    return tuple(point[n]+mesh.position[n]+shift[n] for n in range(3))

VERTEX_SHADER='''#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 normal;
uniform mat4 matrix;
uniform mat4 modelMatrix;
uniform mat3 normalMatrix;
uniform float backgroundMode;
uniform vec4 inkProjection;
out vec3 worldNormal;
out vec3 worldPosition;
out vec3 adjacentNormal;
flat out float silhouetteEdge;
vec3 oct12Normal(float packedValue) {
 vec2 p=vec2(mod(packedValue,4096.0),floor(packedValue/4096.0))/4095.0*2.0-1.0;
 vec3 n=vec3(p,1.0-abs(p.x)-abs(p.y));
 if(n.z<0.0)n.xy=(1.0-abs(n.yx))*vec2(n.x>=0.0?1.0:-1.0,n.y>=0.0?1.0:-1.0);
 return normalize(n);
}
void main() {
 adjacentNormal=vec3(0.0);silhouetteEdge=0.0;
 if(backgroundMode>0.5) {
  vec2 point=gl_VertexID==0?vec2(-1.0,-1.0):gl_VertexID==1?vec2(3.0,-1.0):vec2(-1.0,3.0);
  worldNormal=vec3(0.0,0.0,1.0);worldPosition=vec3(0.0);gl_Position=vec4(point,0.0,1.0);
 } else {
  if(normal.z < -1.5) {
   worldNormal=normalMatrix*oct12Normal(normal.x);
   adjacentNormal=normalMatrix*oct12Normal(normal.y);silhouetteEdge=1.0;
  } else worldNormal=normalMatrix*normal;
  worldPosition=(modelMatrix*vec4(position,1.0)).xyz;
  gl_Position=matrix*vec4(position,1.0);
  if(inkProjection.x>0.0) {
   float wave=dot(position,vec3(.071,.043,.053))+inkProjection.w*.17;
   gl_Position.xy+=sin(vec2(wave,wave+2.1))*inkProjection.yz*gl_Position.w;
   gl_Position.z-=inkProjection.x*gl_Position.w;
  }}
}
'''
FRAGMENT_SHADER='''#version 330 core
in vec3 worldNormal;
in vec3 worldPosition;
in vec3 adjacentNormal;
flat in float silhouetteEdge;
uniform vec4 baseColor;
uniform float shadeMix;
uniform float backgroundMode;
uniform vec4 paperColor;
uniform vec4 paperGridColor;
uniform vec3 eyePosition;
uniform vec4 surfaceMaterial;
uniform vec4 effectParams;
uniform vec3 effectCenter;
uniform vec3 effectScale;
uniform vec4 shadowInverse;
uniform vec2 shadowCenter;
uniform vec4 shadowColor;
out vec4 fragment;
float hash21(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float thin(float value,float width){return 1.0-smoothstep(width,width+0.016,abs(value));}
void main() {
 if(backgroundMode>0.5) {
  vec2 cell=mod(gl_FragCoord.xy,24.0);
  float line=backgroundMode<1.5?1.0-step(0.9,min(cell.x,cell.y)):0.0;
  vec3 paper=mix(paperColor.rgb,paperGridColor.rgb,line*0.17);
  vec2 delta=gl_FragCoord.xy-shadowCenter;
  vec2 local=vec2(dot(delta,shadowInverse.xy),dot(delta,shadowInverse.zw));
  float blob=exp(-dot(local,local)*3.4);
  float contact=exp(-dot(local*vec2(1.8,2.5),local*vec2(1.8,2.5))*3.0);
  fragment=vec4(mix(paper,shadowColor.rgb,shadowColor.a*(blob*.64+contact*.36)),1.0);return;
 }
 vec3 n=normalize(worldNormal);
 vec3 v=normalize(eyePosition-worldPosition);
 if(effectParams.w>.5&&silhouetteEdge>.5) {
  float a=dot(worldNormal,v),b=dot(adjacentNormal,v);
  if(min(a,b)>0.0||max(a,b)<0.0)discard;
 }
 vec3 l=normalize(vec3(-0.7,1.0,0.8));
 float key=max(0.0,dot(n,l));
 float fill=max(0.0,dot(n,normalize(vec3(0.8,0.3,-0.6))));
 float edge=pow(1.0-max(0.0,abs(dot(n,v))),3.0);
 float rough=surfaceMaterial.y;
 float spec=pow(max(0.0,dot(n,normalize(v+l))),mix(100.0,7.0,rough));
 vec3 f0=mix(vec3(.045),baseColor.rgb,surfaceMaterial.x);
 vec3 studio=baseColor.rgb*(.56+.30*key+.15*fill)+f0*spec*(.85-.45*rough)+f0*edge*.18;
 float grain=sin(worldPosition.y*2.8+sin(worldPosition.z*.13)*.8);
 if(surfaceMaterial.w>.5&&surfaceMaterial.w<1.5)studio*=1.0+grain*.018;
 if(surfaceMaterial.w>1.5)studio*=.97+.025*sin(worldPosition.x*.28+sin(worldPosition.y*.09)*2.0);
 vec3 rgb=mix(baseColor.rgb,studio,shadeMix);
 float alpha=baseColor.a;
 if(surfaceMaterial.z>.5&&shadeMix>.5){
  float reflection=pow(max(0.0,dot(reflect(-v,n),normalize(vec3(-.2,.85,.5)))),18.0);
  rgb=mix(baseColor.rgb,vec3(.89,.95,.98),reflection*.42+edge*.24);
  alpha=clamp(baseColor.a*.45+edge*.18+reflection*.08,.025,.35);
 }
 float kind=effectParams.x;float p=effectParams.y;float amount=effectParams.z;
 bool ink=effectParams.w>.5;
 vec3 q=(worldPosition-effectCenter)*effectScale+.5;
 vec3 axis=abs(n);vec2 uv=axis.x>axis.y&&axis.x>axis.z?q.zy:axis.y>axis.z?q.xz:q.xy;
 vec3 accent=vec3(.25,.66,.88);float signal=0.0;
 if(kind>.5&&kind<1.5){
  signal=thin(uv.x*.65+uv.y*.35-(p*1.45-.2),.045);rgb+=vec3(.74,.82,.88)*signal*amount*.40;
 }else if(kind<2.5&&kind>1.5){
  float pulse=sin(p*6.28318)*sin(p*6.28318);signal=pow(edge,.45)*(.30+.70*pulse);
  rgb=mix(rgb,vec3(.98,.83,.64),signal*amount*.46);
 }else if(kind<3.5&&kind>2.5){
  vec2 cell=floor(uv*vec2(20.0,24.0));float dotInk=step(hash21(cell),p);
  signal=dotInk*(.35+.65*hash21(cell+3.1));rgb=mix(rgb,accent,signal*amount*.30);
 }else if(kind<4.5&&kind>3.5){
  if(ink){float drawn=smoothstep(uv.y-.018,uv.y+.018,p*1.1);
   rgb=mix(paperColor.rgb,rgb,.15+.85*drawn);rgb+=vec3(.16,.35,.42)*thin(uv.y-p,.025)*amount;}
 }else if(kind<5.5&&kind>4.5){
  float radius=length((uv-.5)*vec2(1.0,1.12));signal=thin(radius-p*.85,.025);
  rgb=mix(rgb,vec3(1.,.96,.83),signal*amount*.72);
 }else if(kind<6.5&&kind>5.5){
  float band=floor(uv.y*6.0);float reveal=smoothstep(band/8.0,band/8.0+.18,p);
  float seam=1.0-smoothstep(.0,.045,fract(uv.y*6.0));
  rgb*=1.0-amount*(.13*(1.0-reveal)+seam*.15);
 }else if(kind<7.5&&kind>6.5){
  float radius=length(uv-.5);float tide=.03*sin(uv.x*23.+uv.y*13.);
  float wash=1.0-smoothstep(p*.8-.14+tide,p*.8+tide,radius);
  signal=wash*(.65+.35*hash21(floor(uv*38.0)));rgb=mix(rgb,vec3(.18,.40,.57),signal*amount*.30);
 }else if(kind<8.5&&kind>7.5){
  signal=thin(uv.x-p,.018);rgb=mix(rgb,accent,signal*amount*.55);
 }else if(kind<9.5&&kind>8.5){
  if(ink){signal=step(.60,fract((q.x+q.y+q.z)*8.0-p*2.5));rgb=mix(rgb,accent,signal*amount*.80);}
 }else if(kind<10.5&&kind>9.5){
  signal=edge*thin(uv.y-p,.10);rgb+=vec3(.68,.82,.94)*signal*amount*.80;
 }else if(kind<11.5&&kind>10.5){
  signal=exp(-pow((uv.x-p)/.32,2.0))*(.35+.65*edge);rgb=mix(rgb,vec3(.93,.96,.98),signal*amount*.35);
 }else if(kind<12.5&&kind>11.5){
  float a=thin(fract((uv.x+uv.y)*30.)-.5,.055);
  float b=thin(fract((uv.x-uv.y)*25.)-.5,.035);
  signal=max(a,b)*smoothstep(uv.y-.08,uv.y+.08,p);rgb=mix(rgb,vec3(.24,.31,.36),signal*amount*.48);
 }else if(kind<13.5&&kind>12.5){
  float radius=length((uv-.5)*vec2(1.,1.2));
  signal=max(thin(radius-.23,.012),thin(radius-.29,.009));
  signal*=.60+.40*hash21(floor(uv*75.));rgb=mix(rgb,vec3(.43,.27,.39),signal*amount*.78);
 }
 fragment=vec4(clamp(rgb,0.0,1.0),alpha);
}
'''


def surface_format():
    fmt=QSurfaceFormat()
    fmt.setVersion(3,3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(0)
    return fmt


class AssemblyRenderer:
    """Small context-owned VBO renderer, also usable with a hidden FBO proof."""
    def __init__(self):
        self.functions=None;self.program=None;self.buffer=None;self.vao=None
        self.scene=None;self.ranges=[];self.edge_ranges=[];self.edge_segments=0
        self.policy=style_for('miniature');self._uniforms={};self.bounds={};self.pick_bounds={}
        self._pick_inverse=None;self._pick_projection=None;self._pick_camera_key=None
        self._pick_state=None;self.upload_count=0;self.draw_count=0
        self._materials={};self._frame_effect=None;self._shadow_key=None;self._shadow_parameters=None
        self._mesh_policies={};self._preview_light_tones={};self._frame_effect_samples={};self._frame_shade=None
        self._wide_lines=False
        self._cutaway_hidden=frozenset()
        self._psu_cover_ids=frozenset()
        self._gpu_power_ids=frozenset()
        self._pose_keys=frozenset();self._hidden_keys=frozenset();self._mesh_names=frozenset();self._pose_families={}
        self._frame_part_offsets={};self._frame_hidden_parts=frozenset();self._frame_hidden_names=frozenset()

    def initialize(self):
        self.functions=QOpenGLFunctions_3_3_Core()
        if not self.functions.initializeOpenGLFunctions():
            raise RuntimeError('OpenGL 3.3 is unavailable')
        # Some strict core contexts only accept unit-width lines. Probe once,
        # then keep the portable path; no state query is needed per frame.
        self.functions.glLineWidth(1.6)
        self._wide_lines=self.functions.glGetError()==0
        self.functions.glLineWidth(1.)
        self.program=QOpenGLShaderProgram()
        if not self.program.addShaderFromSourceCode(QOpenGLShader.Vertex,VERTEX_SHADER):
            raise RuntimeError('3-D vertex shader could not be compiled')
        if not self.program.addShaderFromSourceCode(QOpenGLShader.Fragment,FRAGMENT_SHADER):
            raise RuntimeError('3-D fragment shader could not be compiled')
        if not self.program.link():raise RuntimeError('3-D shader could not be linked')
        self._uniforms={name:self.program.uniformLocation(name) for name in ('backgroundMode','shadeMix')}
        self.vao=QOpenGLVertexArrayObject();self.buffer=QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        if not self.vao.create() or not self.buffer.create():raise RuntimeError('3-D buffers could not be allocated')
        self.vao.bind();self.buffer.bind();self.program.bind()
        self.program.enableAttributeArray(0);self.program.enableAttributeArray(1)
        self.program.setAttributeBuffer(0,GL_FLOAT,0,3,24)
        self.program.setAttributeBuffer(1,GL_FLOAT,12,3,24)
        self.buffer.release();self.vao.release();self.program.release()

    def upload(self,scene,*,ink_focus='all'):
        if self.program is None:raise RuntimeError('3-D context is not ready')
        self.scene=scene;raw=vertex_bytes(scene)
        self._cutaway_hidden=hidden_mesh_ids(scene.meshes)
        self._psu_cover_ids=psu_cover_mesh_ids(scene.meshes)
        prefixes=tuple(row['mesh_prefix'] for row in scene.metadata.get('auxiliary',{}).get('cables',())
                       if row.get('target_owner')=='gpu' and isinstance(row.get('mesh_prefix'),str) and row['mesh_prefix'])
        self._gpu_power_ids=frozenset(id(mesh) for mesh in scene.meshes if mesh.component=='cables'
            and any(mesh.name==prefix or mesh.name.startswith(prefix+'-') for prefix in prefixes))
        self.policy=style_for(scene.metadata.get('canvas_style',scene.metadata.get('visual_style')))
        styles=scene.metadata.get('mesh_style_ids')
        if not isinstance(styles,(tuple,list)) or len(styles)!=len(scene.meshes):
            styles=[scene.metadata.get('visual_style','miniature')]*len(scene.meshes)
        policies={identity:style_for(identity) for identity in dict.fromkeys(styles)}
        self._mesh_policies={id(mesh):policies[identity] for mesh,identity in zip(scene.meshes,styles)}
        self._materials={id(mesh):material_for(mesh,identity) for mesh,identity in zip(scene.meshes,styles)}
        lighting=scene.metadata.get('lighting_preview') or {}
        self._preview_light_tones={id(scene.meshes[row['mesh_index']]):scene.meshes[row['mesh_index']].color
            for row in lighting.get('zones',()) if lighting.get('mode','artwork')!='artwork'}
        self._shadow_key=None
        self.ranges=[];start=0
        for mesh in scene.meshes:
            self.ranges.append((mesh,start,mesh.vertex_count));start+=mesh.vertex_count
        # Static crease ink shares the same immutable VBO; no second context,
        # retained raster, draw timer or geometry upload is needed for styles.
        self.edge_ranges=[];chunks=[raw];self.edge_segments=0
        for mesh,vertices in edge_batches(scene.meshes,self.policy['id'],styles,focus=ink_focus):
            count=len(vertices)//6
            self.edge_ranges.append((mesh,start,count));start+=count;self.edge_segments+=count//2
            chunks.append(struct.pack('<'+str(len(vertices))+'f',*vertices))
        raw=b''.join(chunks)
        chunks.clear()
        self.buffer.bind();self.buffer.setUsagePattern(QOpenGLBuffer.StaticDraw)
        self.buffer.allocate(raw,len(raw));self.buffer.release()
        del raw
        self.bounds,self.pick_bounds=scene_bounds(scene,self._selected,self._shift)
        self._pose_keys=frozenset(key for key,_ in self.pick_bounds if key!='all')
        self._hidden_keys=self._pose_keys|frozenset(mesh.component for mesh in scene.meshes)
        self._mesh_names=frozenset(mesh.name for mesh in scene.meshes)
        families={}
        for mesh in scene.meshes:
            if mesh.part_id:families.setdefault(mesh.part_id,set()).add('case' if mesh.component=='panel' else mesh.component)
        self._pose_families={key:frozenset(value) for key,value in families.items()}
        self._pick_camera_key=None
        self.upload_count+=1

    @staticmethod
    def _selected(mesh,focus):
        return (focus=='all' or mesh.component==focus or bool(focus) and getattr(mesh,'part_id','')==focus
                or focus=='case' and mesh.component=='panel')

    def _visible(self,mesh,focus,inspection_cutaway=False,hide_gpu_power=False,show_psu=False,
                 hidden_parts=None,hidden_names=None):
        parts=self._frame_hidden_parts if hidden_parts is None else hidden_parts
        names=self._frame_hidden_names if hidden_names is None else hidden_names
        return (self._selected(mesh,focus) and not ((parts or names) and pose_hidden(mesh,parts,names))
                and (inspection_cutaway is not True or id(mesh) not in self._cutaway_hidden)
                and (show_psu is not True or id(mesh) not in self._psu_cover_ids)
                and (not hide_gpu_power or id(mesh) not in self._gpu_power_ids))

    def _shift(self,mesh,exploded,gpu_offset=None,part_offsets=None):
        shift=(0,0,0)
        if exploded:
            w,h,d=self.scene.dimensions
            shift={'panel':(-w*.43,0,d*.11),'gpu':(-w*.54,-h*.02,d*.32),
                'cpu':(-w*.58,h*.20,0),'memory':(-w*.32,h*.16,d*.12),
                'cooler':(-w*.72,h*.30,0),'fans':(w*.45,h*.10,d*.22),
                'psu':(w*.42,-h*.22,-d*.20),'storage':(w*.45,-h*.15,d*.28),
                'expansion':(-w*.40,-h*.22,d*.22)}.get(mesh.component,(0,0,0))
        if mesh.component=='gpu' and gpu_offset is not None:
            shift=tuple(shift[n]+gpu_offset[n] for n in range(3))
        if part_offsets:
            offset=offset_for(mesh,part_offsets)
            return tuple(shift[n]+offset[n] for n in range(3))
        return shift

    def _scalar(self,name,value):
        # Use the explicit GL scalar entry point. PySide's overloaded Qt setter
        # can select an integer uniform overload for Python float arguments.
        self.functions.glUniform1f(self._uniforms[name],float(value))

    def _shadow(self,projection,width,height,focus,exploded,gpu_offset=None,part_offsets=None):
        """A cached projected ground ellipse, not a scene mesh or a render target."""
        key=(self._pick_camera_key,focus,exploded,tuple(gpu_offset) if gpu_offset is not None and component_family(focus)=='gpu' else None,
             tuple(part_offsets.items()) if part_offsets else ())
        if key==self._shadow_key:return self._shadow_parameters
        low,high=self.pick_bounds.get((focus,exploded),self.pick_bounds[('all',False)])
        if part_offsets:
            low,high=posed_bounds(self.pick_bounds,focus,exploded,part_offsets,families=self._pose_families) or (low,high)
        if gpu_offset is not None and component_family(focus)=='gpu':
            low,high=tuple(tuple(p[n]+gpu_offset[n] for n in range(3)) for p in (low,high))
        center=((low[0]+high[0])/2,low[1],(low[2]+high[2])/2)
        def project(point):
            value=projection.map(QVector4D(*point,1.))
            if abs(value.w())<1e-8:return (width/2.,height*.15)
            return ((value.x()/value.w()+1)*width/2.,(value.y()/value.w()+1)*height/2.)
        point=project(center)
        x=project((center[0]+max(8.,high[0]-low[0])*.64,center[1],center[2]))
        z=project((center[0],center[1],center[2]+max(8.,high[2]-low[2])*.64))
        a,b=x[0]-point[0],z[0]-point[0];c,d=x[1]-point[1],z[1]-point[1]
        determinant=a*d-b*c
        inverse=(d/determinant,-b/determinant,-c/determinant,a/determinant) if abs(determinant)>4 else (1/max(16.,abs(a)+abs(b)),0.,0.,1/6.)
        self._shadow_key=key;self._shadow_parameters=(point,inverse)
        return self._shadow_parameters

    def draw(self,width,height,*,yaw=-34.,pitch=18.,zoom=1.,exploded=False,phase=0.,dark=False,focus='all',selected='',effect=None,pixel_scale=1.,transparent_background=False,inspection_cutaway=False,gpu_offset=None,hide_gpu_power=False,show_psu=False,
             part_offsets=None,part_extents=None,hidden_parts=(),hidden_mesh_names=()):
        f=self.functions
        if f is None or self.scene is None:return
        if not (isinstance(gpu_offset,(tuple,list)) and len(gpu_offset)==3
                and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=128 for v in gpu_offset)):
            gpu_offset=None
        part_offsets=valid_offsets(part_offsets,self._pose_keys)
        part_extents=valid_offsets(part_extents,self._pose_keys) or part_offsets
        self._frame_part_offsets=part_offsets
        self._frame_hidden_parts=valid_hidden(hidden_parts,self._hidden_keys)
        self._frame_hidden_names=valid_hidden(hidden_mesh_names,self._mesh_names,maximum=4096)
        f.glViewport(0,0,max(1,width),max(1,height))
        original=self.policy['id']=='miniature'
        background=((.075,.095,.12,1.) if dark else (.94,.955,.965,1.)) if original else self.policy['dark_background' if dark else 'light_background']
        f.glClearColor(*((0.,0.,0.,0.) if transparent_background else background))
        f.glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        f.glEnable(GL_DEPTH_TEST);f.glEnable(GL_BLEND)
        # Separate alpha blending produces premultiplied RGB from the zero-alpha
        # clear used by a transparent desktop widget, including glass edges.
        f.glBlendFuncSeparate(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_ONE,GL_ONE_MINUS_SRC_ALPHA)
        if focus!='all':exploded=False
        center,radius=self.bounds.get((focus,exploded),self.bounds[('all',False)])
        if part_extents:
            limits=posed_bounds(self.pick_bounds,focus,exploded,part_extents,include_origin=True,families=self._pose_families)
            if limits is not None:center,radius=box_sphere(limits)
        distance=radius*3.6*max(.55,min(2.5,zoom))
        yaw,pitch=math.radians(yaw),math.radians(pitch)
        eye=QVector3D(center[0]+distance*math.sin(yaw)*math.cos(pitch),center[1]+distance*math.sin(pitch),center[2]+distance*math.cos(yaw)*math.cos(pitch))
        near,far=max(.1,distance-radius*1.5),distance+radius*2.
        projection=QMatrix4x4();projection.perspective(34.,max(.1,width/max(1,height)),near,far)
        self._ink_projection=(ink_depth_bias(distance,radius),2/max(1,width),2/max(1,height))
        view=QMatrix4x4();view.lookAt(eye,QVector3D(*center),QVector3D(0,1,0))
        camera_key=(width,height,yaw,pitch,zoom,exploded,focus,center,radius)
        if camera_key!=self._pick_camera_key:
            combined=projection*view;inverse,valid=combined.inverted()
            self._pick_inverse=inverse if valid else None;self._pick_projection=combined
            self._pick_camera_key=camera_key
        self._pick_state=dict(width=width,height=height,exploded=exploded,phase=phase,focus=focus,
                              inspection_cutaway=inspection_cutaway,gpu_offset=gpu_offset,hide_gpu_power=hide_gpu_power,show_psu=show_psu)
        if part_offsets:self._pick_state['part_offsets']=part_offsets
        if self._frame_hidden_parts:self._pick_state['hidden_parts']=self._frame_hidden_parts
        if self._frame_hidden_names:self._pick_state['hidden_mesh_names']=self._frame_hidden_names
        self._frame_effect=effect if isinstance(effect,dict) and effect.get('active') is True else None
        self._frame_effect_samples={}
        self.program.bind();self.vao.bind()
        self.program.setUniformValue('eyePosition',eye)
        self.program.setUniformValue('paperColor',QVector4D(*background))
        target=self._frame_effect.get('component','') if self._frame_effect else ''
        limits=self.pick_bounds.get((target,exploded),self.pick_bounds[('all',False)])
        if part_offsets:limits=posed_bounds(self.pick_bounds,target,exploded,part_offsets,families=self._pose_families) or limits
        effect_center=tuple((limits[0][n]+limits[1][n])/2 for n in range(3))
        if gpu_offset is not None and component_family(target)=='gpu':
            effect_center=tuple(effect_center[n]+gpu_offset[n] for n in range(3))
        effect_scale=tuple(1/max(1.,limits[1][n]-limits[0][n]) for n in range(3))
        self.program.setUniformValue('effectCenter',QVector3D(*effect_center))
        self.program.setUniformValue('effectScale',QVector3D(*effect_scale))
        self._scalar('backgroundMode',0.)
        self._scalar('shadeMix',self.policy['shading'])
        self._frame_shade=self.policy['shading']
        if not transparent_background and (self.policy['paper_grid'] or self.policy['contact_shadow']):
            f.glDisable(GL_DEPTH_TEST);f.glDepthMask(False)
            self._scalar('backgroundMode',1. if self.policy['paper_grid'] else 2.)
            self.program.setUniformValue('paperGridColor',QVector4D(*self.policy['grid_dark' if dark else 'grid_light']))
            shadow_center,shadow_inverse=self._shadow(self._pick_projection,width,height,focus,exploded,gpu_offset,part_offsets)
            self.program.setUniformValue('shadowCenter',QVector2D(*shadow_center))
            self.program.setUniformValue('shadowInverse',QVector4D(*shadow_inverse))
            self.program.setUniformValue('shadowColor',QVector4D(.01,.025,.04,self.policy['contact_shadow']*(.7 if dark else 1.)))
            f.glDrawArrays(GL_TRIANGLES,0,3)
            self._scalar('backgroundMode',0.)
            f.glEnable(GL_DEPTH_TEST);f.glDepthMask(True)
        if self.edge_ranges:
            f.glEnable(GL_POLYGON_OFFSET_FILL);f.glPolygonOffset(1.,1.)
        transparent=[]
        for row in self.ranges:
            if not self._visible(row[0],focus,inspection_cutaway,hide_gpu_power,show_psu):continue
            policy=self._mesh_policies.get(id(row[0]),self.policy)
            if row[0].color[3]<1:transparent.append(row)
            else:self._draw_part(row,projection,view,exploded,phase,
                    tone=background if policy['line_only'] else self._highlight_tone(row[0],selected),gpu_offset=gpu_offset)
        # Glass is drawn last without writing depth; opaque internal parts remain.
        f.glDepthMask(False)
        for row in transparent:
            if not self._mesh_policies.get(id(row[0]),self.policy)['line_only']:
                self._draw_part(row,projection,view,exploded,phase,tone=self._highlight_tone(row[0],selected),gpu_offset=gpu_offset)
        f.glDepthMask(True)
        if self.edge_ranges:
            f.glDisable(GL_POLYGON_OFFSET_FILL);f.glDepthFunc(GL_LEQUAL);f.glLineWidth(1.)
            self._scalar('shadeMix',0.)
            self._frame_shade=0.
            line_width=1.
            for row in self.edge_ranges:
                if self._visible(row[0],focus,inspection_cutaway,hide_gpu_power,show_psu):
                    policy=self._mesh_policies.get(id(row[0]),self.policy)
                    stroke_width=max(1.,min(8.,policy['line_width']*number(pixel_scale,1.,.5,8.))) if self._wide_lines else 1.
                    if stroke_width!=line_width:f.glLineWidth(stroke_width);line_width=stroke_width
                    ink=policy['dark_ink' if dark else 'ink']
                    tone=(.28,.74,1.,1.) if dark else (.05,.47,.78,1.)
                    self._draw_part(row,projection,view,exploded,phase,mode=GL_LINES,
                                    tone=tone if self._matches_selection(row[0],selected) else self._preview_light_tones.get(id(row[0]),ink),gpu_offset=gpu_offset)
            f.glDepthFunc(GL_LESS)
        self.vao.release();self.program.release();self.draw_count+=1

    @staticmethod
    def _matches_selection(mesh,selected):
        return bool(selected) and (mesh.component==selected or getattr(mesh,'part_id','')==selected
                                   or selected=='case' and mesh.component=='panel')

    def _highlight_tone(self,mesh,selected):
        if not self._matches_selection(mesh,selected):return None
        return tuple(mesh.color[n]*.70+(.15,.62,.95)[n]*.30 for n in range(3))+(mesh.color[3],)

    def project_point(self,point):
        """Project a world point using the last rendered camera, for input QA."""
        if self._pick_projection is None or not self._pick_state:return None
        p=self._pick_projection.map(QVector4D(*point,1.))
        if abs(p.w())<1e-10:return None
        return ((p.x()/p.w()+1)*self._pick_state['width']/2,
                (1-p.y()/p.w())*self._pick_state['height']/2,p.z()/p.w())

    def pick(self,x,y):
        """Pick only on a user click. Glass does not intercept internal parts."""
        if self._pick_inverse is None or not self._pick_state or self.scene is None:return ''
        state=self._pick_state;w,h=state['width'],state['height']
        if not 0<=x<w or not 0<=y<h:return ''
        nx,ny=x*2/w-1,1-y*2/h
        near=self._pick_inverse.map(QVector4D(nx,ny,-1.,1.))
        far=self._pick_inverse.map(QVector4D(nx,ny,1.,1.))
        if abs(near.w())<1e-10 or abs(far.w())<1e-10:return ''
        origin=tuple(v/near.w() for v in (near.x(),near.y(),near.z()))
        end=tuple(v/far.w() for v in (far.x(),far.y(),far.z()))
        direction=tuple(end[n]-origin[n] for n in range(3));length=math.sqrt(sum(v*v for v in direction))
        if not length:return ''
        direction=tuple(v/length for v in direction);focus=state['focus']
        allowed=ASSEMBLY_COMPONENTS[1:] if focus=='all' else (focus,)
        candidates=set()
        for component in allowed:
            bounds=self.pick_bounds.get((component,state['exploded']))
            if state.get('part_offsets'):
                bounds=posed_bounds(self.pick_bounds,component,state['exploded'],state['part_offsets'],families=self._pose_families)
            if component_family(component)=='gpu' and bounds is not None and state.get('gpu_offset') is not None:
                bounds=tuple(tuple(point[n]+state['gpu_offset'][n] for n in range(3)) for point in bounds)
            if bounds is not None and ray_box(origin,direction,*bounds) is not None:
                candidates.update(self._pose_families.get(component,(component_family(component),)))
        hits={};opaque_case=float('inf')
        for mesh in self.scene.meshes:
            component='case' if mesh.component=='panel' else mesh.component
            if (component not in candidates or mesh.name.startswith('style-') or not self._visible(
                    mesh,focus,state.get('inspection_cutaway',False),state.get('hide_gpu_power',False),state.get('show_psu',False),
                    state.get('hidden_parts',()),state.get('hidden_mesh_names',()))):continue
            target=getattr(mesh,'part_id','') or component
            shift=self._shift(mesh,state['exploded'],state.get('gpu_offset'),state.get('part_offsets'));vertices=mesh.vertices
            points=[posed_point(mesh,vertices[n:n+3],shift,state['phase']) for n in range(0,len(vertices),6)]
            for n in range(0,len(points),3):
                hit=ray_triangle(origin,direction,*points[n:n+3])
                if hit is not None:
                    if hit<hits.get(target,float('inf')):hits[target]=hit
                    if component=='case' and mesh.color[3]>=.999:opaque_case=min(opaque_case,hit)
        hardware=[(distance,component) for component,distance in hits.items() if component!='case']
        if hardware:
            distance,component=min(hardware)
            return component if distance<=opaque_case+1e-7 else 'case'
        return 'case' if 'case' in hits else ''

    def _draw_part(self,row,projection,view,exploded,phase,*,mode=GL_TRIANGLES,tone=None,gpu_offset=None):
        mesh,start,count=row
        policy=self._mesh_policies.get(id(mesh),self.policy)
        model=QMatrix4x4();x,y,z=mesh.position
        shift=self._shift(mesh,exploded,gpu_offset,self._frame_part_offsets);x+=shift[0];y+=shift[1];z+=shift[2]
        model.translate(x,y,z)
        if mesh.rotor:model.rotate(mesh_phase(mesh,phase)*mesh.direction,*mesh.axis)
        self.program.setUniformValue('matrix',projection*view*model)
        self.program.setUniformValue('modelMatrix',model)
        self.program.setUniformValue('normalMatrix',model.normalMatrix())
        if mode==GL_LINES:
            bias,sx,sy=self._ink_projection
            wobble=policy['wobble']*.28
            seed=mesh.vertex_count%1024
            self.program.setUniformValue('inkProjection',QVector4D(bias,sx*wobble,sy*wobble,float(seed)))
        else:self.program.setUniformValue('inkProjection',QVector4D(0.,0.,0.,0.))
        self.program.setUniformValue('baseColor',QVector4D(*(mesh.color if tone is None else tone)))
        shade=0. if mode==GL_LINES else policy['shading']
        if shade!=self._frame_shade:self._scalar('shadeMix',shade);self._frame_shade=shade
        material=self._materials.get(id(mesh),(0.,1.,0.,0.)) if mode!=GL_LINES else (0.,1.,0.,0.)
        self.program.setUniformValue('surfaceMaterial',QVector4D(*material))
        effect=self._frame_effect
        if effect and self._matches_selection(mesh,effect.get('component')):
            sample=effect
            if 'elapsed_ms' in effect:
                identity=policy['id']
                if identity not in self._frame_effect_samples:
                    self._frame_effect_samples[identity]=effect_sample(identity,effect['elapsed_ms'],effect['component'],family=effect.get('family'))
                sample=self._frame_effect_samples[identity]
            params=(number(sample.get('kind'),0,0,13),number(sample.get('progress'),1,0,1),
                    number(sample.get('amount'),0,0,1),1. if mode==GL_LINES else 0.)
        else:params=(0.,0.,0.,1. if mode==GL_LINES else 0.)
        self.program.setUniformValue('effectParams',QVector4D(*params))
        self.functions.glDrawArrays(mode,start,count)

    def close(self):
        if self.vao is not None:self.vao.destroy()
        if self.buffer is not None:self.buffer.destroy()
        if self.program is not None:self.program.removeAllShaders()
        self.vao=self.buffer=self.program=self.functions=None
        self._uniforms={};self.forget_scene()

    def forget_scene(self):
        """Drop CPU mesh ownership even if a lost context cannot be made current."""
        self.scene=None;self.ranges=[];self.edge_ranges=[];self.edge_segments=0;self.bounds={};self.pick_bounds={}
        self._pick_inverse=self._pick_projection=self._pick_camera_key=self._pick_state=None
        self._materials={};self._frame_effect=None;self._shadow_key=None;self._shadow_parameters=None
        self._mesh_policies={};self._preview_light_tones={};self._frame_effect_samples={};self._frame_shade=None
        self._cutaway_hidden=frozenset()
        self._psu_cover_ids=frozenset()
        self._gpu_power_ids=frozenset()
        self._pose_keys=frozenset();self._hidden_keys=frozenset();self._mesh_names=frozenset();self._pose_families={}
        self._frame_part_offsets={};self._frame_hidden_parts=frozenset();self._frame_hidden_names=frozenset()


class AssemblyViewport(QOpenGLWidget):
    """Interactive mesh viewport. Host owns the lazy window and shared clock.

    animationActiveChanged tells the host when it can subscribe to its existing
    MetricEffectClock. Call advance_fans(elapsed_ms) from that shared clock only.
    This widget never starts a timer, frame callback or autonomous orbit.
    """
    rendererError=Signal(str)
    animationActiveChanged=Signal(bool)
    sceneChanged=Signal()
    focusChanged=Signal(str)
    componentSelected=Signal(str)
    gpuAssemblyChanged=Signal()
    partAssemblyChanged=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFormat(surface_format());self.setUpdateBehavior(QOpenGLWidget.NoPartialUpdate)
        self.setMinimumSize(320,240);self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('3D assembly preview')
        self._renderer=AssemblyRenderer();self._scene=build_scene({});self._pending=True
        self._scene_cache=SceneCache()
        self._yaw=-34.;self._pitch=18.;self._zoom=1.;self._exploded=False;self._dark=False
        self._phase=0.;self._rpm=0.;self._fan_available=False;self._animate=False;self._active=False
        self._cpu_phase=0.;self._cpu_rpm=0.;self._cpu_available=False;self._cpu_expiry=0.
        self._cpu_tach_usable=False
        self._real_cpu_rotor_parts=()
        self._demo=False;self._demo_phase=0.
        self._gpu_demo_phase=0.
        self._gpu_insertion=GpuInsertion();self._gpu_plan=insertion_plan(self._scene)
        self._part_motion=PartMotion();self._part_planner=None;self._part_plan={};self._part_plan_key=None
        self._hidden_parts=frozenset();self._hidden_connection_names=frozenset();self._opened_retention_names=frozenset()
        self._released_mounts=frozenset()
        self._changing_scene=False
        self._fan_expiry=0.
        self._effect=SelectionEffect();self._effect_active=False;self._clock_active_state=False
        self._motion=True;self._selection_effects=True
        self._focus='all'
        self._selected='';self._press_position=None;self._dragging=False
        self._pointer=None;self._error='';self._closed=False
        self._transparent_background=False
        self._inspection_cutaway=False
        self._show_psu=False

    @property
    def scene(self):return self._scene

    @property
    def diagnostics(self):
        return dict(meshes=len(self._scene.meshes),triangles=self._scene.triangle_count,
                    geometry_uploads=self._renderer.upload_count,draws=self._renderer.draw_count,
                    fan_animation_active=self._active,phase=self._phase,error=self._error,
                    cpu_phase=self._cpu_phase,demo_motion=self._demo,
                    focus=self._focus,
                    visual_style=self._scene.metadata.get('visual_style','miniature'),
                    static_ink_segments=self._renderer.edge_segments,
                    selected_component=self._selected,
                    effect_active=self._effect_active,effect=self._effect.sample(),
                    animation_active=self._clock_active_state,
                    framebuffer_cap='host controls widget dimensions; no multisampling or post-processing')

    def set_scene(self,spec):
        scene=self._scene_cache.build(spec)
        self._changing_scene=True
        try:
            self.set_inspection_cutaway(spec.get('inspection_cutaway',False))
            self.set_show_psu(spec.get('show_psu',False))
        finally:self._changing_scene=False
        if scene==self._scene:
            AssemblyViewport._refresh_part_plan(self);return
        self._effect.cancel()
        self._gpu_insertion.reset()
        AssemblyViewport._reset_part_motion(self)
        planner=getattr(self,'_part_planner',None)
        rebound=bool(planner is not None and planner.rebind_scene(scene))
        if planner is not None and not rebound:planner.clear()
        self._part_planner=planner if rebound else None
        self._part_plan_key=None;self._opened_retention_names=frozenset();self._released_mounts=frozenset()
        self._scene=scene;self._pending=True
        previous=getattr(self,'_hidden_parts',())
        self._hidden_parts=frozenset(key for key in previous if any(AssemblyRenderer._selected(m,key) for m in scene.meshes))
        self._hidden_connection_names=frozenset(hidden_connections(scene,self._hidden_parts))
        self._gpu_plan=insertion_plan(scene);self.gpuAssemblyChanged.emit()
        self._cpu_tach_usable=scene.metadata.get('cooling',{}).get('cpu_fan_tach_usable') is True
        self._real_cpu_rotor_parts=tuple(scene.metadata.get('cooling',{}).get('real_cpu_rotor_parts') or ())
        if ':' in self._selected and not any(getattr(mesh,'part_id','')==self._selected for mesh in scene.meshes):
            self._selected='';self.componentSelected.emit('all')
        if ':' in self._focus and not any(getattr(mesh,'part_id','')==self._focus for mesh in scene.meshes):self._focus='all'
        AssemblyViewport._refresh_part_plan(self)
        self.sceneChanged.emit();self._update_animation_state();self.update()

    def set_transparent_background(self,enabled):
        """Real zero-alpha FBO clear, with no color-key or background quad."""
        enabled=enabled is True
        if self._transparent_background==enabled:return
        self._transparent_background=enabled
        self.setAutoFillBackground(False)
        self.update()

    def set_fan_state(self,rpm,available=True,timestamp=None):
        valid=available is True and type(rpm) in (int,float) and math.isfinite(rpm) and 0<=rpm<=100000
        age=0.
        if timestamp is not None:
            valid=valid and type(timestamp) in (int,float) and math.isfinite(timestamp)
            age=time.time()-timestamp if valid else GPU_FAN_MAX_AGE+1
            valid=valid and 0<=age<=GPU_FAN_MAX_AGE
        self._rpm=float(rpm) if valid else 0.;self._fan_available=valid
        self._fan_expiry=time.monotonic()+max(0.,GPU_FAN_MAX_AGE-age) if valid else 0.
        self._update_animation_state()

    def set_fan_animation_enabled(self,enabled):
        self._animate=enabled is True;self._update_animation_state()

    def set_fan_motion(self,mode):
        self._demo=mode=='demo';self._update_animation_state()

    def set_cpu_fan_state(self,rpm,available=True,timestamp=None):
        valid=available is True and type(rpm) in (int,float) and math.isfinite(rpm) and 0<=rpm<=12000
        age=time.time()-timestamp if type(timestamp) in (int,float) and math.isfinite(timestamp) else GPU_FAN_MAX_AGE+1
        valid=valid and 0<=age<=GPU_FAN_MAX_AGE
        self._cpu_rpm=float(rpm) if valid else 0.;self._cpu_available=valid
        self._cpu_expiry=time.monotonic()+max(0.,GPU_FAN_MAX_AGE-age) if valid else 0.
        self._update_animation_state()

    def _reset_part_motion(self):
        motion=getattr(self,'_part_motion',None)
        changed=bool(motion and motion.reset())
        if changed:
            self._renderer._pick_state=None
            signal=getattr(self,'partAssemblyChanged',None)
            if signal is not None:signal.emit()
            self.update()
        return changed

    def _refresh_part_plan(self):
        """Only explicit selection/scene/visibility changes may scan geometry."""
        if not hasattr(self,'_part_motion') or getattr(self,'_changing_scene',False):return
        if (not getattr(self,'_motion',True) or not self.isVisible() or self.window().isMinimized()):
            # A hidden owner may receive configuration/visibility callbacks.
            # Keep its detached result; defer even cache queries until active.
            self._part_plan_key=None;return
        target=getattr(self,'_selected','') or 'all'
        key=(id(self._scene),target,self._hidden_parts,self._opened_retention_names,
             getattr(self,'_released_mounts',frozenset()),
             getattr(self,'_inspection_cutaway',False),getattr(self,'_show_psu',False))
        if key==self._part_plan_key:return
        family=part_family(target,self._scene.metadata)
        if family not in ('cpu','memory','fans'):
            plan=dict(available=False,target=target,reason='choose_cpu_or_memory',allowed_opened_mesh_names=())
        elif target=='fans':
            plan=dict(available=False,target=target,reason='choose_individual_case_fan',allowed_opened_mesh_names=())
        else:
            from assembly_part_motion052 import PartMotionPlanner
            if self._part_planner is None:self._part_planner=PartMotionPlanner(self._scene)
            plan=self._part_planner.plan(target,hidden_parts=self._hidden_parts,
                opened_mesh_names=self._opened_retention_names,
                released_mounts=getattr(self,'_released_mounts',()),
                inspection_cutaway=getattr(self,'_inspection_cutaway',False),show_psu=getattr(self,'_show_psu',False))
        plan['component_family']=family
        self._part_plan=plan;self._part_plan_key=key;self.partAssemblyChanged.emit()

    def part_motion_state(self):
        """Detached status only; data/animation ticks never invoke the planner."""
        state=dict(getattr(self,'_part_plan',{}));motion=getattr(self,'_part_motion',None)
        state.update(active=bool(motion and motion.active),progress=motion.progress if motion else 0.,
                     motion_target=motion.target if motion else 0.,
                     hidden_parts=tuple(sorted(getattr(self,'_hidden_parts',()))),
                     released_mounts=tuple(sorted(getattr(self,'_released_mounts',()))),
                     retention_hidden=bool(getattr(self,'_opened_retention_names',())))
        gpu=getattr(self,'_gpu_insertion',None)
        target=state.get('target','')
        if getattr(self,'_exploded',False):state.update(available=False,reason='close_exploded_view')
        elif not getattr(self,'_motion',True):state.update(available=False,reason='motion_disabled')
        elif gpu and (gpu.active or gpu.progress>0):state.update(available=False,reason='return_other_part_first')
        elif getattr(self,'_focus','all') not in ('all',target,state.get('component_family',component_family(target))):
            state.update(available=False,reason='focus_selected_part')
        elif state.get('available') and state.get('allowed_opened_mesh_names') and not state.get('retention_hidden'):
            state.update(available=False,reason='open_retention_first')
        return state

    def preview_part_motion(self,removed=True):
        if (type(removed) is not bool or self._closed or self._error or not self.isVisible()
                or self.window().isMinimized() or not self.part_motion_state().get('available')):return False
        if not self._part_motion.start(removed):return False
        self._renderer._pick_state=None
        self._update_animation_state();self.partAssemblyChanged.emit();self.update();return True

    def set_part_hidden(self,target,enabled):
        """A temporary inspection mask, never a claim of mechanical removal."""
        if (type(enabled) is not bool or not isinstance(target,str) or target=='all'
                or not any(AssemblyRenderer._selected(m,target) for m in self._scene.meshes)):return False
        current=getattr(self,'_hidden_parts',frozenset())
        following=(current|{target}) if enabled else (current-{target})
        if following==current:return True
        if len(following)>64:return False
        AssemblyViewport._reset_part_motion(self)
        gpu=getattr(self,'_gpu_insertion',None)
        if gpu and gpu.reset():self.gpuAssemblyChanged.emit()
        self._hidden_parts=frozenset(following)
        effect=getattr(self,'_effect',None)
        if effect is not None:effect.cancel()
        self._hidden_connection_names=frozenset(hidden_connections(self._scene,self._hidden_parts))
        self._opened_retention_names=frozenset();self._renderer._pick_state=None
        self._released_mounts=frozenset()
        AssemblyViewport._refresh_part_plan(self)
        self._update_animation_state();self.partAssemblyChanged.emit();self.update();return True

    def restore_hidden_parts(self):
        if not getattr(self,'_hidden_parts',()) and not getattr(self,'_opened_retention_names',()) and not getattr(self,'_released_mounts',()):return False
        AssemblyViewport._reset_part_motion(self)
        gpu=getattr(self,'_gpu_insertion',None)
        if gpu and gpu.reset():self.gpuAssemblyChanged.emit()
        self._hidden_parts=frozenset();self._hidden_connection_names=frozenset();self._opened_retention_names=frozenset()
        self._released_mounts=frozenset()
        self._renderer._pick_state=None;AssemblyViewport._refresh_part_plan(self)
        self._update_animation_state();self.partAssemblyChanged.emit();self.update();return True

    def set_retention_hidden(self,enabled):
        if type(enabled) is not bool:return False
        allowed=tuple(self._part_plan.get('allowed_opened_mesh_names',()))
        if enabled and not allowed:return False
        following=frozenset(allowed) if enabled else frozenset()
        if following==self._opened_retention_names:return True
        AssemblyViewport._reset_part_motion(self)
        self._opened_retention_names=following;self._renderer._pick_state=None
        AssemblyViewport._refresh_part_plan(self)
        self._update_animation_state();self.partAssemblyChanged.emit();self.update();return True

    def set_mount_released(self,enabled):
        """Explicit reference release; never a physical screw/cable animation."""
        if type(enabled) is not bool:return False
        target=self._part_plan.get('target','')
        allowed=self._part_plan.get('allowed_mount_release_part_ids',())
        if enabled and (target not in allowed or not self._motion):return False
        gpu=getattr(self,'_gpu_insertion',None)
        if gpu and (gpu.active or gpu.progress>0):return False
        following=frozenset((target,)) if enabled else frozenset()
        if following==getattr(self,'_released_mounts',frozenset()):return True
        AssemblyViewport._reset_part_motion(self);self._released_mounts=following
        self._renderer._pick_state=None;AssemblyViewport._refresh_part_plan(self)
        self._update_animation_state();self.partAssemblyChanged.emit();self.update();return True

    def set_motion_enabled(self,enabled):
        self._motion=enabled is True
        canceled=self._effect.cancel() if not self._motion else False
        self._update_animation_state()
        if canceled:self.update()

    def gpu_insertion_state(self):
        state=dict(getattr(self,'_gpu_plan',{}))
        motion=getattr(self,'_gpu_insertion',None)
        state.update(active=bool(motion and motion.active),progress=motion.progress if motion else 0.,
                     target=motion.target if motion else 0.)
        if getattr(self,'_exploded',False):state.update(available=False,reason='请先关闭展开组件，再演示显卡插拔。')
        elif getattr(self,'_focus','all') not in ('all','gpu','gpu:0'):
            state.update(available=False,reason='请先切换到整机或显卡视图。')
        elif not getattr(self,'_motion',True):state.update(available=False,reason='动效已关闭。')
        part=getattr(self,'_part_motion',None)
        if part and (part.active or part.progress>0):state.update(available=False,reason='return_other_part_first')
        if getattr(self,'_hidden_parts',()) and any(m.component=='gpu' and pose_hidden(m,self._hidden_parts) for m in self._scene.meshes):
            state.update(available=False,reason='target_hidden')
        return state

    def preview_gpu_insertion(self,removed=True):
        """A finite slot-direction demonstration, never a hardware operation."""
        if (self._closed or self._error or not self.isVisible() or self.window().isMinimized()
                or not self.gpu_insertion_state().get('available')):return False
        if not self._gpu_insertion.start(removed is True):return False
        self._renderer._pick_state=None
        self._update_animation_state();self.gpuAssemblyChanged.emit();self.update();return True

    def set_selection_effects_enabled(self,enabled):
        self._selection_effects=enabled is True
        canceled=self._effect.cancel() if not self._selection_effects else False
        self._update_animation_state()
        if canceled:self.update()

    def preview_effect(self,component='case'):
        if (self._closed or self._error or not self._motion or not self._selection_effects
                or not self.isVisible() or self.window().isMinimized()):return False
        matched=[mesh for mesh in self._scene.meshes if AssemblyRenderer._matches_selection(mesh,component) and not pose_hidden(mesh,
                   getattr(self,'_hidden_parts',()),getattr(self,'_hidden_connection_names',()))]
        if not matched:return False
        families={'case' if mesh.component=='panel' else mesh.component for mesh in matched}
        if len(families)!=1:return False
        family=next(iter(families))
        if self._focus!='all' and self._focus not in (component,family):return False
        styles=self._scene.metadata.get('mesh_style_ids') or [self._scene.metadata.get('visual_style','miniature')]*len(self._scene.meshes)
        policies=[effect_for(style) for mesh,style in zip(self._scene.meshes,styles)
                  if AssemblyRenderer._matches_selection(mesh,component)]
        longest=max(policies,key=lambda policy:policy['duration_ms'])
        if not self._effect.start(longest['style'],component,family=family if component_family(component) not in ASSEMBLY_COMPONENTS else None):return False
        self._update_animation_state();self.update();return True

    def _step_fans(self,elapsed_ms):
        if self._fan_available and time.monotonic()>self._fan_expiry:
            self._fan_available=False;self._update_animation_state()
        if getattr(self,'_cpu_available',False) and time.monotonic()>self._cpu_expiry:
            self._cpu_available=False;self._update_animation_state()
        if not self._active:return False
        elapsed=number(elapsed_ms,0,0,136)
        if elapsed<=0:return False
        gpu=getattr(self,'_gpu_insertion',None)
        gpu_paused=bool(gpu and (gpu.active or gpu.progress>0))
        if self._fan_available and not gpu_paused:self._phase=(self._phase+elapsed*self._rpm*360/(60000*120))%360
        if getattr(self,'_cpu_tach_usable',False) and getattr(self,'_cpu_available',False):
            self._cpu_phase=(self._cpu_phase+elapsed*self._cpu_rpm*360/(60000*120))%360
        if getattr(self,'_demo',False):
            previous=self._demo_phase
            self._demo_phase=(self._demo_phase+elapsed*1200*360/(60000*120))%360
            if not gpu_paused:self._gpu_demo_phase=(getattr(self,'_gpu_demo_phase',previous)+elapsed*1200*360/(60000*120))%360
        return True

    def advance_fans(self,elapsed_ms):
        changed=AssemblyViewport._step_fans(self,elapsed_ms)
        if changed:self.update()
        return changed

    def advance_animations(self,elapsed_ms):
        """Advance one shared bounded tick; RPM absence does not block ink FX."""
        fan_changed=AssemblyViewport._step_fans(self,elapsed_ms)
        effect_changed=self._effect.advance(elapsed_ms) if self._effect_active else False
        gpu=getattr(self,'_gpu_insertion',None)
        was_active=bool(gpu and gpu.active)
        insertion_changed=gpu.advance(elapsed_ms) if gpu and was_active else False
        part=getattr(self,'_part_motion',None);part_was_active=bool(part and part.active)
        part_changed=part.advance(elapsed_ms) if part_was_active else False
        if insertion_changed:self._renderer._pick_state=None
        if part_changed:self._renderer._pick_state=None
        self._update_animation_state()
        if was_active and not gpu.active:self.gpuAssemblyChanged.emit()
        if part_was_active and not part.active:self.partAssemblyChanged.emit()
        if fan_changed or effect_changed or insertion_changed or part_changed:self.update()
        return fan_changed or effect_changed or insertion_changed or part_changed

    def set_exploded(self,enabled):
        if self._exploded!=(enabled is True):
            self._exploded=enabled is True;self._update_animation_state();self.update()

    def set_inspection_cutaway(self,enabled):
        """Change only draw/pick visibility; keep the uploaded physical scene."""
        enabled=enabled is True
        if self._inspection_cutaway==enabled:return
        self._inspection_cutaway=enabled
        self._released_mounts=frozenset()
        # Never let a click between this toggle and the next paint use the old
        # cover visibility. The next regular draw restores the same camera ray.
        self._renderer._pick_state=None
        if not getattr(self,'_changing_scene',False):
            AssemblyViewport._reset_part_motion(self);AssemblyViewport._refresh_part_plan(self)
        self.update()

    def set_show_psu(self,enabled):
        """Temporarily remove only a real PSU cover; never rebuild hardware."""
        enabled=enabled is True
        if getattr(self,'_show_psu',False)==enabled:return
        self._show_psu=enabled;self._released_mounts=frozenset();self._renderer._pick_state=None;self.update()
        if not getattr(self,'_changing_scene',False):
            AssemblyViewport._reset_part_motion(self);AssemblyViewport._refresh_part_plan(self)

    def set_dark(self,enabled):
        if self._dark!=(enabled is True):self._dark=enabled is True;self.update()

    def reset_camera(self):
        layout=self._scene.metadata.get('case_layout')
        self._yaw=-34.;self._pitch=18.;self._zoom=1.
        family=component_family(self._focus)
        if family=='gpu':
            if layout=='vertical':self._yaw=145.;self._pitch=10.
            elif self._scene.metadata.get('gpu_mount')=='vertical':self._yaw=-76.;self._pitch=12.
            else:self._pitch=-62.
        elif family=='memory':
            self._yaw=-20.;self._pitch=-55. if layout=='vertical' else 60. if layout=='horizontal' else 12.
        elif family in ('cpu','board','cooler'):
            self._yaw=-80.;self._pitch=60. if layout=='horizontal' else 12.
        elif family in ('storage','expansion','psu'):self._yaw=-52.;self._pitch=24.
        self.update()

    def focus_component(self,name):
        # Authored part IDs need not start with their component family (for
        # example case-fan:0 is a fans mesh). Identity comes from the scene.
        exact=any(mesh.part_id==name and mesh.component in ASSEMBLY_COMPONENTS for mesh in self._scene.meshes)
        if component_family(name) not in ASSEMBLY_COMPONENTS and not exact:return False
        if name!='all' and not any(AssemblyRenderer._selected(mesh,name) for mesh in self._scene.meshes):return False
        if name!=self._focus:
            AssemblyViewport._reset_part_motion(self)
            self._released_mounts=frozenset();self._part_plan_key=None
            styles=self._scene.metadata.get('mesh_style_ids')
            if not isinstance(styles,(tuple,list)) or len(styles)!=len(self._scene.meshes):
                styles=(self._scene.metadata.get('visual_style','miniature'),)
            # One static reallocation on an explicit inspection change. Fan,
            # effect, camera and insertion frames continue using the same VBO.
            if any(style_for(identity)['edges'] for identity in styles):self._pending=True
        self._focus=name;self._update_animation_state();self.reset_camera();self.focusChanged.emit(name);return True

    def select_component(self,name):
        selected='' if name=='all' else name
        if selected and not any(AssemblyRenderer._selected(mesh,selected)
                                and mesh.component in ASSEMBLY_COMPONENTS for mesh in self._scene.meshes):return False
        if selected!=self._selected:
            AssemblyViewport._reset_part_motion(self)
            if hasattr(self,'_opened_retention_names'):self._opened_retention_names=frozenset()
            self._released_mounts=frozenset()
            self._selected=selected;self.componentSelected.emit(selected or 'all')
            AssemblyViewport._refresh_part_plan(self)
            preview=getattr(self,'preview_effect',None)
            if selected and callable(preview):
                if not preview(selected):self.update()
            else:
                effect=getattr(self,'_effect',None)
                if effect is not None:effect.cancel();self._update_animation_state()
                self.update()
        return True

    def _update_animation_state(self):
        visible=bool(not self._closed and not self._error and self.isVisible() and not self.window().isMinimized())
        motion=getattr(self,'_motion',True)
        if not visible or not motion:
            planner=getattr(self,'_part_planner',None)
            discard=getattr(planner,'discard_geometry_cache',None)
            if callable(discard):discard()
        elif getattr(self,'_part_plan_key','already_valid') is None:
            AssemblyViewport._refresh_part_plan(self)
        insertion=getattr(self,'_gpu_insertion',None)
        if insertion and (not visible or not motion or self._exploded or self._focus not in ('all','gpu','gpu:0')):
            if insertion.reset():
                self._renderer._pick_state=None;self.gpuAssemblyChanged.emit();self.update()
        gpu_paused=bool(insertion and (insertion.active or insertion.progress>0))
        part=getattr(self,'_part_motion',None)
        plan=getattr(self,'_part_plan',{})
        if part and (not visible or not motion or self._exploded
                     or self._focus not in ('all',plan.get('target'),plan.get('component_family',component_family(plan.get('target',''))))):
            AssemblyViewport._reset_part_motion(self)
            if getattr(self,'_released_mounts',()):
                self._released_mounts=frozenset();AssemblyViewport._refresh_part_plan(self);self.update()
        def eligible(mesh):
            if not mesh.rotor or not AssemblyRenderer._selected(mesh,self._focus):return False
            parts=getattr(self,'_hidden_parts',());names=getattr(self,'_hidden_connection_names',())
            if (parts or names) and pose_hidden(mesh,parts,names):return False
            if mesh.component=='gpu' and gpu_paused:return False
            if mesh.part_id in getattr(self,'_released_mounts',()):return False
            if part and (part.active or part.progress>0) and mesh.part_id in plan.get('part_ids',()):return False
            if getattr(self,'_demo',False):return True
            if mesh.component=='gpu':return self._fan_available and self._rpm>0 and time.monotonic()<=self._fan_expiry
            if mesh.component=='cooler':return (getattr(mesh,'part_id','') in getattr(self,'_real_cpu_rotor_parts',())
                                                and getattr(self,'_cpu_tach_usable',False) and getattr(self,'_cpu_available',False) and self._cpu_rpm>0
                                                and time.monotonic()<=self._cpu_expiry)
            return False
        active=bool(visible and motion and self._animate and any(eligible(mesh) for mesh in self._scene.meshes))
        self._active=active
        effect=getattr(self,'_effect',None)
        if effect is not None:
            if (not visible or not motion or not self._selection_effects
                    or self._focus!='all' and self._focus not in (effect.component,getattr(effect,'family',None) or component_family(effect.component))):effect.cancel()
            self._effect_active=bool(effect.active and visible and motion and self._selection_effects)
        combined=(active or getattr(self,'_effect_active',False) or bool(insertion and insertion.active and visible and motion)
                  or bool(part and part.active and visible and motion))
        if combined!=getattr(self,'_clock_active_state',False):
            self._clock_active_state=combined;self.animationActiveChanged.emit(combined)

    def initializeGL(self):
        try:
            self._renderer.initialize();self._pending=True
            self.context().aboutToBeDestroyed.connect(self.release_resources)
        except Exception as error:
            self._error=str(error);self._update_animation_state();self.rendererError.emit('3-D rendering is unavailable on this graphics context')

    def paintGL(self):
        if self._error:return
        try:
            if self._pending:self._renderer.upload(self._scene,ink_focus=self._focus);self._pending=False
            ratio=self.devicePixelRatioF()
            phase=self._phase
            if hasattr(self,'_cpu_phase'):
                phase=(dict(gpu=getattr(self,'_gpu_demo_phase',self._demo_phase),
                            **{key:self._demo_phase for key in ('cooler','fans','psu')}) if self._demo
                       else dict(gpu=self._phase,**{key:self._cpu_phase for key in self._real_cpu_rotor_parts}))
            options=dict(yaw=self._yaw,pitch=self._pitch,zoom=self._zoom,exploded=self._exploded,
                         phase=phase,dark=self._dark,focus=self._focus)
            if getattr(self,'_inspection_cutaway',False):options['inspection_cutaway']=True
            if getattr(self,'_show_psu',False):options['show_psu']=True
            insertion=getattr(self,'_gpu_insertion',None)
            if insertion and (insertion.active or insertion.progress>0):
                options.update(gpu_offset=insertion.offset(self._gpu_plan),hide_gpu_power=True,inspection_cutaway=True)
            part=getattr(self,'_part_motion',None)
            hidden_names=getattr(self,'_hidden_connection_names',frozenset())|getattr(self,'_opened_retention_names',frozenset())
            if getattr(self,'_released_mounts',()):
                hidden_names=hidden_names|frozenset(self._part_plan.get('hide_mesh_names',()))
                if isinstance(phase,dict):
                    phase.update({key:0. for key in self._released_mounts})
                    options['phase']=phase
            if getattr(self,'_hidden_parts',()):options['hidden_parts']=self._hidden_parts
            if part and (part.active or part.progress>0):
                plan=self._part_plan;position=part.offset(plan)
                options['part_offsets']={key:position for key in plan.get('part_ids',())}
                options['part_extents']={key:tuple(v*plan['distance_mm'] for v in plan['direction']) for key in plan.get('part_ids',())}
                hidden_names=hidden_names|frozenset(plan.get('hide_mesh_names',()))
            if hidden_names:options['hidden_mesh_names']=hidden_names
            if self._transparent_background:options['transparent_background']=True
            if getattr(self,'_selected',''):options['selected']=self._selected
            effect=getattr(self,'_effect',None)
            if effect is not None and effect.active:options['effect']=effect.sample()
            self._renderer.draw(round(self.width()*ratio),round(self.height()*ratio),pixel_scale=ratio,**options)
        except Exception as error:
            self._error=str(error);self._update_animation_state();self.rendererError.emit('3-D rendering could not be completed')

    def resizeGL(self,width,height):
        pass  # paintGL sets the actual physical framebuffer dimensions.

    def showEvent(self,event):
        super().showEvent(event);self._update_animation_state()

    def refresh_visibility(self):
        self._update_animation_state()

    def hideEvent(self,event):
        self._pointer=None;self._press_position=None;self._dragging=False
        super().hideEvent(event);self._update_animation_state()

    def changeEvent(self,event):
        super().changeEvent(event);self._update_animation_state()

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self._pointer=event.position();self._press_position=event.position();self._dragging=False;event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._pointer is not None:
            point=event.position();delta=point-self._pointer;self._pointer=point
            if not self._dragging:
                distance=point-self._press_position
                self._dragging=distance.x()*distance.x()+distance.y()*distance.y()>16
                if not self._dragging:event.accept();return
            self._yaw=(self._yaw+delta.x()*.4)%360
            self._pitch=max(-78.,min(78.,self._pitch+delta.y()*.3));self.update();event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._pointer is not None and event.button()==Qt.LeftButton:
            if not self._dragging:
                ratio=self.devicePixelRatioF();point=event.position()
                self.select_component(self._renderer.pick(point.x()*ratio,point.y()*ratio) or 'all')
            self._pointer=None;self._press_position=None;self._dragging=False;event.accept()
        else:super().mouseReleaseEvent(event)

    def wheelEvent(self,event):
        steps=event.angleDelta().y()/120
        self._zoom=max(.55,min(2.5,self._zoom*math.pow(.9,steps)));self.update();event.accept()

    def release_resources(self):
        if self.context() is None:return
        self.makeCurrent();self._renderer.close();self.doneCurrent();self._pending=True

    def closeEvent(self,event):
        self._closed=True;self._update_animation_state();self.release_resources();self._retire_cpu_scene();super().closeEvent(event)

    def _retire_cpu_scene(self):
        # Qt's deferred deletion or an external Python reference can outlive
        # the closed window. Neither should keep the full physical arrays or
        # renderer's picking/draw lists alive until the wrapper is collected.
        self._scene_cache.clear();self._renderer.forget_scene()
        self._scene=Scene((),self._scene.dimensions,{})
        self._gpu_plan={}
        planner=getattr(self,'_part_planner',None)
        if planner is not None:planner.clear()
        if getattr(self,'_part_motion',None):self._part_motion.reset()
        self._part_planner=None;self._part_plan={};self._part_plan_key=None
        self._hidden_parts=frozenset();self._hidden_connection_names=frozenset();self._opened_retention_names=frozenset()
        self._released_mounts=frozenset()
