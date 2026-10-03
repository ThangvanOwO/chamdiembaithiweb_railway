"""Compare the deployed Live reader with/without reviewed CNN on source photos.

Local or VPS only. Output contains private student photographs. No database
writes, credit deductions or model training. Validation photos are not new tests.
"""
import argparse
from collections import defaultdict
import contextlib
import io
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
import cv2
from grading.training_data import _prepare_photo, labelled_answer
from grading.engine import hi as engine


def mismatches(result, samples):
    errors=[]
    for sample in samples:
        expected=labelled_answer(sample['part'],sample['labels'])
        actual=result[f'part{sample["part"]}'][sample['question']]
        if sample['part']==2:
            actual=actual[sample['subquestion']]
        if actual!=expected:
            errors.append(dict(part=sample['part'],question=sample['question'],
                subquestion=sample['subquestion'],expected=expected,actual=actual))
    return errors


def run(args):
    dataset=Path(args.dataset).resolve()
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    by_source=defaultdict(list)
    manifest=json.loads((dataset/'manifest.json').read_text(encoding='utf-8'))
    for sample in manifest['samples']:
        if sample.get('source_file'):
            by_source[sample['source_file']].append(sample)
    logging.getLogger('grading.engine.hi').setLevel(logging.ERROR)
    report=[]
    for index,(source,samples) in enumerate(sorted(by_source.items()),1):
        warp_start=time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            gray,e,method,_=_prepare_photo((dataset/source).read_bytes(),'40-08-06',None)
        warp_seconds=time.perf_counter()-warp_start
        key={'part1':{},'part2':{},'part3':{}}
        for sample in samples:
            answer=labelled_answer(sample['part'],sample['labels'])
            part=key[f'part{sample["part"]}']
            if sample['part']==2:
                part.setdefault(sample['question'],{})[sample['subquestion']]=answer
            else:
                part[sample['question']]=answer
        sheet=dict(sheet=index,source=source,warp_method=method,warp_seconds=warp_seconds,
                   regions=len(samples),split=samples[0]['split'])
        for enabled in (False,True):
            mode='candidate' if enabled else 'baseline'
            path=output/f'phieu_{index:02d}_{mode}.png'
            cv2.imwrite(str(path),gray)
            times=[]
            for _ in range(args.repeats):
                log=io.StringIO()
                start=time.perf_counter()
                with patch.dict(os.environ,{'LIVE_REVIEWED_CNN':'1' if enabled else '0'}), \
                     contextlib.redirect_stdout(log),patch('shutil.copy2'):
                    result=e.process_sheet(str(path),pre_warped=True,fast_mode=True,live_bubble_mode=True,
                        live_validation=True,live_cpu_fast=True,correct_answers=key)
                times.append(time.perf_counter()-start)
            errors=mismatches(result,samples)
            sheet[mode]=dict(matched=len(samples)-len(errors),errors=errors,
                median_grade_seconds=statistics.median(times),grade_seconds=times,
                cnn_status=result['cnn_status'],result_image=str(path.with_name(path.stem+'_result.jpg')),
                answers={part:result[part] for part in ('part1','part2','part3')},
                model_log=[line for line in log.getvalue().splitlines() if '[Reviewed CNN]' in line])
        report.append(sheet)
        print(json.dumps({k:v for k,v in sheet.items() if k not in ('baseline','candidate')}
            | {mode:{k:sheet[mode][k] for k in ('matched','median_grade_seconds','cnn_status','model_log')}
                for mode in ('baseline','candidate')},ensure_ascii=False),flush=True)
    summary=dict(dataset=str(dataset),repeats=args.repeats,photos=len(report),
        total_regions=sum(s['regions'] for s in report),
        baseline_matching_regions=sum(s['baseline']['matched'] for s in report),
        candidate_matching_regions=sum(s['candidate']['matched'] for s in report),sheets=report,
        limitation='Existing training/validation source photos, not new independent test photos. '
            'Auto warp + Live reading/scoring/rendering; excludes network and camera time.')
    (output/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='sheets'},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats<1:
        parser.error('--repeats must be positive')
    run(args)
