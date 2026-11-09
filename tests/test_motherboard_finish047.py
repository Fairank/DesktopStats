"""Source-observed motherboard finishes, independent material and geometry controls.

Baseline digests are frozen0.46 catalog/CPU geometry, not a second renderer.
No Qt/window/GL, live device input, samples, clocks or private fixtures required.
"""
import copy
from dataclasses import replace
import hashlib
import json
import math
import struct
import unittest
from unittest.mock import patch

from motherboard_catalog import MODELS,get_model,ASUS_Z790_MANUAL
from assembly_motherboard import _io_clear_cover,layout_anchors,enrich_motherboard
from assembly_geometry import build_scene,color
from assembly_detail import TRIANGLE_BUDGETS
from assembly_lighting import MODES,apply_lighting,light_kind
from assembly_style import apply_model_styles,edge_batches,MAX_STYLE_EDGES
from top_bar_config import HARDWARE_ICON_STYLES

LEGACY_ROWS = {'asrock-b550m-itx-ac': '7679b83c3edf28bb3287d26d0d345c103bea96c337206792c8047e1f4f97e3a4',
 'asrock-b650-pg-lightning': 'd5923b761efc692bd8b6c345e003af49f47cad231978e6950016e128a384dd32',
 'asrock-b650e-steel-legend-wifi': 'c0237986a188008f72e0436600b6feb24b40b0b582ba8dd3d03efeb06d949fa1',
 'asrock-b650i-lightning-wifi': 'fbeb6f460af1a912574dfe5e55c3bdc6b085b9c23e98e30f3981b53c0873b518',
 'asrock-b650m-pg-riptide-wifi': '5a2d2a6c5d94c232a01c823add64ebe569ed50ce1d37e1f5c8ffdc5742d58b39',
 'asrock-h670m-itx-ax': '7ce6e008fa2fae87edb596c86b0c26a76419dd9de50cbaad38a14e65d4cd3f25',
 'asrock-x670e-taichi': '34f3ac8699313f53409064128fe2e12031a71a209ecd4b3db03baae091838e29',
 'asrock-x870-pro-rs': '79cecc9b51db1cd328429443d68ce54c511b025aedadd478e65e4f4ea7f1af01',
 'asrock-z790-pg-itx-tb4': '951ee4de8b59dae27c59ea8060aaa9a257a456a6436fcda97ecf4a5a8ef809b1',
 'asus-prime-b650m-a-wifi-ii': '7321da10da451bf6e9944cdf67e45cea2314dc62e304dc76633437e7214f088f',
 'asus-prime-b760m-a-wifi-d4': '0936bb9f549091d417c2c6ad2217ab0ad462588d1d744b22fecc80fecaf1440a',
 'asus-rog-maximus-z790-hero': '5c244eb0ee81714e28f0890130667b34da7763b6183a37eff412ecacb50058a2',
 'asus-rog-strix-b650e-i-wifi': '0efca3e9296679267f46afe99aeeb205983a2382c5a58766d31fa4c4259d816c',
 'asus-rog-strix-x670e-e-wifi': 'c83decdae8f6427eb3fb5c25fcfb3d1c2303c3f7bed5e09ed4279b475e8fdec6',
 'asus-rog-strix-z790-a-wifi-d4': '73852b4b4ae3391cfd98291eda26355f26c3eb185c593f2b459113f1cccab3df',
 'asus-tuf-b650m-plus-wifi': 'f248e890db661ce6da72ca9525487766b82ceea473a47a2bdfb468812c2dff1b',
 'asus-tuf-z690-plus-wifi-d4': 'ff1076b06ce3e6c237c6e4f6e74b0bd3407af258e65b58df859562b3263ed9f9',
 'asus-tuf-z790-plus-wifi': '0126b29845535d976aefdeffad4d73bd4373810a62cb4864d83972da28e0853c',
 'gigabyte-b550m-ds3h-rev15': '44c8c8c36bc7ae92dfad43427c76e9435bf56fb6041cda033942fb1c2452f8e7',
 'gigabyte-z790-aorus-master': '52f5c66ea41ae5076f1d142efe09dd0df8189893942b4fe7fb35286644f93ec6',
 'msi-b550m-pro-vdh-wifi': '039187aab3653b59e9b185b13659d4bd6404c65ca865f7e894d459e647bdbdca',
 'msi-mag-b550-tomahawk': '3ae0ab0b9ec21a0edb2c191ad33dc62f84e77e4207d07dd43b67d44bc94097f7',
 'msi-mag-b650m-mortar-wifi': '17b3813a8d3d55a3da12cd12574dc82b2353e2c7a3b8b83a4048bb67aaf37f3a',
 'msi-mag-b760m-mortar-wifi': '1ae1f604b9fb60d05cbf19953b5aa2fd4cc5adcaff9bf9a9d31a30480ac13f42',
 'msi-mag-x670e-tomahawk-wifi': '42f270401b0c6baf585b55f2c21b6a34f5c82ee3cbe77bfdac99c23ef3df87bf',
 'msi-meg-x670e-godlike': 'b4b413aa603b18daa9f1478a1a54d13ff60e0ea8f403fe5d65164e9a5b4eedd1',
 'msi-mpg-b650i-edge-wifi': '8dce3b9e0a20e7d93f63e928b619570fdb8fd8873fe4e44d2c6685eaa5d82e67',
 'msi-pro-b760m-a-wifi': 'ddabcca2f0966b310fe60a6dd69fbb56e511e62dd1169b1219359f34f324f97e'}
