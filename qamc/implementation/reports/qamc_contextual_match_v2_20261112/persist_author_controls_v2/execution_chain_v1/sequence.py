"""Wait for the verified external coordinator, then run each command once."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]
import qamc_contextual_match_v2_persist_authors as run
from qamc.common import sha
from qamc.transport_helpers import atomic_json

OUT = Path(__file__).resolve().parent
PRECEDING_PID = 23066
EXPECTED_COMMAND = 'external_continuation_v2/execution_chain_v2/sequence.py'
EXPECTED_PLAN = '4b2c97dadf4b92c8ce80a6f89963f9ecb0ba690f22d8dfc9e1f0daef3bb1cf41'


def preceding_live():
    result = subprocess.run(['ps', '-p', str(PRECEDING_PID), '-o', 'command='], capture_output=True, text=True)
    if result.returncode == 1 and not result.stdout.strip(): return False
    if result.returncode or EXPECTED_COMMAND not in result.stdout:
        raise RuntimeError('Preceding PID observation failed or PID was reused')
    return True


def main():
    plan = run.read(run.OUT/'PLAN.json')
    if sha(plan) != EXPECTED_PLAN: raise RuntimeError('Unexpected frozen author plan')
    run.check(plan, False)
    acceptance = run.read(run.OUT/'ACCEPTANCE.json')
    if (acceptance['phase_plan_sha256'] != EXPECTED_PLAN or acceptance['tests_passed'] != 4
            or acceptance['new_model_calls'] != 0 or not acceptance['wire_parity_with_original_preflight']):
        raise RuntimeError('Offline acceptance absent')
    commands = [[sys.executable, 'scripts/qamc_contextual_match_v2_persist_authors.py', action]
                for action in ('run', 'report')]
    run.frozen(OUT/'PLAN.json', {'phase_plan_sha256': EXPECTED_PLAN,
        'acceptance_sha256': sha(acceptance), 'preceding_pid': PRECEDING_PID,
        'expected_preceding_command': EXPECTED_COMMAND, 'commands': commands,
        'code_byte_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'automatic_restarts': 0, 'goal_complete': False})
    state = {'pid': os.getpid(), 'completed_steps': [], 'automatic_restarts': 0, 'goal_complete': False}
    try:
        while preceding_live():
            run.check(plan, False)
            state.update(phase='VERIFIED_WAIT_FOR_EXTERNAL', verified_live_pid=PRECEDING_PID,
                         updated_unix=time.time())
            atomic_json(OUT/'RUN_STATE.json', state)
            time.sleep(15)
        prior = run.read(run.external.OUT/'execution_chain_v2/RUN_STATE.json')
        if prior.get('phase') != 'EXTERNAL_TERMINAL_NEEDS_ANALYSIS' or prior.get('completed_steps') != [0, 1]:
            raise RuntimeError('External generation and strict report did not both complete')
        run.require_predecessors()
        for step, command in enumerate(commands):
            run.check(plan, True)
            with (OUT/f'{step:02d}.log').open('x') as log:
                child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                state.update(phase='CHILD_RUNNING', child_pid=child.pid, active_step=step, updated_unix=time.time())
                atomic_json(OUT/'RUN_STATE.json', state)
                code = child.wait()
            if code: raise RuntimeError('Author child failed; no automatic restart')
            state['completed_steps'].append(step)
        state.update(phase='AUTHOR_CONTROLS_TERMINAL_NEEDS_ANALYSIS', child_pid=None,
                     active_step=None, updated_unix=time.time())
        atomic_json(OUT/'RUN_STATE.json', state)
    except Exception as error:
        state.update(phase='STOPPED_NO_AUTOMATIC_RESTART', error_type=type(error).__name__,
                     child_pid=None, updated_unix=time.time())
        atomic_json(OUT/'RUN_STATE.json', state)
        raise


if __name__ == '__main__':
    main()
