import ply.lex as lex

from .errors import Diagnostic

reserved = {
    "int": "INT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "char": "CHAR",
    "void": "VOID",
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "do": "DO",
    "for": "FOR",
    "return": "RETURN",
    "break": "BREAK",
    "continue": "CONTINUE",
    "sizeof": "SIZEOF",
}

tokens = [
    "ID", "INT_CONST", "FLOAT_CONST", "CHAR_CONST", "STRING",
    "PLUS", "MINUS", "TIMES", "DIVIDE", "MOD", "INC", "DEC",
    "ASSIGN", "PLUSEQ", "MINUSEQ", "TIMESEQ", "DIVEQ", "MODEQ",
    "ANDEQ", "OREQ", "XOREQ", "LSHIFTEQ", "RSHIFTEQ",
    "EQ", "NE", "LT", "GT", "LE", "GE", "AND", "OR", "NOT",
    "BAND", "BOR", "BXOR", "BNOT", "LSHIFT", "RSHIFT",
    "QUESTION", "COLON", "SEMI", "COMMA",
    "LPAREN", "RPAREN", "LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
] + list(reserved.values())

t_INC = r"\+\+"
t_DEC = r"--"
t_PLUSEQ = r"\+="
t_MINUSEQ = r"-="
t_TIMESEQ = r"\*="
t_DIVEQ = r"/="
t_MODEQ = r"%="
t_ANDEQ = r"&="
t_OREQ = r"\|="
t_XOREQ = r"\^="
t_LSHIFTEQ = r"<<="
t_RSHIFTEQ = r">>="
t_LSHIFT = r"<<"
t_RSHIFT = r">>"
t_EQ = r"=="
t_NE = r"!="
t_LE = r"<="
t_GE = r">="
t_AND = r"&&"
t_OR = r"\|\|"
t_PLUS = r"\+"
t_MINUS = r"-"
t_TIMES = r"\*"
t_DIVIDE = r"/"
t_MOD = r"%"
t_ASSIGN = r"="
t_LT = r"<"
t_GT = r">"
t_NOT = r"!"
t_BAND = r"&"
t_BOR = r"\|"
t_BXOR = r"\^"
t_BNOT = r"~"
t_QUESTION = r"\?"
t_COLON = r":"
t_SEMI = r";"
t_COMMA = r","
t_LPAREN = r"\("
t_RPAREN = r"\)"
t_LBRACE = r"\{"
t_RBRACE = r"\}"
t_LBRACKET = r"\["
t_RBRACKET = r"\]"

t_ignore = " \t\r"

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b"}


def unescape(body):
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            out.append(ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def t_COMMENT_BLOCK(t):
    r"/\*(.|\n)*?\*/"
    t.lexer.lineno += t.value.count("\n")


def t_COMMENT_LINE(t):
    r"//[^\n]*"


def t_PREPROCESSOR(t):
    r"\#[^\n]*"


class FloatF(float):
    pass


def t_FLOAT_CONST(t):
    r"((\d+\.\d*|\.\d+)([eE][-+]?\d+)?|\d+[eE][-+]?\d+)[fF]?"
    text = t.value
    t.value = FloatF(text[:-1]) if text[-1] in "fF" else float(text)
    return t


def t_INT_CONST(t):
    r"0[xX][0-9a-fA-F]+|\d+"
    t.value = int(t.value, 0) if t.value.lower().startswith("0x") else int(t.value)
    return t


def t_CHAR_CONST(t):
    r"'(\\.|[^\\'\n])'"
    t.value = ord(unescape(t.value[1:-1]))
    return t


def t_STRING(t):
    r'"(\\.|[^\\"\n])*"'
    t.value = unescape(t.value[1:-1])
    return t


def t_ID(t):
    r"[A-Za-z_][A-Za-z_0-9]*"
    t.type = reserved.get(t.value, "ID")
    return t


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


def find_column(data, lexpos):
    line_start = data.rfind("\n", 0, lexpos) + 1
    return lexpos - line_start + 1


def t_error(t):
    t.lexer.diagnostics.append(Diagnostic(
        "lexer", f"недопустимий символ '{t.value[0]}'",
        t.lexer.lineno, find_column(t.lexer.lexdata, t.lexpos)))
    t.lexer.skip(1)


def build_lexer():
    lexer = lex.lex()
    lexer.diagnostics = []
    return lexer


def tokenize(code):
    lexer = build_lexer()
    lexer.input(code)
    result = []
    for tok in lexer:
        result.append({
            "type": tok.type,
            "value": tok.value,
            "text": code[tok.lexpos:lexer.lexpos],
            "line": tok.lineno,
            "col": find_column(code, tok.lexpos),
        })
    return result, lexer.diagnostics