LEGACY_GEOMETRY = {'asrock-b550m-itx-ac': 'c17885bbf09716142d4e57cc2d1e181e7d16fefd5c78f5d4a75591bcda28fefe',
 'asrock-b650-pg-lightning': '1cb87b5530df65f34dc3c43befd7613537fb60875a601c4a5e55503082c7fa7c',
 'asrock-h670m-itx-ax': 'ef95dc8801de2c983a332b9a3e5071912cc2e5154dc973c6da8579ea86c9690f',
 'asrock-x870-pro-rs': '0207f96401c935bcb5884a635852d6a030b527213dadd7c1ef61d225daf33cd4',
 'asus-prime-b650m-a-wifi-ii': '83c6c8b579af51109ea76385e017a1ec8e1ca9ee0fc9e48e905b9de019d006bf',
 'asus-prime-b760m-a-wifi-d4': 'e5ff89c58dacabf31dd65957c9dbad75e440bbea4eceb841a3e8a23d9bc224f9',
 'asus-rog-maximus-z790-hero': 'd915e05f5c55c74ddebc3f04d2d74855ee7bb032b62226eb091ed5ba61015452',
 'asus-rog-strix-b650e-i-wifi': '93a22b9ab301b24c14aa7e56cc3ff545e413f6ed8733a35a559c8ecb4a59b775',
 'asus-rog-strix-x670e-e-wifi': 'c1cc673e383913cc71a1e025a0486dadee5538f1bf2e13748f2182eace4bcac0',
 'asus-rog-strix-z790-a-wifi-d4': '2757deb17088ff63664f171dccf5132c06865cc00e00bbff6d9be970d8f4e9f7',
 'asus-tuf-b650m-plus-wifi': '3374907c76bf9d719cc3eaf33e9fc3fc9ece141aa7a493e51e36b9bcb4c741f9',
 'asus-tuf-z690-plus-wifi-d4': '77ad04ca21f55f68abd667b211bbcc017d3e6c552a78e6e62f795a90e70866ff',
 'asus-tuf-z790-plus-wifi': '71706a2961ca3cea16e443112265a156ccfbc81364b8725499c525f2d75abd54',
 'gigabyte-b550m-ds3h-rev15': '21dd72b477a487081bb26e27bd6b75982a542c7ea6c9426a662d01d545376c65',
 'msi-b550m-pro-vdh-wifi': 'b5a0f6c2d89bfb8c2db804b803c6682b949a15652c497d5830adc89a6c31e23b',
 'msi-mag-b550-tomahawk': '01b15175b62b483b7dc8839beeb20af78fdaee759b1b9f182435458a9f02b4bb',
 'msi-mag-b650m-mortar-wifi': 'cd853f07b919dfe392433f9062aeb0096983ff353ea9afcb54738766472c2f15',
 'msi-mag-b760m-mortar-wifi': 'd973e0ce9e38f151f929bf1d5922346f1054fd045d02fc08d835fee11e6b5710',
 'msi-mag-x670e-tomahawk-wifi': '3ea886a43abe655c1529ee83f464ddee85218b5cd0432425c7048c5dae98f73b',
 'msi-meg-x670e-godlike': 'e97af22082ffe487c3101a435ed4ef200d17ce1a8cfcb9f92344a8b08ad94328',
 'msi-mpg-b650i-edge-wifi': 'b733e34aa2d582a3777a1ca58e4a7b48948af6ecbd3f8f8476a7cfe76a880e9f',
 'msi-pro-b760m-a-wifi': 'b8f0c81346ed1378e492393c455c26e22562cfedeef4d51170c7fd5f00785fa2'}
