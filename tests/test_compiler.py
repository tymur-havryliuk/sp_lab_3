import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cc.compiler import compile_source  # noqa: E402
from cc.python_runner import run_python  # noqa: E402
from cc.parser import grammar_info  # noqa: E402


def run(code):
    r = compile_source(code)
    assert r["ok"], r["diagnostics"]
    assert r["run"]["error"] is None, r["run"]["error"]
    return r["run"]["output"]


class GrammarTest(unittest.TestCase):
    def test_no_unresolved_conflicts(self):
        self.assertFalse([w for w in grammar_info()["warnings"] if "conflict" in w])


class SemanticsTest(unittest.TestCase):
    def test_precedence_and_associativity(self):
        self.assertEqual(run('int main(){ printf("%d %d %d", 2+3*4, 10-4-3, 2*3+4); return 0; }'), "14 3 10")

    def test_assignment_is_right_associative(self):
        self.assertEqual(run('int main(){ int a, b; a = b = 4; printf("%d %d", a, b); return 0; }'), "4 4")

    def test_integer_division_truncates_toward_zero(self):
        self.assertEqual(run('int main(){ printf("%d %d %d", 7/2, -7/2, -7%2); return 0; }'), "3 -3 -1")

    def test_dangling_else_binds_to_nearest_if(self):
        code = 'int main(){ if (1) if (0) printf("A"); else printf("B"); return 0; }'
        self.assertEqual(run(code), "B")

    def test_arrays_by_reference(self):
        code = "void set(int a[]){ a[0] = 42; } int main(){ int x[2]; set(x); printf(\"%d\", x[0]); return 0; }"
        self.assertEqual(run(code), "42")

    def test_compound_bitwise_assignments(self):
        code = 'int main(){ int a = 5; a |= 8; a &= 12; a ^= 1; a <<= 2; a >>= 1; printf("%d", a); return 0; }'
        self.assertEqual(run(code), "26")

    def test_sizeof(self):
        code = ('int main(){ int a[10]; double d; char s[] = "abc";'
                ' printf("%d %d %d %d %d", sizeof(int), sizeof(double), sizeof a, sizeof(d), sizeof(s)); return 0; }')
        self.assertEqual(run(code), "4 8 40 8 4")

    def test_bitwise_assign_on_float_is_error(self):
        r = compile_source("int main(){ float f = 1.5; f <<= 1; return 0; }")
        self.assertFalse(r["ok"])

    def test_semantic_errors_detected(self):
        r = compile_source(open(os.path.join(ROOT, "examples", "90_semantic_errors.c"), encoding="utf-8").read())
        errors = [d for d in r["diagnostics"] if d["severity"] == "error"]
        self.assertFalse(r["ok"])
        self.assertGreaterEqual(len(errors), 10)

    def test_syntax_error_recovery_reports_several_errors(self):
        r = compile_source(open(os.path.join(ROOT, "examples", "91_syntax_errors.c"), encoding="utf-8").read())
        self.assertGreaterEqual(len([d for d in r["diagnostics"] if d["stage"] == "parser"]), 3)

    def test_runtime_errors(self):
        r = compile_source("int main(){ int z = 0; return 1 / z; }")
        self.assertIn("ділення на нуль", r["run"]["error"])


class PythonBackendTest(unittest.TestCase):
    def test_examples_match_interpreter(self):
        for path in sorted(glob.glob(os.path.join(ROOT, "examples", "0*.c"))):
            with self.subTest(example=os.path.basename(path)):
                r = compile_source(open(path, encoding="utf-8").read())
                pr = run_python(r["python"])
                self.assertIsNone(pr["error"], pr["error"])
                self.assertEqual(pr["output"], r["run"]["output"])

    def test_side_effects_and_scopes(self):
        code = ("int g = 0; void bump(){ g += 2; }"
                "int main(){ int i = 1; { int i = 2; printf(\"%d \", i); } int a[3] = {5, 6, 7}; int k = 0;"
                " int x = a[k++] + ++k; int y = (x = 10) + 1; int n = 3; while (n--) bump();"
                " for (int j = 0; j < 5; j++) { if (j == 2) continue; g++; }"
                " printf(\"%d %d %d %d %d %d\", i, x, y, k, g, -7 % 3); return 0; }")
        r = compile_source(code)
        pr = run_python(r["python"])
        self.assertIsNone(pr["error"], pr["error"])
        self.assertEqual(pr["output"], r["run"]["output"])


if __name__ == "__main__":
    unittest.main()
