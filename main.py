import argparse
import os
import sys

from cc.compiler import compile_source
from cc.parser import grammar_info


def print_diagnostics(diags):
    for d in diags:
        kind = "попередження" if d["severity"] == "warning" else "помилка"
        col = f":{d['col']}" if d["col"] else ""
        print(f"  [{d['stage']}] рядок {d['line']}{col}: {kind}: {d['message']}")


def run_file(path, args):
    with open(path, encoding="utf-8") as f:
        code = f.read()
    result = compile_source(code, run=not args.no_run)

    if args.tokens:
        print("=== Токени ===")
        for t in result["tokens"]:
            print(f"  {t['line']:>3}:{t['col']:<3} {t['type']:<12} {t['value']!r}")
        print()

    if result["ast_text"]:
        print("=== AST ===")
        print(result["ast_text"])
        print()

    if result["diagnostics"]:
        print("=== Діагностика ===")
        print_diagnostics(result["diagnostics"])
        print()

    if not result["ok"]:
        print("Компіляцію зупинено через помилки.")
        return 1

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    py_path = os.path.join(out_dir, base + ".py")
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(result["python"])

    if args.python:
        print("=== Python ===")
        print(result["python"])

    run = result["run"]
    if run is not None:
        print("=== Виконання (інтерпретатор AST) ===")
        print(run["output"], end="" if run["output"].endswith("\n") or not run["output"] else "\n")
        if run["error"]:
            print(f"[помилка виконання, рядок {run['line']}] {run['error']}")
        else:
            print(f"[main повернула {run['exit_code']}]")
    if args.run_python:
        from cc.python_runner import run_python
        jr = run_python(result["python"])
        print(f"\n=== Виконання Python ({jr['ms']} мс) ===")
        print(jr["output"], end="")
        if jr["error"]:
            print(f"[помилка Python] {jr['error']}")
        elif run is not None:
            print("[вивід Python збігається з інтерпретатором]" if jr["output"] == run["output"] else "[вивід Python ВІДРІЗНЯЄТЬСЯ]")
    print(f"\nPython збережено у {os.path.relpath(py_path)}  (запуск: python3 {os.path.relpath(py_path)})")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Компілятор підмножини C: PLY (LALR) → AST → інтерпретатор / Python")
    ap.add_argument("file", nargs="?", help="вхідний файл .c")
    ap.add_argument("--tokens", action="store_true", help="показати потік токенів")
    ap.add_argument("--python", action="store_true", help="надрукувати згенерований Python-код")
    ap.add_argument("--run-python", action="store_true", help="запустити згенерований Python-код")
    ap.add_argument("--no-run", action="store_true", help="не виконувати програму")
    ap.add_argument("--grammar", action="store_true", help="інформація про LALR-автомат")
    ap.add_argument("--web", action="store_true", help="запустити веб-інтерфейс")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if args.grammar:
        info = grammar_info()
        print(f"Продукцій граматики: {info['productions']}")
        print(f"Станів LALR(1)-автомата: {info['states']}")
        conflicts = [w for w in info["warnings"] if "conflict" in w]
        print(f"Нерозв'язаних конфліктів: {len(conflicts)}")
        for w in conflicts:
            print("  " + w)
        print(f"Повний опис станів і таблиць: {info['parser_out']}")
        return 0
    if args.web:
        from server import serve
        serve(args.port)
        return 0
    if not args.file:
        ap.print_help()
        return 1
    return run_file(args.file, args)


if __name__ == "__main__":
    sys.exit(main())
