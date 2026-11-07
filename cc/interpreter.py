import sys
import threading

from . import ast_nodes as A
from .builtins import BUILTINS, call_builtin
from .errors import CRuntimeError

MAX_STEPS = 5_000_000


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class Env:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def define(self, name, ctype, value):
        self.vars[name] = [ctype, value]

    def cell(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise CRuntimeError(f"невідома змінна '{name}'")


# у C ціле ділення відкидає дробову частину до нуля, а // у Python округлює вниз
def c_div(a, b, line):
    if b == 0:
        raise CRuntimeError("ділення на нуль", line)
    if isinstance(a, float) or isinstance(b, float):
        return a / b
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def c_mod(a, b, line):
    if b == 0:
        raise CRuntimeError("ділення на нуль в операції %", line)
    return a - b * c_div(a, b, line)


def convert(value, ctype):
    if ctype in ("int", "char"):
        return int(value)
    if ctype in ("float", "double"):
        return float(value)
    return value


ARITH = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "<=": lambda a, b: int(a <= b),
    ">=": lambda a, b: int(a >= b),
    "==": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "&": lambda a, b: a & b,
    "|": lambda a, b: a | b,
    "^": lambda a, b: a ^ b,
    "<<": lambda a, b: a << b,
    ">>": lambda a, b: a >> b,
}


