# Проверенные аналоги и способы получения данных

Проверка: 23.10.2026. Это ограниченный обзор релевантных решений, не утверждение, что проверены все репозитории и закрытые чаты интернета. Репозитории/документация прочитаны; кандидаты здесь не установлены, не запущены и не прошли security audit. Наличие функции в README означает заявление разработчика, не испытанную совместимость.

## Аналоги

| Кандидат | Что подтверждено первичным источником | Применение / ограничение |
|---|---|---|
| [Traul](https://github.com/dandaka/traul) | Репозиторий описывает коммуникационный индекс, SQLite FTS5 и embeddings через Ollama; перечисляет Telegram, Gmail, WhatsApp, Slack, Discord, Linear, Claude Code, Markdown; AGPL-3.0 | Самый близкий по предмету кандидат из проверенных. Изучить нормализацию и sync. Не подтверждены требуемые MAX, Mail.ru, Instagram, ChatGPT, mobile always-on, строгая политика удаления/ACL. Не копировать код до лицензионного решения. |
| [WeKnora](https://github.com/Tencent/WeKnora) | Платформа документного knowledge retrieval; README описывает hybrid retrieval, разные storage/model backends | Хороший backend-кандидат, особенно при существующем адаптере. Не считать IM channel равнозначным доступу к полному личному архиву. Версия контракта интеграции и версия текущего upstream могут отличаться. |
| [Onyx](https://github.com/onyx-dot-app/onyx) и [поиск Onyx](https://onyx.app/search) | Enterprise AI/search platform, единый интерфейс к внутренним знаниям | Проверить готовые коннекторы и сложность эксплуатации. Не заявлять покрытие личных российских мессенджеров или бесплатность каждой функции. Разделение лицензий/edition проверить на выбранном commit. |
| [Khoj](https://github.com/khoj-ai/khoj), [документация](https://docs.khoj.dev/) | Self-hostable personal AI и поиск по документам; в репозитории AGPL-3.0 | Полезный UX/reference для личного поиска, но не доказанная универсальная синхронизация всех переписок. |
| [Karakeep](https://github.com/karakeep-app/karakeep) | Self-hostable хранение ссылок, заметок, изображений и поиск | Дополнительный способ сохранить ссылки/публикации, не основной транспорт личных сообщений. Не ставить ещё одну обязательную базу только ради bookmarks. |

findMyChat: код и лицензия не верифицированы; кандидат не используется для архитектурного решения.

## Лицензионная проверка

На дату обзора просмотрены исходные страницы лицензий; это не заключение о совместимости будущей сборки.

- Traul: AGPL-3.0 указана в README/репозитории. Полный текст LICENSE и выбранный commit необходимо проверить до заимствования.
- WeKnora: [LICENSE](https://github.com/Tencent/WeKnora/blob/main/LICENSE) указывает MIT для проекта, с отдельными лицензиями перечисленных third-party компонентов.
- Onyx: [LICENSE](https://github.com/onyx-dot-app/onyx/blob/main/LICENSE) разделяет MIT Expat core и Onyx Enterprise License для ee-каталогов; third-party компоненты сохраняют исходные лицензии. Нельзя называть весь репозиторий MIT.
- Khoj: [LICENSE](https://github.com/khoj-ai/khoj/blob/master/LICENSE) содержит GNU AGPL; README маркирует AGPL-3.0.
- Karakeep: [LICENSE](https://github.com/karakeep-app/karakeep/blob/main/LICENSE) содержит GNU AGPL v3. Условия выбранного release и его зависимостей проверяются отдельно.

Ни один сторонний исходный файл в этот пакет не скопирован. Лицензия будущего оригинального продукта ещё не выбрана; публичная доступность ТЗ не заменяет решение о лицензии кода.

## Уроки и обсуждения

- [Traul Getting Started](https://github.com/dandaka/traul): ссылка Getting Started в README, плюс примеры sync/search/get/embed. Это первичная инструкция автора, ещё не воспроизведённый runbook нашего продукта.
- [Авторское обсуждение Traul](https://www.reddit.com/r/ClaudeCode/comments/1rvort4/i_gave_my_claude_code_agent_a_search_engine/): сигнал, что задача поиска контекста между мессенджерами уже решается. Инженерные характеристики берутся из репозитория, а не комментариев.
- [Авторское обсуждение findMyChat](https://www.reddit.com/r/SideProject/comments/1nij6ar): дополнительный кандидат. Проверка кода не завершена, в shortlist для внедрения не включён.
- [Официальное объяснение экспорта Telegram](https://telegram.org/blog/export-and-more): JSON/HTML, в том числе вложения, экспорт отдельных чатов через Desktop. Это рабочее направление для первого offline среза, а не live-sync.
- [Официальная инструкция Gmail sync](https://developers.google.com/workspace/gmail/api/guides/sync): full/partial sync и push как триггер. Это база для реализации корректных checkpoint, а не урок «подключить бот за пять минут».


## Матрица источников

«Подтверждён маршрут» означает наличие документации, не подключение конкретного аккаунта.

| Источник | Маршрут первой реализации | Что нельзя обещать | Статус |
|---|---|---|---|
| ChatGPT | Разрешённый export → адаптивный parser; доступный поисковый connector как дополнительный путь | Доступ ко всем workspace, вложениям и каждому скрытому тексту; API модели не равен API истории ChatGPT | [Официальный export](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data) проверен; конкретный архив не получен |
| Telegram | Desktop JSON/HTML export; далее отдельно подтверждённый клиентский read-only доступ | Bot API не доказывает доступ к личной истории; отсутствующие/удалённые/секретные чаты не восстанавливаются обещанием | [Экспорт](https://telegram.org/blog/export-and-more) проверен; live не подключён |
| WhatsApp | Пользовательский экспорт текста и медиа; parser с профилями локали и формата | TXT не является полным восстановимым backup; не обещать весь аккаунт, обратный импорт, удалённые сообщения или полную live историю через Business API | [Официальная инструкция](https://faq.whatsapp.com/1180414079177245/?cms_platform=iphone&locale=de_DE) обнаружена; образец нужен для contract test |
| Gmail | Read-only API, initial enumeration + partial history sync | Первый экран/страница не полный архив; истёкшие history cursor требуют resync | [Документация](https://developers.google.com/workspace/gmail/api/guides/sync) проверена |
| Google Drive | Разрешённый read-only connector/API; файлы, экспорт текста, revisions, comments при наличии прав | Shortcuts, shared drives, Docs comments и permission changes требуют собственных тестов; недоступный файл не пустой | API-маршрут требует отдельной проверки контракта и прав; live-коннектора в прототипе нет |
| GitHub | Read-only repository files + issues/PR/discussions; pin commit/revision | Private repo не становится публичным при выдаче; comments не равны merged code | API-маршрут возможен; реализация live-коннектора в этом прототипе отсутствует |
| Mail.ru | IMAP read-only, MIME parser; UIDVALIDITY reconciliation | Mail.ru Почта, Облако и VK — разные коннекторы, не единый полный grant | [Официальная настройка](https://help.mail.ru/mail/login/mailer/) подтверждает IMAP/TLS 993; аккаунт не подключён |
| MAX | Только доказанный разрешённый export/официальный доступ; бот как ограниченный источник, если этого достаточно | Bot API не даёт оснований считать весь личный архив доступным | [Официальная API-документация](https://dev.max.ru/docs-api) описывает ботов. Полный personal-history route не подтверждён |
| Instagram | Доступная выгрузка информации через Accounts Center; импорт выбранных сообщений и медиа после проверки формата | Нельзя обещать все Direct/исчезающие сообщения/сохранённые Reels и их полное видео из одного API | [Meta о скачивании информации](https://about.fb.com/news/2023/10/manage-your-information-across-apps/) подтверждает направление; фактический состав экспорта проверяется на образце |
| VK / Облако Mail / Яндекс | Отдельные capability manifests и permitted exports/API | Принадлежность одному бренду не общий доступ | В scope каталога, adapter audit не выполнен |

## Протокол сравнения перед выбором

1. Зафиксировать upstream commit, лицензию каждого заимствуемого компонента и зависимости; проверить SECURITY/advisories и поддерживаемые версии.
2. Один обезличенный корпус и одинаковые запросы для Traul, существующего knowledge backend и lexical baseline.
3. Измерить recall, цитирование, поиск на русском, cold/warm latency, стоимость, потребление памяти, импорт после crash, обработку edit/delete и потерю checkpoint.
4. Проверить отрицательные сценарии: чужой scope, отозванный доступ, вредоносный архив, prompt injection, пустой/сломанный response.
5. Зафиксировать ADR: adopt / adapt / reject с причинами; отказаться от дополнительного движка, если существующий порт и backend удовлетворяют критериям.

Интернет-обзор не заменяет этот пробный запуск. «Все возможные нюансы» недоказуемы; задача ТЗ — сделать риски явными и проверяемыми, а не скрыть неизвестное обещанием универсальности.
