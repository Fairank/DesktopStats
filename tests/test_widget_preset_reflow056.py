"""Preset commits honor resize reflow and retain separate assembly saves."""
import copy
import unittest

from desktop_placement import desktop_plan
from stats_config import DEFAULT, validate
from widget_catalog import from_template
from tests.test_assembly_save055 import controller

SCREENS = [dict(id='two',primary=True,x=2560,y=-509,width=1440,height=2480)]
POSITIONS = {'cpu':[3446,-475],'gpu':[3696,-475]}


def configured(reflow=True):
    ui=controller()
    value=copy.deepcopy(DEFAULT)
    value.update(mode='separate',widgets={kind:from_template(kind+'_model')for kind in('cpu','gpu')},
                 widget_order=['cpu','gpu'],reflow_on_resize=reflow)
    for kind,width in (('cpu',240),('gpu',280)):
        value['widgets'][kind].update(enabled=True,width=width,height=240,screen_target='two')
    ui._saved=validate(value);ui._draft=copy.deepcopy(ui._saved)
    ui._commit.__func__.__globals__['validate']=validate
    ui.plans=[]
    def capacity(value,rearrange):
        ui.capacity_calls.append((copy.deepcopy(value),rearrange))
        specs,points=desktop_plan(value,SCREENS,POSITIONS,rearrange)
        ui.plans.append((specs,points))
        return ''
    ui.layout_error=capacity
    return ui


def enlarge(ui):
    for kind,width,height in (('cpu',360,360),('gpu',440,300)):
        ui._draft['widgets'][kind].update(width=width,height=height)


def overlap(specs,points):
    boxes=[(*points[row['id']],row['width'],row['height'])for row in specs]
    a,b=boxes
    return min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])


class WidgetPresetReflow056Tests(unittest.TestCase):
    def test_real_preset_commit_reflows_the_observed_right_edge_overlap(self):
        ui=configured();enlarge(ui)
        old_specs,old_points=desktop_plan(ui._draft,SCREENS,POSITIONS,False)
        self.assertTrue(overlap(old_specs,old_points))  # Real native failure's geometry.
        self.assertTrue(ui._commit(scope='desktop'))
        self.assertEqual(ui.applyRequested.calls,[(True,)])
        specs,points=ui.plans[-1]
        self.assertFalse(overlap(specs,points))
        for row in specs:
            x,y=points[row['id']]
            self.assertGreaterEqual(x,2560);self.assertGreaterEqual(y,-509)
            self.assertLessEqual(x+row['width'],4000);self.assertLessEqual(y+row['height'],1971)
        self.assertEqual(ui.saved_attempts,[ui._saved])

    def test_disabled_reflow_keeps_the_users_manual_placement_policy(self):
        ui=configured(False);enlarge(ui)
        self.assertTrue(ui._commit(scope='desktop'))
        self.assertEqual(ui.applyRequested.calls,[(False,)])
        self.assertTrue(overlap(*ui.plans[-1]))
        self.assertEqual(ui.plans[-1][1]['cpu'],POSITIONS['cpu'])

    def test_non_size_desktop_edits_do_not_rearrange_windows(self):
        ui=configured();ui._draft['widgets']['cpu']['title']='CPU status'
        self.assertTrue(ui._commit(scope='desktop'))
        self.assertEqual(ui.applyRequested.calls,[(False,)])
        self.assertEqual(ui.plans[-1][1],POSITIONS)

    def test_saving_assembly_does_not_apply_or_reflow_pending_widget_dimensions(self):
        ui=configured();original=copy.deepcopy(ui._saved);enlarge(ui)
        ui._draft['assembly']['inspection_cutaway']=True
        self.assertTrue(ui.saveAssembly())
        self.assertEqual(ui._saved['widgets'],original['widgets'])
        self.assertTrue(ui._saved['assembly']['inspection_cutaway'])
        self.assertNotEqual(ui._draft['widgets'],original['widgets'])
        self.assertEqual(ui.applyRequested.calls,[(False,)])
        self.assertEqual(ui.autostart_calls,[])


if __name__=='__main__':unittest.main()
