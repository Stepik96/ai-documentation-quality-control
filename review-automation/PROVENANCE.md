# PR-Agent: происхождение адаптации

Исследован [The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent),
ревизия `a8c604794ddb5766dc3fa674cbb64aac6f9f509f` (05.11.2026).
README называет проект community-maintained; это не hosted Qodo.
Прочитаны README, AGENTS.md, LICENSE, reviewer, settings, prompts,
additional_configurations и LiteLLM handler. Upstream AGENTS относится к разработке
самого PR-Agent; его команды uv и стек не переносятся на наш проект.

| Источник upstream | Что использовано | Изменение для команды |
|---|---|---|
| `pr_agent/settings/pr_reviewer_prompts.toml`, `pr_review_prompt.system` | Конкретные ошибки из diff, условия возникновения, отказ от style-nits, недоверенность PR | Фрагмент реально загружается контроллером; добавлены русские правила продукта |
| Тот же prompt, `TicketCompliance` | Разделение выполненных/невыполненных/непроверенных критериев | Явные строки критериев с ID, evidence и remaining в JSON Schema |
| `pr_agent/settings/configuration.toml`, `[pr_reviewer]` | `require_tests_review`, `require_security_review`, `require_ticket_analysis_review`, `extra_instructions` | Семантика перенесена в rules.md и проверки проекта; Dynaconf не запускается |
| Там же, `persistent_comment`, `persistent_finding_state` | Повторное review и предыдущие замечания | SQLite, маркер результата, стабильные finding ID; одно formal review на версию контекста |
| `pr_agent/tools/pr_reviewer.py` | Сбор контекста → анализ → проверка ответа → публикация | Разделены Codex analyzer и Python gate/publisher, без агентского исправления кода |
| `docs/docs/usage-guide/additional_configurations.md` | Раздельные настройки и ограничения публикации | Локальная policy, dry-run по умолчанию, согласие привязано к hash |

Постоянный комментарий PR-Agent здесь не реализован буквально: используется formal
review с идемпотентным маркером. Копируется принцип учёта предыдущих результатов,
а не обещание функциональной эквивалентности PR-Agent.
Полный prompt и configuration.toml сохранены без изменения; configuration.toml —
reference, не активный конфиг. Исполняется только явно извлекаемый фрагмент prompt.
Jinja/TicketCompliance Pydantic классы не исполняются и не импортируются.

Канонические материалы на зафиксированной ревизии:

- [Reviewer prompt](https://github.com/The-PR-Agent/pr-agent/blob/a8c604794ddb5766dc3fa674cbb64aac6f9f509f/pr_agent/settings/pr_reviewer_prompts.toml)
- [Configuration](https://github.com/The-PR-Agent/pr-agent/blob/a8c604794ddb5766dc3fa674cbb64aac6f9f509f/pr_agent/settings/configuration.toml)
- [Reviewer implementation](https://github.com/The-PR-Agent/pr-agent/blob/a8c604794ddb5766dc3fa674cbb64aac6f9f509f/pr_agent/tools/pr_reviewer.py)
- [LiteLLM handler](https://github.com/The-PR-Agent/pr-agent/blob/a8c604794ddb5766dc3fa674cbb64aac6f9f509f/pr_agent/algo/ai_handlers/litellm_ai_handler.py)
- [MIT License](https://github.com/The-PR-Agent/pr-agent/blob/a8c604794ddb5766dc3fa674cbb64aac6f9f509f/LICENSE)

В README пример локального PR-Agent использует OPENAI_KEY; reviewer вызывает
LiteLLMAIHandler. Документированного backend для `codex login`/ChatGPT Plus в
исследованных материалах не найдено. Отсутствие подтверждения не выдаётся за
универсальное доказательство отсутствия любого будущего backend.
Выбранный вариант — адаптация лицензированных материалов, НЕ прямая интеграция.

MIT License с Copyright (c) 2026 The PR Agent находится в `vendor/pr-agent/LICENSE`
и должна оставаться рядом с копиями/существенными частями материалов.
