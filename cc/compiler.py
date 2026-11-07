import time

from .ast_export import fill_spans, to_json, to_text
from .codegen_python import generate_python
from .interpreter import run_program
from .lexer import tokenize
from .parser import parse
from .semantic import analyze


def compile_source(code, run=True):
    result = {
        "ok": False,
        "tokens": [],
        "diagnostics": [],
        "ast": None,
        "ast_text": "",
        "python": "",
        "run": None,
        "timings": {},
    }
    timings = result["timings"]

    def timed(stage, func, *args):
        start = time.perf_counter()
        value = func(*args)
        timings[stage] = round((time.perf_counter() - start) * 1000, 2)
        return value

    tokens, _ = timed("lexer", tokenize, code)
    result["tokens"] = tokens

    ast, diagnostics = timed("parser", parse, code)
    diagnostics.sort(key=lambda d: (d.line, d.col))
    if ast is not None:
        fill_spans(ast)
    if ast is None or any(d.severity == "error" for d in diagnostics):
        result["diagnostics"] = [d.to_dict() for d in diagnostics]
        if ast is not None:
            result["ast"] = to_json(ast)
            result["ast_text"] = to_text(ast)
        return result

    diagnostics += timed("semantic", analyze, ast)
    result["diagnostics"] = [d.to_dict() for d in diagnostics]
    result["ast"] = to_json(ast)
    result["ast_text"] = to_text(ast)
    if any(d.severity == "error" for d in diagnostics):
        return result

    result["ok"] = True
    result["python"] = timed("codegen", generate_python, ast)
    if run:
        result["run"] = timed("interpreter", run_program, ast)
    return result
