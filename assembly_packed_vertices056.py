"""Lossless, immutable viewer-cache storage after the whole factory finishes.

Only eligible large finite tuples are packed, at native IEEE float64 precision.
No fit/model/position/normal/palette/GL format is changed. Existing typed open
models and uncertain metadata/case identities retain their original objects.
Original code: PolyForm Noncommercial 1.0.0; upstream asset rights are unchanged.
"""
from array import array
from collections.abc import Sequence
from dataclasses import replace
import math
import operator

from assembly_geometry import Mesh,Scene

MINIMUM_VALUES=4096
MAX_METADATA_NODES=20000
# Case/shroud/window material ownership remains outside this first slice.
COMPONENTS=frozenset(('cpu','gpu','memory','board','cooler','fans','psu','storage','expansion','cables'))


class Float64Vertices(Sequence):
    """Tuple-compatible numeric reads, backed by an immutable bytes owner.

    A slice returns a tuple, so downstream point/dictionary/normal code never
    receives a format-d memoryview as a hash key. Equal tuples have equal hashes.
    Concatenation/repetition may allocate tuples, exactly as explicit callers
    request; the normal viewport never performs either operation.
    """
    __slots__=('_payload','_view','__weakref__')

    def __init__(self,values):
        if hasattr(self,'_payload'):raise AttributeError('Immutable vertex storage is already initialized')
        if type(values)is not tuple:raise TypeError('A source tuple is required')
        for value in values:
            if type(value)not in(int,float):raise ValueError('Non-numeric vertex retained at source')
            try:converted=float(value)
            except(OverflowError,ValueError):raise ValueError('Vertex cannot be represented as float64')from None
            if not math.isfinite(converted)or converted!=value:
                raise ValueError('Vertex cannot round-trip exactly as a finite float64')
        packed=array('d',values)
        if packed.itemsize!=8:raise ValueError('Native IEEE float64 is unavailable')
        owner=packed.tobytes()
        object.__setattr__(self,'_payload',owner)
        object.__setattr__(self,'_view',memoryview(owner).cast('d'))

    def __setattr__(self,name,value):raise AttributeError('Immutable vertex storage')
    def __delattr__(self,name):raise AttributeError('Immutable vertex storage')
    def __len__(self):return len(self._payload)//8
    def __iter__(self):return iter(self._view)
    def __getitem__(self,key):
        value=self._view[key]
        return tuple(value)if isinstance(key,slice)else value
    def __eq__(self,other):
        if other is self:return True
        if not isinstance(other,(tuple,Float64Vertices)):return NotImplemented
        return len(self)==len(other)and all(a==b for a,b in zip(self,other))
    def __hash__(self):return hash(tuple(self))
    def __add__(self,other):
        return tuple(self)+other if isinstance(other,tuple)else NotImplemented
    def __radd__(self,other):
        return other+tuple(self)if isinstance(other,tuple)else NotImplemented
    def __mul__(self,count):return tuple(self)*operator.index(count)
    __rmul__=__mul__
    def __deepcopy__(self,memo):return self
    def __reduce__(self):return type(self),(tuple(self),)
    @property
    def packed_bytes(self):return self._payload
    @property
    def nbytes(self):return len(self._payload)


def _protected_owners(scene,candidates,max_nodes):
    """Bounded metadata ownership audit; None means retain the entire Scene.

    Direct PN aliases, retained Mesh objects and explicit integer id references
    protect their source owner. Unknown object types or an over-budget graph
    are conservative passthrough, never guessed-safe compaction.
    """
    by_mesh={id(mesh):id(mesh.vertices)for mesh in scene.meshes}
    protected=set();seen=set();stack=[scene.metadata];scheduled=1
    while stack:
        value=stack.pop();identity=id(value)
        if identity in candidates:protected.add(identity);continue
        if identity in seen:continue
        seen.add(identity)
        if type(value)is Mesh:
            protected.add(id(value.vertices));continue
        if type(value)is int:
            if value in candidates:protected.add(value)
            if value in by_mesh:protected.add(by_mesh[value])
            continue
        if value is None or type(value)in(str,bool,float,bytes):continue
        if type(value)is dict:
            amount=len(value)*2
            if scheduled+amount>max_nodes:return None
            scheduled+=amount
            for key,item in value.items():stack.extend((key,item))
        elif type(value)in(tuple,list,set,frozenset):
            if scheduled+len(value)>max_nodes:return None
            scheduled+=len(value);stack.extend(value)
        else:return None
    return protected


def compact_scene(scene,*,minimum_values=MINIMUM_VALUES,max_metadata_nodes=MAX_METADATA_NODES):
    """Replace only owned large tuples after physical assembly/fit is complete.

    A shared tuple is either preserved everywhere or maps to one packed object.
    Metadata itself, anchors, source meshes and their original values stay
    untouched. Returning the original Scene is a valid conservative result.
    """
    if type(minimum_values)is not int or minimum_values<1:raise ValueError('Positive storage threshold required')
    if type(max_metadata_nodes)is not int or max_metadata_nodes<1:raise ValueError('Positive metadata bound required')
    owners={};excluded=set()
    for mesh in scene.meshes:
        values=mesh.vertices
        if type(values)is not tuple:continue
        if mesh.component not in COMPONENTS:excluded.add(id(values))
        if mesh.component in COMPONENTS and len(values)>=minimum_values:owners.setdefault(id(values),values)
    for identity in excluded:owners.pop(identity,None)
    if not owners:return scene
    protected=_protected_owners(scene,owners,max_metadata_nodes)
    if protected is None:return scene
    converted={}
    for identity,values in owners.items():
        if identity in protected:continue
        try:converted[identity]=Float64Vertices(values)
        except(ValueError,OverflowError):continue
    if not converted:return scene
    meshes=tuple(replace(mesh,vertices=converted[id(mesh.vertices)])
        if id(mesh.vertices)in converted else mesh for mesh in scene.meshes)
    return Scene(meshes,scene.dimensions,scene.metadata)
