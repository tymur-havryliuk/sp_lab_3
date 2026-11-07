import os

import ply.yacc as yacc

from . import ast_nodes as A
from .errors import Diagnostic
from .lexer import FloatF, build_lexer, find_column, tokens  # noqa: F401

BUILD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build")

# від найнижчого пріоритету до найвищого
precedence = (
    ("nonassoc", "IFX"),  # if без else
    ("nonassoc", "ELSE"),
    ("right", "ASSIGN", "PLUSEQ", "MINUSEQ", "TIMESEQ", "DIVEQ", "MODEQ",
     "ANDEQ", "OREQ", "XOREQ", "LSHIFTEQ", "RSHIFTEQ"),
    ("right", "QUESTION", "COLON"),
    ("left", "OR"),
    ("left", "AND"),
    ("left", "BOR"),
    ("left", "BXOR"),
    ("left", "BAND"),
    ("left", "EQ", "NE"),
    ("left", "LT", "GT", "LE", "GE"),
    ("left", "LSHIFT", "RSHIFT"),
    ("left", "PLUS", "MINUS"),
    ("left", "TIMES", "DIVIDE", "MOD"),
    ("right", "UMINUS", "NOT", "BNOT", "INC", "DEC"),
)

start = "translation_unit"


def p_translation_unit(p):
    """translation_unit : external_decl_list"""
    p[0] = A.Program(p[1], lineno=1)


def p_external_decl_list(p):
    """external_decl_list : external_decl_list external_decl
                          | external_decl"""
    p[0] = p[1] + p[2] if len(p) == 3 else p[1]


def p_external_decl(p):
    """external_decl : function_def
                     | function_proto
                     | declaration"""
    p[0] = p[1] if isinstance(p[1], list) else [p[1]]


def p_type_spec(p):
    """type_spec : INT
                 | FLOAT
                 | DOUBLE
                 | CHAR
                 | VOID"""
    p[0] = p[1]


def p_function_def(p):
    """function_def : type_spec ID LPAREN param_list_opt RPAREN compound_stmt"""
    p[0] = A.FuncDef(p[1], p[2], p[4], p[6], lineno=p.lineno(2))


def p_function_proto(p):
    """function_proto : type_spec ID LPAREN param_list_opt RPAREN SEMI"""
    p[0] = A.FuncDecl(p[1], p[2], p[4], lineno=p.lineno(2))


def p_param_list_opt(p):
    """param_list_opt : param_list
                      | VOID
                      | empty"""
    p[0] = p[1] if isinstance(p[1], list) else []


def p_param_list(p):
    """param_list : param_list COMMA param
                  | param"""
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_param(p):
    """param : type_spec ID
             | type_spec ID LBRACKET RBRACKET"""
    p[0] = A.Param(p[1], p[2], len(p) == 5, lineno=p.lineno(2))


def p_declaration(p):
    """declaration : type_spec init_declarator_list SEMI"""
    decls = []
    for (name, is_array, size, init, line) in p[2]:
        decl = A.VarDecl(p[1], name, is_array, size, init, lineno=line)
        decl.end_lineno = p.lineno(3)
        decls.append(decl)
    p[0] = decls


def p_init_declarator_list(p):
    """init_declarator_list : init_declarator_list COMMA init_declarator
                            | init_declarator"""
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_init_declarator(p):
    """init_declarator : declarator
                       | declarator ASSIGN initializer"""
    name, is_array, size, line = p[1]
    p[0] = (name, is_array, size, p[3] if len(p) == 4 else None, line)


def p_declarator(p):
    """declarator : ID
                  | ID LBRACKET INT_CONST RBRACKET
                  | ID LBRACKET RBRACKET"""
    if len(p) == 2:
        p[0] = (p[1], False, None, p.lineno(1))
    else:
        p[0] = (p[1], True, p[3] if len(p) == 5 else None, p.lineno(1))


def p_initializer(p):
    """initializer : expr
                   | LBRACE expr_list RBRACE
                   | LBRACE expr_list COMMA RBRACE"""
    p[0] = p[1] if len(p) == 2 else A.InitList(p[2], lineno=p.lineno(1))


def p_expr_list(p):
    """expr_list : expr_list COMMA expr
                 | expr"""
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_compound_stmt(p):
    """compound_stmt : LBRACE block_item_list RBRACE
                     | LBRACE RBRACE"""
    p[0] = A.Block(p[2] if len(p) == 4 else [], lineno=p.lineno(1))
    p[0].end_lineno = p.lineno(len(p) - 1)


def p_block_item_list(p):
    """block_item_list : block_item_list block_item
                       | block_item"""
    p[0] = p[1] + p[2] if len(p) == 3 else p[1]


def p_block_item(p):
    """block_item : declaration
                  | statement"""
    if isinstance(p[1], list):
        p[0] = p[1]
    else:
        p[0] = [p[1]] if p[1] is not None else []


