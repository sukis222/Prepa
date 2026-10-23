# Запуск Prepa через Podman Compose

Нужны Podman и podman-compose. Они устанавливаются на macOS, не в Python .venv.
Для установки через Homebrew: `brew install podman podman-compose`.
Первичная настройка: `podman machine init --cpus 2 --memory 4096 --disk-size 30`,
затем `podman machine start`. Podman запускает Linux VM; после её остановки
запустите VM перед Compose. Docker и Colima не нужны.

## Одна команда запуска

В корне проекта создайте `.env` по `.env.example` и заполните токен, список доступа
(либо `*`) и POSTGRES_PASSWORD. Затем:

```bash
podman compose up --build -d
```

Для демосценария добавьте `PREPARATION_MODE=demo` в `.env` и повторите команду запуска.
Это включает тестовые TXT-результаты без LLM и PDF; `/result` выдаёт их повторно.

PostgreSQL проходит healthcheck, после чего бот применяет недостающие миграции
и начинает polling. Процесс работает непривилегированным пользователем внутри
контейнера. `.env` и резервные копии не попадают в образ. Сервис PostgreSQL не
публикует порт на хост, поэтому локальная PostgreSQL может существовать отдельно.

Compose передаёт боту PGHOST=postgres и PGDATABASE/PGUSER/PGPASSWORD из POSTGRES_*
настроек. DATABASE_URL из `.env` используется только при локальном запуске Python.
Изменение POSTGRES_PASSWORD у уже созданного volume само по себе не меняет пароль
роли в БД: согласованно измените пароль роли и настройки подключения.

```bash
podman compose ps
podman compose logs --tail=50 bot
podman compose restart
podman compose down
podman compose up -d
```

Проект имеет стабильное имя `prepa`. Данные лежат в именованном volume
`prepa_postgres_data`, вне файловой системы контейнера. `restart`, `down` и
пересоздание контейнеров сохраняют volume. `podman compose down -v`, ручное удаление
volume или удаление VM Podman удалят данные; это не обычный способ перезапуска.
Restart policy `unless-stopped` действует, когда VM Podman работает.

Один токен Telegram должен использовать только один poller. Перед переключением
с Python на Compose остановите локальный процесс бота. PostgreSQL можно оставить
работать, но новые записи контейнерного бота попадут уже в контейнерную БД.

## Перенос существующей БД

Локальная БД и Podman-volume — разные хранилища. Не переносите каталог PostgreSQL
между macOS и Linux; используйте логический `pg_dump`/`pg_restore` той же версии.
Перед финальным dump остановите старый бот, чтобы снимок не отстал от новых записей.
Сохраняйте dump только в закрытой папке `output/backups/`, исключённой из Git.

1. Поднимите только БД: `podman compose up -d --wait postgres`.
2. Убедитесь, что целевая БД пустая. Не восстанавливайте поверх существующих данных.
3. Снимите custom-format dump локальной БД через `pg_dump -Fc --no-owner --no-acl`.
   Пароль передавайте через окружение или `.pgpass`, не в командной строке.
4. Восстановите dump в контейнере:

```bash
podman compose exec -T postgres sh -c \
  'exec pg_restore --exit-on-error --single-transaction --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < output/backups/prepa.dump
podman compose up --build -d
```

Исходную локальную БД и dump сохраните до проверки переноса. После переключения
источником актуальных данных становится Podman-volume. Проверяйте не только число
учеников/запросов, но и содержимое записей и сессий. Для проверки сохранности
остановите бот, сравните контрольные суммы таблиц до и после пересоздания postgres,
а затем запустите бот снова. Не выводите содержимое ученических таблиц в общий лог.

Volume защищает от пересоздания контейнера, но не заменяет резервные копии.
