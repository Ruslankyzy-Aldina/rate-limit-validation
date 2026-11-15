from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(r"C:\Users\Admin\Desktop\Учеба\work\slowapi\rate-limit-validation")
REFERENCE = Path(r"C:\Users\Admin\Desktop\Учеба\work\docs\Rate_Limiting_Report_Edited.docx")
OUTPUT = ROOT / "Rate_Limiting_Report_Final.docx"


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def borders(table, color="D9D9D9"):
    tbl_pr = table._tbl.tblPr
    tbl_borders = tbl_pr.first_child_found_in("w:tblBorders")
    if tbl_borders is None:
        tbl_borders = OxmlElement("w:tblBorders")
        tbl_pr.append(tbl_borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = tbl_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tbl_borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), color)


def set_cell(cell, text, bold=False, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(9)
    if color:
        run.font.color.rgb = RGBColor(*color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    borders(t)
    for i, h in enumerate(headers):
        set_cell(t.rows[0].cells[i], h, True, (255, 255, 255))
        shade(t.rows[0].cells[i], "1F4E78")
    for r_i, row in enumerate(rows):
        cells = t.add_row().cells
        for i, value in enumerate(row):
            set_cell(cells[i], value)
            if r_i % 2:
                shade(cells[i], "F2F6FA")
    if widths:
        for row in t.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def heading(doc, text, level=1):
    p = doc.add_paragraph(text, style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    return p


def para(doc, text="", bold_lead=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.08
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


doc = Document(str(REFERENCE))
body = doc._element.body
for child in list(body):
    if child.tag != qn("w:sectPr"):
        body.remove(child)

section = doc.sections[0]
section.top_margin = Inches(0.7)
section.bottom_margin = Inches(0.65)
section.left_margin = Inches(0.8)
section.right_margin = Inches(0.8)

styles = doc.styles
styles["Normal"].font.name = "Aptos"
styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
styles["Normal"].font.size = Pt(10.5)
for name, size in (("Title", 20), ("Heading 1", 14), ("Heading 2", 11.5)):
    st = styles[name]
    st.font.name = "Aptos Display" if name == "Title" else "Aptos"
    st._element.rPr.rFonts.set(qn("w:eastAsia"), st.font.name)
    st.font.size = Pt(size)
    st.font.color.rgb = RGBColor(0, 0, 0)

title = doc.add_paragraph("Исследование rate limiting для FastAPI", style="Title")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph("Сравнение slowapi, pyrate-limiter и throttled-py на Redis, Valkey и DragonFly")
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.runs[0].italic = True
sub.runs[0].font.size = Pt(11)
date = doc.add_paragraph("Финальный отчёт 15 ноября 2026 года")
date.alignment = WD_ALIGN_PARAGRAPH.CENTER
date.runs[0].font.size = Pt(9)

heading(doc, "Аннотация", 1)
para(doc, "В отчёте приведены результаты запуска трёх реальных FastAPI-интеграций с Redis-compatible хранилищами. В отличие от выводов только по документации, все основные утверждения проверены кодом проекта и воспроизводимыми тестами: 20 параллельных запросов, остановка хранилища во время работы и подмена X-Forwarded-For.")
para(doc, "Главный результат: все три библиотеки ограничивают конкурентную серию одинаково — 5 ответов 200 и 15 ответов 429. При отказе хранилища slowapi и pyrate-limiter возвращают 500 из-за необработанного ConnectionError, а throttled-py возвращает 503 благодаря собственной FastAPI-обработке StoreUnavailableError.", bold_lead="Главный результат: ")

heading(doc, "1 Цель и методика", 1)
para(doc, "Цель исследования — проверить не заявленные возможности библиотек, а фактическое поведение приложений с настоящими backend-сервисами. Для всех лимитеров использовался лимит 5 запросов в минуту. Контейнеры запускались через docker-compose.")
table(doc, ["Компонент", "Версия или адрес", "Назначение"], [
    ("slowapi", "0.1.10", "FastAPI-декоратор поверх limits"),
    ("pyrate-limiter", "4.5.1", "RedisBucket и StateBucket"),
    ("throttled-py", "3.5.0", "Async FastAPI Limiter и RedisStore"),
    ("Redis", "localhost:6381", "Redis 7"),
    ("Valkey", "localhost:6382", "Valkey 8.1.10"),
    ("DragonFly", "localhost:6383", "Redis-compatible DragonFly"),
], [1.8, 1.7, 3.8])
para(doc, "Полный запуск выполняется командой .\\tests\\run_all.ps1. Скрипт совместим с Windows PowerShell 5.1, очищает выделенную тестовую DB между сценариями, запускает приложение, проводит проверки и восстанавливает остановленный контейнер.")

heading(doc, "2 Сверка утверждений с исходным кодом", 1)
para(doc, "Факты из внешних ссылок были сверены не только с документацией, но и с установленными пакетами в .venv и исходным кодом проекта. Ниже приведены проверяемые утверждения и результат сверки.")
table(doc, ["Утверждение", "Проверка исходного кода", "Вывод"], [
    ("throttled-py имеет RedisStore и FastAPI integration", "throttled.asyncio.store.RedisStore; throttled.asyncio.contrib.fastapi.Limiter", "Подтверждено"),
    ("throttled-py переводит отказ store в 503", "Limiter обрабатывает StoreUnavailableError и создаёт HTTPException(503)", "Подтверждено"),
    ("pyrate-limiter использует RedisBucket для sliding log", "RedisBucket.init загружает Lua script и хранит bucket в Redis", "Подтверждено"),
    ("pyrate-limiter использует RedisStateStore для token bucket", "StateBucket с TokenBucket и RedisStateStore", "Подтверждено"),
    ("slowapi может подавлять ошибки backend", "В приложении явно заданы swallow_errors=False и in_memory_fallback_enabled=False", "В этой конфигурации ошибки не подавляются"),
], [2.6, 3.2, 1.5])
para(doc, "Использованные первичные источники: github.com/laurentS/slowapi; github.com/vutran1710/PyrateLimiter; github.com/ZhuoZhuoCrayon/throttled-py; throttled-py.readthedocs.io/en/latest/contrib/fastapi.html. Ссылки в исходном документе с utm_source=chatgpt.com заменены на прямые ссылки на репозитории и документацию.")

heading(doc, "3 Реализация тестового приложения", 1)
para(doc, "В репозитории находятся три отдельных приложения: app/slowapi_app.py, app/pyrate_limiter_app.py и app/throttled_app.py. Общие маршруты — /health и /limited. Для Valkey приложения, использующие redis-py, преобразуют схему valkey:// в redis://, поскольку Redis-клиент принимает Redis URL scheme, а сам Valkey говорит по Redis-протоколу.")
para(doc, "Тесты и orchestration находятся в tests/run_matrix.ps1 и tests/run_all.ps1. Проект, docker-compose и инструкции опубликованы в репозитории https://github.com/Ruslankyzy-Aldina/rate-limit-validation.")

heading(doc, "4 Результаты экспериментов", 1)
heading(doc, "4.1 Параллельные запросы", 2)
para(doc, "Для каждой из девяти комбинаций отправлено 20 одновременных запросов к /limited. Перед серией тестовая DB очищалась.")
table(doc, ["Лимитер", "Redis", "Valkey", "DragonFly"], [
    ("slowapi", "5×200; 15×429", "5×200; 15×429", "5×200; 15×429"),
    ("pyrate-limiter", "5×200; 15×429", "5×200; 15×429", "5×200; 15×429"),
    ("throttled-py", "5×200; 15×429", "5×200; 15×429", "5×200; 15×429"),
], [1.8, 1.8, 1.8, 1.8])
para(doc, "Результат показывает, что в проверенной конфигурации все три интеграции атомарно ограничивают конкурентный доступ через Redis-compatible backend.")

heading(doc, "4.2 Остановка хранилища во время работы", 2)
table(doc, ["Лимитер", "Redis", "Valkey", "DragonFly", "После восстановления"], [
    ("slowapi", "500", "500", "500", "PONG"),
    ("pyrate-limiter", "500", "500", "500", "PONG"),
    ("throttled-py", "503", "503", "503", "PONG"),
], [1.6, 1.0, 1.0, 1.2, 1.5])
para(doc, "HTTP 500 — не код, возвращённый Redis. Это результат необработанного исключения подключения, которое FastAPI/Uvicorn превращает в Internal Server Error. Для slowapi причина усилена явными настройками без подавления ошибок и без in-memory fallback. Pyrate-limiter также не регистрирует обработчик redis.exceptions.ConnectionError. Throttled-py перехватывает StoreUnavailableError и возвращает контролируемый 503 с detail Rate limit store unavailable.")

heading(doc, "4.3 Подмена X Forwarded For", 2)
table(doc, ["Лимитер", "5 запросов с адресом A", "6-й запрос с адресом B", "Интерпретация"], [
    ("slowapi", "200, 200, 200, 200, 200", "200", "Uvicorn с proxy headers использовал новый forwarded key"),
    ("pyrate-limiter", "200, 200, 200, 200, 200", "429", "Текущий код ключевал по request.client.host"),
    ("throttled-py", "200, 200, 200, 200, 200", "200", "FastAPI key function использовала адрес клиента"),
], [1.6, 2.0, 1.3, 2.8])
para(doc, "Запуск slowapi с --no-proxy-headers дал 429 для шестого запроса, что подтверждает влияние доверия к proxy headers. Ни одна библиотека не должна принимать X-Forwarded-For от произвольного прямого клиента: в production forwarded headers должны обрабатываться только от доверенного reverse proxy.")

heading(doc, "5 Сравнение и выводы", 1)
table(doc, ["Критерий", "slowapi", "pyrate-limiter", "throttled-py"], [
    ("Интеграция", "Простой декоратор", "Ручной вызов limiter", "Async-декоратор"),
    ("Алгоритм в тесте", "moving-window", "sliding log и token bucket", "token bucket"),
    ("Отказ backend", "500", "500", "503"),
    ("Результат concurrency", "5/15", "5/15", "5/15"),
    ("Особенность", "Минимум кода", "Выбор алгоритма", "Контролируемая ошибка 503"),
], [1.7, 1.7, 2.0, 1.7])
para(doc, "Для простого FastAPI-лимита удобен slowapi. Pyrate-limiter полезен, когда требуется явно выбирать алгоритм и работать с bucket API. Throttled-py выделяется готовой async FastAPI-интеграцией и корректным статусом 503 при недоступности хранилища. В production для любой библиотеки следует отдельно определить политику отказа, мониторинг backend и доверенные proxy headers.")

heading(doc, "6 Воспроизводимость", 1)
para(doc, "1. Запустить Docker Desktop.\n2. В каталоге проекта выполнить docker compose up -d.\n3. Активировать .venv и установить requirements.txt.\n4. Выполнить .\\tests\\run_all.ps1.\n5. Прочитать отчёт в README.md и этот документ.")
para(doc, "GitHub: https://github.com/Ruslankyzy-Aldina/rate-limit-validation")

heading(doc, "7 Заключение", 1)
para(doc, "Экспериментальная матрица подтвердила работу всех трёх лимитеров на Redis, Valkey и DragonFly. Наиболее полезная находка — различие политики отказа: необработанный ConnectionError даёт HTTP 500, а явная интеграционная обработка даёт HTTP 503. Это поведение определяется не самим Redis-compatible хранилищем, а настройками и исходным кодом FastAPI-интеграции.")

doc.core_properties.title = "Исследование rate limiting для FastAPI"
doc.core_properties.subject = "Сравнение slowapi, pyrate-limiter и throttled-py"
doc.core_properties.author = ""
doc.save(str(OUTPUT))
print(OUTPUT)
