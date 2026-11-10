"""Exact Pascal front-facet source contract and bounded closed relief."""
from collections import Counter
import json
import math
from pathlib import Path
import re
import struct
import unittest

from assembly_geometry import Mesh,box
from assembly_gpu_pascal053 import refine,WINDOW_UV,HEAD_UV
import gpu_pascal_surface055 as surface

ROOT=Path(__file__).resolve().parents[1]


def edges(vertices,f32=False):
    def point(values):
        if f32:values=struct.unpack('<3f',struct.pack('<3f',*values))
        return tuple(values)
    result=Counter()
    for at in range(0,len(vertices),18):
        p=[point(vertices[at+n:at+n+3])for n in(0,6,12)]
        if len(set(p))<3:raise AssertionError('Collapsed facet after float conversion')
        for a,b in zip(p,p[1:]+p[:1]):result[tuple(sorted((a,b)))]+=1
    return result


class GpuPascal055Tests(unittest.TestCase):
    def test_widget_and_mesh_share_the_exact_source_topology_not_a_renamed_card(self):
        text=(ROOT/'native/HardwareGpuPascal055.js').read_text('utf-8')
        data=json.loads(re.search(r'^var data=(\{.*\})$',text,re.M).group(1))
        self.assertEqual(data,surface.descriptor())
        self.assertIn(surface.descriptor_sha256(),text)
        self.assertEqual(data['id'],'nvidia-gtx1080-founders')
        self.assertEqual(data['existing_blades'],53)
        self.assertFalse(data['depth_measured']);self.assertFalse(data['rotor_changed'])
        self.assertEqual(len(data['facets']),23)

    def test_every_source_plane_has_finite_relief_and_two_distinct_vent_notches(self):
        self.assertEqual(len(surface.VENTS),2)
        self.assertNotEqual(surface.VENTS[0],surface.VENTS[1])
        for row in surface.FACETS:
            points=tuple(surface.POINTS[key]for key in row[:3])
            a,b,c=surface._plane(points)
            self.assertTrue(all(math.isfinite(value)for value in(a,b,c)))
            for u,v,height in points:self.assertAlmostEqual(a*u+b*v+c,height,places=12)
        self.assertGreater(len({surface._plane(tuple(surface.POINTS[key]for key in row[:3]))for row in surface.FACETS}),5)

    def test_relief_is_closed_in_float64_and_float32_without_touching_the_rotor(self):
        length,width,thickness=300.,135.,54.
        shell=Mesh('gpu-shroud',box(width,thickness,length),(.5,.6,.7,1.),component='gpu',part_id='gpu:0')
        reference=dict(window_outline=tuple(((u-.5)*length,(.5-v)*width)for u,v in WINDOW_UV),
            fan_holes=((length*.28,0.,width*.34),),
            paint_head_seats=tuple(((u-.5)*length,(.5-v)*width,2.35)for u,v in HEAD_UV))
        original=shell.vertices
        meshes,metadata=surface.relief_meshes(shell,reference,'balanced')
        self.assertEqual(len(meshes),23);self.assertEqual(metadata['front_relief_facets'],23)
        self.assertIs(shell.vertices,original)
        self.assertFalse(metadata['front_relief_manufacturer_CAD'])
        self.assertLess(sum(mesh.vertex_count//3 for mesh in meshes),8192)
        problems=[]
        for mesh in meshes:
            self.assertFalse(mesh.rotor);self.assertEqual(mesh.part_id,'gpu:0')
            self.assertTrue(all(math.isfinite(value)for value in mesh.vertices))
            for f32 in(False,True):
                try:
                    incidence=edges(mesh.vertices,f32)
                    bad=[(edge,count)for edge,count in incidence.items()if count!=2]
                    if bad:problems.append((mesh.name,f32,len(bad),bad[:3]))
                except AssertionError as error:problems.append((mesh.name,f32,str(error)))
            for at in range(0,len(mesh.vertices),6):self.assertAlmostEqual(math.hypot(*mesh.vertices[at+3:at+6]),1.,places=6)
        self.assertEqual(problems,[])

    def test_other_exact_gpus_do_not_gain_pascal_parts_or_source_claims(self):
        original=(Mesh('gpu-shroud',box(100.,50.,250.),(.5,.6,.7,1.),component='gpu',part_id='gpu:0'),)
        for identity in('nvidia-gtx780ti-reference','msi-gtx1080ti-gaming-x-11g','unreviewed-gpu'):
            result,metadata=refine(original,{'gpu':{'appearance':{'id':identity}}},'balanced')
            self.assertIs(result,original);self.assertEqual(metadata,{})


if __name__=='__main__':unittest.main()
