"""On-demand native OpenGL assembly viewport using existing Qtbase libraries.

Import this module only when the user opens the assembly viewer. There is no
Quick3D, external asset loader, hardware access, polling or animation timer.
Original code/art: PolyForm Noncommercial 1.0.0, see LICENSE and LICENSING.md.
"""
import math
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMatrix4x4, QVector3D, QVector4D, QSurfaceFormat
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLFunctions_3_3_Core, QOpenGLShader,
                             QOpenGLShaderProgram, QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from assembly_geometry import build_scene, number, vertex_bytes
from top_bar_feedback import GPU_FAN_MAX_AGE

GL_FLOAT=0x1406
GL_TRIANGLES=0x0004
GL_DEPTH_TEST=0x0B71
GL_BLEND=0x0BE2
GL_SRC_ALPHA=0x0302
GL_ONE_MINUS_SRC_ALPHA=0x0303
GL_ONE=1
GL_COLOR_BUFFER_BIT=0x4000
GL_DEPTH_BUFFER_BIT=0x0100

VERTEX_SHADER='''#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 normal;
uniform mat4 matrix;
uniform mat3 normalMatrix;
out vec3 worldNormal;
void main() { worldNormal=normalMatrix*normal; gl_Position=matrix*vec4(position,1.0); }
'''
FRAGMENT_SHADER='''#version 330 core
in vec3 worldNormal;
uniform vec4 baseColor;
out vec4 fragment;
void main() {
 vec3 n=normalize(worldNormal);
 float key=max(0.0,dot(n,normalize(vec3(-0.7,1.0,0.8))));
 float rim=max(0.0,dot(n,normalize(vec3(0.8,0.3,-0.6))));
 fragment=vec4(baseColor.rgb*(0.52+0.36*key+0.18*rim),baseColor.a);
}
'''


