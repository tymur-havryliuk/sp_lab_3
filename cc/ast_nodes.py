class Node:
    _fields = ()

    def __init__(self, *args, lineno=0):
        if len(args) != len(self._fields):
            raise TypeError(f"{type(self).__name__} очікує поля {self._fields}")
        for name, value in zip(self._fields, args):
            setattr(self, name, value)
        self.lineno = lineno
        self.ctype = None
        self.end_lineno = None

    def children(self):
        for name in self._fields:
            value = getattr(self, name)
            if isinstance(value, Node):
                yield name, value
            elif isinstance(value, list) and any(isinstance(v, Node) for v in value):
                yield name, value

    def attrs(self):
        result = {}
        for name in self._fields:
            value = getattr(self, name)
            if not isinstance(value, (Node, list)) and value is not None:
                result[name] = value
        return result

    def __repr__(self):
        return f"{type(self).__name__}({self.attrs()})"


class Program(Node):
    _fields = ("decls",)


class FuncDef(Node):
    _fields = ("ret_type", "name", "params", "body")


class FuncDecl(Node):
    _fields = ("ret_type", "name", "params")


class Param(Node):
    _fields = ("type", "name", "is_array")


class VarDecl(Node):
    _fields = ("type", "name", "is_array", "size", "init")


class InitList(Node):
    _fields = ("items",)


class Block(Node):
    _fields = ("items",)


class If(Node):
    _fields = ("cond", "then", "else_")


class While(Node):
    _fields = ("cond", "body")


class DoWhile(Node):
    _fields = ("body", "cond")


class For(Node):
    _fields = ("init", "cond", "step", "body")


class Return(Node):
    _fields = ("value",)


class Break(Node):
    _fields = ()


class Continue(Node):
    _fields = ()


class ExprStmt(Node):
    _fields = ("expr",)


class BinOp(Node):
    _fields = ("op", "left", "right")


class UnaryOp(Node):
    _fields = ("op", "operand")


class IncDec(Node):
    _fields = ("op", "prefix", "target")


class Assign(Node):
    _fields = ("op", "target", "value")


class Ternary(Node):
    _fields = ("cond", "then", "else_")


class Cast(Node):
    _fields = ("type", "expr")


class Call(Node):
    _fields = ("name", "args")


class Index(Node):
    _fields = ("name", "index")


class SizeOf(Node):
    _fields = ("type_name", "expr")


class Var(Node):
    _fields = ("name",)


class Const(Node):
    _fields = ("value", "type")
