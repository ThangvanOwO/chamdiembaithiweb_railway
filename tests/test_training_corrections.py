"""Raw question crops, explicit human labels, permissions and reviewed export."""
import base64
import io
import hashlib
import json
import tempfile
import zipfile
from unittest.mock import patch

import cv2
import numpy as np
from django.contrib.auth.models import User
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from grading.models import TrainingCorrection
from grading.training_data import question_preview, sheet_preview, labelled_answer, validate_labels, write_dataset
from api.training_views import sample_revision

ROOT = '/api/v1/training/corrections/'


class TrainingCorrectionTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name, SECURE_SSL_REDIRECT=False)
        settings.enable()
        self.addCleanup(settings.disable)
        self.admin = User.objects.create_user('training-admin', password='Test-Password-123', is_superuser=True, is_staff=True)
        self.teacher = User.objects.create_user('training-teacher')
        self.other_admin = User.objects.create_user('training-admin2', is_superuser=True, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.cells = [{'id': 'Dung', 'x': 20.0, 'y': 20.0}, {'id': 'Sai', 'x': 60.0, 'y': 20.0}]
        gray = np.full((42, 82), 240, np.uint8)
        cv2.circle(gray, (20,20), 10, 40, -1)
        cv2.circle(gray, (60,20), 10, 50, 1)
        self.png = cv2.imencode('.png', gray)[1].tobytes()
        self.data = {'source_hash': 'a'*64, 'template_code': '40-08-06', 'part': 2, 'question': 6,
                     'subquestion': 'c', 'detected': '', 'cells': self.cells,
                     'geometry': {'bbox': [20, 20, 102, 62], 'width': 82, 'height':42, 'radius': 13,
                                  'aligned': True, 'method':'frontend_corners', 'template_hash':'b'*64},
                     'image_base64': base64.b64encode(self.png).decode()}
        self.labels = {'Dung': 'filled', 'Sai': 'empty'}

    def token(self, user=None):
        return signing.dumps({'user': (user or self.admin).pk, 'data': self.data}, salt='training-preview-v1', compress=True)

    def save(self, **overrides):
        data = {'preview_token': self.token(), 'labels': self.labels, 'confirmed': True, **overrides}
        return self.client.post(ROOT+'save/', data, format='json')

    def test_missing_c_is_saved_as_human_mark_not_prediction(self):
        response = self.save()
        self.assertEqual(response.status_code, 201)
        sample = TrainingCorrection.objects.get()
        self.assertEqual((sample.detected, sample.answer, sample.status), ('', 'Dung', 'pending'))
        with sample.image.open() as image:
            self.assertEqual(image.read(), self.png)

    def test_unaligned_crop_is_not_accepted_as_training_truth(self):
        self.data['geometry']['aligned'] = False
        self.assertEqual(self.save().status_code,400)
        self.assertEqual(TrainingCorrection.objects.count(),0)

    def test_requires_complete_explicit_labels_and_confirmation(self):
        for data in [{'confirmed': False}, {'labels': {'Dung':'filled'}},
                     {'labels': {'Dung':'filled', 'Sai':'predicted'}},
                     {'labels': {**self.labels, '../../oops':'filled'}}]:
            self.assertEqual(self.save(**data).status_code, 400)
        self.assertEqual(TrainingCorrection.objects.count(), 0)

    def test_preview_cannot_be_tampered_replayed_by_other_user_or_expired(self):
        self.assertEqual(self.save(preview_token=self.token()+'x').status_code, 400)
        self.assertEqual(self.save(preview_token=self.token(self.other_admin)).status_code, 403)
        with patch('django.core.signing.TimestampSigner.unsign', side_effect=signing.SignatureExpired('expired')):
            self.assertEqual(self.save().status_code, 400)

    def test_duplicate_does_not_make_new_crop_and_revision_resets_approval(self):
        self.save()
        sample = TrainingCorrection.objects.get()
        self.client.post(ROOT+f'{sample.pk}/review/', {'status':'approved','confirmed':True, 'revision':sample_revision(sample)}, format='json')
        self.assertTrue(self.save().data['duplicate'])
        sample.refresh_from_db()
        self.assertEqual(sample.status, 'approved')
        self.save(labels={'Dung':'empty', 'Sai':'filled'})
        sample.refresh_from_db()
        self.assertEqual((sample.status, sample.answer, sample.reviewed_by), ('pending','Sai',None))
        self.assertEqual(TrainingCorrection.objects.count(), 1)

    def test_all_correction_endpoints_require_superuser(self):
        self.client.force_authenticate(self.teacher)
        for method, path in [('get',ROOT),('get',ROOT+'export/'),('post',ROOT+'preview/'),
                             ('post',ROOT+'save/'),('post',ROOT+'1/review/')]:
            self.assertEqual(getattr(self.client,method)(path).status_code, 403)

    def test_private_crop_requires_owner_or_admin(self):
        self.save()
        sample = TrainingCorrection.objects.get()
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(sample.image.url).status_code,404)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(sample.image.url).status_code,(401,404))
        self.client.force_authenticate(self.admin)
        response = self.client.get(sample.image.url)
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        # Consume through TestClient's streaming wrapper, which disconnects
        # close_old_connections while closing the response inside TestCase's
        # enclosing transaction. Closing manually breaks PostgreSQL tests.
        self.assertEqual(b''.join(response.streaming_content), self.png)

    def test_export_excludes_unreviewed_and_includes_raw_32px_labels(self):
        self.save()
        output = io.BytesIO()
        self.assertEqual(write_dataset(output,TrainingCorrection.objects.all()),0)
        sample = TrainingCorrection.objects.get()
        self.assertEqual(self.client.post(ROOT+f'{sample.pk}/review/', {'status':'approved'}, format='json').status_code,400)
        self.client.post(ROOT+f'{sample.pk}/review/', {'status':'approved','confirmed':True, 'revision':sample_revision(sample)}, format='json')
        output = io.BytesIO()
        self.assertEqual(write_dataset(output,TrainingCorrection.objects.all()),1)
        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read('manifest.json'))['samples'][0]
            self.assertEqual(manifest['group_id'],'a'*64)
            self.assertNotIn('teacher',manifest)
            self.assertEqual(len(manifest['bubbles']),2)
            patch_image = cv2.imdecode(np.frombuffer(archive.read(manifest['bubbles'][0]['file']),np.uint8),0)
            self.assertEqual(patch_image.shape,(32,32))

    def test_labels_handle_decimal_negative_multimark_and_uncertainty(self):
        self.assertEqual(labelled_answer(2, {'Dung':'filled','Sai':'filled'}),'X')
        self.assertEqual(labelled_answer(2, {'Dung':'skip','Sai':'empty'}),'?')
        labels = {'sign':'filled','comma_2':'filled','digit_1_0':'filled','digit_3_2':'filled'}
        self.assertEqual(labelled_answer(3,labels),'-0.2')
        self.assertEqual(labelled_answer(3, {'digit_0_1':'filled','digit_0_2':'filled'}),'X')
        self.assertEqual(labelled_answer(3, {'digit_0_1':'filled','comma_3':'filled'}),'X')

    def test_preview_crops_only_requested_raw_region_all_parts(self):
        from grading.engine import hi
        # Whole-sheet synthetic fixture has no personal identifiers or overlays.
        image = np.full((1920,1400,3),245,np.uint8)
        path = 'grading/engine/templates/template_default.json'
        hi.load_template(path)
        for x,y in hi.ALL_BUBBLE_CENTERS:
            cv2.circle(image,(int(x),int(y)),hi.BUBBLE_RADIUS,(80,80,80),1)
        encoded = cv2.imencode('.jpg',image)[1].tobytes()
        corners = [[0,0],[1399,0],[1399,1919],[0,1919]]
        for part,q,sub,count in [(1,6,'',4),(2,6,'c',2),(3,1,'',45)]:
            data,png = question_preview(encoded,'40-08-06',part,q,sub,corners)
            self.assertEqual(len(data['cells']),count)
            self.assertLess(data['geometry']['width'], 350)
            crop = cv2.imdecode(np.frombuffer(png,np.uint8),0)
            self.assertEqual(crop.ndim,2)
            self.assertLess(crop.shape[0],500)

    def test_bad_images_template_traversal_and_corners_are_rejected(self):
        raw = cv2.imencode('.png',np.full((200,200),255,np.uint8))[1].tobytes()
        cases = [('not-photo','40-08-06',None), (raw,'../../secret',None),
                 (raw,'40-08-06',[[0,0],[10,0],[10,10],[0,10]]),
                 (raw,'40-08-06',[[0,0],[300,0],[300,300],[0,300]])]
        for raw,code,corners in cases:
            if isinstance(raw,str): raw = raw.encode()
            with self.assertRaises(ValueError):
                question_preview(raw,code,2,6,'c',corners)

    def test_preview_api_ignores_client_predicted_labels(self):
        with patch('api.training_views.question_preview',return_value=({k:v for k,v in self.data.items() if k!='image_base64'},self.png)):
            response = self.client.post(ROOT+'preview/', {'image':SimpleUploadedFile('source.jpg',self.png),
                'part':'2','question':'6','subquestion':'c','answer':'Sai'}, format='multipart')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('labels',response.data)
        self.assertEqual(response.data['detected'],'')

    def test_stale_review_cannot_approve_a_label_changed_by_another_request(self):
        self.save()
        sample = TrainingCorrection.objects.get()
        revision = sample_revision(sample)
        self.save(labels={'Dung':'empty','Sai':'filled'})
        response = self.client.post(ROOT+f'{sample.pk}/review/',
            {'status':'approved','confirmed':True,'revision':revision}, format='json')
        self.assertEqual(response.status_code,409)
        sample.refresh_from_db()
        self.assertEqual(sample.status,'pending')


