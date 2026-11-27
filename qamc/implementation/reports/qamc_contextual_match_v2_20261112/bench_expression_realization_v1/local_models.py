"""Run frozen text simplification and two-way entailment on local CPU."""
from pathlib import Path

SIMPLIFIER = ("kcsheang/ts-t5-base-4tokens", "b4ef76fa8443e08b6ef3abb1f80ca860e51b14b7")
ENTAILMENT = ("MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c")
CONTROL = "simplify: C_0.95 L_0.75 WR_0.75 DTD_0.75  "
THRESHOLD = 0.75


def snapshot(spec):
    repo, revision = spec
    return Path.home() / ".cache/huggingface/hub" / ("models--" + repo.replace("/", "--")) / "snapshots" / revision


class FrozenModels:
    def __init__(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, T5ForConditionalGeneration

        torch.set_num_threads(4)
        self.torch = torch
        a, b = snapshot(SIMPLIFIER), snapshot(ENTAILMENT)
        self.simple_tokenizer = AutoTokenizer.from_pretrained(a, local_files_only=True)
        self.simple = T5ForConditionalGeneration.from_pretrained(a, local_files_only=True, use_safetensors=True).eval()
        self.entailment_tokenizer = AutoTokenizer.from_pretrained(b, local_files_only=True)
        self.entailment = AutoModelForSequenceClassification.from_pretrained(
            b, local_files_only=True, use_safetensors=True).eval()
        self.entailment_index, = [k for k, v in self.entailment.config.id2label.items()
                                  if v.casefold() == "entailment"]
        self.simplified = 0
        self.entailment_pairs = 0

    def simplify(self, sentences):
        if not sentences:
            return []
        data = self.simple_tokenizer([CONTROL + s for s in sentences], padding=True, return_tensors="pt")
        if data["input_ids"].shape[1] > 256:
            raise ValueError("Specialist input exceeds its frozen model size")
        with self.torch.inference_mode():
            out = self.simple.generate(**data, num_beams=8, do_sample=False, max_length=128, early_stopping=True)
        self.simplified += len(sentences)
        return self.simple_tokenizer.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)

    def mutual(self, pairs):
        if not pairs:
            return []
        left, right = zip(*pairs, strict=True)
        data = self.entailment_tokenizer(list(left) + list(right), list(right) + list(left),
                                         padding=True, return_tensors="pt")
        if data["input_ids"].shape[1] > 512:
            raise ValueError("Entailment input exceeds its frozen model size")
        with self.torch.inference_mode():
            out = self.entailment(**data).logits.softmax(dim=-1)[:, self.entailment_index].tolist()
        self.entailment_pairs += 2 * len(pairs)
        return [min(a, b) for a, b in zip(out[:len(pairs)], out[len(pairs):], strict=True)]
