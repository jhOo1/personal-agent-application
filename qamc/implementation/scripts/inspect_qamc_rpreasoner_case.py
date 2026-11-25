"""Compact complete-source reading, omitting only verified duplicate text."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT)]
import run_qamc_rpreasoner_paper as r


def main():
    wanted = sys.argv[1:]
    plans = r.read(r.OUT / 'PAIRED_REVIEW_PLAN.json')['rows']
    queue = {v['uid']: v for v in r.read(r.OUT / 'REVIEW_QUEUE.json')['rows']}
    calls, imports = r.ledger()
    for plan in plans:
        if plan['uid'] not in wanted:
            continue
        c = r.read(ROOT / queue[plan['uid']]['packet'])
        public, ref = c['public_input'], c['evaluation_only_reference']
        sources = {v['memory_id']: v['text'] for v in public['memories']}
        duplicate = ref.get('implicit_persona')
        if duplicate is not None:
            assert (duplicate if isinstance(duplicate, list) else [duplicate]) == list(sources.values())
        print('\nCASE', plan['uid'])
        print('PUBLIC', json.dumps(public, ensure_ascii=False))
        print('REFERENCE', json.dumps({k: v for k, v in ref.items() if k != 'implicit_persona'}, ensure_ascii=False))
        print('CONTRASTS', json.dumps(c['contrasts'], ensure_ascii=False))
        seen_answers = {}
        for arm, info in plan['methods'].items():
            if arm not in plan['needs_read']:
                prior = info['prior_reviews'][0]
                print('EXACT_REUSED', arm, prior['observations'], prior.get('conditional_ai_bounds'))
                continue
            out = c['candidate'] if arm == 'CANDIDATE' else c['controls'][arm]
            print('METHOD', arm)
            if out.get('aggregation'):
                print('RANKS', [(v['memory_id'], v['mle_order'], v['ipe_order'], v['policy']) for v in out['aggregation']])
            else:
                print('SELECTION', json.dumps(out.get('selection'), ensure_ascii=False))
            view = out['view']
            rendered = []
            for v in view['source_evidence']:
                same = v['text'] == sources[v['memory_id']]
                rendered.append({**{k: value for k, value in v.items() if k != 'text'},
                                 'text': 'VERIFIED_COMPLETE_ORIGINAL_ABOVE' if same else v['text']})
            print('VIEW', json.dumps({**{k: v for k, v in view.items() if k != 'source_evidence'},
                                      'source_evidence': rendered}, ensure_ascii=False))
            answer_hash = r.sha(out['answer'])
            if answer_hash in seen_answers:
                print('FULL_ANSWER_EXACTLY_IDENTICAL_TO', seen_answers[answer_hash])
            else:
                print('FULL_ANSWER', out['answer'])
                seen_answers[answer_hash] = arm
            score = out.get('score')
            if arm == 'CANDIDATE' and score is None:
                atom = r.available_atomic(out, c['case'], calls, imports)
                if atom:
                    score = {'atomic': atom, 'raw_visible_Judge_response': r.read(Path(atom['origin']))['answer']}
            print('SCORE', json.dumps(score, ensure_ascii=False))


if __name__ == '__main__':
    main()