class TrainingSheetTests(TrainingCorrectionTests):
    """Use isolated DB/media; never seed synthetic labels into production."""
    def batch(self, entries=None, approve=True, raw=None, **overrides):
        raw = self.png if raw is None else raw
        self.data['source_hash'] = hashlib.sha256(self.png).hexdigest()
        self.data.setdefault('needs_review', False)
        items = entries if entries is not None else [
            {'preview_token':self.token(), 'labels':self.labels, 'review_confirmed':False}]
        fields = {'items':json.dumps(items), 'confirmed':'true', 'approve':str(approve).lower(),
                  'image':SimpleUploadedFile('source.png',raw), **overrides}
        return self.client.post(ROOT+'sheet/save/',fields,format='multipart')

    def test_bulk_export_has_original_once_and_confirmed_bubble_labels(self):
        response = self.batch()
        self.assertEqual(response.status_code,200,response.data)
        sample = TrainingCorrection.objects.get()
        self.assertEqual(sample.status,'approved')
        self.assertEqual(sample.reviewed_by,self.admin)
        with sample.image.storage.open(sample.geometry['source_image']) as original:
            self.assertEqual(original.read(),self.png)
        out = io.BytesIO()
        self.assertEqual(write_dataset(out,TrainingCorrection.objects.all()),1)
        with zipfile.ZipFile(out) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['schema_version'],2)
            row = manifest['samples'][0]
            self.assertEqual(archive.read(row['source_file']),self.png)
            self.assertEqual(row['labels'],self.labels)
            self.assertNotIn('source_image',row['geometry'])
        again = self.batch()
        self.assertEqual(again.data['duplicates'],1)
        self.assertEqual(TrainingCorrection.objects.count(),1)

    def test_yellow_requires_manual_review_before_bulk_approval(self):
        self.data['source_hash'] = hashlib.sha256(self.png).hexdigest()
        self.data['needs_review'] = True
        self.assertEqual(self.batch().status_code,400)
        self.assertEqual(TrainingCorrection.objects.count(),0)
        entries = [{'preview_token':self.token(),'labels':self.labels,'review_confirmed':True}]
        self.assertEqual(self.batch(entries=entries).status_code,200)

    def test_bulk_all_validated_before_writes_and_rejects_cross_sheet(self):
        self.data['source_hash'] = hashlib.sha256(self.png).hexdigest()
        first = {'preview_token':self.token(),'labels':self.labels}
        self.data['question'] = 7
        second = {'preview_token':self.token(),'labels':{'Dung':'filled'}}
        self.assertEqual(self.batch(entries=[first,second]).status_code,400)
        self.assertEqual(TrainingCorrection.objects.count(),0)
        self.assertEqual(self.batch(entries=[first,first]).status_code,400)
        self.assertEqual(self.batch(confirmed='false').status_code,400)
        self.assertEqual(self.batch(raw=b'changed').status_code,400)
        self.assertEqual(TrainingCorrection.objects.count(),0)

    def test_bulk_permissions_and_signed_preview_security(self):
        self.data['source_hash'] = hashlib.sha256(self.png).hexdigest()
        for user in (self.teacher, None):
            self.client.force_authenticate(user)
            self.assertIn(self.batch().status_code,(401,403))
            self.assertIn(self.client.post(ROOT+'sheet/preview/',{}).status_code,(401,403))
        self.client.force_authenticate(self.admin)
        wrong = [{'preview_token':self.token(self.other_admin),'labels':self.labels}]
        self.assertEqual(self.batch(entries=wrong).status_code,403)
        tampered = [{'preview_token':self.token()+'x','labels':self.labels}]
        self.assertEqual(self.batch(entries=tampered).status_code,400)
        self.data['geometry']['aligned'] = False
        self.assertEqual(self.batch().status_code,400)

    def test_original_photo_access_is_private_and_revision_edit_resets_review(self):
        self.batch()
        sample = TrainingCorrection.objects.get()
        url = '/media/'+sample.geometry['source_image']
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_authenticate(self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(b''.join(response.streaming_content),self.png)
        path = ROOT+f'{sample.pk}/correct/'
        old_revision = sample_revision(sample)
        changed = {'revision':old_revision,'labels':{'Dung':'empty','Sai':'filled'},'confirmed':True}
        self.assertEqual(self.client.post(path,changed,format='json').status_code,200)
        sample.refresh_from_db()
        self.assertEqual((sample.answer,sample.status,sample.reviewed_by),('Sai','pending',None))
        self.assertEqual(self.client.post(path,changed,format='json').status_code,409)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(path,changed,format='json').status_code,403)

    def test_whole_sheet_crops_all_parts_using_one_photo_decode(self):
        from grading.grader import engine
        import grading.training_data as data_module
        engine.load_template('grading/engine/templates/template_default.json')
        image = np.full((1920,1400,3),245,np.uint8)
        for x,y in engine.ALL_BUBBLE_CENTERS:
            cv2.circle(image,(int(x),int(y)),engine.BUBBLE_RADIUS,(80,80,80),2)
        raw = cv2.imencode('.jpg',image)[1].tobytes()
        with patch('grading.training_data.decode_photo',wraps=data_module.decode_photo) as decode:
            crops = sheet_preview(raw,'40-08-06',[[0,0],[1399,0],[1399,1919],[0,1919]])
        self.assertEqual(decode.call_count,1)
        self.assertEqual(len(crops),78)
        self.assertEqual(sum(len(d['cells']) for d,_ in crops),494)
        for data,png in crops:
            self.assertEqual(set(data['candidate_labels']),{c['id'] for c in data['cells']})
            self.assertEqual(data['source_hash'],hashlib.sha256(raw).hexdigest())
            self.assertLess(cv2.imdecode(np.frombuffer(png,np.uint8),0).shape[0],500)

    def test_sheet_preview_flags_scan_mismatch_without_using_answer_key(self):
        self.data['detected'] = 'Dung'
        self.data['needs_review'] = False
        self.data['candidate_labels'] = self.labels
        with patch('api.training_views.sheet_preview',return_value=[(self.data,self.png)]):
            response = self.client.post(ROOT+'sheet/preview/',{
                'image':SimpleUploadedFile('source.png',self.png),
                'scan_answers':json.dumps({'part2':{'6':{'c':''}}}),
                'correct_answers':json.dumps({'part2':{'6':{'c':'Sai'}}}),
            },format='multipart')
        self.assertEqual(response.status_code,200)
        row = response.data['samples'][0]
        self.assertTrue(row['needs_review'])
        self.assertEqual(row['candidate_labels'],self.labels)

    def test_bulk_database_failure_rolls_back_labels_and_new_image_files(self):
        from api.training_views import persist_question
        self.data['source_hash'] = hashlib.sha256(self.png).hexdigest()
        first = {'preview_token':self.token(),'labels':self.labels}
        self.data['question'] = 7
        second = {'preview_token':self.token(),'labels':self.labels}
        calls = []
        def fail_second(*args,**kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('simulated database failure')
            return persist_question(*args,**kwargs)
        with patch('api.training_views.persist_question',side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.batch(entries=[first,second])
        self.assertEqual(TrainingCorrection.objects.count(),0)
        self.assertEqual(list(__import__('pathlib').Path(self.media.name).rglob('*.png')),[])
