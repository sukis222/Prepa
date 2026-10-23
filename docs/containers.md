# Запуск Prepa через Compose

Нужны Docker и Docker Compose (на macOS — Docker Desktop).
Вместо Docker можно использовать Podman с podman-compose:
`brew install podman podman-compose`, затем
`podman machine init --cpus 2 --memory 4096 --disk-size 30` и
`podman machine start`. Для Podman замените `docker compose` ниже на `podman compose`.

## Одна команда запуска

В корне проекта создайте `.env` по `.env.example` и заполните токен, список доступа
(либо `*`) и POSTGRES_PASSWORD. Затем:

```bash
docker compose up --build -d
```

Для демосценария добавьте `PREPARATION_MODE=demo` в `.env` и повторите команду запуска.
Это включает один демонстрационный PDF без LLM; `/result` выдаёт их повторно.
Для настоящих задач задайте `PREPARATION_MODE=real`, `OPENROUTER_API_KEY` и бесплатную
`OPENROUTER_MODEL`. В образ установлен XeLaTeX для одного PDF с условиями задач.
Подробности и ограничения источников — в [настройках OpenRouter](openrouter.md).

PostgreSQL проходит healthcheck, после чего бот применяет недостающие миграции
и начинает polling. Процесс работает непривилегированным пользователем внутри
контейнера. `.env` и резервные копии не попадают в образ. Сервис PostgreSQL не
публикует порт на хост, поэтому локальная PostgreSQL может существовать отдельно.

Compose передаёт боту PGHOST=postgres и PGDATABASE/PGUSER/PGPASSWORD из POSTGRES_*
настроек. DATABASE_URL из `.env` используется только при локальном запуске Python.
Изменение POSTGRES_PASSWORD у уже созданного volume само по себе не меняет пароль
роли в БД: согласованно измените пароль роли и настройки подключения.

```bash
docker compose ps
docker compose logs --tail=50 bot
docker compose restart
docker compose down
docker compose up -d
```

Проект имеет стабильное имя `prepa`. Данные лежат в именованном volume
`prepa_postgres_data`, вне файловой системы контейнера. `restart`, `down` и
пересоздание контейнеров сохраняют volume. `docker compose down -v`, ручное удаление
volume или удаление VM Podman удалят данные; это не обычный способ перезапуска.
Restart policy `unless-stopped` действует, когда VM Podman работает.

Один токен Telegram должен использовать только один poller. Перед переключением
с Python на Compose остановите локальный процесс бота. PostgreSQL можно оставить
работать, но новые записи контейнерного бота попадут уже в контейнерную БД.

## Перенос существующей БД

Локальная БД и Compose-volume — разные хранилища. Не переносите каталог PostgreSQL
между macOS и Linux; используйте логический `pg_dump`/`pg_restore` той же версии.
Перед финальным dump остановите старый бот, чтобы снимок не отстал от новых записей.
Сохраняйте dump только в закрытой папке `output/backups/`, исключённой из Git.

1. Поднимите только БД: `docker compose up -d --wait postgres`.
2. Убедитесь, что целевая БД пустая. Не восстанавливайте поверх существующих данных.
3. Снимите custom-format dump локальной БД через `pg_dump -Fc --no-owner --no-acl`.
   Пароль передавайте через окружение или `.pgpass`, не в командной строке.
4. Восстановите dump в контейнере:

```bash
docker compose exec -T postgres sh -c \
  'exec pg_restore --exit-on-error --single-transaction --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < output/backups/prepa.dump
docker compose up --build -d
```

Исходную локальную БД и dump сохраните до проверки переноса. После переключения
источником актуальных данных становится Compose-volume. Проверяйте не только число
учеников/запросов, но и содержимое записей и сессий. Для проверки сохранности
остановите бот, сравните контрольные суммы таблиц до и после пересоздания postgres,
а затем запустите бот снова. Не выводите содержимое ученических таблиц в общий лог.

Volume защищает от пересоздания контейнера, но не заменяет резервные копии.
