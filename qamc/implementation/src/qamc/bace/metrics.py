"""Transparent score diagnostics; unknown labels never become negatives."""
import math
import random
import statistics
from collections import defaultdict,Counter


def score_distribution(rows):
    """Variation without truth labels is descriptive, never discrimination proof."""
    values=[r['score'] for r in rows if r.get('status')=='ASSESSED' and r.get('score') is not None]
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in values):
        raise ValueError('Invalid raw assessment score')
    return {'assessed_with_score':len(values),'not_assessed_with_score':len(rows)-len(values),
            'minimum':min(values) if values else None,'maximum':max(values) if values else None,
            'median':statistics.median(values) if values else None,
            'distinct_scores':len(set(values)),
            'frequency':[{'raw_score':v,'count':n} for v,n in sorted(Counter(values).items())],
            'variation_establishes_discrimination':False}


def binary_metrics(rows,bins=5):
    known=[r for r in rows if type(r.get('label')) is bool and r.get('score') is not None]
    if any(not math.isfinite(r['score']) or not 0<=r['score']<=1 for r in known):
        raise ValueError('Invalid bounded raw score')
    pos=[r['score'] for r in known if r['label']];neg=[r['score'] for r in known if not r['label']]
    auc=sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg)) if pos and neg else None
    # Aggregate tied thresholds, avoiding arbitrary optimistic tie ordering.
    by_score=defaultdict(list)
    for row in known:by_score[row['score']].append(row['label'])
    tp=fp=0;ap=0.
    for score in sorted(by_score,reverse=True):
        labels=by_score[score];added=sum(labels);tp+=added;fp+=len(labels)-added
        if pos:ap+=added/len(pos)*tp/(tp+fp)
    reliability=[];ece=0.
    for i in range(bins):
        group=[r for r in known if min(int(r['score']*bins),bins-1)==i]
        observed=sum(r['label'] for r in group)/len(group) if group else None
        predicted=sum(r['score'] for r in group)/len(group) if group else None
        if group:ece+=len(group)/len(known)*abs(observed-predicted)
        reliability.append({'lower':i/bins,'upper':(i+1)/bins,'n':len(group),'empirical_positive_fraction':observed,'mean_raw_score':predicted})
    return {'labeled':len(known),'unlabeled':len(rows)-len(known),'positives':len(pos),'negatives':len(neg),
            'roots':len({r['root'] for r in known}),'auroc':auc,'average_precision':ap if pos else None,
            'brier_raw_score_diagnostic':sum((r['score']-r['label'])**2 for r in known)/len(known) if known else None,
            'ece_raw_score_diagnostic':ece if known else None,'reliability':reliability,
            'raw_scores_are_calibrated_probabilities':False}


def root_auc_interval(rows,repeats=1000,seed=20261105):
    groups=defaultdict(list)
    for row in rows:
        if type(row.get('label')) is bool:groups[row['root']].append(row)
    if len(groups)<2:return {'interval':None,'reason':'insufficient_roots'}
    rng=random.Random(seed);keys=sorted(groups);values=[]
    for _ in range(repeats):
        draw=[r for k in rng.choices(keys,k=len(keys)) for r in groups[k]]
        value=binary_metrics(draw)['auroc']
        if value is not None:values.append(value)
    values.sort()
    if len(values)<repeats//2:return {'interval':None,'valid_bootstraps':len(values),'reason':'class_degeneracy'}
    return {'interval':[values[int(.025*(len(values)-1))],values[int(.975*(len(values)-1))]],
            'valid_bootstraps':len(values),'repeats':repeats,'root_count':len(keys),
            'interpretation':'exploratory clustered interval conditional on label validity'}
