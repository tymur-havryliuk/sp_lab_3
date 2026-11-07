from . import ast_nodes as A
from .builtins import BUILTINS, count_format_args
from .errors import Diagnostic

NUMERIC = {"int", "float", "double", "char"}
INTEGER = {"int", "char"}
FLOATING = {"float", "double"}
SIZES = {"char": 1, "int": 4, "float": 4, "double": 8, "void": 1}
POINTER_SIZE = 8
INTEGER_ONLY_ASSIGN = {"%=", "&=", "|=", "^=", "<<=", ">>="}


def arith_type(a, b):
    if "double" in (a, b):
        return "double"
    if "float" in (a, b):
        return "float"
    return "int"
COMPARISON_OPS = {"<", ">", "<=", ">=", "==", "!="}
LOGICAL_OPS = {"&&", "||"}
INTEGER_ONLY_OPS = {"%", "&", "|", "^", "<<", ">>"}


def is_array(t):
    return t is not None and t.endswith("[]")


def elem_type(t):
    return t[:-2]


class Symbol:
    def __init__(self, name, type_, kind, lineno, params=None, defined=False):
        self.name = name
        self.type = type_
        self.kind = kind
        self.lineno = lineno
        self.params = params
        self.defined = defined
        self.array_size = None


class Scope:
    def __init__(self, parent=None):
        self.symbols = {}
        self.parent = parent

    def lookup(self, name):
        scope = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None


