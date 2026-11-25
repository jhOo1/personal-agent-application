"""Reusable finite-stage ledger dispatch; no service activity at import time."""
import os
from pathlib import Path
import time

from qamc.common import sha, canonical, token_estimate
from qamc.transport_helpers import atomic_json
from .review_pacing_v2 import SharedGate, PacedControl
from .cache_inventory import inventory
from .cache import service_filtered
from proposals.qamc_protocol_alignment.transport import NativeSampler, SamplingTransportError
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import Runtime, read, frozen
import proposals.qamc_sentence_units.runtime as runtime_module
from proposals.qamc_pa_transfer.cache_acceleration import prefilter_exact


class BudgetGate(SharedGate):
    def __init__(self, *args, limit, **kwargs):
        self.limit = limit
        super().__init__(*args, **kwargs)

    def reserve_if_ready(self, stopped=lambda: False):
        with self.lock:
            if self.reservations >= self.limit:
                raise SamplingTransportError("frozen_component_budget_exhausted_no_dispatch")
            return super().reserve_if_ready(stopped)


class ComponentDispatcher:
    def __init__(self, root, out, run, plan, check, job_builder, block):
        self.root, self.out, self.run = map(Path, (root, out, run))
        self.plan, self.check, self.job_builder, self.block = plan, check, job_builder, block
        self.allowed = set(plan["allowed_unit_keys"])
        self.gate = BudgetGate(self.run/"PACING.json", spacing=3.2, cooldown=301,
                               limit=plan["maximum_new_physical_requests"])
        runtime_module.exact = prefilter_exact
        self.rt = {key: Runtime(self.root, self.out/key, self.run/key, check,
                               sampler_class=self.sampler) for key in plan["protocols"]}

    def sampler(self, *args, **kwargs):
        sampler = NativeSampler(*args, **kwargs)
        sampler.control = PacedControl(sampler.control, self.gate)
        return sampler

    def observed(self, job):
        value = self.rt[self.block(job["unit"]["stage"])].output(job["unit"])
        if value and value["request_sha256"] != sha(job["request"]):
            raise ValueError("Recorded output request differs")
        return value

    def dispatch(self, name, jobs):
        self.check(self.plan)
        for key, runtime in self.rt.items():
            selected = []
            for job in jobs:
                if self.block(job["unit"]["stage"]) != key:
                    continue
                u = job["unit"]
                if sampling_key(u) not in self.allowed or self.job_builder(
                        self.plan, u["root_id"], u["method"], u["stage"], job["request"]) != job:
                    raise ValueError("Unallocated job or changed protocol")
                messages = canonical(job["request"]["messages"])
                if token_estimate(messages) > 32768 or len(messages.encode()) > 2_000_000:
                    frozen(self.run/key/"outputs"/(sampling_key(u)+".json"), {
                        "unit":u, "request_sha256":sha(job["request"]), "status":"CAPACITY_BLOCKED",
                        "origin":"OFFLINE_CAPACITY_GUARD", "new_physical_request":False})
                else:
                    selected.append(job)
            if not selected:
                continue
            path = self.out/key/(name+"_CACHE.json")
            wanted = {sha(j["request"]) for j in selected}
            index = read(path) if path.exists() else service_filtered(
                self.root, inventory(self.root, wanted), wanted, self.plan["service_reference_sha256"])
            if index["schema_skips"]:
                raise ValueError("Unrecognized cache schema")
            frozen(path, index)
            atomic_json(self.out/"RUN_STATE.json", {"phase":"RUNNING", "pid":os.getpid(),
                "stage":name, "model_block":key, "updated_unix":time.time(), "goal_complete":False})
            runtime.stage({**self.plan, "protocol":self.plan["protocols"][key]},
                          "component", name, selected, index)
