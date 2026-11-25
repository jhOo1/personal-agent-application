"""Leakage-safe external input and native-score adapters, no API client setup.

Callers must supply frozen retrieval/profile preparation and an accepted final
policy. These functions do not silently turn full histories into Top-24 evidence.
"""
import re
from html import unescape
from qamc.common import sha


def implicit_messages(conversation, kind):
    if kind=='choice':
        return [{'role':'user' if k in {'query','user_selection'} else 'assistant','content':v}
                for k,v in conversation.items()]
    if kind=='persona':
        return [{'role':r,'content':turn[r]}for turn in conversation.values() for r in ['user','assistant']]
    raise ValueError('unknown implicit preference type')


def prefeval_input(row, form, kind, intervening, inter_turns, explicit_ack=None):
    """Only the explicit track is allowed to reveal the preference field."""
    if inter_turns not in {10,100}:
        raise ValueError('unfrozen length condition')
    filler=[m for turn in intervening for m in turn['conversation']]
    filler=filler[:2*inter_turns]
    if len(filler)!=2*inter_turns or filler[-1]['role']!='assistant':
        raise ValueError('official intervening prefix incomplete')
    if form=='explicit':
        if not isinstance(explicit_ack,str) or not explicit_ack.strip():
            raise ValueError('official explicit preference acknowledgement must be generated once and shared')
        hist=[{'role':'user','content':row['preference']},{'role':'assistant','content':explicit_ack}]
    elif form=='implicit':
        hist=implicit_messages(row['conversation'],kind)
    else:
        raise ValueError('unknown preference form')
    hist+=filler
    return {'query':row['question']+' (Please respond within 300 words.)',
            'history':[{'id':f'h{i:04d}',**m}for i,m in enumerate(hist)],'variant_group':sha(row['question']),
            'inter_turns':inter_turns,'form':form,'kind':kind}


def tag(text,name):
    m=re.search('<'+name+r'>(.*?)</'+name+'>',text,re.S|re.I)
    if m is None:raise ValueError('missing official judge tag: '+name)
    return unescape(re.sub('<[^>]*>','',m.group(1))).strip()


def prefeval_score(row, answer, gateway, key, prompt_dir):
    """Author error-type prompts and final logic, Qwen Judge substitution explicit."""
    system="You are a helpful assistant in evaluating an AI assistant's reponse. You should be fair and strict and follow the user's instruction"
    names={'acknow':'check_acknowledge.txt','violate':'check_violation.txt','hallucinate':'check_hallucination.txt','helpful':'check_helpful.txt'}
    out={}
    for metric,name in names.items():
        text=(prompt_dir/name).read_text()
        # Preserve author substitutions and ordering; never inject method names.
        text=text.replace('{end_generation}',answer).replace('{question}',row['question'])
        if metric!='acknow':text=text.replace('{preference}',row['preference'])
        if metric=='hallucinate':text=text.replace('{assistant_restatement}',out['acknow']['extract_pref'])
        raw=gateway.complete(key+'/'+metric,system,text,2048)
        val=tag(raw,'answer').lower()
        if val not in {'yes','no'}:raise ValueError('nonbinary preference judge answer')
        out[metric]={'answer':val,'raw':raw}
        if metric=='acknow':out[metric]['extract_pref']=tag(raw,'preference')
    ack=out['acknow']['answer']=='yes';hall=ack and out['hallucinate']['answer']=='yes'
    violation=out['violate']['answer']=='yes';unhelp=out['helpful']['answer']=='no'
    inconsistent=ack and not hall and violation and not unhelp
    hallucinated_violation=ack and hall and violation and not unhelp
    unaware=not ack and violation and not unhelp
    return {'metric':'PrefEval_native_error_logic_Qwen_Judge_variant','preference_adherence_accuracy':int(not any([inconsistent,hallucinated_violation,unaware,unhelp])),
            'error_types':out,'unhelpful':unhelp,'inconsistent':inconsistent,'hallucinated_violation':hallucinated_violation,'unaware_violation':unaware}


def op_numeric(text):
    # Match the author's first-number parser; do not coerce failed API calls to zero.
    m=re.search(r'(?<![\d.])-?(?:\d+(?:\.\d+)?|\.\d+)(?![\d.])',text or '')
    if not m:raise ValueError('missing OP native score')
    return max(0.,min(1.,float(m.group(0))))


def grouped_diversity(answers,embedding_function):
    if len(answers)<2 or any(not isinstance(a,str)or not a for a in answers):
        raise ValueError('complete repetition group required; failure is not zero score')
    import numpy as np
    a=np.asarray(embedding_function(answers),dtype=float)
    if a.ndim!=2 or a.shape[0]!=len(answers)or not np.isfinite(a).all():raise ValueError('invalid embedding response')
    norm=np.linalg.norm(a,axis=1,keepdims=True)
    if (norm==0).any():raise ValueError('zero embedding')
    a=a/norm;sim=a@a.T;upper=sim[np.triu_indices(len(answers),k=1)]
    return {'overall_diversity_score':max(0.,min(1.,1-float(upper.mean()))),'mean_cosine_similarity':float(upper.mean()),'answer_count':len(answers)}