def surface_format():
    fmt=QSurfaceFormat()
    fmt.setVersion(3,3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(0)
    return fmt


class AssemblyRenderer:
    """Small context-owned VBO renderer, also usable with a hidden FBO proof."""
    def __init__(self):
        self.functions=None;self.program=None;self.buffer=None;self.vao=None
        self.scene=None;self.ranges=[];self.bounds={};self.upload_count=0;self.draw_count=0

    def initialize(self):
        self.functions=QOpenGLFunctions_3_3_Core()
        if not self.functions.initializeOpenGLFunctions():
            raise RuntimeError('OpenGL 3.3 is unavailable')
        self.program=QOpenGLShaderProgram()
        if not self.program.addShaderFromSourceCode(QOpenGLShader.Vertex,VERTEX_SHADER):
            raise RuntimeError('3-D vertex shader could not be compiled')
        if not self.program.addShaderFromSourceCode(QOpenGLShader.Fragment,FRAGMENT_SHADER):
            raise RuntimeError('3-D fragment shader could not be compiled')
        if not self.program.link():raise RuntimeError('3-D shader could not be linked')
        self.vao=QOpenGLVertexArrayObject();self.buffer=QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        if not self.vao.create() or not self.buffer.create():raise RuntimeError('3-D buffers could not be allocated')
        self.vao.bind();self.buffer.bind();self.program.bind()
        self.program.enableAttributeArray(0);self.program.enableAttributeArray(1)
        self.program.setAttributeBuffer(0,GL_FLOAT,0,3,24)
        self.program.setAttributeBuffer(1,GL_FLOAT,12,3,24)
        self.buffer.release();self.vao.release();self.program.release()

    def upload(self,scene):
        if self.program is None:raise RuntimeError('3-D context is not ready')
        self.scene=scene;raw=vertex_bytes(scene)
        self.buffer.bind();self.buffer.setUsagePattern(QOpenGLBuffer.StaticDraw)
        self.buffer.allocate(raw,len(raw));self.buffer.release()
        self.ranges=[];start=0
        for mesh in scene.meshes:
            self.ranges.append((mesh,start,mesh.vertex_count));start+=mesh.vertex_count
        self.bounds={}
        for focus in ('all','gpu','cpu','memory','board','case'):
            rows=[mesh for mesh in scene.meshes if self._selected(mesh,focus)]
            if not rows:continue
            for exploded in (False,True) if focus=='all' else (False,):
                low=[float('inf')]*3;high=[float('-inf')]*3
                for mesh in rows:
                    shift=self._shift(mesh,exploded)
                    for axis in range(3):
                        values=mesh.vertices[axis::6]
                        low[axis]=min(low[axis],min(values)+mesh.position[axis]+shift[axis])
                        high[axis]=max(high[axis],max(values)+mesh.position[axis]+shift[axis])
                center=tuple((low[i]+high[i])/2 for i in range(3))
                radius=math.sqrt(sum((high[i]-low[i])**2 for i in range(3)))/2
                self.bounds[(focus,exploded)]=(center,max(1.,radius))
        self.upload_count+=1

    @staticmethod
    def _selected(mesh,focus):
        return focus=='all' or mesh.component==focus or focus=='case' and mesh.component=='panel'

    def _shift(self,mesh,exploded):
        if not exploded:return (0,0,0)
        w,h,d=self.scene.dimensions
        return {'panel':(-w*.43,0,d*.11),'gpu':(-w*.54,-h*.02,d*.32),
                'cpu':(-w*.58,h*.20,0),'memory':(-w*.32,h*.16,d*.12)}.get(mesh.component,(0,0,0))

    def draw(self,width,height,*,yaw=-34.,pitch=18.,zoom=1.,exploded=False,phase=0.,dark=False,focus='all'):
        f=self.functions
        if f is None or self.scene is None:return
        f.glViewport(0,0,max(1,width),max(1,height))
        f.glClearColor(*((.075,.095,.12,1.) if dark else (.94,.955,.965,1.)))
        f.glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        f.glEnable(GL_DEPTH_TEST);f.glEnable(GL_BLEND)
        # The clear color is opaque. Keep alpha opaque while mixing glass RGB;
        # Qt's premultiplied widget/FBO composition must not see RGB > alpha.
        f.glBlendFuncSeparate(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_ONE,GL_ONE_MINUS_SRC_ALPHA)
        if focus!='all':exploded=False
        center,radius=self.bounds.get((focus,exploded),self.bounds[('all',False)])
        distance=radius*3.6*max(.55,min(2.5,zoom))
        yaw,pitch=math.radians(yaw),math.radians(pitch)
        eye=QVector3D(center[0]+distance*math.sin(yaw)*math.cos(pitch),center[1]+distance*math.sin(pitch),center[2]+distance*math.cos(yaw)*math.cos(pitch))
        projection=QMatrix4x4();projection.perspective(34.,max(.1,width/max(1,height)),
            max(.1,distance-radius*1.5),distance+radius*2.)
        view=QMatrix4x4();view.lookAt(eye,QVector3D(*center),QVector3D(0,1,0))
        self.program.bind();self.vao.bind()
        transparent=[]
        for row in self.ranges:
            if not self._selected(row[0],focus):continue
            if row[0].color[3]<1:transparent.append(row)
            else:self._draw_part(row,projection,view,exploded,phase)
        # Glass is drawn last without writing depth; opaque internal parts remain.
        f.glDepthMask(False)
        for row in transparent:self._draw_part(row,projection,view,exploded,phase)
        f.glDepthMask(True)
        self.vao.release();self.program.release();self.draw_count+=1

    def _draw_part(self,row,projection,view,exploded,phase):
        mesh,start,count=row
        model=QMatrix4x4();x,y,z=mesh.position
        shift=self._shift(mesh,exploded);x+=shift[0];y+=shift[1];z+=shift[2]
        model.translate(x,y,z)
        if mesh.rotor:model.rotate(phase*mesh.direction,*mesh.axis)
        self.program.setUniformValue('matrix',projection*view*model)
        self.program.setUniformValue('normalMatrix',model.normalMatrix())
        self.program.setUniformValue('baseColor',QVector4D(*mesh.color))
        self.functions.glDrawArrays(GL_TRIANGLES,start,count)

    def close(self):
        if self.vao is not None:self.vao.destroy()
        if self.buffer is not None:self.buffer.destroy()
        if self.program is not None:self.program.removeAllShaders()
        self.vao=self.buffer=self.program=self.functions=None
        self.scene=None;self.ranges=[];self.bounds={}


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

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFormat(surface_format());self.setUpdateBehavior(QOpenGLWidget.NoPartialUpdate)
        self.setMinimumSize(320,240);self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('3D assembly preview')
        self._renderer=AssemblyRenderer();self._scene=build_scene({});self._pending=True
        self._yaw=-34.;self._pitch=18.;self._zoom=1.;self._exploded=False;self._dark=False
        self._phase=0.;self._rpm=0.;self._fan_available=False;self._animate=False;self._active=False
        self._fan_expiry=0.
        self._focus='all'
        self._pointer=None;self._error='';self._closed=False

    @property
    def scene(self):return self._scene

    @property
    def diagnostics(self):
        return dict(meshes=len(self._scene.meshes),triangles=self._scene.triangle_count,
                    geometry_uploads=self._renderer.upload_count,draws=self._renderer.draw_count,
                    fan_animation_active=self._active,phase=self._phase,error=self._error,
                    focus=self._focus,
                    framebuffer_cap='host controls widget dimensions; no multisampling or post-processing')

    def set_scene(self,spec):
        scene=build_scene(spec)
        if scene==self._scene:return
        self._scene=scene;self._pending=True;self.sceneChanged.emit();self._update_animation_state();self.update()

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

    def advance_fans(self,elapsed_ms):
        if self._fan_available and time.monotonic()>self._fan_expiry:
            self._fan_available=False;self._update_animation_state()
        if not self._active:return False
        elapsed=number(elapsed_ms,0,0,136)
        if elapsed<=0:return False
        self._phase=(self._phase+elapsed*self._rpm*360/(60000*120))%360
        self.update();return True

    def set_exploded(self,enabled):
        if self._exploded!=(enabled is True):self._exploded=enabled is True;self.update()

    def set_dark(self,enabled):
        if self._dark!=(enabled is True):self._dark=enabled is True;self.update()

    def reset_camera(self):
        layout=self._scene.metadata.get('case_layout')
        self._yaw=-34.;self._pitch=18.;self._zoom=1.
        if self._focus=='gpu':
            self._pitch=10. if layout=='vertical' else -62.
            if self._scene.metadata.get('gpu_mount')=='vertical':self._yaw=-76.;self._pitch=12.
        elif self._focus in ('cpu','memory','board'):
            self._yaw=-80.;self._pitch=60. if layout=='horizontal' else 12.
        self.update()

    def focus_component(self,name):
        if name not in ('all','case','gpu','cpu','memory','board'):return False
        if name!='all' and not any(AssemblyRenderer._selected(mesh,name) for mesh in self._scene.meshes):return False
        self._focus=name;self._update_animation_state();self.reset_camera();self.focusChanged.emit(name);return True

    def _update_animation_state(self):
        active=bool(not self._closed and not self._error and self._animate and self._fan_available and self._rpm>0
                    and time.monotonic()<=self._fan_expiry
                    and self._focus in ('all','gpu')
                    and self.isVisible() and not self.window().isMinimized()
                    and any(mesh.rotor for mesh in self._scene.meshes))
        if active!=self._active:self._active=active;self.animationActiveChanged.emit(active)

    def initializeGL(self):
        try:
            self._renderer.initialize();self._pending=True
            self.context().aboutToBeDestroyed.connect(self.release_resources)
        except Exception as error:
            self._error=str(error);self._update_animation_state();self.rendererError.emit('3-D rendering is unavailable on this graphics context')

    def paintGL(self):
        if self._error:return
        try:
            if self._pending:self._renderer.upload(self._scene);self._pending=False
            ratio=self.devicePixelRatioF()
            self._renderer.draw(round(self.width()*ratio),round(self.height()*ratio),yaw=self._yaw,pitch=self._pitch,
                                zoom=self._zoom,exploded=self._exploded,phase=self._phase,dark=self._dark,focus=self._focus)
        except Exception as error:
            self._error=str(error);self._update_animation_state();self.rendererError.emit('3-D rendering could not be completed')

    def resizeGL(self,width,height):
        pass  # paintGL sets the actual physical framebuffer dimensions.

    def showEvent(self,event):
        super().showEvent(event);self._update_animation_state()

    def hideEvent(self,event):
        self._pointer=None;super().hideEvent(event);self._update_animation_state()

    def changeEvent(self,event):
        super().changeEvent(event);self._update_animation_state()

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self._pointer=event.position();event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._pointer is not None:
            point=event.position();delta=point-self._pointer;self._pointer=point
            self._yaw=(self._yaw+delta.x()*.4)%360
            self._pitch=max(-78.,min(78.,self._pitch+delta.y()*.3));self.update();event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        self._pointer=None;super().mouseReleaseEvent(event)

    def wheelEvent(self,event):
        steps=event.angleDelta().y()/120
        self._zoom=max(.55,min(2.5,self._zoom*math.pow(.9,steps)));self.update();event.accept()

    def release_resources(self):
        if self.context() is None:return
        self.makeCurrent();self._renderer.close();self.doneCurrent();self._pending=True

    def closeEvent(self,event):
        self._closed=True;self._update_animation_state();self.release_resources();super().closeEvent(event)
