"""Execute the authorized smoke gate then every remaining development case once."""
import argparse
import subprocess
import sys

from .common import ROOT, dump
from .gate import smoke_gate
from .report import report


def main(version):
    run_dir = ROOT / "runs" / version
    run_dir.mkdir(parents=True, exist_ok=True)
    for phase in ("smoke", "development"):
        path = run_dir / (phase + ".log")
        with path.open("a") as stream:
            child = subprocess.Popen([sys.executable, "-u", "-m", "qamc.experiment", phase,
                                      "--version", version, "--workers", "10"], stdout=stream, stderr=subprocess.STDOUT, cwd=ROOT)
            dump(run_dir / "supervisor_state.json", {"phase": phase, "child_pid": child.pid, "version": version,
                                                     "status": "running", "log": str(path)})
            print(f"started {phase} pid={child.pid} log={path}", flush=True)
            code = child.wait()
        report(version)
        if code:
            dump(run_dir / "supervisor_state.json", {"phase": phase, "child_pid": child.pid, "version": version,
                                                     "status": "failed", "exit_code": code})
            raise SystemExit(code)
        if phase == "smoke" and not smoke_gate(version)["passed"]:
            dump(run_dir / "supervisor_state.json", {"phase": phase, "version": version, "status": "engineering_gate_failed"})
            raise SystemExit(2)
    dump(run_dir / "supervisor_state.json", {"phase": "development", "version": version, "status": "terminal"})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="v0_1")
    main(p.parse_args().version)