TARGET_IMMUTABLE = {'asrock-b650e-steel-legend-wifi': '594281e4c1b9a0de4b576ceade30ae35a8bd1421842749b04ad5ca7c956fb8a2',
 'asrock-b650i-lightning-wifi': '3725ea359009b1cc7bc34209c7cf6f96afb3adb8c731d96dfec2f733d802c43c',
 'asrock-b650m-pg-riptide-wifi': '4c0b323d7bb06eb8002c4c9e2e1b9a8d1356e85efc88c6329b5d0b05ea64eb42',
 'asrock-x670e-taichi': '32d1a786860bbd988e5777f9f1ddeff8cd11d30ce8486d03366dea5e2c37f7a2',
 'asrock-z790-pg-itx-tb4': '42a814ca6bc938a69fc72002830f5d50997aa64389dea78a3ee80ac13e14b9bb',
 'gigabyte-z790-aorus-master': 'fa9de2be473ce8f1b830afb26f18b6e942fd514800971a66f9fae1e2f3d66dd9'}
PRESERVED_FIELDS = ('id',
 'label',
 'brand',
 'form_factor',
 'socket',
 'memory_type',
 'dimensions_mm',
 'cpu_uv',
 'dimm_uv',
 'pcie',
 'm2',
 'connectors',
 'rear_ports',
 'rear_layout',
 'rear_layout_source',
 'battery_uv',
 'diagnostics',
 'mount_uv',
 'mount_method',
 'mount_page',
 'native_m2_only',
 'accessory_cards_assumed_installed',
 'unplaced_source_features',
 'optional_m2_fan_sink_installed')

