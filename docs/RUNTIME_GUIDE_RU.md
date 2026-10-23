# Поиск по перепискам: исполняемый offline-срез P1

Рабочий локальный CLI: синтетические экспорты ChatGPT, Telegram, WhatsApp и EML → SQLite с исходными байтами и наблюдаемыми ревизиями → лексический поиск → точный текст, контекст и первоисточник в JSON.

Нет внешних зависимостей, сетевых запросов, моделей, платных сервисов, ключей и подключений аккаунтов. Нужен Python 3.10+ с SQLite FTS5. Проверено на Python 3.12.14 и SQLite 3.53.1.

## Запуск

Из корня репозитория:

```sh
python demo.py
python -m unittest discover -s tests -v
```

Demo создаёт временный архив, импортирует четыре fixtures, ищет «аренда», открывает один первоисточник, проверяет повторный импорт и удаляет временный архив после завершения. Отчёт остаётся в reports/demo-result.json. Fixtures полностью синтетические, адреса принадлежат example.invalid.

Собственные команды для проверки на этих же fixtures:

```sh
python runtime.py --db sample.sqlite --owner demo import fixtures/telegram.json --format telegram --account synthetic --conversation sample
python runtime.py --db sample.sqlite --owner demo search аренда
python runtime.py --db sample.sqlite --owner demo coverage
python runtime.py --db sample.sqlite --owner demo view RECORD_ID_FROM_SEARCH
```

`view` возвращает точный полный текст записи, указатель в исходном экспорте, content hash, исходный blob hash, историю наблюдений и соседние записи. `archive://` — локатор записи этого архива, не обещанная внешняя веб-ссылка. Исходные bytes сохранены в SQLite без изменения; поле raw_source в JSON — только UTF-8 preview с заменой невалидных символов.

## Что действительно реализовано

- Telegram: один JSON чат с messages, текстовые rich segments, reply IDs, stable message IDs.
- ChatGPT: массив conversations с mapping; все экспортированные текстовые узлы, включая ветки, без угадывания активной ветки.
- WhatsApp: один явно заданный текстовый профиль DD/MM/YYYY, HH:MM - Author: text, продолжение сообщений на новых строках. Другие локали не обещаются.
- EML: stdlib MIME parser, text/plain, Message-ID, From, Date; HTML-only отклоняется.
- Импорт атомарен, повтор той же записи не размножает архив; старая уже наблюдавшаяся версия не откатывает последнюю.
- SQLite FTS5 unicode61, точные токены в режиме AND, результаты по BM25; текст не исполняется.
- Coverage всегда partial/unknown: экспорт не доказывает полноту сервиса. Неполнота и пропуски медиа видны даже при пустом ответе.
- ZIP bundle без распаковки на диск; проверяются traversal, symlinks, шифрование, nested archives, размеры, ratio, повторные/неучтённые пути; все члены валидируются до транзакции.
- KnowledgeBackend Protocol отделяет search/view/coverage от будущего backend. Никакой новый RAG, WeKnora deployment или векторный индекс не создаётся.

## Границы безопасности и достоверности

Это single-owner local CLI, не сервер. `--owner` — consistency guard архива, не аутентификация человека. Тот, кто может читать SQLite-файл, видит его содержимое; шифрования и защиты от владельца OS нет. Не выставлять CLI/БД в сеть. Права filesystem и резервные копии принадлежат оператору. Пилот предназначен для синтетики, реальные архивы здесь не подключены и не проверены.

Контекст упорядочен по первому наблюдению при импорте, а не по доказанной хронологии источника. Ревизии — последовательность наблюдений, не аттестованная source-version. Неизвестные старые версии, ранее не импортированные, могут выглядеть новым наблюдением: authoritative conflict resolution ещё не реализован. Ключ WhatsApp дата+автор+порядковый номер эвристический, не provider ID; при перестановке сообщений с одинаковым временем нужна проверка. Исчезновение записи из нового экспорта не удаляет её. Live sync, deletion/revocation, purge, coverage полноты и multi-user ACL не реализованы.

Смыслового поиска, stemming, исправления опечаток, ASR/OCR, media retrieval и LLM synthesis нет. Пользовательские слова с формой «аренда» и «аренды» не обязаны совпасть. No-match означает только отсутствие совпадения в импортированном охвате.

Ограничения пилота: 8 MiB на файл/ZIP-член, 24 MiB ZIP и распакованного суммарного содержимого, 100 членов, compression ratio ≤100, 10 000 записей в файле, 100 000 символов на сообщение, 100 результатов поиска.

## ZIP manifest

```json
{"version":1,"entries":[{"path":"telegram.json","format":"telegram","account":"synthetic","conversation":"sample"}]}
```

Manifest и все перечисленные файлы лежат в ZIP. Неперечисленные файлы отклоняются. Для Telegram/ChatGPT conversation берётся из фактического экспорта; label применяется к WhatsApp/EML и пустому импорту. Архивы не загружаются никуда.

## Проверка и следующий шаг

28 unittest сценариев: 4 формата, exact viewer, дубликаты, изменения, reorder rollback regression, first-observed context, scope mismatch, malformed schema, unknown timezone, empty result/coverage, inert injection, ZIP safety/atomicity. Набор можно воспроизвести командой выше.

Дальше: согласованный реальный export-profile contract, улучшение source order/revision attestation, затем заменяемый hybrid backend. Подключение аккаунта не вытекает из запуска этого demo. Лицензия не выбрана: публичная доступность исходников не означает open-source лицензию.

## Дополнение: адаптер connector_evidence

Нейтральный импорт сохранённых ответов read-only коннектора. Сохраняет source message ID, conversation ID, авторскую роль, исходные created/updated timestamps, HTTPS URL, text offsets и evidence_kind (complete_message / partial_message / search_excerpt). content_omitted не индексируется и добавляет явный coverage gap. Частичный результат нельзя пометить полным. Этот импорт не подключается к сервису самостоятельно и не создаёт credentials.

Формат включён в --format connector_evidence. Пример схемы находится в tests/test_connector_evidence.py и содержит только вымышленные данные example.invalid. Полный набор после дополнения: 28 тестов. В комплект входят только синтетические данные.
