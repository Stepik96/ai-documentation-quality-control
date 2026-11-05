# Проверка 05.11.2026

Команда: `python -m unittest discover -s review-automation/tests -v` из рабочего каталога.
Python 3.12.7. Пройдено 36 тестов, ошибок 0. Полный результат воспроизводим локально.
Это тесты управляющей логики; модельные выводы и GitHub API в них имитируются.

| Обязательный сценарий | Проверка | Результат |
|---|---|---|
| Корректное изменение | correct_documentation + full_local_cycle | APPROVE в разрешающей тестовой policy; dry-run, ни одной записи в GitHub |
| Подтверждённая ошибка | confirmed_bug | REQUEST_CHANGES как локальное решение |
| Невыполненный пункт | unfulfilled_task | REQUEST_CHANGES |
| Противоречие документации | documentation_contradiction | REQUEST_CHANGES при подтверждённом finding |
| Нет требований | missing_requirements_for_behavior | HUMAN |
| Новые коммиты | new_commit_rechecks, commit_during_analysis, wrong_head | Повторная проверка; устаревший результат отклонён |
| Исправление найденной проблемы | previous_finding_fix | Предыдущий finding передан следующему review; блокер снят по новому ответу |
| Падение тестов | failed_test, absent_ci, duplicate_ci_context | Положительное решение запрещено |
| Некорректный ответ/сбой агента | invalid_agent_response, invalid_response_no_publication, cli_nonzero | Публикаций нет |
| Повтор без дублей | full_local_cycle_no_duplicate, publish_and_retry_after_lost_local_state | Одна публикация в FakeGitHub, повторный POST не отправлен |
| Правила автоматизации внутри PR | rule_change_inside_pr, renaming_sensitive_file | HUMAN |
| Недоступна авторизация/лимит | no_credentials, agent_error_quota_auth_bounded | Остановка; максимум две попытки того же контекста |
| Тайм-аут | timeout_fails_closed | Нет решения и публикации |
| Безопасность CLI-адаптера | stdin_schema_and_no_github_credentials | Проверены stdin, upstream prompt, schema, тайм-аут, отсутствие GitHub/API ключей в env |
| Неверная строка/критерий | invalid_line, invented_criteria | Ответ отклонён |
| Изменение main/задачи | base_changes_fingerprint, issue_edit_changes_fingerprint | Контекст меняется, старый ответ не подходит |
| Draft | draft_skipped | Не проверяется |
| Fork/неизвестный автор | fork, unknown_author | HUMAN; код не исполняется |
| Остановка во время анализа | stop_during_analysis | Нет публикации |
| Изменение policy | policy_changed_invalidates_consent | Публикация блокируется |
| Автослияние | merge_always_disabled | Режим отклонён до сетевой записи |

Документальное противоречие и реальная ошибка здесь задаются фиктивным ответом
агента: тест подтверждает реакцию gate, а не обнаружение моделью. Исправление
finding также имитируется; качество выводов модели нужно проверить отдельно.
Mock test публикации не создаёт real PR и не отправляет сообщений команде.

Реальные проверки:

- GitHub-плагин: получены метаданные приватного репозитория, ветки, обе структуры,
  документация main и API-черновик develop, список открытых PR (пуст).
- В дереве main нет workflows/AGENTS.md/приложения. Endpoint actions/workflows
  отклонён allowlist самого плагина, это не успешная проверка настроек Actions.
- Обе ветки `protected=false`. Rulesets: HTTP 403 с требованием тарифа/публичности.
- Установленный Codex CLI: 0.144.6; проверены exec help и features list.
- `codex login status`: Not logged in. Официальный способ автоматизации прочитан.
- Git HTTPS из терминала: соединение недоступно. Локального GitHub token нет.
- `controller.py doctor`: Python/Codex доступны, GitHub token отсутствует,
  mode dry-run, merge_available false.

Не выполнены реальные сквозные испытания Codex → GitHub review, security smoke-test
авторизованного CLI, реальные retry после потерянного ответа GitHub, CI workflow
на сервере и merge. Причины: отсутствует CLI login, отдельная GitHub identity,
контролируемый тестовый репозиторий и подтверждённая защита main.
Автопубликацию до этих испытаний не включать. Реальные review модели требуют
проверки на позитивном и негативном контролируемом примере, не только schema smoke.

Приложение, бизнес-тесты, сборка, база данных и ML-качество: недоступны, потому что
реализация приложения ещё не появилась. Добавленный CI проверяет только контроллер.
