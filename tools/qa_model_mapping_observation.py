"""Classify raw read-only mapping observations against native joined phases.

A stale cls_state2 may remain while native map loading tears down dictionaries.
Such samples are retained, but are not evidence of an active joined renderer.
"""
from datetime import datetime, timedelta
import re


def analyze(samples, native_log):
    if not samples: raise ValueError('No native mapping observations')
    day = datetime.fromtimestamp(samples[0]['observed_time']).date()
    previous = None
    start = None
    intervals = []
    for line in native_log.splitlines():
        match = re.match(r'(\d\d:\d\d:\d\d\.\d\d\d) (.*)', line)
        if not match: continue
        clock = datetime.strptime(match[1],'%H:%M:%S.%f').time()
        point = datetime.combine(day,clock)
        if previous and point < previous - timedelta(hours=12):
            day += timedelta(days=1)
            point = datetime.combine(day,clock)
        previous = point
        message = match[2]
        if 'joiner: conectado al host como slot ' in message:
            if start is not None: intervals.append((start,point.timestamp()))
            start = point.timestamp()
        elif any(event in message for event in ('joiner: el host carga ', 'joiner: mapa local ',
                   'native world attachment failed', 'CRASH ', 'cmd: quit', 'cmd: coopleave')):
            if start is not None:
                intervals.append((start,point.timestamp()))
                start = None
    if start is not None: intervals.append((start,float('inf')))
    active=[]
    excluded=[]
    for sample in samples:
        if sample['cls_state'] != 2: continue
        if any(begin <= sample['observed_time'] < end for begin,end in intervals): active.append(sample)
        elif sample.get('model_mapping_mismatches'): excluded.append(sample)
    return {'joined_intervals':intervals,'joined_samples':len(active),
            'max_joined_model_mismatches':max((x.get('model_mapping_mismatches',0) for x in active),default=0),
            'max_all_cls2_model_mismatches':max((x.get('model_mapping_mismatches',0) for x in samples if x['cls_state']==2),default=0),
            'unjoined_transition_outliers':[{'observed_time':x['observed_time'],'server_time':x['server_time'],
                                          'model_mapping_mismatches':x['model_mapping_mismatches']} for x in excluded]}