class Interpreter:
    def __init__(self, program):
        self.program = program
        self.globals = Env()
        self.functions = {}
        self.out = []
        self.steps = 0

    def tick(self, node):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise CRuntimeError("перевищено ліміт кроків виконання (можливо, нескінченний цикл)", node.lineno)


    def run(self):
        for decl in self.program.decls:
            if isinstance(decl, A.FuncDef):
                self.functions[decl.name] = decl
            elif isinstance(decl, A.VarDecl):
                self.exec_VarDecl(decl, self.globals)
        if "main" not in self.functions:
            raise CRuntimeError("немає функції main()")
        return self.call_function(self.functions["main"], [], self.program)

    def call_function(self, func, args, call_node):
        env = Env(self.globals)
        for param, value in zip(func.params, args):
            env.define(param.name, param.type, value if param.is_array else convert(value, param.type))
        try:
            self.exec_list(func.body.items, env)
        except ReturnSignal as r:
            return convert(r.value, func.ret_type) if r.value is not None else None
        return 0 if func.ret_type != "void" else None


    def execute(self, node, env):
        self.tick(node)
        getattr(self, "exec_" + type(node).__name__)(node, env)

    def exec_list(self, items, env):
        for item in items:
            self.execute(item, env)

    def exec_VarDecl(self, node, env):
        if node.is_array:
            zero = 0.0 if node.type in ("float", "double") else 0
            values = [zero] * node.size
            if isinstance(node.init, A.InitList):
                for i, item in enumerate(node.init.items):
                    values[i] = convert(self.eval(item, env), node.type)
            elif isinstance(node.init, A.Const):
                for i, ch in enumerate(node.init.value):
                    values[i] = ord(ch)
            env.define(node.name, node.type + "[]", values)
        else:
            value = self.eval(node.init, env) if node.init is not None else 0
            env.define(node.name, node.type, convert(value, node.type))

    def exec_Block(self, node, env):
        self.exec_list(node.items, Env(env))

    def exec_ExprStmt(self, node, env):
        if node.expr is not None:
            self.eval(node.expr, env)

    def exec_If(self, node, env):
        if self.eval(node.cond, env):
            self.execute(node.then, env)
        elif node.else_ is not None:
            self.execute(node.else_, env)

    def run_body(self, body, env):
        try:
            self.execute(body, env)
        except BreakSignal:
            return False
        except ContinueSignal:
            pass
        return True

    def exec_While(self, node, env):
        while self.eval(node.cond, env):
            self.tick(node)
            if not self.run_body(node.body, env):
                break

    def exec_DoWhile(self, node, env):
        while True:
            self.tick(node)
            if not self.run_body(node.body, env) or not self.eval(node.cond, env):
                break

    def exec_For(self, node, env):
        loop_env = Env(env)
        if isinstance(node.init, list):
            self.exec_list(node.init, loop_env)
        elif node.init is not None:
            self.execute(node.init, loop_env)
        while node.cond is None or self.eval(node.cond, loop_env):
            self.tick(node)
            if not self.run_body(node.body, loop_env):
                break
            if node.step is not None:
                self.eval(node.step, loop_env)

    def exec_Return(self, node, env):
        raise ReturnSignal(self.eval(node.value, env) if node.value is not None else None)

    def exec_Break(self, node, env):
        raise BreakSignal()

    def exec_Continue(self, node, env):
        raise ContinueSignal()


    def eval(self, node, env):
        return getattr(self, "eval_" + type(node).__name__)(node, env)

    def eval_Const(self, node, env):
        return node.value

    def eval_Var(self, node, env):
        return env.cell(node.name)[1]

    def _array_slot(self, node, env):
        ctype, array = env.cell(node.name)
        index = self.eval(node.index, env)
        if not 0 <= index < len(array):
            raise CRuntimeError(f"вихід за межі масиву '{node.name}': індекс {index}, розмір {len(array)}", node.lineno)
        return array, index, ctype[:-2]

    def eval_Index(self, node, env):
        array, index, _ = self._array_slot(node, env)
        return array[index]

    def store(self, target, value, env):
        if isinstance(target, A.Var):
            cell = env.cell(target.name)
            cell[1] = convert(value, cell[0])
            return cell[1]
        array, index, ctype = self._array_slot(target, env)
        array[index] = convert(value, ctype)
        return array[index]

    def eval_BinOp(self, node, env):
        op = node.op
        if op == "&&":
            return int(bool(self.eval(node.left, env)) and bool(self.eval(node.right, env)))
        if op == "||":
            return int(bool(self.eval(node.left, env)) or bool(self.eval(node.right, env)))
        a, b = self.eval(node.left, env), self.eval(node.right, env)
        if op == "/":
            return c_div(a, b, node.lineno)
        if op == "%":
            return c_mod(a, b, node.lineno)
        result = ARITH[op](a, b)
        return float(result) if node.ctype in ("float", "double") else result

    def eval_UnaryOp(self, node, env):
        v = self.eval(node.operand, env)
        if node.op == "-":
            return -v
        if node.op == "+":
            return v
        if node.op == "!":
            return int(not v)
        return ~v

    def eval_IncDec(self, node, env):
        old = self.eval(node.target, env)
        new = self.store(node.target, old + (1 if node.op == "++" else -1), env)
        return new if node.prefix else old

    def eval_Assign(self, node, env):
        value = self.eval(node.value, env)
        if node.op != "=":
            current = self.eval(node.target, env)
            op = node.op[:-1]
            if op == "/":
                value = c_div(current, value, node.lineno)
            elif op == "%":
                value = c_mod(current, value, node.lineno)
            else:
                value = ARITH[op](current, value)
        return self.store(node.target, value, env)

    def eval_Ternary(self, node, env):
        branch = node.then if self.eval(node.cond, env) else node.else_
        return convert(self.eval(branch, env), node.ctype)

    def eval_SizeOf(self, node, env):
        return node.size_value

    def eval_Cast(self, node, env):
        value = self.eval(node.expr, env)
        return convert(value, node.type) if node.type != "void" else None

    def eval_Call(self, node, env):
        self.tick(node)
        args = [self.eval(a, env) for a in node.args]
        if node.name in self.functions:
            return self.call_function(self.functions[node.name], args, node)
        if node.name in BUILTINS:
            return call_builtin(node.name, args, self.out)
        raise CRuntimeError(f"функцію '{node.name}' оголошено, але не визначено", node.lineno)


def run_program(program, timeout=10.0):
    interp = Interpreter(program)
    result = {"output": "", "exit_code": None, "error": None, "line": 0}

    def target():
        try:
            result["exit_code"] = interp.run()
        except CRuntimeError as e:
            result["error"], result["line"] = str(e), e.line
        except RecursionError:
            result["error"] = "переповнення стеку викликів (занадто глибока рекурсія)"
        except Exception as e:  # noqa: BLE001 — показуємо користувачу будь-яку внутрішню помилку
            result["error"] = f"внутрішня помилка інтерпретатора: {type(e).__name__}: {e}"

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(250_000)
    threading.stack_size(512 * 1024 * 1024)
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    threading.stack_size(0)
    thread.join(timeout)
    sys.setrecursionlimit(old_limit)
    if thread.is_alive():
        interp.steps = MAX_STEPS + 1
        result["error"] = f"перевищено час виконання ({timeout:.0f} c)"
    result["output"] = "".join(interp.out)
    return result
