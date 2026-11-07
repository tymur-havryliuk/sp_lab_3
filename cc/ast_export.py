from . import ast_nodes as A

CATEGORY = {
    "Program": "program",
    "FuncDef": "decl", "FuncDecl": "decl", "Param": "decl", "VarDecl": "decl", "InitList": "decl",
    "Block": "stmt", "If": "stmt", "While": "stmt", "DoWhile": "stmt", "For": "stmt",
    "Return": "stmt", "Break": "stmt", "Continue": "stmt", "ExprStmt": "stmt",
    "Const": "const", "Var": "var", "Index": "var",
}


def label(node):
    name = type(node).__name__
    if isinstance(node, A.FuncDef) or isinstance(node, A.FuncDecl):
        return f"{name} {node.ret_type} {node.name}()"
    if isinstance(node, A.Param):
        return f"Param {node.type}{'[]' if node.is_array else ''} {node.name}"
    if isinstance(node, A.VarDecl):
        arr = f"[{node.size if node.size is not None else ''}]" if node.is_array else ""
        return f"VarDecl {node.type} {node.name}{arr}"
    if isinstance(node, A.Const):
        if node.type == "string":
            text = node.value.replace("\n", "\\n")
            return f'Const "{text[:24]}{"…" if len(text) > 24 else ""}"'
        if node.type == "char":
            return f"Const '{chr(node.value)}'" if chr(node.value).isprintable() else f"Const char {node.value}"
        return f"Const {node.value}"
    if isinstance(node, A.Var):
        return f"Var {node.name}"
    if isinstance(node, A.Index):
        return f"Index {node.name}[]"
    if isinstance(node, A.Call):
        return f"Call {node.name}()"
    if isinstance(node, A.IncDec):
        return f"IncDec {'prefix' if node.prefix else 'postfix'} {node.op}"
    if isinstance(node, (A.BinOp, A.UnaryOp, A.Assign)):
        return f"{name} {node.op}"
    if isinstance(node, A.SizeOf):
        what = f"({node.type_name})" if node.type_name else ""
        size = getattr(node, "size_value", None)
        return f"SizeOf{what}" + (f" = {size}" if size is not None else "")
    if isinstance(node, A.Cast):
        return f"Cast ({node.type})"
    return name


GROUPED = {("FuncDef", "params"), ("FuncDecl", "params"), ("Call", "args"), ("For", "init")}


def fill_spans(node):
    """Рядок кінця вузла: найдальший рядок серед нього самого і всіх нащадків."""
    end = max(node.end_lineno or 0, node.lineno or 0)
    for _, child in node.children():
        for c in (child if isinstance(child, list) else [child]):
            if isinstance(c, A.Node):
                end = max(end, fill_spans(c))
    node.end_lineno = end
    return end


def to_json(node, role=None):
    if node is None:
        return None
    result = {
        "name": label(node),
        "kind": type(node).__name__,
        "category": CATEGORY.get(type(node).__name__, "expr"),
        "line": node.lineno,
        "end": node.end_lineno or node.lineno,
    }
    if node.ctype:
        result["ctype"] = node.ctype
    if role:
        result["role"] = role
    children = []
    for field, value in node.children():
        if isinstance(value, list):
            items = [to_json(v) for v in value if isinstance(v, A.Node)]
            if (type(node).__name__, field) in GROUPED:
                children.append({"name": f"{field} [{len(items)}]", "kind": "group",
                                 "category": "group", "role": field,
                                 "line": min(i["line"] for i in items), "end": max(i["end"] for i in items),
                                 "children": items})
            else:
                children.extend(items)
        else:
            children.append(to_json(value, role=field))
    if children:
        result["children"] = children
    return result


def to_text(node, prefix="", is_last=True, role=None, out=None):
    top = out is None
    out = [] if top else out
    connector = "" if top else ("└── " if is_last else "├── ")
    head = f"{role}: " if role else ""
    typ = f"  : {node.ctype}" if node.ctype else ""
    out.append(f"{prefix}{connector}{head}{label(node)}{typ}   (рядок {node.lineno})")
    child_prefix = prefix + ("" if top else ("    " if is_last else "│   "))
    entries = []
    for field, value in node.children():
        if isinstance(value, list):
            entries.extend((None if type(node).__name__ in ("Program", "Block") else field, v)
                           for v in value if isinstance(v, A.Node))
        else:
            entries.append((field, value))
    for i, (field, child) in enumerate(entries):
        to_text(child, child_prefix, i == len(entries) - 1, field, out)
    return "\n".join(out) if top else None