class Analyzer:
    def __init__(self):
        self.diagnostics = []
        self.globals = Scope()
        self.scope = self.globals
        self.current_func = None
        self.loop_depth = 0


    def error(self, node, msg):
        self.diagnostics.append(Diagnostic("semantic", msg, node.lineno))

    def warn(self, node, msg):
        self.diagnostics.append(Diagnostic("semantic", msg, node.lineno, severity="warning"))

    def declare(self, node, symbol):
        if symbol.name in self.scope.symbols:
            prev = self.scope.symbols[symbol.name]
            self.error(node, f"'{symbol.name}' вже оголошено в цій області видимості (рядок {prev.lineno})")
            return
        self.scope.symbols[symbol.name] = symbol

    def push(self):
        self.scope = Scope(self.scope)

    def pop(self):
        self.scope = self.scope.parent

    def visit(self, node):
        if node is None:
            return None
        if isinstance(node, list):
            for item in node:
                self.visit(item)
            return None
        return getattr(self, "visit_" + type(node).__name__)(node)

    def check_assignable(self, node, target_type, value_type, what):
        if value_type is None or target_type is None:
            return
        if value_type == "void":
            self.error(node, f"{what}: значення типу void не можна використати")
        elif is_array(target_type) or is_array(value_type) or "string" in (target_type, value_type):
            if target_type != value_type:
                self.error(node, f"{what}: несумісні типи {target_type} і {value_type}")
        elif target_type in INTEGER and value_type in FLOATING:
            self.warn(node, f"{what}: неявне перетворення {value_type} → {target_type} (втрата дробової частини)")


    def analyze(self, program):
        self.visit(program)
        main = self.globals.lookup("main")
        if main is None or main.kind != "func" or not main.defined:
            self.diagnostics.append(Diagnostic("semantic", "не знайдено функцію main()", 1, severity="warning"))
        return self.diagnostics

    def visit_Program(self, node):
        self.visit(node.decls)
        for sym in self.globals.symbols.values():
            if sym.kind == "func" and not sym.defined and sym.name != "main":
                self.warn(A.Node(lineno=sym.lineno), f"функцію '{sym.name}' оголошено, але не визначено")

    def _declare_function(self, node, defined):
        if node.name in BUILTINS:
            self.error(node, f"'{node.name}' — вбудована функція, її не можна перевизначати")
            return
        params = [p.type + ("[]" if p.is_array else "") for p in node.params]
        prev = self.globals.symbols.get(node.name)
        if prev is not None:
            if prev.kind != "func":
                self.error(node, f"'{node.name}' вже оголошено як змінну")
            elif prev.params != params or prev.type != node.ret_type:
                self.error(node, f"сигнатура '{node.name}' не збігається з попереднім оголошенням (рядок {prev.lineno})")
            elif prev.defined and defined:
                self.error(node, f"функцію '{node.name}' вже визначено (рядок {prev.lineno})")
            else:
                prev.defined = prev.defined or defined
            return
        self.globals.symbols[node.name] = Symbol(node.name, node.ret_type, "func", node.lineno, params, defined)

    def visit_FuncDecl(self, node):
        self._declare_function(node, defined=False)

    def visit_FuncDef(self, node):
        self._declare_function(node, defined=True)
        self.current_func = node
        self.push()
        for p in node.params:
            if p.type == "void":
                self.error(p, f"параметр '{p.name}' не може мати тип void")
            self.declare(p, Symbol(p.name, p.type + ("[]" if p.is_array else ""), "var", p.lineno))
        self.visit(node.body.items)
        self.pop()
        if node.ret_type != "void" and node.name != "main" and not self._always_returns(node.body):
            self.warn(node, f"функція '{node.name}' може завершитись без return")
        self.current_func = None

    def _always_returns(self, stmt):
        if isinstance(stmt, A.Return):
            return True
        if isinstance(stmt, A.Block):
            return any(self._always_returns(s) for s in stmt.items)
        if isinstance(stmt, A.If):
            return stmt.else_ is not None and self._always_returns(stmt.then) and self._always_returns(stmt.else_)
        return False

    def visit_VarDecl(self, node):
        if node.type == "void":
            self.error(node, f"змінна '{node.name}' не може мати тип void")
        full_type = node.type + ("[]" if node.is_array else "")
        if node.is_array:
            init = node.init
            if node.size is not None and node.size <= 0:
                self.error(node, f"розмір масиву '{node.name}' має бути додатним")
            if isinstance(init, A.InitList):
                for item in init.items:
                    self.check_assignable(item, node.type, self.visit(item), f"ініціалізація '{node.name}'")
                if node.size is not None and len(init.items) > node.size:
                    self.error(node, f"забагато елементів в ініціалізаторі масиву '{node.name}'")
                if node.size is None:
                    node.size = len(init.items)
            elif isinstance(init, A.Const) and init.type == "string" and node.type == "char":
                init.ctype = "string"
                need = len(init.value) + 1
                if node.size is None:
                    node.size = need
                elif need > node.size:
                    self.error(node, f"рядок не вміщується в масив '{node.name}'")
            elif init is not None:
                self.error(node, f"масив '{node.name}' ініціалізується списком {{...}}")
            elif node.size is None:
                self.error(node, f"не вказано розмір масиву '{node.name}'")
        elif isinstance(node.init, A.InitList):
            self.error(node, f"'{node.name}' не масив, список {{...}} не підходить")
        elif node.init is not None:
            self.check_assignable(node, node.type, self.visit(node.init), f"ініціалізація '{node.name}'")
        symbol = Symbol(node.name, full_type, "var", node.lineno)
        symbol.array_size = node.size if node.is_array else None
        self.declare(node, symbol)


    def visit_Block(self, node):
        self.push()
        self.visit(node.items)
        self.pop()

    def visit_ExprStmt(self, node):
        self.visit(node.expr)

    def check_condition(self, expr):
        t = self.visit(expr)
        if t is not None and t not in NUMERIC:
            self.error(expr, f"умова має бути числовою, а не {t}")

    def visit_If(self, node):
        self.check_condition(node.cond)
        self.visit(node.then)
        self.visit(node.else_)

    def visit_While(self, node):
        self.check_condition(node.cond)
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1

    def visit_DoWhile(self, node):
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1
        self.check_condition(node.cond)

    def visit_For(self, node):
        self.push()
        self.visit(node.init)
        if node.cond is not None:
            self.check_condition(node.cond)
        self.visit(node.step)
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1
        self.pop()

    def visit_Return(self, node):
        func = self.current_func
        if node.value is None:
            if func.ret_type != "void":
                self.error(node, f"функція '{func.name}' має повернути значення типу {func.ret_type}")
            return
        t = self.visit(node.value)
        if func.ret_type == "void":
            self.error(node, f"void-функція '{func.name}' не може повертати значення")
        else:
            self.check_assignable(node, func.ret_type, t, "return")

    def visit_Break(self, node):
        if self.loop_depth == 0:
            self.error(node, "break поза циклом")

    def visit_Continue(self, node):
        if self.loop_depth == 0:
            self.error(node, "continue поза циклом")


    def visit_Const(self, node):
        node.ctype = node.type
        return node.ctype

    def visit_Var(self, node):
        sym = self.scope.lookup(node.name)
        if sym is None:
            self.error(node, f"змінна '{node.name}' не оголошена")
            return None
        if sym.kind == "func":
            self.error(node, f"'{node.name}' — функція, а не змінна")
            return None
        node.ctype = sym.type
        return node.ctype

    def visit_Index(self, node):
        sym = self.scope.lookup(node.name)
        index_type = self.visit(node.index)
        if index_type is not None and index_type not in INTEGER:
            self.error(node, f"індекс масиву має бути цілим, а не {index_type}")
        if sym is None:
            self.error(node, f"масив '{node.name}' не оголошено")
            return None
        if sym.kind != "var" or not is_array(sym.type):
            self.error(node, f"'{node.name}' не є масивом")
            return None
        node.ctype = elem_type(sym.type)
        return node.ctype

    def visit_Call(self, node):
        arg_types = [self.visit(a) for a in node.args]
        if node.name in BUILTINS:
            ret, params = BUILTINS[node.name]
            if node.name == "printf":
                self._check_printf(node, arg_types)
                params = None
        else:
            sym = self.scope.lookup(node.name)
            if sym is None:
                self.error(node, f"функція '{node.name}' не оголошена (додайте прототип вище)")
                return None
            if sym.kind != "func":
                self.error(node, f"'{node.name}' не є функцією")
                return None
            ret, params = sym.type, sym.params
        if params is not None:
            if len(params) != len(node.args):
                self.error(node, f"'{node.name}' очікує {len(params)} аргумент(и), передано {len(node.args)}")
            else:
                for i, (pt, at) in enumerate(zip(params, arg_types), 1):
                    if pt == "string" and at == "char[]":
                        continue
                    self.check_assignable(node, pt, at, f"аргумент {i} функції '{node.name}'")
        node.ctype = ret
        return ret

    def _check_printf(self, node, arg_types):
        if not node.args or arg_types[0] not in ("string", "char[]"):
            self.error(node, "перший аргумент printf має бути форматним рядком")
            return
        fmt = node.args[0]
        if isinstance(fmt, A.Const):
            expected = count_format_args(fmt.value)
            if expected != len(node.args) - 1:
                self.warn(node, f"printf: формат очікує {expected} аргумент(и), передано {len(node.args) - 1}")
        for t in arg_types[1:]:
            if t == "void":
                self.error(node, "printf: значення типу void не можна надрукувати")

    def visit_BinOp(self, node):
        lt, rt = self.visit(node.left), self.visit(node.right)
        if lt is None or rt is None:
            return None
        for t in (lt, rt):
            if t not in NUMERIC:
                self.error(node, f"оператор '{node.op}' не застосовний до типу {t}")
                return None
        if node.op in COMPARISON_OPS or node.op in LOGICAL_OPS:
            node.ctype = "int"
        elif node.op in INTEGER_ONLY_OPS:
            if lt in FLOATING or rt in FLOATING:
                self.error(node, f"оператор '{node.op}' вимагає цілих операндів")
            node.ctype = "int"
        else:
            node.ctype = arith_type(lt, rt)
        return node.ctype

    def visit_UnaryOp(self, node):
        t = self.visit(node.operand)
        if t is None:
            return None
        if t not in NUMERIC:
            self.error(node, f"унарний '{node.op}' не застосовний до типу {t}")
            return None
        if node.op == "~" and t in FLOATING:
            self.error(node, "'~' вимагає цілого операнда")
        node.ctype = "int" if node.op in ("!", "~") or t == "char" else t
        return node.ctype

    def _check_lvalue(self, node, target):
        if not isinstance(target, (A.Var, A.Index)):
            self.error(node, f"ліва частина '{node.op}' не є змінною (не lvalue)")
            return False
        return True

    def visit_IncDec(self, node):
        t = self.visit(node.target)
        if not self._check_lvalue(node, node.target) or t is None:
            return None
        if t not in NUMERIC:
            self.error(node, f"'{node.op}' не застосовний до типу {t}")
            return None
        node.ctype = t
        return t

    def visit_Assign(self, node):
        tt = self.visit(node.target)
        vt = self.visit(node.value)
        if not self._check_lvalue(node, node.target) or tt is None:
            return None
        if is_array(tt):
            self.error(node, "масиву не можна присвоїти значення цілком")
            return None
        if node.op in INTEGER_ONLY_ASSIGN and (tt in FLOATING or vt in FLOATING):
            self.error(node, f"'{node.op}' вимагає цілих операндів")
        self.check_assignable(node, tt, vt, "присвоєння")
        node.ctype = tt
        return tt

    def visit_Ternary(self, node):
        self.check_condition(node.cond)
        a, b = self.visit(node.then), self.visit(node.else_)
        if a is None or b is None:
            return None
        if a in NUMERIC and b in NUMERIC:
            node.ctype = arith_type(a, b)
        elif a == b:
            node.ctype = a
        else:
            self.error(node, f"гілки ?: мають несумісні типи {a} і {b}")
            return None
        return node.ctype

    # sizeof рахується під час компіляції, вираз усередині не виконується
    def visit_SizeOf(self, node):
        node.ctype = "int"
        if node.type_name is not None:
            node.size_value = SIZES[node.type_name]
            return "int"
        t = self.visit(node.expr)
        if t is None:
            node.size_value = 0
        elif t == "string":
            node.size_value = len(node.expr.value) + 1
        elif is_array(t):
            sym = self.scope.lookup(node.expr.name) if isinstance(node.expr, A.Var) else None
            if sym is not None and sym.array_size is not None:
                node.size_value = SIZES[elem_type(t)] * sym.array_size
            else:
                node.size_value = POINTER_SIZE
                self.warn(node, "sizeof параметра-масиву дає розмір вказівника, а не масиву")
        elif t == "void":
            self.error(node, "sizeof не застосовний до void-виразу")
            node.size_value = 0
        else:
            node.size_value = SIZES[t]
        return "int"

    def visit_Cast(self, node):
        t = self.visit(node.expr)
        if t is not None and node.type != "void" and t not in NUMERIC:
            self.error(node, f"не можна привести {t} до {node.type}")
        node.ctype = node.type
        return node.ctype


def analyze(program):
    return Analyzer().analyze(program)
