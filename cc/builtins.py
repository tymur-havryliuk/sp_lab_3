import math
import re

BUILTINS = {
    "printf": ("int", None),
    "puts": ("int", ["string"]),
    "putchar": ("int", ["int"]),
    "abs": ("int", ["int"]),
    "fabs": ("double", ["double"]),
    "sqrt": ("double", ["double"]),
    "pow": ("double", ["double", "double"]),
}

FORMAT_RE = re.compile(r"%([-+ 0#]*)(\d+|\*)?(?:\.(\d+|\*))?(?:hh|h|ll|l|L|z)?([diouxXeEfFgGcs%])")


def count_format_args(fmt):
    n = 0
    for m in FORMAT_RE.finditer(fmt):
        if m.group(4) == "%":
            continue
        n += 1 + (m.group(2) == "*") + (m.group(3) == "*")
    return n


def char_array_to_str(value):
    if isinstance(value, list):
        chars = []
        for code in value:
            if code == 0:
                break
            chars.append(chr(code))
        return "".join(chars)
    return str(value)


def c_format(fmt, args):
    args = list(args)
    pos = 0

    def take():
        nonlocal pos
        if pos >= len(args):
            return 0
        pos += 1
        return args[pos - 1]

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
            value = int(value)
            if conv == "u":
                value &= 0xFFFFFFFF
            conv = "d"
        elif conv in "xXo":
            value = int(value) & 0xFFFFFFFF
        elif conv in "eEfFgG":
            value = float(value)
        elif conv == "c":
            value = chr(int(value))
        elif conv == "s":
            value = char_array_to_str(value)
        spec = "%" + flags + (width or "") + ("." + prec if prec is not None else "") + conv
        return spec % value

    return FORMAT_RE.sub(repl, fmt)


def call_builtin(name, args, out):
    if name == "printf":
        text = c_format(char_array_to_str(args[0]), args[1:])
        out.append(text)
        return len(text)
    if name == "puts":
        out.append(char_array_to_str(args[0]) + "\n")
        return 0
    if name == "putchar":
        out.append(chr(int(args[0])))
        return int(args[0])
    if name == "abs":
        return abs(int(args[0]))
    if name == "fabs":
        return abs(float(args[0]))
    if name == "sqrt":
        return math.sqrt(args[0])
    if name == "pow":
        return math.pow(args[0], args[1])
    raise KeyError(name)
