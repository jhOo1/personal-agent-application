"""Use the published MCQ formatter/parser without importing API launch code."""
import ast
import random
import re
from .audit import ROOT, digest

OFFICIAL = ROOT/'vendor/PrefEval/utils/utils_mcq.py'


def official_functions():
    from bs4 import BeautifulSoup
    wanted={'get_mcq_question_format','format_options','extract_choice'}
    tree=ast.parse(OFFICIAL.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    if {n.name for n in nodes} != wanted:
        raise ValueError('Official MCQ interface changed')
    namespace={'BeautifulSoup':BeautifulSoup,'re':re}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(OFFICIAL),'exec'),namespace)
    return namespace


def prepare(row, *, seed, acknowledgement):
    """Input comes from official mcq_options; evaluation-only data stays separate.

    The acknowledgement must be generated once and shared before execution.
    Its provenance and cost belong to preparation, never fabricated or omitted.
    """
    if not isinstance(acknowledgement,str) or not acknowledgement.strip():
        raise ValueError('Explicit preference acknowledgement required')
    options=row['classification_task_options']
    if not isinstance(options,list) or len(options)!=4 or len(set(options))!=4:
        raise ValueError('Four distinct official options required')
    shuffled=random.Random(seed).sample(options,len(options))
    f=official_functions()
    public={'query':row['question']+f['get_mcq_question_format'](shuffled),
            'history':[{'role':'user','content':row['preference']},
                       {'role':'assistant','content':acknowledgement}],
            'inter_turns':0,'track':'explicit_classification',
            'official_formatter_sha256':digest(OFFICIAL)}
    # First original option is the official key; never serialize it in public.
    private={'correct_choice':'ABCD'[shuffled.index(options[0])],
             'parser_sha256':digest(OFFICIAL)}
    return public,private


def score(answer,reference):
    choice=official_functions()['extract_choice'](answer)
    return {'metric':'PrefEval_official_choice_parser_accuracy',
            'choice':choice,'accuracy':int(choice==reference['correct_choice']),
            'parser_sha256':digest(OFFICIAL)}
