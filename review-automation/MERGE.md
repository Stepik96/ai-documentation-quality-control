# Публикация и merge: реализация, ещё не включённая в production

Режимы: dry-run (локально), publish (formal review), merge (formal review + условное слияние).
Текущая policy остаётся dry-run, approved_policy_sha256 пуст. Автоматического включения нет.

Publisher публикует COMMENT / REQUEST_CHANGES / APPROVE с commit_id и уникальным
маркером контекста; после сбоя сначала ищет уже созданное review, предотвращая повтор.
Перед действием повторно собираются PR, версии обеих веток, критерии, CI и обсуждение.

merge_gate.py вызывает PUT /pulls/{number}/merge с ожидаемым head SHA только после:

- APPROVE по всем детерминированным условиям controller.decide;
- независимой GitHub App identity и согласованного hash политики;
- подтверждения strict required status checks, enforcement для admin;
- обязательных approvals, dismiss stale reviews, отсутствия bypass allowances;
- GitHub-enforced conversation resolution;
- совпадения обязательных checks с защищёнными checks;
- отсутствия дополнительных неквалифицированных rulesets;
- включения reviewed base в head и отсутствия перемещения source/target;
- актуального APPROVED этого бота и отсутствия CHANGES_REQUESTED других reviewers;
- clean mergeable_state и открытого non-draft PR в разрешённую ветку.

Гонка base после финального чтения должна блокироваться самим GitHub strict
up-to-date branch protection. Один head SHA в merge API от неё не защищает.
Защита — обязательная предпосылка, а не рекомендация. При ошибке API, неизвестном
состоянии, неподдерживаемой защите или ошибке прав процесс останавливается.
Законченным merge считается только ответ merged=true с SHA.

Категория в начальной policy: только документация вне human_paths. Код, требования,
автоматизация, секреты, инфраструктура и опасные изменения человеку. allowed_authors
пока пуст: список команды должен войти в итоговую согласованную policy.

Для mode=merge App должен дополнительно иметь contents:write (merge endpoint) и
administration:read (проверка защиты); они НЕ выдавались и НЕ запрашиваются в dry-run.
Administration write и обход правил не нужны и не предусмотрены.
Изменение App permissions подтверждает владелец установки в GitHub.

Проверки: 48 тестов всего; merge-тесты имитируют GitHub. Проверены успешный вызов с SHA,
перемещение base, отсутствие защиты, ruleset, чужой Request changes, устаревший
Approve, ошибка API. Это не реальные сквозные испытания GitHub merge и не доказательство
серверного поведения при гонке. До включения нужен отдельный тестовый репозиторий
с соответствующей защитой и пробные formal reviews/merge, включая гонку base.

Прежние утверждения README/VALIDATION «merge не реализован/всегда запрещён» описывают
версию v1; этот документ описывает новый исполнитель. Наличие кода не означает
готовность текущего GitHub-тарифа, защиты и App permissions.

Финальное включение: после реальных испытаний показать результаты и точную policy
пользователю, получить итоговое подтверждение, установить mode и approved_policy_sha256,
затем перезапустить локальную задачу. Без этого реальные PR не публикуются/не сливаются.