LEGACY_STYLE_SHA = {'asrock-b550m-itx-ac': '0cd2e2c41c10f397db7e9ec3afe34360c5ab841097d0e837b76443cd857f504a',
 'asrock-b650-pg-lightning': 'e98d876de1219eebf6f8360caa7b2a78ea02d84bdb780ad076aaf16dadd3e60b',
 'asrock-h670m-itx-ax': '454973b712c0f99cdcf328ec522736f4fa8281da8761611dbeb116ca23b76d2b',
 'asrock-x870-pro-rs': 'c3c992c7f3be00fe31b9d6ffb97533a5857b1b8f2c7e04892a05ec6cf41b0eaa',
 'asus-prime-b650m-a-wifi-ii': '4fda48e1051067c2fb93b48c7055bc9b493a41d6fb3c611248b2c56ee049c1ec',
 'asus-prime-b760m-a-wifi-d4': 'cbfd09499106089a78ed1968400df2bbf925e485111f45fbf175255330749252',
 'asus-rog-maximus-z790-hero': '44276aa9f49a6aa76b94aba86450a587e4caf2c6c875f15d92765c4fa7bb14d6',
 'asus-rog-strix-b650e-i-wifi': 'a2637895a5f737e8c3a7dcac73bfbe957121c84f075ebc65c5ceea0bb2fbd9c6',
 'asus-rog-strix-x670e-e-wifi': 'c03a07793bdd58c8ed2820e8cd94f640d636bcbd9eb79b4ce1be71ae648d40b8',
 'asus-rog-strix-z790-a-wifi-d4': 'cbd4034d03ee87be2b2da093c0e95dcc8cef647433f342c0a049c07607fdf10a',
 'asus-tuf-b650m-plus-wifi': '628a428e8949cac04f8ccab3f101ed815e4dc15b93cda04c12340145576b3b29',
 'asus-tuf-z690-plus-wifi-d4': 'fd8f61619615c1a9f98f1f25e05605359327fc5bbce8bb91e6874103d70313af',
 'asus-tuf-z790-plus-wifi': '5957a55b46a81265781eeb6f82dfe7fe37d4fc41d4ae19d3995f7fef371e0668',
 'gigabyte-b550m-ds3h-rev15': 'a4578d3fadd9f70325c16d3439b814b7de9eeb4f51abb3def67f74763fcaa434',
 'msi-b550m-pro-vdh-wifi': '6add3ed6e5a16ad6ac4c71e668f9717b39f019560ed62b7134b0bfa414adf45a',
 'msi-mag-b550-tomahawk': '31f36e3f327417ccb2be039ba45d982d77ac82326bc4eb912e4938c8a63f6ff1',
 'msi-mag-b650m-mortar-wifi': 'dac81d27b2237edb89781a44835aee93688c140afcb7d98a7a2818f3a58bfd8c',
 'msi-mag-b760m-mortar-wifi': '89a2ecb590387462db19ed08beb25d4a421d1eb4c62cbceb1e97b043a220d14a',
 'msi-mag-x670e-tomahawk-wifi': 'af1a140af53cff6364d3ee731615ac7b45ad5b042482d41f85dc168a6eeb8721',
 'msi-meg-x670e-godlike': 'a676e3b0a342bd0958b901a3bd4d3359d0149f063d818a713ad3c68f4d9c86c4',
 'msi-mpg-b650i-edge-wifi': '2a8198fd93f1f5739ce293cc0e1fd7cd33da135601ad0437a1c4651606ebb594',
 'msi-pro-b760m-a-wifi': 'fb3c42b58fd3603f9a3a4bca60517eebbdaea768f2738fb3edc73f9cd5d6c5ab'}

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
ASUS_INSETS={'asus-rog-strix-z790-a-wifi-d4','asus-rog-strix-x670e-e-wifi','asus-rog-maximus-z790-hero'}
ASUS_M2_OLD=((.164,.506),(.688,.506),(.706,.486),(.974,.486),(.974,.549),(.922,.577),(.164,.577))
ASUS_M2_052=((.164,.506),(.902,.506),(.920,.486),(.974,.486),(.974,.549),(.922,.577),(.164,.577))

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def legacy_header_metadata051(testcase,row):
    """Reverse only the eight source-qualified051 header annotations.

    These five keys were absent on these exact eight old fan connectors. All
    original connector coordinates/fields and the rest of the complete row
    still pass the unchanged0.46 digest; no model is exempted from that check.
    The current annotations must independently match the primary manual.
    """
    testcase.assertEqual(row['id'],'asus-rog-strix-z790-a-wifi-d4')
    restored=copy.deepcopy(row)
    current=[value for value in row['connectors'] if value['kind']=='fan']
    previous=[value for value in restored['connectors'] if value['kind']=='fan']
    expected=(('CPU_OPT','cpu_opt',(.355,.014)),('CPU_FAN','cpu_fan',(.625,.014)),
        ('CHA_FAN2','case_fan',(.372,.466)),('AIO_PUMP','aio_pump',(.404,.466)),
        ('CHA_FAN1','case_fan',(.274,.985)),('CHA_FAN3','case_fan',(.724,.985)),
        ('CHA_FAN4','case_fan',(.819,.985)),('CHA_FAN5','case_fan',(.862,.985)))
    testcase.assertEqual(len(current),8)
    keys=('label','role','role_verified','role_source','role_source_page')
    for value,old,(label,role,uv) in zip(current,previous,expected):
        testcase.assertEqual(value['uv'],uv)
        testcase.assertEqual({key:value[key] for key in keys},dict(label=label,role=role,
            role_verified=True,role_source=ASUS_Z790_MANUAL,role_source_page=14))
        testcase.assertIs(value['role_verified'],True)
        for key in keys:del old[key]
    # One independently source-reviewed052 polygon correction. Keep the old
    # whole-row digest instead of replacing it or exempting this model.
    upper=next(c for c in restored['heatsinks'] if c['name']=='m2-upper')
    testcase.assertEqual(upper['polygon'],ASUS_M2_052);upper['polygon']=ASUS_M2_OLD
    return restored


