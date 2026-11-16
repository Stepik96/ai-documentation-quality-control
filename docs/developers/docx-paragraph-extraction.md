# Стили абзацев в DOCX

Скрипт выводит стиль и текст каждого непустого абзаца основного тела документа в исходном порядке. Если среди этих абзацев нет встроенного стиля «Заголовок 1», скрипт печатает одно замечание.

Из корня проекта в PowerShell с подготовленной `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install "python-docx>=1.2,<2"
.\.venv\Scripts\python.exe scripts/extract_docx_paragraphs.py scripts/fixtures/with-heading.docx
.\.venv\Scripts\python.exe scripts/extract_docx_paragraphs.py scripts/fixtures/with-bold-text.docx
```

[Документ со стилем «Заголовок 1»](../../scripts/fixtures/with-heading.docx):

```text
[Заголовок 1] Порядок работы
[Обычный] Откройте документ.
[Обычный] Проверьте его оформление.
```

[Документ с полужирным текстом в стиле «Обычный»](../../scripts/fixtures/with-bold-text.docx):

```text
[Обычный] Порядок работы
[Обычный] Откройте документ.
[Обычный] Проверьте его оформление.
Не найден заголовок первого уровня
```
