import os
import subprocess
import sys
import tempfile
import time


def run_python(source, timeout=15):
    with tempfile.TemporaryDirectory(prefix="c2py_") as tmp:
        path = os.path.join(tmp, "program.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        start = time.perf_counter()
        try:
            proc = subprocess.run([sys.executable, "-I", path], capture_output=True, timeout=timeout, cwd=tmp, env=env)
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": "", "error": f"перевищено час виконання ({timeout} c)",
                    "ms": round((time.perf_counter() - start) * 1000, 1)}
        ms = round((time.perf_counter() - start) * 1000, 1)
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace").replace(path, "program.py").strip()
        if proc.returncode != 0:
            return {"ok": False, "output": out, "error": err or f"код завершення {proc.returncode}", "ms": ms}
        return {"ok": True, "output": out, "error": None, "ms": ms}