def payload_sha(meshes):
    result=hashlib.sha256()
    for mesh in meshes:
        values=[mesh.name,mesh.color,mesh.position,mesh.component,mesh.rotor,mesh.direction,mesh.axis,mesh.part_id]
        result.update(json.dumps(values,separators=(',',':')).encode())
        result.update(struct.pack('<'+str(len(mesh.vertices))+'d',*mesh.vertices))
    return result.hexdigest()

def board_meshes(identity,level='balanced',model=None):
    row=copy.deepcopy(model) if model is not None else get_model(identity)
    spec=dict(board=dict(model_id=identity),memory=dict(count=0),
              cpu=dict(model_id='intel-13700kf' if row['socket']=='LGA1700' else 'amd-9950x'))
    with patch('assembly_motherboard.resolve',return_value=row):
        anchors=layout_anchors(spec,400.,600.,500.,90.,0.,-150.)
    meshes,meta=enrich_motherboard((),spec,anchors,level)
    return meshes,meta,anchors


def legacy_socket_geometry052(testcase,identity,meshes,anchors):
    """Reverse only declared052 socket banks and exact-ASUS upper M2 fixes."""
    from assembly_detail import _boxes
    values=meshes
    if identity=='asus-rog-strix-z790-a-wifi-d4':
        import assembly_detail
        from assembly_geometry import unit_polygon
        model=get_model(identity);next(c for c in model['heatsinks'] if c['name']=='m2-upper')['polygon']=ASUS_M2_OLD
        original_plate=assembly_detail.perforated_plate
        upper=next(c for c in model['heatsinks'] if c['name']=='m2-upper')
        bw=anchors['board']['width'];bh=anchors['board']['height']
        outer=unit_polygon([list(p) for p in ASUS_M2_OLD],bw,bh)
        recess=min(3.,upper['depth_mm']*.42)
        old_channels=[((u-.5)*bw,(.5-v)*bh,3.2) for u,v in model['mount_uv']
                      if assembly_detail._point_inside((u,v),ASUS_M2_OLD)]
        u0,u1=min(p[0] for p in ASUS_M2_OLD),max(p[0] for p in ASUS_M2_OLD)
        v0,v1=min(p[1] for p in ASUS_M2_OLD),max(p[1] for p in ASUS_M2_OLD)
        for n in range(upper['grooves']):
            u=u0+(u1-u0)*(.20+.60*n/max(1,upper['grooves']-1));v=v0+(v1-v0)*.50
            cx,cy=(u-.5)*bw,(.5-v)*bh
            channel=assembly_detail.chamfer_rect(.65,(v1-v0)*bh*.68,.12)
            old_channels.append(tuple((x+cx,y+cy) for x,y in channel))
        def old_upper_walls(*args,**kwargs):
            # Only the newly enabled exact-ASUS upper plinth/crown supply
            # True here. All other calls retain their original default.
            if kwargs.get('clip_walls') is True:
                testcase.assertEqual(args[0],outer)
                kwargs=dict(kwargs,clip_walls=False)
                if args[2]==recess:
                    # Reverse only052's bounded groove-height containment.
                    # The unchanged old full payload still verifies every
                    # original groove, mount-hole wall and all other parts.
                    testcase.assertEqual(len(args[1]),len(old_channels))
                    args=(args[0],old_channels,*args[2:])
            return original_plate(*args,**kwargs)
        with patch.object(assembly_detail,'perforated_plate',new=old_upper_walls):
            values,_meta,legacy_anchors=board_meshes(identity,model=model)
        testcase.assertEqual(legacy_anchors['dimm_centers'],anchors['dimm_centers'])
        first=next(i for i,m in enumerate(meshes) if m.name=='detail-board-m2-heatsink')
        testcase.assertEqual(meshes[first+1].name,'board-heatsink-recessed-crown')
        testcase.assertEqual([m for i,m in enumerate(meshes) if i not in (first,first+1)],
                             [m for i,m in enumerate(values) if i not in (first,first+1)])
    bx=anchors['board']['x'];new_banks=[];old_strips=[]
    for _x,y,z in anchors['dimm_centers']:
        for side in (-1,1):new_banks.append(((3.6,132.,.16),(bx-3.,y,z+side*.88)))
        old_strips.append(((.28,132.,1.9),(bx-1.9,y,z)))
    contacts=[m for m in values if m.name=='detail-board-memory-socket-contact-wells']
    testcase.assertEqual(len(contacts),1);testcase.assertEqual(contacts[0].vertices,_boxes(new_banks))
    return tuple(replace(m,vertices=_boxes(old_strips)) if m.name=='detail-board-memory-socket-contact-wells' else m for m in values)


