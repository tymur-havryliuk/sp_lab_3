# Лабораторна 3: синтаксичний аналізатор C на PLY (Lex/YACC для Python)

Конвеєр: **лексер (ply.lex) → LALR(1)-парсер (ply.yacc) → AST → семантичний аналіз →
інтерпретатор AST + трансляція у Python → візуалізація AST у браузері (d3.js)**.

## Запуск

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # один раз

.venv/bin/python main.py examples/01_factorial.c        # AST, діагностика, виконання, Python у build/
.venv/bin/python main.py examples/01_factorial.c --tokens
.venv/bin/python main.py examples/01_factorial.c --python --run-python   # Python-код + його запуск
.venv/bin/python main.py --grammar                      # статистика LALR-автомата
.venv/bin/python main.py --web --port 8080              # http://localhost:8080 (без --port — 8000)
.venv/bin/python theory/conflicts_demo.py               # демо shift/reduce та reduce/reduce
.venv/bin/python -m unittest discover tests             # тести
```

## Структура

| Файл | Що робить |
|---|---|
| `cc/lexer.py` | токени, регулярні вирази, ключові слова, коментарі |
| `cc/parser.py` | граматика C, таблиця пріоритетів, побудова AST, відновлення після помилок |
| `cc/ast_nodes.py` | класи вузлів AST |
| `cc/semantic.py` | таблиця символів, області видимості, перевірка типів |
| `cc/interpreter.py` | виконання програми обходом AST |
| `cc/codegen_python.py` | трансляція AST → Python |
| `cc/python_runner.py` | запуск згенерованого Python окремим процесом |
| `cc/ast_export.py` | AST → JSON (для d3) і текстове дерево |
| `cc/compiler.py` | конвеєр усіх етапів |
| `server.py` | HTTP-сервер: `/api/compile`, `/api/run-python`, `/api/grammar`, `/api/examples`, статика |
| `web/index.html`, `web/app.css` | розмітка та стилі веб-інтерфейсу |
| `web/app.js` | редактор CodeMirror, схема конвеєра, вкладки, запуск згенерованого Python |
| `web/ast-tree.js` | інтерактивне дерево AST на d3.js |
| `web/grammar.js` | вкладка «Граматика»: пріоритети й правила BNF |
| `theory/conflicts_demo.py` | демонстрація конфліктів для теоретичних питань |
| `build/parser.out` | згенерований PLY опис усіх станів LALR-автомата |

Підтримувана підмножина C: `int`, `float`, `double`, `char`, `void`; глобальні й локальні змінні,
одновимірні масиви з ініціалізаторами, рядки як `char[]`; функції, прототипи, рекурсія;
`if/else`, `while`, `do-while`, `for`, `break`, `continue`, `return`; усі арифметичні,
логічні, побітові оператори, порівняння, `?:`, `++/--`, усі складені присвоєння
(`+= -= *= /= %= &= |= ^= <<= >>=`), `sizeof`, приведення типів;
`printf`, `puts`, `putchar`, `abs`, `fabs`, `sqrt`, `pow`.
