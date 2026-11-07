from . import ast_nodes as A

PY_RESERVED = {
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif",
    "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while",
    "with", "yield", "match", "case", "print", "range", "int", "float", "len", "list", "str",
    "chr", "ord", "abs", "math", "re", "sys", "min", "max", "sum", "type", "id", "input", "object",
    "printf", "puts", "putchar",
}

FLOATING = {"float", "double"}
COMPARISON = {"<", ">", "<=", ">=", "==", "!="}

# пріоритети операторів Python (більше — сильніше зв'язує)
P = {
    "if": 1, "or": 2, "and": 3, "not": 4, "cmp": 5, "|": 6, "^": 7, "&": 8,
    "<<": 9, ">>": 9, "+": 10, "-": 10, "*": 11, "/": 11, "%": 11, "unary": 12, "atom": 15,
}

BUILTIN_PY = {
    "printf": "printf", "puts": "puts", "putchar": "putchar",
    "abs": "abs", "fabs": "abs", "sqrt": "math.sqrt", "pow": "math.pow",
}

HEADER = """import math
import re
import sys

sys.setrecursionlimit(100000)
"""

RUNTIME = r'''def _mod(a, b):
    return a - b * int(a / b)


def _cstr(text, size):
    codes = [ord(ch) for ch in text]
    return codes + [0] * (size - len(codes))


def _str(value):
    if isinstance(value, list):
        chars = []
        for code in value:
            if code == 0:
                break
            chars.append(chr(code))
        return "".join(chars)
    return str(value)


def _set(arr, i, value):
    arr[i] = value
    return value


def _preinc(arr, i, delta):
    arr[i] += delta
    return arr[i]


def _postinc(arr, i, delta):
    old = arr[i]
    arr[i] = old + delta
    return old


_FORMAT = re.compile(r"%([-+ 0#]*)(\d+|\*)?(?:\.(\d+|\*))?(?:hh|h|ll|l|L|z)?([diouxXeEfFgGcs%])")


def printf(fmt, *args):
    args = list(args)

    def take():
        return args.pop(0) if args else 0

    def repl(m):
        flags, width, prec, conv = m.groups()
        if conv == "%":
            return "%"
        if width == "*":
            width = str(take())
        if prec == "*":
            prec = str(take())
        value = take()
        if conv in "diu":
            value = int(value) & 0xFFFFFFFF if conv == "u" else int(value)
            conv = "d"
        elif conv in "xXo":
            value = int(value) & 0xFFFFFFFF
        elif conv in "eEfFgG":
            value = float(value)
        elif conv == "c":
            value = chr(int(value))
        elif conv == "s":
            value = _str(value)
        spec = "%" + flags + (width or "") + ("." + prec if prec is not None else "") + conv
        return spec % value

    text = _FORMAT.sub(repl, _str(fmt))
    sys.stdout.write(text)
    return len(text)


def puts(s):
    sys.stdout.write(_str(s) + "\n")
    return 0


def putchar(c):
    sys.stdout.write(chr(c))
    return c
'''


def py_string(s):
    out = ['"']
    for ch in s:
        if ch == "\0":
            out.append("\\x00")
        elif ch in '"\\':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 32:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def py_char(code):
    if code == 0:
        return "0"
    ch = chr(code)
    special = {"\n": "\\n", "\t": "\\t", "\r": "\\r", "'": "\\'", "\\": "\\\\"}
    if ch in special:
        return f"ord('{special[ch]}')"
    if 32 <= code <= 126:
        return f"ord('{ch}')"
    return str(code)


def zero_of(ctype):
    return "0.0" if ctype in FLOATING else "0"


def safe_name(name):
    return name + "_" if name in PY_RESERVED or name.startswith("_") else name


def assigned_vars(node):
    """Імена змінних, яким щось присвоюється всередині вузла (для перевірки range-циклу)."""
    names = set()

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
            return
        if not isinstance(n, A.Node):
            return
        if isinstance(n, (A.Assign, A.IncDec)) and isinstance(n.target, A.Var):
            names.add(n.target.name)
        if isinstance(n, A.VarDecl):
            names.add(n.name)
        for _, child in n.children():
            walk(child)

    walk(node)
    return names