class MotherboardFinish047Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure offline construction only')))

    def test_only_six_rows_change_and_layout_unknowns_remain_exact(self):
        rows={row['id']:row for row in MODELS}
        self.assertTrue(set(LEGACY_ROWS).issubset(rows))
        for identity,old_hash in LEGACY_ROWS.items():
            with self.subTest(model=identity):
                row=rows[identity]
                if identity not in TARGET_IMMUTABLE:
                    comparison=legacy_header_metadata051(self,row) if identity=='asus-rog-strix-z790-a-wifi-d4' else row
                    self.assertEqual(canonical(comparison),old_hash)
                else:
                    self.assertEqual(canonical({key:row.get(key) for key in PRESERVED_FIELDS}),TARGET_IMMUTABLE[identity])
                    self.assertEqual(row['finish_status'],'photo_reviewed')
                    self.assertFalse(row['heatsink_depths_verified'])
                    for cover in row['heatsinks']:
                        self.assertFalse(cover['depth_verified']);self.assertFalse(cover['cad_verified'])
                        self.assertEqual(cover['finish_color_accuracy'],'qualitative_reference')
                        self.assertTrue(cover['outline_source'].startswith('https://'))
        self.assertIn('rev.1.0',rows['gigabyte-z790-aorus-master']['label'])
        self.assertNotIn('MASTER X',rows['gigabyte-z790-aorus-master']['label'])
        self.assertNotIn('vrm-top',{c['name'] for c in rows['asrock-b650i-lightning-wifi']['heatsinks']})
        self.assertNotIn('vrm-top',{c['name'] for c in rows['asrock-b650m-pg-riptide-wifi']['heatsinks']})

    def test_per_cover_finish_colors_plinth_crown_and_legacy_fallback(self):
        model=get_model('msi-mag-b760m-mortar-wifi');model['static_finish_regions']=()
        polygon=((.3,.12),(.65,.12),(.65,.21),(.3,.21))
        model['heatsinks']=(dict(name='finish-blue',polygon=polygon,depth_mm=8.,grooves=3,finish_color='#335577'),
            dict(name='finish-grey',polygon=((.3,.7),(.65,.7),(.65,.78),(.3,.78)),depth_mm=5.,grooves=0))
        for level in ('eco','balanced','close'):
            meshes,_,_=board_meshes(model['id'],level,model)
            blue=[m for m in meshes if m.name=='board-finish-blue-heatsink']
            crown=[m for m in meshes if m.name=='board-heatsink-recessed-crown']
            grey=[m for m in meshes if m.name=='board-finish-grey-heatsink']
            self.assertEqual(len(blue),1);self.assertEqual(len(grey),1)
            self.assertEqual(blue[0].color,color('#335577'))
            self.assertTrue(all(m.color==blue[0].color for m in crown))
            self.assertEqual(bool(crown),level!='eco')
            self.assertEqual(grey[0].color,color(model['heatsink_color']))

    def test_asus_inset_is_named_and_cannot_leak_to_other_models(self):
        for row in MODELS:
            forced=copy.deepcopy(row);forced['io_clear_inset']=True
            cover=_io_clear_cover(forced)
            self.assertEqual(cover is not None,row['id'] in ASUS_INSETS,row['id'])
            if cover:
                forced['heatsinks']=tuple(reversed(forced['heatsinks']))
                self.assertEqual(_io_clear_cover(forced),cover)
                forced['heatsinks']=tuple(c for c in forced['heatsinks'] if c['name']!='vrm-io')
                self.assertIsNone(_io_clear_cover(forced))
        row=get_model('asus-rog-strix-z790-a-wifi-d4');row['io_clear_inset']=False
        self.assertIsNone(_io_clear_cover(row))

    def test_static_material_inlays_are_hosted_and_never_light_zones(self):
        total=0
        for identity in TARGET_IMMUTABLE:
            row=get_model(identity);meshes,_,anchors=board_meshes(identity)
            covers={cover['name']:cover for cover in row['heatsinks']}
            for region in row.get('static_finish_regions',()):
                total+=1;self.assertFalse(region['emissive']);self.assertFalse(region['depth_verified'])
                self.assertEqual(region['finish_color_accuracy'],'qualitative_reference')
                parent=covers[region['parent_cover']] if region['parent_cover'] else None
                mesh=next(m for m in meshes if m.name=='board-static-finish-'+region['id'])
                self.assertEqual(light_kind(mesh),'')
                self.assertAlmostEqual(mesh.position[0],anchors['board']['x']-1.1-(parent['depth_mm'] if parent else 0)-region['depth_mm']/2)
                self.assertAlmostEqual(max(mesh.vertices[0::6])-min(mesh.vertices[0::6]),region['depth_mm'])
                for mode in MODES:
                    values,info=apply_lighting((mesh,),mode)
                    self.assertIs(values[0],mesh);self.assertEqual(info['lighting_preview']['zones'],[])
        self.assertEqual(total,8)

    def test_no_guessed_fans_holes_or_installed_accessories(self):
        for identity in TARGET_IMMUTABLE:
            row=get_model(identity);meshes,meta,_=board_meshes(identity)
            self.assertFalse(any(m.rotor for m in meshes))
            self.assertFalse(any(c.get('static_fan') for c in row['heatsinks']))
            self.assertFalse(meta['installed_ssd_count_inferred'])
            if row['form_factor']=='itx':self.assertEqual(row['mount_method'],'reference_unverified_hole_centers')
            else:self.assertEqual(row['mount_uv'],())
        taichi=get_model('asrock-x670e-taichi')
        self.assertIn('active_vrm_cooling_fan_dimensions_and_position_unverified',taichi['unplaced_source_features'])
        self.assertIs(taichi['optional_m2_fan_sink_installed'],False)

    def test_thirteen_saved_styles_share_physical_geometry_and_current_budgets(self):
        self.assertEqual(len(HARDWARE_ICON_STYLES),13);self.assertTrue(set(SIX).issubset(HARDWARE_ICON_STYLES))
        for identity in TARGET_IMMUTABLE:
            for level in ('eco','balanced','close'):
                with self.subTest(model=identity,lod=level):
                    meshes,board_meta,_=board_meshes(identity,level)
                    meshes=tuple(replace(m,part_id='board:0') for m in meshes)
                    self.assertLessEqual(sum(len(m.vertices)//18 for m in meshes),TRIANGLE_BUDGETS[level])
                    self.assertTrue(all(math.isfinite(value) for m in meshes for value in m.vertices))
                    for style in HARDWARE_ICON_STYLES:
                        values,meta=apply_model_styles(meshes,style,{},(400.,600.,500.),{'front':'open'},
                            finish_materials=board_meta['finish_materials'])
                        for old,new in zip(meshes,values):
                            self.assertIs(old.vertices,new.vertices)
                            self.assertEqual((old.position,old.axis,old.direction,old.rotor,old.part_id),
                                             (new.position,new.axis,new.direction,new.rotor,new.part_id))
                        if style=='miniature':self.assertEqual(len(values),len(meshes))
                        roles=board_meta['finish_materials']['roles']
                        pcb=next(m for m in values if roles.get(m.name)=='pcb')
                        armor=[m for m in values if roles.get(m.name)=='armor']
                        self.assertTrue(armor)
                        if style not in ('notebook_line','outline','sketch'):
                            self.assertTrue(all(m.color!=pcb.color for m in armor),(identity,style))
                        else:
                            self.assertTrue(all(m.color==pcb.color for m in armor))
                            self.assertTrue(all(m.position[0]<pcb.position[0] for m in armor))
                    edges=edge_batches(meshes,'notebook_line')
                    self.assertLessEqual(sum(len(vertices)//12 for _,vertices in edges),MAX_STYLE_EDGES)
                    self.assertTrue(all(len(vertices)//12<=512 for _,vertices in edges))

    def test_untouched_scene_bytes_and_six_actual_assembly_contracts(self):
        for identity,expected in LEGACY_GEOMETRY.items():
            meshes,board_meta,anchors=board_meshes(identity)
            self.assertEqual(payload_sha(legacy_socket_geometry052(self,identity,meshes,anchors)),expected,identity)
            self.assertNotIn('finish_materials',board_meta)
            colors=[]
            for style in SIX:
                # Even an accidentally supplied role map cannot opt an
                # unrelated model into the six source-finish profiles.
                values,_=apply_model_styles(meshes,style,{},(400.,600.,500.),{'front':'open'},
                    finish_materials=dict(model_id=identity,roles={m.name:'armor' for m in meshes}))
                colors.append([(m.name,m.color) for m in values])
            self.assertEqual(hashlib.sha256(json.dumps(colors,separators=(',',':')).encode()).hexdigest(),LEGACY_STYLE_SHA[identity],identity)
        for identity in TARGET_IMMUTABLE:
            model=get_model(identity)
            spec=dict(case=dict(dimensions_mm=dict(width=340.,height=600.,depth=600.),layout='tower'),
                board=dict(model_id=identity),gpu=dict(present=False),memory=dict(count=0),detail_level='balanced',
                cpu=dict(style='lga_rect' if model['socket']=='LGA1700' else 'am5',appearance=dict(
                    id='intel-13700kf' if model['socket']=='LGA1700' else 'amd-9950x')))
            scene=build_scene(spec);meta=scene.metadata['motherboard'];anchors=scene.metadata['attachment_anchors']
            self.assertEqual(meta['model_id'],identity)
            self.assertEqual(meta['rendered_memory_sockets'],len(model['dimm_uv']))
            self.assertEqual(meta['documented_slot_counts']['m2'],len(model['m2']))
            self.assertFalse(meta['cad_verified']);self.assertFalse(meta['installed_ssd_count_inferred'])
            self.assertEqual(anchors['board']['height'],model['dimensions_mm']['height'])
            self.assertEqual(anchors['board']['width'],model['dimensions_mm']['width'])
            expected_y=anchors['board']['y']+(.5-model['cpu_uv'][1])*model['dimensions_mm']['height']
            expected_z=anchors['board']['rear_z']+model['cpu_uv'][0]*model['dimensions_mm']['width']
            self.assertAlmostEqual(anchors['cpu']['y'],expected_y);self.assertAlmostEqual(anchors['cpu']['z'],expected_z)
            self.assertLessEqual(scene.triangle_count,TRIANGLE_BUDGETS['balanced'])
            from assembly_scene_cache import SceneCache
            cache=SceneCache();original=cache.build(spec)
            with patch('assembly_scene_cache.build_scene',side_effect=AssertionError('Palette must reuse physical scene')):
                paper=cache.build(dict(spec,visual_style='papercut'))
                restored=cache.build(dict(spec,visual_style='miniature'))
            self.assertIs(restored,original)
            roles=paper.metadata['motherboard']['finish_materials']['roles']
            pcb=next(m for m in paper.meshes if roles.get(m.name)=='pcb')
            self.assertTrue(all(m.color!=pcb.color for m in paper.meshes if roles.get(m.name)=='armor'))
            for before,after in zip(original.meshes,paper.meshes):self.assertIs(before.vertices,after.vertices)

if __name__=='__main__':unittest.main()
