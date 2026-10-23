# Correspondence Search Prototype

Нейтральный локальный прототип поиска по экспортам переписок. Python standard library + SQLite FTS5. Исполняемый результат: импорт → нормализованный архив с наблюдаемыми ревизиями → лексический поиск → точный текст и контекст.

**Режим по умолчанию: lexical / partial / offline.** По умолчанию это не semantic search и не готовый универсальный поиск по аккаунтам. Нет live sync, моделей, автоматического преобразования вопроса в поисковые термы, сетевых запросов, платных сервисов или подключения аккаунтов. В default CLI запросы задаются вручную; точные токены объединяются AND. Coverage только partial/unknown.

## Быстрый запуск

Python 3.10+ с SQLite FTS5. Внешние Python-пакеты не нужны.

```sh
python demo.py
python -m unittest discover -s tests -v
```

Demo использует только синтетические fixtures четырёх форматов, создаёт временную SQLite-базу, проверяет поиск/просмотр/повторный импорт и удаляет временную базу. Локальный синтетический отчёт появляется в reports/ и не предназначен для commit.

```sh
python runtime.py --db sample.sqlite --owner demo import fixtures/telegram.json --format telegram --account synthetic --conversation sample
python runtime.py --db sample.sqlite --owner demo search аренда
python runtime.py --db sample.sqlite --owner demo coverage
python runtime.py --db sample.sqlite --owner demo view RECORD_ID_FROM_SEARCH
```

## Реализовано

- ChatGPT JSON mapping, Telegram JSON, один профиль WhatsApp TXT, EML text/plain.
- Offline connector_evidence: сохранённые ответы read-only источника с provenance и явными пропусками, но не самостоятельное подключение.
- Exact source viewer, наблюдаемые ревизии, дедупликация и ограниченный безопасный ZIP import.
- 45 синтетических тестов, в том числе опасный ZIP, повтор/правка, пустой результат, неполнота, scope mismatch.
- KnowledgeBackend Protocol для будущей замены поиска; добавлен отдельный экспериментальный [локальный hybrid-адаптер](docs/HYBRID.md). Он требует локальных весов и optional ML-зависимостей, не меняет default CLI и не генерирует ответы. Правильное сообщение не гарантирует правильного ответного фрагмента; similarity не вероятность истины.

## Безопасность и ограничения

Single-owner local CLI. --owner проверяет согласованность, но не удостоверяет человека. SQLite не зашифрована. Не выставлять программу или базу в сеть, не коммитить реальные архивы. Отсутствие результата не доказывает отсутствие сообщения, а content_omitted означает недоступный текст в данном ответе источника, не отсутствие текста в самом чате.

[Privacy and limitations](PRIVACY_AND_LIMITATIONS.md) · [Security](SECURITY.md) · [Подробный CLI guide](docs/RUNTIME_GUIDE_RU.md) · [Changelog](CHANGELOG.md)

## Проектная документация, не готовые функции

[Целевое ТЗ](docs/TECHNICAL_SPEC_RU.md), [prior art и ограничения сервисов](docs/PRIOR_ART_AND_CONNECTORS_RU.md), паспорт коннектора и 30 целевых acceptance scenarios в docs/. Они описывают более широкий будущий продукт. Эти 30 сценариев не равны 45 выполненным unit tests CLI и optional adapter.

## Лицензия

Лицензия оригинального кода пока не выбрана. Исходники публично доступны для ознакомления; проект не заявляется open source, и отдельная лицензия на использование, изменение или распространение здесь не предоставлена. Сторонний исходный код не включён. Стандартные библиотеки Python/SQLite сохраняют собственные условия.