def contains(node, kinds):
    if isinstance(node, list):
        return any(contains(x, kinds) for x in node)
    if not isinstance(node, A.Node):
        return False
    if isinstance(node, kinds):
        return True
    return any(contains(child, kinds) for _, child in node.children())


def var_names(node):
    names = set()

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
        elif isinstance(n, A.Node):
            if isinstance(n, A.Var):
                names.add(n.name)
            for _, child in n.children():
                walk(child)

    walk(node)
    return names


class PythonGenerator:
    def __init__(self):
        self.lines = []
        self.indent = 0
        self.signatures = {}
        self.globals = {}
        self.scopes = []
        self.loops = []           # для continue: що треба виконати перед переходом на наступну ітерацію
        self.func_ret = None
        self.assigned_globals = set()

    def emit(self, text):
        self.lines.append("    " * self.indent + text)

    # ---------- імена та області видимості ----------

    # у Python одна область видимості на функцію, тому змінна вкладеного блоку
    # з тим самим ім'ям, що й зовнішня (або глобальна), перейменовується: i -> i_2
    def declare_local(self, c_name):
        active = {j for scope in self.scopes for j in scope.values()} | set(self.globals.values())
        base = safe_name(c_name)
        name, n = base, 2
        while name in active:
            name = f"{base}_{n}"
            n += 1
        self.scopes[-1][c_name] = name
        return name

    def resolve(self, c_name, assigning=False):
        for scope in reversed(self.scopes):
            if c_name in scope:
                return scope[c_name]
        name = self.globals.get(c_name, safe_name(c_name))
        if assigning and self.scopes:
            self.assigned_globals.add(name)
        return name

    # ---------- програма ----------

    def generate(self, program):
        has_main = False
        for d in program.decls:
            if isinstance(d, (A.FuncDef, A.FuncDecl)):
                self.signatures[d.name] = d.params
                self.globals[d.name] = safe_name(d.name)
                has_main = has_main or (isinstance(d, A.FuncDef) and d.name == "main")
            elif isinstance(d, A.VarDecl):
                self.globals[d.name] = safe_name(d.name)

        self.lines = HEADER.split("\n") + [""]
        for d in program.decls:
            if isinstance(d, A.FuncDef):
                self.gen_function(d)
                self.lines += ["", ""]
        self.lines += RUNTIME.rstrip("\n").split("\n") + ["", ""]
        globals_ = [d for d in program.decls if isinstance(d, A.VarDecl)]
        for d in globals_:
            self.emit(f"{self.globals[d.name]} = {self.var_init(d)}")
        if globals_:
            self.lines += ["", ""]
        if has_main:
            self.emit('if __name__ == "__main__":')
            self.emit("    main()")
        return "\n".join(self.lines).rstrip("\n") + "\n"

    def gen_function(self, f):
        self.func_ret = f.ret_type
        self.scopes = [{}]
        self.assigned_globals = set()
        params = [self.declare_local(p.name) for p in f.params]
        self.emit(f"def {self.globals[f.name]}({', '.join(params)}):")
        self.indent += 1
        start = len(self.lines)
        for item in f.body.items:
            self.gen_stmt(item)
        if len(self.lines) == start:
            self.emit("pass")
        if self.assigned_globals:
            self.lines.insert(start, "    " * self.indent + "global " + ", ".join(sorted(self.assigned_globals)))
        self.indent -= 1
        self.scopes = []

    def var_init(self, d):
        if d.is_array:
            if isinstance(d.init, A.InitList):
                items = [self.coerce(i, d.type) for i in d.init.items]
                rest = d.size - len(items)
                return f"[{', '.join(items)}]" + (f" + [{zero_of(d.type)}] * {rest}" if rest > 0 else "")
            if isinstance(d.init, A.Const):
                return f"_cstr({py_string(d.init.value)}, {d.size})"
            return f"[{zero_of(d.type)}] * {d.size}"
        return self.coerce(d.init, d.type) if d.init is not None else zero_of(d.type)

    # ---------- оператори ----------

    def gen_block(self, stmt):
        self.indent += 1
        self.scopes.append({})
        start = len(self.lines)
        for item in (stmt.items if isinstance(stmt, A.Block) else [stmt]):
            self.gen_stmt(item)
        if len(self.lines) == start:
            self.emit("pass")
        self.scopes.pop()
        self.indent -= 1

    def gen_stmt(self, s):
        if isinstance(s, A.VarDecl):
            init = self.var_init(s)
            self.emit(f"{self.declare_local(s.name)} = {init}")
        elif isinstance(s, A.Block):
            self.scopes.append({})
            for item in s.items:
                self.gen_stmt(item)
            self.scopes.pop()
        elif isinstance(s, A.ExprStmt):
            if s.expr is not None:
                self.emit(self.statement_expr(s.expr))
        elif isinstance(s, A.If):
            self.emit(f"if {self.cond(s.cond)}:")
            self.gen_block(s.then)
            node = s.else_
            while isinstance(node, A.If):
                self.emit(f"elif {self.cond(node.cond)}:")
                self.gen_block(node.then)
                node = node.else_
            if node is not None:
                self.emit("else:")
                self.gen_block(node)
        elif isinstance(s, A.While):
            self.emit(f"while {self.cond(s.cond)}:")
            self.loops.append([])
            self.gen_block(s.body)
            self.loops.pop()
        elif isinstance(s, A.DoWhile):
            # у Python немає do-while: тіло, потім перевірка умови
            check = f"if not {self.cond_at(s.cond, P['cmp'] + 1)}:"
            self.emit("while True:")
            self.loops.append([check, "    break"])
            self.gen_block(s.body)
            self.loops.pop()
            self.indent += 1
            self.emit(check)
            self.emit("    break")
            self.indent -= 1
        elif isinstance(s, A.For):
            self.gen_for(s)
        elif isinstance(s, A.Return):
            self.emit("return" if s.value is None else f"return {self.coerce(s.value, self.func_ret)}")
        elif isinstance(s, A.Break):
            self.emit("break")
        elif isinstance(s, A.Continue):
            for line in self.loops[-1]:
                self.emit(line)
            self.emit("continue")
        else:
            raise TypeError(type(s).__name__)

    def gen_for(self, s):
        self.scopes.append({})
        rng = self.as_range(s)
        if rng is not None:
            var, args = rng
            self.emit(f"for {self.declare_local(var)} in range({', '.join(args)}):")
            self.loops.append([])
            self.gen_block(s.body)
            self.loops.pop()
            self.scopes.pop()
            return
        if isinstance(s.init, list):
            for d in s.init:
                self.gen_stmt(d)
        elif s.init is not None and s.init.expr is not None:
            self.emit(self.statement_expr(s.init.expr))
        cond = self.cond(s.cond) if s.cond is not None else "True"
        step = [self.statement_expr(s.step)] if s.step is not None else []
        self.emit(f"while {cond}:")
        self.loops.append(step)                     # continue має виконати крок циклу
        self.gen_block(s.body)
        self.loops.pop()
        self.indent += 1
        for line in step:
            self.emit(line)
        self.indent -= 1
        self.scopes.pop()

    # for (int i = a; i < b; i++) -> for i in range(a, b), якщо це безпечно
    def as_range(self, s):
        if not (isinstance(s.init, list) and len(s.init) == 1):
            return None
        d = s.init[0]
        if d.is_array or d.type not in ("int", "char") or d.init is None:
            return None
        var = d.name
        c, step = s.cond, s.step
        if not (isinstance(c, A.BinOp) and c.op in ("<", "<=", ">", ">=") and isinstance(c.left, A.Var)
                and c.left.name == var):
            return None
        bound = c.right
        if contains(bound, (A.Assign, A.IncDec, A.Call, A.Index)) or var in var_names(bound):
            return None
        if bound.ctype in FLOATING or contains(d.init, (A.Assign, A.IncDec)):
            return None
        changed = assigned_vars(s.body)
        if var in changed or var_names(bound) & changed:
            return None
        if contains(s.body, A.Call) and var_names(bound) & set(self.globals):
            return None
        if isinstance(step, A.IncDec) and isinstance(step.target, A.Var) and step.target.name == var:
            delta = 1 if step.op == "++" else -1
        elif (isinstance(step, A.Assign) and step.op in ("+=", "-=") and isinstance(step.target, A.Var)
              and step.target.name == var and isinstance(step.value, A.Const) and step.value.type == "int"
              and step.value.value > 0):
            delta = step.value.value if step.op == "+=" else -step.value.value
        else:
            return None
        if (delta > 0) != (c.op in ("<", "<=")):
            return None
        start = self.value(d.init)
        if isinstance(bound, A.Const) and bound.type == "int":
            end = str(bound.value + (1 if c.op == "<=" else -1 if c.op == ">=" else 0))
        else:
            b = self.value_at(bound, P["+"] + 1)
            end = f"{b} + 1" if c.op == "<=" else f"{b} - 1" if c.op == ">=" else self.value(bound)
        args = [start, end] if delta == 1 else [start, end, str(delta)]
        return var, args

    def statement_expr(self, e):
        if isinstance(e, A.Cast) and e.type == "void":
            e = e.expr
        if isinstance(e, A.IncDec):
            return f"{self.target(e.target, True)} {'+' if e.op == '++' else '-'}= 1"
        if isinstance(e, A.Assign):
            target = self.target(e.target, True)
            if e.op == "=":
                return f"{target} = {self.coerce(e.value, e.target.ctype)}"
            return f"{target} = {self.compound_value(e)}" if self.needs_rewrite(e) else \
                f"{target} {e.op} {self.value(e.value)}"
        return self.value(e)

    def needs_rewrite(self, e):
        op = e.op[:-1]
        int_target = e.target.ctype in ("int", "char")
        return op in ("/", "%") and int_target or (int_target and e.value.ctype in FLOATING)

    def compound_value(self, e):
        """Значення складеного присвоєння x op= v з урахуванням правил C."""
        op = e.op[:-1]
        current = self.target(e.target)
        int_target = e.target.ctype in ("int", "char")
        if op == "%" and int_target:
            return f"_mod({current}, {self.value(e.value)})"
        if op == "/" and int_target:
            return f"int({current} / {self.value_at(e.value, P['/'] + 1)})"
        expr = f"{current} {op} {self.value_at(e.value, P[op] + 1)}"
        return f"int({expr})" if int_target and e.value.ctype in FLOATING else expr

    # ---------- вирази ----------

    def target(self, t, assigning=False):
        if isinstance(t, A.Var):
            return self.resolve(t.name, assigning)
        return f"{self.resolve(t.name)}[{self.value(t.index)}]"

    def wrap(self, code, prec, min_prec):
        return f"({code})" if prec < min_prec else code

    def value_p(self, e):
        code, prec, kind = self.gen(e)
        if kind == "logic":                          # 2 && 3 у Python дає 3, а в C — 1
            return f"(1 if {code} else 0)", P["atom"]
        return code, prec

    def value(self, e):
        return self.value_p(e)[0]

    def value_at(self, e, min_prec):
        code, prec = self.value_p(e)
        return self.wrap(code, prec, min_prec)

    def cond_p(self, e):
        code, prec, _ = self.gen(e)
        return code, prec

    def cond(self, e):
        return self.cond_p(e)[0]

    def cond_at(self, e, min_prec):
        code, prec = self.cond_p(e)
        return self.wrap(code, prec, min_prec)

    def coerce(self, e, target):
        if target in ("int", "char") and e.ctype in FLOATING:
            return f"int({self.value(e)})"
        if target in FLOATING and e.ctype not in FLOATING:
            if isinstance(e, A.Const) and e.type == "int":
                return f"{float(e.value)!r}"
            return f"float({self.value(e)})"
        return self.value(e)

    def gen(self, e):
        if isinstance(e, A.Const):
            if e.type == "char":
                return py_char(e.value), P["atom"], "num"
            if e.type == "string":
                return py_string(e.value), P["atom"], "num"
            if e.type in FLOATING:
                return repr(float(e.value)), P["atom"], "num"
            return str(e.value), P["atom"], "num"
        if isinstance(e, A.Var):
            return self.resolve(e.name), P["atom"], "num"
        if isinstance(e, A.Index):
            return f"{self.resolve(e.name)}[{self.value(e.index)}]", P["atom"], "num"
        if isinstance(e, A.SizeOf):
            return str(e.size_value), P["atom"], "num"
        if isinstance(e, A.Call):
            if e.name in BUILTIN_PY:
                args = [self.value(a) for a in e.args]
            else:
                params = self.signatures.get(e.name, [])
                args = [self.value(a) if p.is_array else self.coerce(a, p.type) for a, p in zip(e.args, params)]
            name = BUILTIN_PY.get(e.name) or self.resolve(e.name)
            return f"{name}({', '.join(args)})", P["atom"], "num"
        if isinstance(e, A.UnaryOp):
            if e.op == "!":
                return f"not {self.cond_at(e.operand, P['not'])}", P["not"], "num"
            inner = self.value_at(e.operand, P["unary"])
            if inner.startswith(e.op):
                inner = f"({inner})"
            return f"{e.op}{inner}", P["unary"], "num"
        if isinstance(e, A.IncDec):
            # у Python немає ++: для змінної — оператор моржа :=, для елемента масиву — допоміжна функція
            delta = 1 if e.op == "++" else -1
            if isinstance(e.target, A.Var):
                name = self.resolve(e.target.name, True)
                sign = "+" if delta > 0 else "-"
                if e.prefix:
                    return f"({name} := {name} {sign} 1)", P["atom"], "num"
                back = "-" if delta > 0 else "+"
                return f"(({name} := {name} {sign} 1) {back} 1)", P["atom"], "num"
            arr, idx = self.resolve(e.target.name), self.value(e.target.index)
            func = "_preinc" if e.prefix else "_postinc"
            return f"{func}({arr}, {idx}, {delta})", P["atom"], "num"
        if isinstance(e, A.Assign):
            value = self.coerce(e.value, e.target.ctype) if e.op == "=" else self.compound_value(e)
            if isinstance(e.target, A.Var):
                return f"({self.resolve(e.target.name, True)} := {value})", P["atom"], "num"
            return f"_set({self.resolve(e.target.name)}, {self.value(e.target.index)}, {value})", P["atom"], "num"
        if isinstance(e, A.Cast):
            if e.type == "void":
                return self.value_p(e.expr) + ("num",)
            if e.type in ("int", "char") and e.expr.ctype in FLOATING:
                return f"int({self.value(e.expr)})", P["atom"], "num"
            if e.type in FLOATING and e.expr.ctype not in FLOATING:
                return f"float({self.value(e.expr)})", P["atom"], "num"
            return self.value_p(e.expr) + ("num",)
        if isinstance(e, A.Ternary):
            c = self.cond_at(e.cond, P["or"])
            return (f"{self.value_at(e.then, P['or'])} if {c} else {self.value_at(e.else_, P['if'])}",
                    P["if"], "num")
        if isinstance(e, A.BinOp):
            op = e.op
            if op in ("&&", "||"):
                py, prec = ("and", P["and"]) if op == "&&" else ("or", P["or"])
                return f"{self.cond_at(e.left, prec)} {py} {self.cond_at(e.right, prec + 1)}", prec, "logic"
            if op in COMPARISON:
                # у Python порівняння слабші за побітові операції та ланцюжаться (a < b < c),
                # тому вкладене порівняння завжди беремо в дужки
                return f"{self.value_at(e.left, P['|'])} {op} {self.value_at(e.right, P['|'])}", P["cmp"], "num"
            if op == "/" and e.ctype == "int":
                return f"int({self.value(e.left)} / {self.value_at(e.right, P['/'] + 1)})", P["atom"], "num"
            if op == "%" and e.ctype == "int":
                return f"_mod({self.value(e.left)}, {self.value(e.right)})", P["atom"], "num"
            prec = P[op]
            return f"{self.value_at(e.left, prec)} {op} {self.value_at(e.right, prec + 1)}", prec, "num"
        raise TypeError(type(e).__name__)


def generate_python(program):
    return PythonGenerator().generate(program)
