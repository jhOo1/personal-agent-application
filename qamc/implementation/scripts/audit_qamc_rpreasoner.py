#!/usr/bin/env python3
"""Inspect upstream literal prompt wiring without importing API/config modules."""
import ast,json,string,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'literature/qamc_pa_v1/RPEval'
OUT=ROOT/'reports/qamc_fused_gate'

def extract(path):
    values={};templates={}
    for node in ast.parse(path.read_text()).body:
        if not isinstance(node,ast.Assign):continue
        for target in node.targets:
            if not isinstance(target,ast.Name):continue
            try:values[target.id]=ast.literal_eval(node.value)
            except (ValueError,TypeError):pass
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='PromptTemplate':
                kws={x.arg:x.value for x in node.value.keywords}
                t=kws.get('template');text=values.get(t.id) if isinstance(t,ast.Name) else ast.literal_eval(t) if isinstance(t,ast.Constant) else None
                if isinstance(text,str):templates[target.id]={'template':text,'placeholders':sorted({n for _,n,_,_ in string.Formatter().parse(text) if n}),'declared_input_variables':ast.literal_eval(kws['input_variables'])}
    return templates

def main():
    path=UP/'prompts_715.py';templates=extract(path)
    mle=templates['MLE_estimation_prompt_mmcq_template_v0'];ipe=templates['CPE_estimation_prompt_mmcq_template_v0'];gen=templates['RPA_multi_generation_template']
    result={'status':'UPSTREAM_ENTRYPOINT_NOT_FAITHFUL_WITHOUT_REPAIR','new_model_calls':0,'root_prompt_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mle_and_ipe_text_identical':mle['template']==ipe['template'],'generation_receives_predicted_intent':'intent' in gen['placeholders'],'templates':{k:templates[k] for k in ('MLE_estimation_prompt_mmcq_template_v0','CPE_estimation_prompt_mmcq_template_v0','RPA_multi_generation_template')},'source_callsite':'generation_task/eval_multi.py:301 passes intent=pred_policy but root template omits it','repair_policy':'Do not silently patch and call it unchanged author reproduction; recover primary-paper prompts, document changes and validate generated answer actually receives predicted policy.'}
    (OUT/'RPREASONER_WIRING_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert result['mle_and_ipe_text_identical'] and not result['generation_receives_predicted_intent']
    print(json.dumps({k:v for k,v in result.items() if k!='templates'}))
if __name__=='__main__':main()
