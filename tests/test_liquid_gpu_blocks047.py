"""Retail GPU-block source boundary, optional packs and actual bounded geometry; no native app."""
import copy,hashlib,importlib.util,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from hardware_packs import PackError,PackStore,_archive
from liquid_gpu_blocks047 import IDS,records,get_record
from liquid_gpu_schema047 import compatibility,port_pair_status
from liquid_pack_schema046 import validate_reference
from liquid_geometry046 import build_component
from assembly_cooling import _transform
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
ASTRAL='alphacool-core-rtx5090-rog-astral';XFX='alphacool-core-rx9070xt-swift-quicksilver'
MSI='alphacool-core-rtx5090-suprim-vanguard';CORSAIR='corsair-xg7-rgb-rtx3080ti-3080-fe'
TUF='watercool-heatkiller-v-ultra-rtx5090-tuf'

def segment_hits(meshes,start,end):
    """Independent finite triangle ray, not a solid-color or scalar port check."""
    sub=lambda a,b:tuple(x-y for x,y in zip(a,b))
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    cross=lambda a,b:(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    direction=sub(end,start)
    for mesh in meshes:
        for at in range(0,len(mesh.vertices),18):
            a,b,c=[tuple(mesh.vertices[at+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12)]
            u,v=sub(b,a),sub(c,a);p=cross(direction,v);det=dot(u,p)
            if abs(det)<1e-10:continue
            t=sub(start,a);s=dot(t,p)/det
            if s< -1e-8 or s>1+1e-8:continue
            q=cross(t,u);r=dot(direction,q)/det
            if r< -1e-8 or s+r>1+1e-8:continue
            fraction=dot(v,q)/det
            if 1e-6<fraction<1-1e-6:return True
    return False

class RetailGpuBlock047Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','threading.Thread.start','subprocess.Popen','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No native/window/network/background activity')))

    def test_author_import_is_lazy_invalid_queries_do_not_construct_and_returns_are_detached(self):
        spec=importlib.util.spec_from_file_location('fresh_gpu_author047',ROOT/'liquid_gpu_blocks047.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertIsNone(module._RECORDS);self.assertIsNone(module.get_record('missing'))
        self.assertEqual(module.records('cpu_block'),());self.assertIsNone(module._RECORDS)
        record=module.get_record(IDS[0]);record['ports'].clear()
        self.assertTrue(module.get_record(IDS[0])['ports'])
        self.assertEqual(len(module.records()),12)

    def test_twelve_source_qualified_models_exclude_held_and_preserve_unknown_dimension_scope(self):
        values=records();self.assertEqual(len(values),12);self.assertEqual(len(set(IDS)),12)
        self.assertEqual({r['brand'] for r in values},{'Alphacool','Watercool','Corsair'})
        self.assertEqual(sum(r['gpu_vendor']=='AMD' for r in values),3)
        self.assertFalse(any(r['product_id'] in ('15681','CX-9020023-WW') for r in values))
        self.assertEqual(get_record(ASTRAL)['materials']['cold_plate'],'chrome-plated copper')
        self.assertEqual(get_record(TUF)['materials']['terminal'],'POM/acetal')
        self.assertIsNone(get_record(CORSAIR)['materials']['terminal'])
        for row in values:
            self.assertEqual(validate_reference(row),row);json.dumps(row,allow_nan=False)
            self.assertFalse(row['gpu_compatibility']['chip_name_sufficient'])
            self.assertFalse(row['gpu_compatibility']['assembly_pose_verified'])
            if row['brand']!='Watercool':
                self.assertTrue(all(v is None for v in row['dimensions_mm'].values()))
                self.assertFalse(row['dimensions_verified']);self.assertEqual(row['dimensions_scope'],'unknown')
        self.assertTrue(all(v is None for v in get_record(CORSAIR)['published_envelopes'][0]['dimensions_mm'].values()))

    def test_exact_cards_revisions_conflicts_do_not_expand_to_chip_names_or_other_skus(self):
        astral=get_record(ASTRAL)
        self.assertEqual(compatibility(astral,product_code='90YV0LW1-M0NA00')['state'],'manufacturer_listed')
        self.assertEqual(compatibility(astral,card_label='NVIDIA GeForce RTX5090')['state'],'unlisted')
        self.assertEqual(compatibility(astral,product_code='90YV0LY1-M0NA00')['state'],'unlisted')
        self.assertEqual(compatibility(astral,card_label=astral['gpu_compatibility']['entries'][0]['card_label'],product_code='90YV0LY1-M0NA00')['state'],'unlisted')
        msi=get_record(MSI);card='MSI GeForce RTX 5090 32G SUPRIM SOC'
        self.assertEqual(compatibility(msi,card_label=card)['state'],'revision_confirmation_required')
        self.assertEqual(compatibility(msi,card_label=card,pcb_revision='MS-V530 Ver:2.1')['state'],'manufacturer_listed')
        self.assertEqual(compatibility(msi,card_label=card,pcb_revision='MS-V530 Ver:2.0')['state'],'unlisted_revision')
        self.assertEqual(compatibility(msi,card_label='MSI GeForce RTX 5090 32G SUPRIM OC')['state'],'unlisted')
        xfx=get_record(XFX);swift='RX-97TSWF3W9'
        self.assertEqual(compatibility(xfx,product_code=swift,pcb_revision='V2.0')['state'],'manufacturer_listed')
        self.assertEqual(compatibility(xfx,product_code=swift,pcb_revision='V3.0')['state'],'source_conflict')
        self.assertEqual(compatibility(xfx,product_code=swift,pcb_revision='A.0')['state'],'excluded')
        self.assertEqual(compatibility(xfx,product_code='RX-97TQIC-extra',pcb_revision='V2.0')['state'],'unlisted')
        self.assertTrue(all(not compatibility(row,card_label=row['gpu_compatibility']['entries'][0]['card_label'])['assembly_supported'] for row in records()))

    def test_hydraulic_columns_are_not_interchangeable_and_unknown_pairs_remain_unknown(self):
        row=get_record(CORSAIR)
        self.assertEqual(port_pair_status(row,'face-a-left','face-b-left'),'same_hydraulic_column_forbidden')
        self.assertEqual(port_pair_status(row,'face-a-left','face-b-right'),'different_verified_columns_reference_only')
        self.assertEqual(port_pair_status(row,'face-a-left','face-a-right'),'different_verified_columns_reference_only')
        self.assertEqual(port_pair_status(get_record(ASTRAL),'face-a-left','face-b-right'),'hydraulic_groups_unverified')
        self.assertEqual(port_pair_status(row,'bad','face-a-left'),'unknown_port')
        self.assertEqual(port_pair_status(row,[],'face-a-left'),'invalid_pair')

    def test_untrusted_gpu_fields_reject_without_type_errors_or_precision_inference(self):
        for path,value in ((('geometry_family',),[]),(('geometry_recipe',),{}),(('reviewed',),7),
            (('backplate','cooling'),'active'),(('gpu_compatibility','assembly_pose_verified'),True),
            (('lighting','led_count'),10000),(('terminal_configurations',0,'geometry_reference','positions_verified'),True)):
            row=get_record(ASTRAL);target=row
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(PackError):validate_reference(row)

    def test_terminal_configuration_keeps_its_own_envelope_and_unknown_sockets(self):
        from liquid_gpu_geometry047 import build_component as build_gpu
        row=get_record(TUF);standard=build_gpu(row,'eco');side=build_gpu(row,'eco',terminal='sideport')
        self.assertEqual(standard[1]['reference_envelope_mm']['width'],259.5)
        self.assertEqual(side[1]['reference_envelope_mm']['width'],249.5)
        self.assertEqual(side[1]['dimensions_mm']['width'],249.5);self.assertTrue(side[1]['dimensions_verified'])
        self.assertEqual(standard[1]['ports_count'],6);self.assertEqual(len(standard[1]['ports']),2)
        self.assertEqual(standard[1]['unplaced_documented_ports'],4)
        self.assertIsNone(side[1]['ports_count']);self.assertEqual(side[1]['ports'],[])
        self.assertFalse(side[1]['routes_supported'])
        with self.assertRaises(ValueError):build_gpu(row,terminal='unknown')

    def test_all_twelve_actual_three_lod_meshes_are_bounded_open_finite_static_and_split(self):
        from liquid_gpu_geometry047 import LIMITS
        for row in records():
            for level in ('eco','balanced','close'):
                meshes,meta=build_component(row,level)
                with self.subTest(model=row['id'],level=level):
                    self.assertLessEqual(meta['triangle_count'],LIMITS[level]);self.assertLessEqual(len(meshes),24)
                    self.assertEqual({m.part_id for m in meshes},{p['id'] for p in meta['subparts']})
                    self.assertFalse(any(m.rotor or m.component!='cooler' or 'pcb' in m.name for m in meshes))
                    self.assertEqual(meta['assembly_stage'],'standalone_reference_only');self.assertFalse(meta['attached_to_gpu'])
                    json.dumps(meta,allow_nan=False)
                    for mesh in meshes:
                        self.assertTrue(all(math.isfinite(x) for x in mesh.vertices))
                        for at in range(0,len(mesh.vertices),6):self.assertAlmostEqual(sum(x*x for x in mesh.vertices[at+3:at+6]),1.,places=6)
                    for port in meta['ports']:
                        start=tuple(p+n*5 for p,n in zip(port['position'],port['normal']))
                        end=tuple(p-n*2 for p,n in zip(port['position'],port['normal']))
                        self.assertFalse(segment_hits(meshes,start,end),(row['id'],port['id'],level))

    def test_reference_grooves_are_open_recesses_not_overlapping_opaque_cap_triangles(self):
        # At an illustrative branch away from the central chamber, the top
        # metal sheet must really be cut, with a floor below the shallow recess.
        meshes,_=build_component(get_record(ASTRAL),'eco')
        top=tuple(m for m in meshes if m.name=='loop-gpu-recessed-metal-channel-study')
        floor=tuple(m for m in meshes if m.name=='loop-gpu-reference-coolant-channel-floor')
        point=(104.77,4.1,0.)
        # Default inspection orientation maps canonical x->-X,y->Y,z->-Z.
        ray=(point[0],point[1],0.)
        self.assertFalse(segment_hits(top,(ray[0],ray[1],-4.),(ray[0],ray[1],2.8)))
        self.assertTrue(segment_hits(floor,(ray[0],ray[1],-4.),(ray[0],ray[1],4.)))
        # The broad right-side metal land from the primary photograph is
        # preserved rather than filled with invented additional channel work.
        self.assertTrue(segment_hits(top,(-90.,0.,-4.),(-90.,0.,2.8)))

    def test_rigid_pose_and_all_thirteen_styles_preserve_the_same_physical_arrays(self):
        from assembly_style import apply_model_styles
        row=get_record(ASTRAL);base,meta=build_component(row,'eco',basis=((1,0,0),(0,1,0),(0,0,1)))
        center=(10.,-20.,15.);basis=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.))
        posed,ports=build_component(row,'eco',center,basis)
        for a,b in zip(base,posed):self.assertEqual(_transform(a.vertices,center,basis),b.vertices)
        for style in HARDWARE_ICON_STYLES:
            painted,_=apply_model_styles(base,style,{},(260,161,35),{'front':'open'})
            self.assertEqual(len(painted),len(base))
            self.assertTrue(all(a.vertices is b.vertices and a.part_id==b.part_id for a,b in zip(base,painted)))

    def test_real_export_is_deterministic_immutable_and_runtime_does_not_need_author_library(self):
        from tools.export_gpu_block_packs047 import export
        import hardware_packs as packs
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=export(root/'packs');b=export(root/'packs')
            self.assertEqual(a,b);self.assertEqual(a['unique_products'],12);self.assertEqual(len(a['packs']),4)
            collection=next(p for p in a['packs'] if p['group']=='collection');file=root/'packs'/Path(collection['file']).name
            raw=file.read_bytes();manifest,models=_archive(raw);self.assertEqual(len(models),12)
            store=PackStore(root/'installed');store.install(file)
            import builtins
            original=builtins.__import__
            def guard(name,*args,**kwargs):
                if name=='liquid_gpu_blocks047':raise AssertionError('Runtime loaded the author catalogue')
                return original(name,*args,**kwargs)
            with patch.object(packs,'_store',store),patch('builtins.__import__',new=guard):
                from liquid_component_runtime046 import get_component
                self.assertEqual(get_component('gpu_block',ASTRAL)['id'],ASTRAL)
                self.assertEqual(store.get_model('cpu',ASTRAL),None)
            file.write_bytes(b'altered')
            with self.assertRaises(FileExistsError):export(root/'packs')
            self.assertEqual(file.read_bytes(),b'altered')

if __name__=='__main__':unittest.main()