def p_statement(p):
    """statement : compound_stmt
                 | expr_stmt
                 | selection_stmt
                 | iteration_stmt
                 | jump_stmt"""
    p[0] = p[1]


# відновлення після синтаксичної помилки: пропустити все до ";"
def p_statement_error(p):
    """statement : error SEMI"""
    p[0] = None


def p_expr_stmt(p):
    """expr_stmt : expr SEMI
                 | SEMI"""
    p[0] = A.ExprStmt(p[1] if len(p) == 3 else None, lineno=p.lineno(1))
    p[0].end_lineno = p.lineno(len(p) - 1)


def p_selection_if(p):
    """selection_stmt : IF LPAREN expr RPAREN statement %prec IFX"""
    p[0] = A.If(p[3], p[5], None, lineno=p.lineno(1))


def p_selection_if_else(p):
    """selection_stmt : IF LPAREN expr RPAREN statement ELSE statement"""
    p[0] = A.If(p[3], p[5], p[7], lineno=p.lineno(1))


def p_iteration_while(p):
    """iteration_stmt : WHILE LPAREN expr RPAREN statement"""
    p[0] = A.While(p[3], p[5], lineno=p.lineno(1))


def p_iteration_do(p):
    """iteration_stmt : DO statement WHILE LPAREN expr RPAREN SEMI"""
    p[0] = A.DoWhile(p[2], p[5], lineno=p.lineno(1))
    p[0].end_lineno = p.lineno(7)


def p_iteration_for(p):
    """iteration_stmt : FOR LPAREN for_init expr_opt SEMI expr_opt RPAREN statement"""
    p[0] = A.For(p[3], p[4], p[6], p[8], lineno=p.lineno(1))


def p_for_init(p):
    """for_init : declaration
                | expr_opt SEMI"""
    if isinstance(p[1], list):
        p[0] = p[1]
    else:
        p[0] = A.ExprStmt(p[1], lineno=p.lineno(2)) if p[1] is not None else None


def p_jump_return(p):
    """jump_stmt : RETURN expr_opt SEMI"""
    p[0] = A.Return(p[2], lineno=p.lineno(1))
    p[0].end_lineno = p.lineno(3)


def p_jump_break(p):
    """jump_stmt : BREAK SEMI"""
    p[0] = A.Break(lineno=p.lineno(1))


def p_jump_continue(p):
    """jump_stmt : CONTINUE SEMI"""
    p[0] = A.Continue(lineno=p.lineno(1))


def p_expr_opt(p):
    """expr_opt : expr
                | empty"""
    p[0] = p[1]


def p_expr_binary(p):
    """expr : expr PLUS expr
            | expr MINUS expr
            | expr TIMES expr
            | expr DIVIDE expr
            | expr MOD expr
            | expr LT expr
            | expr GT expr
            | expr LE expr
            | expr GE expr
            | expr EQ expr
            | expr NE expr
            | expr AND expr
            | expr OR expr
            | expr BAND expr
            | expr BOR expr
            | expr BXOR expr
            | expr LSHIFT expr
            | expr RSHIFT expr"""
    p[0] = A.BinOp(p[2], p[1], p[3], lineno=p.lineno(2))


def p_expr_assign(p):
    """expr : expr ASSIGN expr
            | expr PLUSEQ expr
            | expr MINUSEQ expr
            | expr TIMESEQ expr
            | expr DIVEQ expr
            | expr MODEQ expr
            | expr ANDEQ expr
            | expr OREQ expr
            | expr XOREQ expr
            | expr LSHIFTEQ expr
            | expr RSHIFTEQ expr"""
    p[0] = A.Assign(p[2], p[1], p[3], lineno=p.lineno(2))


def p_expr_ternary(p):
    """expr : expr QUESTION expr COLON expr"""
    p[0] = A.Ternary(p[1], p[3], p[5], lineno=p.lineno(2))


def p_expr_unary(p):
    """expr : MINUS expr %prec UMINUS
            | PLUS expr %prec UMINUS
            | NOT expr
            | BNOT expr"""
    p[0] = A.UnaryOp(p[1], p[2], lineno=p.lineno(1))


def p_expr_prefix(p):
    """expr : INC expr
            | DEC expr"""
    p[0] = A.IncDec(p[1], True, p[2], lineno=p.lineno(1))


def p_expr_postfix(p):
    """expr : expr INC
            | expr DEC"""
    p[0] = A.IncDec(p[2], False, p[1], lineno=p.lineno(2))


def p_expr_cast(p):
    """expr : LPAREN type_spec RPAREN expr %prec UMINUS"""
    p[0] = A.Cast(p[2], p[4], lineno=p.lineno(1))


def p_expr_group(p):
    """expr : LPAREN expr RPAREN"""
    p[0] = p[2]


