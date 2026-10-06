# Translation Studio

Автор — [M2us](https://github.com/M2us). Проект распространяется по [лицензии MIT](LICENSE); при распространении сохраняются уведомление об авторстве и текст лицензии. У сторонних зависимостей свои лицензии.

Версия 1.0 — первый выпуск, 6 октября 2026 года. Изменения и ограничения описаны в [CHANGELOG.md](CHANGELOG.md).

[English](README.md) · [Руководство пользователя](Docs/UserGuide.ru.md)

**[Скачать portable 1.0 для Windows](https://github.com/M2us/translation-studio/releases/download/v1.0/Translation-Studio-Windows-Portable.zip)** · [Все выпуски](https://github.com/M2us/translation-studio/releases) · [SHA-256](https://github.com/M2us/translation-studio/releases/download/v1.0/Portable-SHA256.txt)

Автоматические архивы GitHub **Source code** содержат исходники; для запуска скачивайте portable ZIP.

Приложение Windows для сравнения оригинала и перевода игр. Текст редактируется в общих JSON-каталогах, которые читает и игровой сборщик. Вкладки, ограничения, изображения, озвучка, связи и кнопки сборки задаются в `Translation/project.json` внутри игры.

Распакуйте всю portable-папку и запустите `TranslationStudio.exe`. Отдельный Python для готовой сборки не нужен. Откройте подготовленный проект или скопируйте учебный пример в свою папку. Примеры не содержат ROM и не являются переводами реальных игр.

Основной язык проекта и технической документации — английский. Русский интерфейс и руководство — дополнительная локализация. Тема и язык запоминаются автоматически; первый запуск использует английский.

Карта документации — [Docs/README.md](Docs/README.md). Подключение игр — [IntegrationGuide](Docs/IntegrationGuide.md), разработка — [CONTRIBUTING.md](CONTRIBUTING.md), инструкции ИИ-агентам — [AGENTS.md](AGENTS.md).
