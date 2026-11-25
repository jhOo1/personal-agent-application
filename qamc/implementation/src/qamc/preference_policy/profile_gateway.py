"""Shared revision adapter: compact source wire format, keep one real Gateway."""
from .profile_input import wire
from qamc.b6_evidence import query_body


class ProfileGateway:
    def __init__(self,base):self.base=base
    def __getattr__(self,name):return getattr(self.base,name)
    def complete(self,key,system,payload,max_tokens=4096):return self.base.complete(key,system,wire(payload),max_tokens)
    def object(self,key,prompt,payload,validator=None,max_tokens=4096):
        def check(obj):
            if validator:validator(obj)
            # Task anchors cannot be answer options or the MCQ formatting request.
            root=payload.get('original_input',payload)if isinstance(payload,dict)else{}
            query=root.get('query','')if isinstance(root,dict)else''
            body=query.split('\n\nChoose the best option')[0]
            def visit(x):
                if isinstance(x,dict):
                    for k,v in x.items():
                        if k=='query_anchor'and query and (not isinstance(v,str)or len(v)>240 or v not in body):raise ValueError('query_anchor must be a short original-request span, not an option or output-format instruction')
                        visit(v)
                elif isinstance(x,list):
                    for v in x:visit(v)
            visit(obj)
        generation=not key.startswith(('score/','source_diagnostic/','external_score/'))
        supplement='\nInput revision: profile_navigation is frozen Writer navigation, not an extra vote or a source of new goals. Use original raw units to check it. Query anchors must quote a short phrase (<=240 characters) from the original request, not answer options or the option-letter output instruction. Do not split any output-format-only instruction into a separate task scope. Q0 is the current request, never an additional historical preference. Units use short identifiers; copy exact identifiers.\n'
        return self.base.object(key,prompt+supplement if generation else prompt,wire(payload),check if generation else validator,max_tokens)
