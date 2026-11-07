import os
import sys

import ply.lex as lex
import ply.yacc as yacc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
os.makedirs(BUILD, exist_ok=True)


class DemoLexer:
    reserved = {"if": "IF", "else": "ELSE", "print": "PRINT"}
    tokens = ["NUM", "ID", "PLUS", "MINUS", "TIMES", "LPAREN", "RPAREN", "SEMI"] + list(reserved.values())
    t_PLUS, t_MINUS, t_TIMES = r"\+", r"-", r"\*"
    t_LPAREN, t_RPAREN, t_SEMI = r"\(", r"\)", r";"
    t_ignore = " \t\n"

    def t_NUM(self, t):
        r"\d+"
        t.value = int(t.value)
        return t

    def t_ID(self, t):
        r"[a-z]+"
        t.type = self.reserved.get(t.value, "ID")
        return t

    def t_error(self, t):
        raise SyntaxError(t.value[0])

    def build(self):
        return lex.lex(module=self)


tokens = DemoLexer.tokens


class Log:
    def __init__(self):
        self.lines = []

    def warning(self, msg, *a, **k):
        self.lines.append(msg % a)

    error = info = debug = critical = warning


def build(grammar, name):
    log = Log()
    parser = yacc.yacc(module=grammar, debug=True, debugfile=f"demo_{name}.out",
                       outputdir=BUILD, write_tables=False, errorlog=log)
    conflicts = [line for line in log.lines if "conflict" in line]
    return parser, conflicts


def show_conflicts(name, conflicts):
    if conflicts:
        for c in conflicts:
            print("  PLY: " + c)
    else:
        print("  PLY: конфліктів немає")
    detail = os.path.join(BUILD, f"demo_{name}.out")
    with open(detail, encoding="utf-8") as f:
        marked = [line.strip()[1:].strip() for line in f if line.strip().startswith("!")]
    for line in marked[:4]:
        prefix = "конфлікт" if "conflict" in line else "відкинуто"
        print(f"    parser.out, {prefix}: {line}")
    if len(marked) > 4:
        print(f"    ... ще {len(marked) - 4}, див. {os.path.relpath(detail, ROOT)}")


class GrammarBase:
    def p_error(self, p):
        raise SyntaxError(f"синтаксична помилка біля {p}")


class ExprGrammar(GrammarBase):
    tokens = tokens
    start = "e"

    def p_e_bin(self, p):
        """e : e PLUS e
             | e MINUS e
             | e TIMES e"""
        a, b = p[1], p[3]
        p[0] = a + b if p[2] == "+" else a - b if p[2] == "-" else a * b

    def p_e_num(self, p):
        """e : NUM"""
        p[0] = p[1]

    def p_e_group(self, p):
        """e : LPAREN e RPAREN"""
        p[0] = p[2]


class ExprGrammarWithPrecedence(ExprGrammar):
    precedence = (
        ("left", "PLUS", "MINUS"),
        ("left", "TIMES"),
    )


class DanglingElse(GrammarBase):
    tokens = tokens
    start = "s"

    def p_s_if(self, p):
        """s : IF LPAREN ID RPAREN s"""
        p[0] = f"if({p[3]}) {{ {p[5]} }}"

    def p_s_if_else(self, p):
        """s : IF LPAREN ID RPAREN s ELSE s"""
        p[0] = f"if({p[3]}) {{ {p[5]} }} else {{ {p[7]} }}"

    def p_s_print(self, p):
        """s : PRINT NUM SEMI"""
        p[0] = f"print {p[2]};"


class ReduceReduce(GrammarBase):
    tokens = tokens
    start = "s"

    def p_s_decl(self, p):
        """s : type_name SEMI"""
        p[0] = f"оголошення типу {p[1]}"

    def p_s_expr(self, p):
        """s : var_name SEMI"""
        p[0] = f"вираз зі змінною {p[1]}"

    def p_type_name(self, p):
        """type_name : ID"""
        p[0] = p[1]

    def p_var_name(self, p):
        """var_name : ID"""
        p[0] = p[1]


def main():
    lexer = DemoLexer().build()

    print("=" * 72)
    print("1) e : e + e | e - e | e * e | NUM   — БЕЗ пріоритетів")
    parser, conflicts = build(ExprGrammar(), "expr_no_prec")
    show_conflicts("expr_no_prec", conflicts)
    for src, correct in [("2 * 3 + 4", 10), ("10 - 4 - 3", 3), ("2 + 3 * 4", 14)]:
        got = parser.parse(src, lexer=lexer)
        mark = "OK" if got == correct else "НЕПРАВИЛЬНО"
        print(f"  {src:<12} = {got:<4} (має бути {correct}) {mark}")
    print("  Висновок: за замовчуванням shift ⇒ усе стає правоасоціативним з однаковим пріоритетом:")
    print("            2*3+4 розібрано як 2*(3+4), а 10-4-3 як 10-(4-3).")

    print("=" * 72)
    print("2) Та сама граматика + precedence = (('left','PLUS','MINUS'), ('left','TIMES'))")
    parser, conflicts = build(ExprGrammarWithPrecedence(), "expr_prec")
    show_conflicts("expr_prec", conflicts)
    for src, correct in [("2 * 3 + 4", 10), ("10 - 4 - 3", 3), ("2 + 3 * 4", 14)]:
        got = parser.parse(src, lexer=lexer)
        print(f"  {src:<12} = {got:<4} (має бути {correct}) {'OK' if got == correct else 'НЕПРАВИЛЬНО'}")
    print("  Правило: порівнюємо пріоритет ПРАВИЛА (останній термінал у ньому) з пріоритетом")
    print("  токена-lookahead. Токен вищий → shift; правило вище → reduce;")
    print("  рівні → асоціативність: left → reduce, right → shift, nonassoc → помилка.")

    print("=" * 72)
    print("3) Висячий else:  s : IF ( ID ) s | IF ( ID ) s ELSE s | PRINT NUM ;")
    parser, conflicts = build(DanglingElse(), "dangling_else")
    show_conflicts("dangling_else", conflicts)
    src = "if (a) if (b) print 1; else print 2;"
    print(f"  {src}")
    print(f"  → {parser.parse(src, lexer=lexer)}")
    print("  Shift за замовчуванням прив'язує else до НАЙБЛИЖЧОГО if — саме так, як вимагає стандарт C.")
    print("  У нашому парсері C конфлікт прибрано явно: %prec IFX і ('nonassoc','IFX'), ('nonassoc','ELSE').")

    print("=" * 72)
    print("4) Reduce/reduce:  s : type_name ; | var_name ;   type_name : ID   var_name : ID")
    parser, conflicts = build(ReduceReduce(), "reduce_reduce")
    show_conflicts("reduce_reduce", conflicts)
    print(f"  x;  → {parser.parse('x;', lexer=lexer)}")
    print("  yacc/PLY обирає правило, що стоїть РАНІШЕ у граматиці (type_name : ID).")
    print("  Reduce/reduce майже завжди означає помилку в граматиці: її треба переписати")
    print("  (у справжньому C це вирішують «lexer hack»: лексер віддає TYPE_NAME замість ID для typedef-імен).")


if __name__ == "__main__":
    sys.exit(main())
