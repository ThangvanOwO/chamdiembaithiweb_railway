"""Reviewed CNN integration: preserve blank/double/invalid raw evidence."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from grading.engine import hi as engine
from grading.engine import live_bubble_reader as live
from grading.engine import reviewed_bubble_model as model

ROOT = Path(__file__).resolve().parents[1]


class ReviewedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'LIVE_REVIEWED_CNN': '1'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.gray = np.full((160, 200), 230, np.uint8)
        self.points = [(40, 60), (100, 60), (160, 60)]

    def session_with_probability(self, *values):
        session = Mock()
        session.run.return_value = [np.log(np.array([[1-p, p] for p in values], np.float32))]
        return patch.object(model, 'session', return_value=session), session

    def refine(self, evidence, **kwargs):
        return model.refine_evidence(self.gray, self.points[:len(evidence)], evidence, 13, True, **kwargs)

    def test_crop_matches_reviewed_export_rounding_and_inclusive_edges(self):
        self.gray = np.arange(160*200, dtype=np.uint16).reshape(160, 200).astype(np.uint8)
        actual = model.crop_for_model(self.gray, (40.5, 60.8))
        expected = cv2.resize(self.gray[48:75,27:54],(32,32),interpolation=cv2.INTER_AREA)
        np.testing.assert_array_equal(actual, expected)

    def test_faint_broad_ink_is_confirmed_without_inventing_ink_on_sparse_cell(self):
        evidence = [live.InkEvidence('uncertain', .1425, .8029, 4),
                    live.InkEvidence('uncertain', .10, .1, 0)]
        session_patch, _ = self.session_with_probability(.682, .999)
        with session_patch:
            result = self.refine(evidence)
        self.assertEqual([e.state for e in result], ['marked', 'uncertain'])

    def test_blank_invalid_and_definite_marks_never_load_or_change(self):
        evidence = [live.InkEvidence('blank', .01, 0, 0),
                    live.InkEvidence('marked', .8, 1, 4),
                    live.InkEvidence('invalid', 0, 0, 0)]
        with patch.object(model, 'session', side_effect=AssertionError('Unnecessary inference')):
            self.assertEqual(self.refine(evidence), evidence)

    def test_printed_text_or_shadow_can_clear_uncertainty_when_model_agrees(self):
        evidence = [live.InkEvidence('uncertain', .08, .10, 0),
                    live.InkEvidence('uncertain', .165, .51, 3)]
        session_patch, _ = self.session_with_probability(.344, .024)
        with session_patch:
            self.assertEqual([e.state for e in self.refine(evidence)], ['blank','blank'])

    def test_model_cannot_clear_a_broad_ambiguous_mark(self):
        evidence = [live.InkEvidence('uncertain', .1, .8, 4)]
        session_patch, _ = self.session_with_probability(.001)
        with session_patch:
            self.assertEqual(self.refine(evidence), evidence)

    def test_two_definite_marks_remain_double_marked(self):
        evidence = [live.InkEvidence('marked', .7, 1, 4),live.InkEvidence('marked', .3, .9, 4)]
        with patch.object(model, 'session', side_effect=AssertionError('Do not clear real marks')):
            result = self.refine(evidence)
        self.assertEqual(live._select(result),(-1,True))

    def test_disabled_unaligned_and_other_radius_keep_original(self):
        evidence = [live.InkEvidence('uncertain', .14, .8, 4)]
        with patch.object(model, 'session', side_effect=AssertionError('Wrong route')):
            for radius, aligned in [(13,False),(10,True)]:
                self.assertEqual(model.refine_evidence(self.gray,self.points[:1],evidence,radius,aligned),evidence)
            with patch.dict(os.environ, {'LIVE_REVIEWED_CNN':'0'}):
                self.assertEqual(self.refine(evidence),evidence)

    def test_missing_model_and_invalid_output_preserve_uncertainty(self):
        evidence=[live.InkEvidence('uncertain',.14,.8,4)]
        with patch.object(model,'session',return_value=None):
            self.assertEqual(self.refine(evidence),evidence)
        for invalid in [np.array([[np.nan,0]]),np.zeros((2,2))]:
            fake=Mock()
            fake.run.return_value=[invalid]
            with patch.object(model,'session',return_value=fake), self.assertLogs(model.logger,level='ERROR'):
                self.assertEqual(self.refine(evidence),evidence)

    def test_batch_inference_and_diagnostics_are_request_local(self):
        evidence=[live.InkEvidence('uncertain',.14,.8,4)]*3
        session_patch, fake=self.session_with_probability(.7,.7,.7)
        first,second={},{}
        with session_patch:
            self.refine(evidence,diagnostics=first)
        self.assertEqual(fake.run.call_count,1)
        self.assertEqual(fake.run.call_args.args[1]['input'].shape,(3,1,32,32))
        self.assertEqual(first,{'inferred':3,'resolved':3})
        self.assertEqual(second,{})

    def test_model_checksum_failure_is_cached_and_keeps_reader_available(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'wrong.onnx').write_bytes(b'bad')
            info={'file':'wrong.onnx','sha256':'wrong','version':'test'}
            model.session.cache_clear()
            try:
                with patch.object(model,'MODEL_DIR',root),patch.object(model,'metadata',return_value=info),self.assertLogs(model.logger,level='ERROR'):
                    self.assertIsNone(model.session())
                self.assertIsNone(model.session())
            finally:
                model.session.cache_clear()

    def test_missing_or_corrupt_manifest_disables_model_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            try:
                with patch.object(model, 'MODEL_DIR', root):
                    for text in (None, 'broken JSON', '[]'):
                        if text is not None:
                            (root / 'manifest.json').write_text(text, encoding='utf-8')
                        model.metadata.cache_clear()
                        self.assertEqual(model.metadata(), {})
                        self.assertFalse(model.supports_geometry(13, 1400, 1920, []))
            finally:
                model.metadata.cache_clear()


class ReviewedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            engine.load_template(str(ROOT/'grading/engine/templates/template_default.json'))

    def setUp(self):
        self.environment=patch.dict(os.environ,{'LIVE_REVIEWED_CNN':'1'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.gray=np.full((1920,1400),235,np.uint8)
        ids={(x,y) for x in engine.SBD_COLS_X+engine.MADE_COLS_X for y in engine.SBD_MADE_DIGIT_Y}
        for x,y in engine.ALL_BUBBLE_CENTERS:
            cv2.circle(self.gray,(int(x),int(y)),10 if (x,y) in ids else 13,75,2)

    def read(self,gray):
        e=engine
        p1,_,_=live.read_part1(gray,e.PART1_COLS,e.PART1_CHOICES,reviewed_model=True)
        p2,_=live.read_part2(gray,e.PART2_BLOCKS,e.PART2_STEP_X,e.PART2_STEP_Y,e.PART2_ROWS,
                           align=True,reviewed_model=True)
        p3,_=live.read_part3(gray,e.PART3_BLOCKS,e.PART3_SIGN_Y,e.PART3_COMMA_Y,e.PART3_DIGIT_START_Y,
                           e.PART3_DIGIT_STEP_Y,local_symbols=True,reviewed_model=True)
        return p1,p2,p3

    def test_only_trained_geometry_can_enable_cnn(self):
        e=engine
        self.assertTrue(model.supports_geometry(e.BUBBLE_RADIUS,e.WARP_WIDTH,e.WARP_HEIGHT,e.ALL_BUBBLE_CENTERS))
        self.assertFalse(model.supports_geometry(10,e.WARP_WIDTH,e.WARP_HEIGHT,e.ALL_BUBBLE_CENTERS))
        self.assertFalse(model.supports_geometry(13,1400,1920,e.ALL_BUBBLE_CENTERS[:-1]))

    def test_blank_printed_grid_brightness_and_specks_never_gain_answers(self):
        for gain in (.65,1,1.08):
            gray=np.clip(self.gray.astype(float)*gain,0,255).astype(np.uint8)
            for x,y in engine.ALL_BUBBLE_CENTERS:
                cv2.circle(gray,(int(x)+2,int(y)+2),1,35,1)
            p1,p2,p3=self.read(gray)
            self.assertTrue(all(v=='' for v in p1.values()))
            self.assertTrue(all(v=='' for rows in p2.values() for v in rows.values()))
            self.assertTrue(all(v=='' for v in p3.values()))

    def test_clear_single_and_double_marks_keep_selection_rules(self):
        first,second=engine.PART1_COLS[:2]
        for x,y in [(first['start_x'],first['start_y']),
                    (second['start_x'],second['start_y']),
                    (second['start_x']+second['step_x'],second['start_y'])]:
            cv2.circle(self.gray,(round(x),round(y)),9,45,-1)
        p1,_,_=self.read(self.gray)
        self.assertEqual(p1[1],'A')
        self.assertEqual(p1[11],'X')


if __name__=='__main__':
    unittest.main()