def p_expr_call(p):
    """expr : ID LPAREN arg_list RPAREN
            | ID LPAREN RPAREN"""
    p[0] = A.Call(p[1], p[3] if len(p) == 5 else [], lineno=p.lineno(1))


def p_arg_list(p):
    """arg_list : arg_list COMMA expr
                | expr"""
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_expr_index(p):
    """expr : ID LBRACKET expr RBRACKET"""
    p[0] = A.Index(p[1], p[3], lineno=p.lineno(1))


def p_expr_sizeof_type(p):
    """expr : SIZEOF LPAREN type_spec RPAREN"""
    p[0] = A.SizeOf(p[3], None, lineno=p.lineno(1))


# без дужок лише `sizeof ім'я`: повна форма `sizeof expr` конфліктує з `sizeof (int) x`
def p_expr_sizeof_expr(p):
    """expr : SIZEOF LPAREN expr RPAREN
            | SIZEOF ID"""
    operand = p[3] if len(p) == 5 else A.Var(p[2], lineno=p.lineno(2))
    p[0] = A.SizeOf(None, operand, lineno=p.lineno(1))


def p_expr_id(p):
    """expr : ID"""
    p[0] = A.Var(p[1], lineno=p.lineno(1))


def p_expr_int(p):
    """expr : INT_CONST"""
    p[0] = A.Const(p[1], "int", lineno=p.lineno(1))


def p_expr_float(p):
    """expr : FLOAT_CONST"""
    p[0] = A.Const(float(p[1]), "float" if isinstance(p[1], FloatF) else "double", lineno=p.lineno(1))


def p_expr_char(p):
    """expr : CHAR_CONST"""
    p[0] = A.Const(p[1], "char", lineno=p.lineno(1))


def p_expr_string(p):
    """expr : STRING"""
    p[0] = A.Const(p[1], "string", lineno=p.lineno(1))


def p_empty(p):
    """empty :"""
    p[0] = None


def p_error(tok):
    diags = _parser.diagnostics
    if tok is None:
        diags.append(Diagnostic("parser", "неочікуваний кінець файлу", _parser.last_line))
        return
    value = tok.value if tok.type != "STRING" else f'"{tok.value}"'
    diags.append(Diagnostic(
        "parser", f"синтаксична помилка біля '{value}' (токен {tok.type})",
        tok.lineno, find_column(tok.lexer.lexdata, tok.lexpos)))


os.makedirs(BUILD_DIR, exist_ok=True)


class _GrammarLog:
    def __init__(self):
        self.lines = []

    def warning(self, msg, *args, **kwargs):
        self.lines.append("WARNING: " + (msg % args))

    def error(self, msg, *args, **kwargs):
        self.lines.append("ERROR: " + (msg % args))

    info = debug = critical = warning


grammar_log = _GrammarLog()
_parser = yacc.yacc(
    method="LALR",
    debug=True,
    debugfile="parser.out",
    outputdir=BUILD_DIR,
    write_tables=False,
    errorlog=grammar_log,
)
_parser.diagnostics = []
_parser.last_line = 1


def parse(code):
    lexer = build_lexer()
    _parser.diagnostics = lexer.diagnostics
    _parser.last_line = code.count("\n") + 1
    ast = _parser.parse(code, lexer=lexer, tracking=True)
    return ast, _parser.diagnostics


def _token_texts():
    from . import lexer as L
    texts = {name: name.lower() for name in L.reserved.values()}
    for name in L.tokens:
        rule = getattr(L, "t_" + name, None)
        if isinstance(rule, str):
            texts[name] = rule.replace("\\", "")
    texts.update({"ID": "ідентифікатор", "INT_CONST": "ціле", "FLOAT_CONST": "дробове",
                  "CHAR_CONST": "символ", "STRING": "рядок"})
    return texts


def grammar_details():
    texts = _token_texts()
    rules = {}
    for prod in _parser.productions[1:]:
        rules.setdefault(prod.name, []).append(list(prod.prod))
    terminals = set(tokens) | {"error"}
    info = grammar_info()
    return {
        "stats": {"productions": info["productions"] - 1, "states": info["states"],
                  "conflicts": len([w for w in info["warnings"] if "conflict" in w]),
                  "terminals": len(tokens), "nonterminals": len(rules)},
        "start": start,
        "precedence": [{"level": i + 1, "assoc": assoc, "tokens": [{"name": t, "text": texts.get(t, t)} for t in toks]}
                       for i, (assoc, *toks) in enumerate(precedence)],
        "rules": [{"lhs": lhs, "alternatives": alts} for lhs, alts in rules.items()],
        "terminals": sorted(terminals),
        "texts": texts,
    }


def grammar_info():
    lr = _parser
    return {
        "states": len(lr.action),
        "productions": len(lr.productions),
        "warnings": grammar_log.lines,
        "parser_out": os.path.join(BUILD_DIR, "parser.out"),
    }
