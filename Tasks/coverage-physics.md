# Охват тем задачами по физике

Аудит содержания от 20 ноября 2026 года. Таблицы ниже фиксируют состояние на эту дату.

После аудита все 579 карточек ЕГЭ №01–26 распределены по темам. Тематические TeX обновлены, 65 рубрик получили первые подборки. Текущие привязки и объём переноса находятся в [карте карточек](../.scratch/ege-topic-crosswalk/numbered-topics.json) и [отчёте](../.scratch/ege-topic-crosswalk/report.json). Актуальные ссылки на подборки находятся в [README](../knowledge/README.md#задачи-по-темам).

Эталон — раздел 2 утверждённого кодификатора ЕГЭ-2027 по физике. Названия в таблице сокращены. [Кодификатор, спецификация и демоверсия ФИПИ](https://doc.fipi.ru/ege/demoversii-specifikacii-kodifikatory/2027/fi_11_2027.zip).

В кодификаторе **127 элементов содержания**. По 123 найдена привязка хотя бы к одной задаче, по 4 привязка не подтверждена. В проекте 132 отдельных тематических подборок.

После исходного аудита добавлены **58 подборок** (481 вхождений задач). Из них 40 доведены до десяти, в остальных до цели не хватает 99 карточек.

Проверены текущие TeX по номерам и актуальный манифест тематических подборок. Основания — метки первичных карточек и дополнительные совпадения, подтверждённые по условиям. Код включает несколько понятий, поэтому наличие задачи не означает, что проверены все понятия внутри кода. Общий код раздела не засчитывается по дочерним пунктам.

«Не подтверждено» означает, что в проверенных данных не найдено надёжной привязки. Это может быть реальный пробел или задача с отсутствующей, широкой либо устаревшей меткой. Номера в скобках — позиции внутри файла, а не номера карточек сайта.

| Раздел | Есть привязка | Не подтверждено | Всего |
|---|---:|---:|---:|
| Механика | 36 | 1 | 37 |
| Молекулярная физика и термодинамика | 27 | 1 | 28 |
| Электродинамика, включая оптику | 48 | 2 | 50 |
| Квантовая физика | 12 | 0 | 12 |

## Темы без подтверждённой отдельной практики

- **1.2.1** Инерциальные системы отсчёта, первый закон Ньютона и принцип относительности Галилея.
- **2.2.8** Второй закон термодинамики и необратимость.
- **3.6.9** Фотоаппарат и глаз как оптические системы.
- **3.6.12** Дисперсия света.

Примеры частичного покрытия: №21 (28) проверяет трансформатор при изменении тока от гальванического элемента. Это подтверждает практику по трансформатору, но не по выработке и передаче энергии переменным током. №18 (2) проверяет сохранение частоты электромагнитной волны при преломлении, но не ориентацию векторов в волне. №18 (16, 18) содержит проверяемые утверждения о сравнении диапазонов электромагнитных волн и условии интерференционного максимума.

Примеры подтверждения по условиям: №12 (6, 8, 18) — магнитный поток и ЭДС. Подборка 2.2 (карточки 3464 и 3543) — взаимодействие молекул и пределы применимости модели идеального газа. Подборки 6.4.3 и 6.6.1 (8870, 6204, 6513, 11522) — спектральные линии и уровни водорода. Подборка 6.2.3 (6365, 33055) — давление света.

## Элементы официального кодификатора

| Код | Тема | Тематические подборки | Задачи в банке по номерам |
|---|---|---|---|
| 1.1.1 | Механическое движение, относительность движения и система отсчёта | [1.1.1](../output/topics/task-1-1-1.tex), [1.1.5](../output/topics/task-1-1-5.tex), [1.1.8](../output/topics/task-1-1-8.tex), [1.2.1](../output/topics/task-1-2-1.tex) | — |
| 1.1.2 | Материальная точка, траектория, радиус-вектор, перемещение и путь | — | [№1](../output/fipi-physics/task-01.tex) (18) |
| 1.1.3 | Скорость и сложение скоростей, перемещение и путь по графику скорости | [1.1.5](../output/topics/task-1-1-5.tex) | [№1](../output/fipi-physics/task-01.tex) (2, 5) |
| 1.1.4 | Ускорение материальной точки и его проекции | [1.1.6](../output/topics/task-1-1-6.tex) | [№1](../output/fipi-physics/task-01.tex) (3, 4) |
| 1.1.5 | Равномерное прямолинейное движение | [1.2.1](../output/topics/task-1-2-1.tex) | [№1](../output/fipi-physics/task-01.tex) (10, 14, 16, 17) |
| 1.1.6 | Равноускоренное прямолинейное движение | [1.1.6](../output/topics/task-1-1-6.tex) | [№1](../output/fipi-physics/task-01.tex) (1, 6, 7, 8, 9, …), [№6](../output/fipi-physics/task-06.tex) (3, 4, 5), [№22](../output/fipi-physics/task-22.tex) (2, 3, 4, 5, 29) |
| 1.1.7 | Свободное падение и движение тела, брошенного под углом к горизонту | [1.3.5](../output/topics/task-1-3-5.tex), [1.3.6](../output/topics/task-1-3-6.tex) | [№5](../output/fipi-physics/task-05.tex) (5, 20), [№6](../output/fipi-physics/task-06.tex) (16, 19), [№22](../output/fipi-physics/task-22.tex) (7, 8, 1, 6), [№26](../output/fipi-physics/task-26.tex) (22, 23) |
| 1.1.8 | Движение по окружности, угловая скорость и центростремительное ускорение | [1.4.3](../output/topics/task-1-4-3.tex) | [№6](../output/fipi-physics/task-06.tex) (10), [№22](../output/fipi-physics/task-22.tex) (24), [№26](../output/fipi-physics/task-26.tex) (5, 18) |
| 1.1.9 | Поступательное и вращательное движение твёрдого тела | — | [№26](../output/fipi-physics/task-26.tex) (28) |
| 1.2.1 | Инерциальные системы отсчёта, первый закон Ньютона и принцип относительности Галилея | — | **Не подтверждено** |
| 1.2.2 | Масса и плотность | — | [№20](../output/fipi-physics/task-20.tex) (1) |
| 1.2.3 | Сила, суперпозиция сил и равнодействующая | — | [№6](../output/fipi-physics/task-06.tex) (4) |
| 1.2.4 | Второй закон Ньютона | [1.8.2](../output/topics/task-1-8-2.tex), [1.12.2](../output/topics/task-1-12-2.tex) | [№2](../output/fipi-physics/task-02.tex) (1, 7, 8, 12, 13, …), [№22](../output/fipi-physics/task-22.tex) (19, 25), [№26](../output/fipi-physics/task-26.tex) (5, 10, 12, 13, 14, …) |
| 1.2.5 | Третий закон Ньютона | [1.8.3](../output/topics/task-1-8-3.tex) | [№5](../output/fipi-physics/task-05.tex) (9) |
| 1.2.6 | Всемирное тяготение, сила тяжести и центр тяжести | [1.10.1](../output/topics/task-1-10-1.tex) | [№2](../output/fipi-physics/task-02.tex) (2, 9, 10, 14, 15, …) |
| 1.2.7 | Сила упругости, закон Гука и вес тела | [1.10.1](../output/topics/task-1-10-1.tex), [1.10.4](../output/topics/task-1-10-4.tex) | [№2](../output/fipi-physics/task-02.tex) (3, 5, 17, 18) |
| 1.2.8 | Сухое трение покоя и скольжения | [1.9.2](../output/topics/task-1-9-2.tex) | [№2](../output/fipi-physics/task-02.tex) (4, 11), [№22](../output/fipi-physics/task-22.tex) (18), [№26](../output/fipi-physics/task-26.tex) (16) |
| 1.2.9 | Давление | [1.11.1](../output/topics/task-1-11-1.tex) | [№4](../output/fipi-physics/task-04.tex) (15) |
| 1.3.1 | Момент силы и плечо силы | [1.12.1](../output/topics/task-1-12-1.tex), [1.12.2](../output/topics/task-1-12-2.tex), [1.16.1](../output/topics/task-1-16-1.tex) | [№26](../output/fipi-physics/task-26.tex) (2) |
| 1.3.2 | Центр масс и центр тяжести | [1.12.1](../output/topics/task-1-12-1.tex), [1.12.2](../output/topics/task-1-12-2.tex), [1.13.4](../output/topics/task-1-13-4.tex), [1.16.1](../output/topics/task-1-16-1.tex) | [№22](../output/fipi-physics/task-22.tex) (22, 21), [№26](../output/fipi-physics/task-26.tex) (1) |
| 1.3.3 | Условия равновесия твёрдого тела | [1.13.2](../output/topics/task-1-13-2.tex), [1.13.3](../output/topics/task-1-13-3.tex) | [№4](../output/fipi-physics/task-04.tex) (8, 16), [№24](../output/fipi-physics/task-24.tex) (18, 20, 22, 25), [№26](../output/fipi-physics/task-26.tex) (2, 6, 10, 17, 26, …) |
| 1.3.4 | Закон Паскаля | [1.13.1](../output/topics/task-1-13-1.tex), [1.13.2](../output/topics/task-1-13-2.tex), [1.13.5](../output/topics/task-1-13-5.tex) | [№22](../output/fipi-physics/task-22.tex) (17) |
| 1.3.5 | Гидростатическое давление | [1.13.4](../output/topics/task-1-13-4.tex), [1.13.5](../output/topics/task-1-13-5.tex) | [№4](../output/fipi-physics/task-04.tex) (15, 19), [№5](../output/fipi-physics/task-05.tex) (12), [№6](../output/fipi-physics/task-06.tex) (12), [№22](../output/fipi-physics/task-22.tex) (13, 14, 15, 16, 30) |
| 1.3.6 | Закон Архимеда и условия плавания тел | [1.13.4](../output/topics/task-1-13-4.tex), [1.13.5](../output/topics/task-1-13-5.tex) | [№4](../output/fipi-physics/task-04.tex) (6, 7, 12, 18), [№5](../output/fipi-physics/task-05.tex) (13, 19), [№6](../output/fipi-physics/task-06.tex) (15, 18), [№24](../output/fipi-physics/task-24.tex) (27) |
| 1.4.1 | Импульс материальной точки | [1.14.1](../output/topics/task-1-14-1.tex), [1.14.2](../output/topics/task-1-14-2.tex) | [№3](../output/fipi-physics/task-03.tex) (7, 8, 9, 11) |
| 1.4.2 | Импульс системы тел | [1.14.1](../output/topics/task-1-14-1.tex), [1.14.2](../output/topics/task-1-14-2.tex), [1.14.3](../output/topics/task-1-14-3.tex) | [№3](../output/fipi-physics/task-03.tex) (2) |
| 1.4.3 | Изменение и сохранение импульса | [1.14.1](../output/topics/task-1-14-1.tex), [1.14.3](../output/topics/task-1-14-3.tex), [1.14.4](../output/topics/task-1-14-4.tex), [1.14.5](../output/topics/task-1-14-5.tex), [1.15.8](../output/topics/task-1-15-8.tex) | [№3](../output/fipi-physics/task-03.tex) (1, 19), [№22](../output/fipi-physics/task-22.tex) (9, 10, 12), [№24](../output/fipi-physics/task-24.tex) (16), [№26](../output/fipi-physics/task-26.tex) (4, 8, 9, 11, 13, …) |
| 1.4.4 | Работа силы | [1.15.1](../output/topics/task-1-15-1.tex), [1.15.5](../output/topics/task-1-15-5.tex) | [№3](../output/fipi-physics/task-03.tex) (3, 13), [№6](../output/fipi-physics/task-06.tex) (17) |
| 1.4.5 | Мощность силы | [1.15.2](../output/topics/task-1-15-2.tex) | — |
| 1.4.6 | Кинетическая энергия и теорема о её изменении | [1.15.3](../output/topics/task-1-15-3.tex), [1.15.4](../output/topics/task-1-15-4.tex), [1.15.8](../output/topics/task-1-15-8.tex) | [№3](../output/fipi-physics/task-03.tex) (4, 12), [№5](../output/fipi-physics/task-05.tex) (18) |
| 1.4.7 | Потенциальная энергия в поле тяжести и при упругой деформации | [1.15.1](../output/topics/task-1-15-1.tex), [1.15.5](../output/topics/task-1-15-5.tex), [1.15.6](../output/topics/task-1-15-6.tex) | [№3](../output/fipi-physics/task-03.tex) (5, 15, 16, 17), [№6](../output/fipi-physics/task-06.tex) (20) |
| 1.4.8 | Изменение и сохранение механической энергии | [1.3.5](../output/topics/task-1-3-5.tex), [1.14.4](../output/topics/task-1-14-4.tex), [1.15.1](../output/topics/task-1-15-1.tex), [1.15.3](../output/topics/task-1-15-3.tex), [1.15.5](../output/topics/task-1-15-5.tex), [1.15.6](../output/topics/task-1-15-6.tex), [1.15.7](../output/topics/task-1-15-7.tex), [1.15.8](../output/topics/task-1-15-8.tex) | [№3](../output/fipi-physics/task-03.tex) (6, 14, 18, 20), [№5](../output/fipi-physics/task-05.tex) (6, 8), [№6](../output/fipi-physics/task-06.tex) (6), [№22](../output/fipi-physics/task-22.tex) (26), [№24](../output/fipi-physics/task-24.tex) (16), [№26](../output/fipi-physics/task-26.tex) (3, 8, 11, 15, 18, …) |
| 1.5.1 | Гармонические колебания, их кинематика, динамика и энергия | [1.9.2](../output/topics/task-1-9-2.tex), [1.17.1](../output/topics/task-1-17-1.tex), [1.17.2](../output/topics/task-1-17-2.tex), [1.17.3](../output/topics/task-1-17-3.tex), [1.17.4](../output/topics/task-1-17-4.tex), [1.17.5](../output/topics/task-1-17-5.tex) | [№6](../output/fipi-physics/task-06.tex) (7, 8, 13), [№22](../output/fipi-physics/task-22.tex) (20, 28), [№25](../output/fipi-physics/task-25.tex) (21) |
| 1.5.2 | Период и частота колебаний, математический и пружинный маятники | [1.15.4](../output/topics/task-1-15-4.tex), [1.17.1](../output/topics/task-1-17-1.tex), [1.17.3](../output/topics/task-1-17-3.tex), [1.17.4](../output/topics/task-1-17-4.tex), [1.17.5](../output/topics/task-1-17-5.tex) | [№4](../output/fipi-physics/task-04.tex) (1, 5, 9, 10, 11), [№6](../output/fipi-physics/task-06.tex) (1, 13), [№22](../output/fipi-physics/task-22.tex) (27) |
| 1.5.3 | Вынужденные механические колебания и резонанс | [1.17.5](../output/topics/task-1-17-5.tex) | [№18](../output/fipi-physics/task-18.tex) (8) |
| 1.5.4 | Поперечные и продольные механические волны, скорость и длина волны | [1.18.1](../output/topics/task-1-18-1.tex) | [№4](../output/fipi-physics/task-04.tex) (14) |
| 1.5.5 | Звук и его скорость | [1.18.2](../output/topics/task-1-18-2.tex) | [№4](../output/fipi-physics/task-04.tex) (3, 4, 13, 14, 17, …) |
| 2.1.1 | Модели строения вещества и количество вещества | [2.1.1](../output/topics/task-2-1-1.tex), [2.2](../output/topics/task-2-2.tex), [2.3](../output/topics/task-2-3.tex) | [№10](../output/fipi-physics/task-10.tex) (1) |
| 2.1.2 | Тепловое движение атомов и молекул | [2.1.2](../output/topics/task-2-1-2.tex) | [№7](../output/fipi-physics/task-07.tex) (1) |
| 2.1.3 | Взаимодействие частиц вещества | [2.2](../output/topics/task-2-2.tex) | — |
| 2.1.4 | Диффузия и броуновское движение | — | [№18](../output/fipi-physics/task-18.tex) (5) |
| 2.1.5 | Модель идеального газа в МКТ | [2.1.2](../output/topics/task-2-1-2.tex), [2.1.3](../output/topics/task-2-1-3.tex), [2.2](../output/topics/task-2-2.tex), [2.2.1](../output/topics/task-2-2-1.tex) | [№7](../output/fipi-physics/task-07.tex) (4, 5) |
| 2.1.6 | Связь давления газа со средней кинетической энергией молекул | [2.5.2](../output/topics/task-2-5-2.tex) | [№7](../output/fipi-physics/task-07.tex) (6), [№10](../output/fipi-physics/task-10.tex) (1), [№23](../output/fipi-physics/task-23.tex) (16) |
| 2.1.7 | Абсолютная температура | [2.4.3](../output/topics/task-2-4-3.tex) | [№7](../output/fipi-physics/task-07.tex) (13, 2) |
| 2.1.8 | Связь температуры газа со средней кинетической энергией молекул | [2.3](../output/topics/task-2-3.tex), [2.4.3](../output/topics/task-2-4-3.tex), [2.5.1](../output/topics/task-2-5-1.tex), [2.5.3](../output/topics/task-2-5-3.tex) | [№7](../output/fipi-physics/task-07.tex) (2, 3, 4) |
| 2.1.9 | Уравнение p = nkT | [2.5.4](../output/topics/task-2-5-4.tex), [2.6.2](../output/topics/task-2-6-2.tex) | [№7](../output/fipi-physics/task-07.tex) (5, 7, 8), [№10](../output/fipi-physics/task-10.tex) (2) |
| 2.1.10 | Уравнение Менделеева — Клапейрона и внутренняя энергия идеального газа | [2.1.1](../output/topics/task-2-1-1.tex), [2.3](../output/topics/task-2-3.tex), [2.4.2](../output/topics/task-2-4-2.tex), [2.5.4](../output/topics/task-2-5-4.tex), [2.6.2](../output/topics/task-2-6-2.tex) | [№7](../output/fipi-physics/task-07.tex) (9, 15, 17), [№9](../output/fipi-physics/task-09.tex) (5), [№10](../output/fipi-physics/task-10.tex) (3, 4, 5, 14, 17), [№23](../output/fipi-physics/task-23.tex) (9, 20, 11, 19), [№24](../output/fipi-physics/task-24.tex) (1, 8, 11, 14, 17, …) |
| 2.1.11 | Закон Дальтона | — | [№9](../output/fipi-physics/task-09.tex) (11), [№10](../output/fipi-physics/task-10.tex) (3, 4, 5) |
| 2.1.12 | Изопроцессы в газе с постоянным количеством вещества | [1.13.1](../output/topics/task-1-13-1.tex), [2.5.4](../output/topics/task-2-5-4.tex), [2.6.2](../output/topics/task-2-6-2.tex), [2.6.4](../output/topics/task-2-6-4.tex), [2.6.6](../output/topics/task-2-6-6.tex), [2.11.2](../output/topics/task-2-11-2.tex) | [№7](../output/fipi-physics/task-07.tex) (10, 11, 12, 13, 14, …), [№9](../output/fipi-physics/task-09.tex) (4), [№10](../output/fipi-physics/task-10.tex) (8, 9, 11), [№23](../output/fipi-physics/task-23.tex) (14), [№24](../output/fipi-physics/task-24.tex) (19) |
| 2.1.13 | Насыщенный и ненасыщенный пар, давление и плотность насыщенного пара | [2.7.3](../output/topics/task-2-7-3.tex), [2.10.5](../output/topics/task-2-10-5.tex) | [№9](../output/fipi-physics/task-09.tex) (9, 18), [№10](../output/fipi-physics/task-10.tex) (12), [№23](../output/fipi-physics/task-23.tex) (12), [№24](../output/fipi-physics/task-24.tex) (11) |
| 2.1.14 | Влажность воздуха | [2.7.4](../output/topics/task-2-7-4.tex) | [№7](../output/fipi-physics/task-07.tex) (1), [№9](../output/fipi-physics/task-09.tex) (2, 6, 12), [№23](../output/fipi-physics/task-23.tex) (12, 8), [№24](../output/fipi-physics/task-24.tex) (1, 4, 6, 13, 24) |
| 2.1.15 | Испарение, конденсация и кипение | [2.10.5](../output/topics/task-2-10-5.tex) | [№9](../output/fipi-physics/task-09.tex) (10) |
| 2.1.16 | Плавление и кристаллизация | [2.9.2](../output/topics/task-2-9-2.tex) | [№8](../output/fipi-physics/task-08.tex) (8), [№10](../output/fipi-physics/task-10.tex) (16), [№23](../output/fipi-physics/task-23.tex) (3) |
| 2.1.17 | Преобразование энергии при фазовых переходах | [2.9.2](../output/topics/task-2-9-2.tex), [2.10.5](../output/topics/task-2-10-5.tex) | [№24](../output/fipi-physics/task-24.tex) (10) |
| 2.2.1 | Тепловое равновесие и температура | [2.4.2](../output/topics/task-2-4-2.tex), [2.9.2](../output/topics/task-2-9-2.tex) | [№9](../output/fipi-physics/task-09.tex) (8), [№23](../output/fipi-physics/task-23.tex) (2) |
| 2.2.2 | Внутренняя энергия | [2.1.1](../output/topics/task-2-1-1.tex), [2.8.1](../output/topics/task-2-8-1.tex), [2.11.1](../output/topics/task-2-11-1.tex) | [№7](../output/fipi-physics/task-07.tex) (19), [№24](../output/fipi-physics/task-24.tex) (28) |
| 2.2.3 | Теплопередача и её виды | — | [№10](../output/fipi-physics/task-10.tex) (17), [№18](../output/fipi-physics/task-18.tex) (16) |
| 2.2.4 | Количество теплоты и удельная теплоёмкость | [2.6.4](../output/topics/task-2-6-4.tex), [2.9.1](../output/topics/task-2-9-1.tex), [2.10.5](../output/topics/task-2-10-5.tex) | [№8](../output/fipi-physics/task-08.tex) (6, 9, 14), [№9](../output/fipi-physics/task-09.tex) (17), [№10](../output/fipi-physics/task-10.tex) (7, 16) |
| 2.2.5 | Удельные теплоты парообразования, плавления и сгорания | [2.3](../output/topics/task-2-3.tex), [2.9.2](../output/topics/task-2-9-2.tex), [2.10.5](../output/topics/task-2-10-5.tex) | [№8](../output/fipi-physics/task-08.tex) (7, 15), [№9](../output/fipi-physics/task-09.tex) (17, 19), [№10](../output/fipi-physics/task-10.tex) (7) |
| 2.2.6 | Работа в термодинамике и её вычисление по pV-диаграмме | [2.6.4](../output/topics/task-2-6-4.tex), [2.11.1](../output/topics/task-2-11-1.tex), [2.11.2](../output/topics/task-2-11-2.tex) | [№8](../output/fipi-physics/task-08.tex) (5) |
| 2.2.7 | Первый закон термодинамики и адиабатный процесс | [2.6.4](../output/topics/task-2-6-4.tex), [2.6.6](../output/topics/task-2-6-6.tex), [2.8.1](../output/topics/task-2-8-1.tex), [2.10.5](../output/topics/task-2-10-5.tex), [2.11.1](../output/topics/task-2-11-1.tex), [2.11.2](../output/topics/task-2-11-2.tex), [2.11.4](../output/topics/task-2-11-4.tex) | [№7](../output/fipi-physics/task-07.tex) (16, 20), [№8](../output/fipi-physics/task-08.tex) (1, 2, 3, 4, 17, …), [№9](../output/fipi-physics/task-09.tex) (13), [№10](../output/fipi-physics/task-10.tex) (15, 18), [№23](../output/fipi-physics/task-23.tex) (13), [№24](../output/fipi-physics/task-24.tex) (2, 5, 9, 16, 21, …) |
| 2.2.8 | Второй закон термодинамики и необратимость | — | **Не подтверждено** |
| 2.2.9 | Принцип действия и КПД тепловой машины | [2.11.2](../output/topics/task-2-11-2.tex), [2.12.1](../output/topics/task-2-12-1.tex), [2.12.3](../output/topics/task-2-12-3.tex) | [№8](../output/fipi-physics/task-08.tex) (10, 11, 12, 13, 16, …), [№10](../output/fipi-physics/task-10.tex) (6), [№24](../output/fipi-physics/task-24.tex) (3, 7, 9) |
| 2.2.10 | Цикл Карно и предельный КПД | [2.11.2](../output/topics/task-2-11-2.tex), [2.12.1](../output/topics/task-2-12-1.tex), [2.12.3](../output/topics/task-2-12-3.tex) | [№9](../output/fipi-physics/task-09.tex) (20), [№24](../output/fipi-physics/task-24.tex) (15, 23) |
| 2.2.11 | Уравнение теплового баланса | [2.4.2](../output/topics/task-2-4-2.tex), [2.4.3](../output/topics/task-2-4-3.tex), [2.9.2](../output/topics/task-2-9-2.tex) | [№23](../output/fipi-physics/task-23.tex) (5), [№24](../output/fipi-physics/task-24.tex) (12) |
| 3.1.1 | Электризация, виды зарядов и сохранение электрического заряда | [3.1.1](../output/topics/task-3-1-1.tex), [3.1.2](../output/topics/task-3-1-2.tex), [3.1.3](../output/topics/task-3-1-3.tex), [3.5](../output/topics/task-3-5.tex), [3.5.2](../output/topics/task-3-5-2.tex), [3.5.4](../output/topics/task-3-5-4.tex), [3.6](../output/topics/task-3-6.tex) | [№18](../output/fipi-physics/task-18.tex) (16), [№21](../output/fipi-physics/task-21.tex) (7, 19) |
| 3.1.2 | Взаимодействие точечных зарядов и закон Кулона | [3.1.1](../output/topics/task-3-1-1.tex), [3.1.2](../output/topics/task-3-1-2.tex), [3.1.3](../output/topics/task-3-1-3.tex), [3.2](../output/topics/task-3-2.tex), [3.2.1](../output/topics/task-3-2-1.tex) | [№11](../output/fipi-physics/task-11.tex) (1, 2, 4, 5) |
| 3.1.3 | Электрическое поле и его действие на заряд | — | [№21](../output/fipi-physics/task-21.tex) (24), [№25](../output/fipi-physics/task-25.tex) (11, 28) |
| 3.1.4 | Напряжённость и линии электрического поля | [3.1.3](../output/topics/task-3-1-3.tex), [3.5](../output/topics/task-3-5.tex), [3.5.1](../output/topics/task-3-5-1.tex), [3.5.2](../output/topics/task-3-5-2.tex), [3.5.3](../output/topics/task-3-5-3.tex), [3.5.5](../output/topics/task-3-5-5.tex) | [№21](../output/fipi-physics/task-21.tex) (16) |
| 3.1.5 | Потенциальность электростатического поля, потенциал и напряжение | [3.4](../output/topics/task-3-4.tex), [3.4.5](../output/topics/task-3-4-5.tex), [3.4.6](../output/topics/task-3-4-6.tex), [3.4.8](../output/topics/task-3-4-8.tex) | [№14](../output/fipi-physics/task-14.tex) (2) |
| 3.1.6 | Суперпозиция напряжённостей и потенциалов | [3.2.1](../output/topics/task-3-2-1.tex) | [№25](../output/fipi-physics/task-25.tex) (6) |
| 3.1.7 | Проводники в электростатическом поле и равновесие зарядов | [3.5](../output/topics/task-3-5.tex), [3.5.1](../output/topics/task-3-5-1.tex) | [№14](../output/fipi-physics/task-14.tex) (3) |
| 3.1.8 | Диэлектрики в электростатическом поле и диэлектрическая проницаемость | [3.6](../output/topics/task-3-6.tex), [3.6.1](../output/topics/task-3-6-1.tex) | [№14](../output/fipi-physics/task-14.tex) (5) |
| 3.1.9 | Конденсатор и его электроёмкость | [3.6](../output/topics/task-3-6.tex), [3.6.1](../output/topics/task-3-6-1.tex), [3.7.2](../output/topics/task-3-7-2.tex) | [№14](../output/fipi-physics/task-14.tex) (6, 8), [№21](../output/fipi-physics/task-21.tex) (18, 23, 27), [№25](../output/fipi-physics/task-25.tex) (7) |
| 3.1.10 | Параллельное и последовательное соединения конденсаторов | [3.6](../output/topics/task-3-6.tex), [3.6.1](../output/topics/task-3-6-1.tex) | [№21](../output/fipi-physics/task-21.tex) (26), [№25](../output/fipi-physics/task-25.tex) (7) |
| 3.1.11 | Энергия заряженного конденсатора | [3.6](../output/topics/task-3-6.tex), [3.6.1](../output/topics/task-3-6-1.tex) | [№14](../output/fipi-physics/task-14.tex) (9), [№25](../output/fipi-physics/task-25.tex) (7, 14, 18) |
| 3.2.1 | Сила тока и постоянный ток | [3.8.3](../output/topics/task-3-8-3.tex) | [№11](../output/fipi-physics/task-11.tex) (6, 7, 8) |
| 3.2.2 | Условия существования тока, напряжение и ЭДС | — | [№21](../output/fipi-physics/task-21.tex) (1) |
| 3.2.3 | Закон Ома для участка цепи | [3.9.1](../output/topics/task-3-9-1.tex), [3.10.2](../output/topics/task-3-10-2.tex) | [№11](../output/fipi-physics/task-11.tex) (9, 18, 19) |
| 3.2.4 | Сопротивление проводника и удельное сопротивление | [3.9.2](../output/topics/task-3-9-2.tex), [3.9.3](../output/topics/task-3-9-3.tex), [3.10.2](../output/topics/task-3-10-2.tex), [3.13.4](../output/topics/task-3-13-4.tex) | [№20](../output/fipi-physics/task-20.tex) (14), [№25](../output/fipi-physics/task-25.tex) (29) |
| 3.2.5 | Источники тока, ЭДС и внутреннее сопротивление | — | [№21](../output/fipi-physics/task-21.tex) (1) |
| 3.2.6 | Закон Ома для полной цепи | [3.12.2](../output/topics/task-3-12-2.tex) | [№15](../output/fipi-physics/task-15.tex) (14, 15, 18), [№21](../output/fipi-physics/task-21.tex) (17, 1, 8, 20), [№25](../output/fipi-physics/task-25.tex) (14) |
| 3.2.7 | Параллельное и последовательное соединения проводников | [3.10.2](../output/topics/task-3-10-2.tex) | [№11](../output/fipi-physics/task-11.tex) (14, 15, 16, 17, 20), [№15](../output/fipi-physics/task-15.tex) (19), [№25](../output/fipi-physics/task-25.tex) (25) |
| 3.2.8 | Работа постоянного тока и закон Джоуля — Ленца | [3.10.2](../output/topics/task-3-10-2.tex), [3.11.1](../output/topics/task-3-11-1.tex), [3.11.3](../output/topics/task-3-11-3.tex) | [№11](../output/fipi-physics/task-11.tex) (10, 11), [№25](../output/fipi-physics/task-25.tex) (12) |
| 3.2.9 | Мощность тока и тепловая мощность на резисторе | [1.15.2](../output/topics/task-1-15-2.tex), [3.10.2](../output/topics/task-3-10-2.tex), [3.11.2](../output/topics/task-3-11-2.tex), [3.11.3](../output/topics/task-3-11-3.tex) | [№11](../output/fipi-physics/task-11.tex) (12, 13), [№14](../output/fipi-physics/task-14.tex) (10), [№15](../output/fipi-physics/task-15.tex) (16, 17), [№25](../output/fipi-physics/task-25.tex) (2, 26) |
| 3.2.10 | Носители заряда, проводимость сред, полупроводники и диод | — | [№21](../output/fipi-physics/task-21.tex) (1) |
| 3.3.1 | Магниты, магнитная индукция, линии поля и суперпозиция | — | [№21](../output/fipi-physics/task-21.tex) (5, 26) |
| 3.3.2 | Опыт Эрстеда, магнитные поля проводника и катушки с током | — | [№21](../output/fipi-physics/task-21.tex) (5, 26) |
| 3.3.3 | Сила Ампера | [3.18.2](../output/topics/task-3-18-2.tex) | [№12](../output/fipi-physics/task-12.tex) (1, 2, 20), [№14](../output/fipi-physics/task-14.tex) (11), [№21](../output/fipi-physics/task-21.tex) (5, 25, 26, 3), [№25](../output/fipi-physics/task-25.tex) (9, 16, 29) |
| 3.3.4 | Сила Лоренца и движение заряда в магнитном поле | [3.18.1](../output/topics/task-3-18-1.tex) | [№12](../output/fipi-physics/task-12.tex) (3, 4, 5), [№15](../output/fipi-physics/task-15.tex) (2, 4, 5), [№21](../output/fipi-physics/task-21.tex) (5, 26), [№25](../output/fipi-physics/task-25.tex) (1) |
| 3.4.1 | Поток магнитной индукции | [3.19.3](../output/topics/task-3-19-3.tex) | [№12](../output/fipi-physics/task-12.tex) (18, 6) |
| 3.4.2 | Электромагнитная индукция и ЭДС индукции | [3.19.3](../output/topics/task-3-19-3.tex) | [№12](../output/fipi-physics/task-12.tex) (6, 8), [№21](../output/fipi-physics/task-21.tex) (29) |
| 3.4.3 | Закон электромагнитной индукции Фарадея | [3.19.3](../output/topics/task-3-19-3.tex) | [№12](../output/fipi-physics/task-12.tex) (6, 7, 8, 9, 10, …), [№14](../output/fipi-physics/task-14.tex) (14, 17), [№21](../output/fipi-physics/task-21.tex) (15), [№25](../output/fipi-physics/task-25.tex) (10, 12) |
| 3.4.4 | ЭДС индукции в движущемся проводнике | — | [№25](../output/fipi-physics/task-25.tex) (5) |
| 3.4.5 | Правило Ленца | — | [№14](../output/fipi-physics/task-14.tex) (13), [№15](../output/fipi-physics/task-15.tex) (1) |
| 3.4.6 | Индуктивность, самоиндукция и ЭДС самоиндукции | — | [№12](../output/fipi-physics/task-12.tex) (11, 12, 13, 14), [№21](../output/fipi-physics/task-21.tex) (5, 10) |
| 3.4.7 | Энергия магнитного поля катушки с током | [3.21.1](../output/topics/task-3-21-1.tex) | [№12](../output/fipi-physics/task-12.tex) (15, 16, 17) |
| 3.5.1 | Свободные электромагнитные колебания в идеальном контуре | [3.21.1](../output/topics/task-3-21-1.tex) | [№13](../output/fipi-physics/task-13.tex) (1, 2, 3, 4, 5, …), [№14](../output/fipi-physics/task-14.tex) (19), [№15](../output/fipi-physics/task-15.tex) (12, 13), [№21](../output/fipi-physics/task-21.tex) (2) |
| 3.5.2 | Сохранение энергии в идеальном колебательном контуре | [3.21.1](../output/topics/task-3-21-1.tex) | [№25](../output/fipi-physics/task-25.tex) (3, 24) |
| 3.5.3 | Вынужденные электромагнитные колебания и резонанс | [3.19.3](../output/topics/task-3-19-3.tex), [3.21.1](../output/topics/task-3-21-1.tex) | [№21](../output/fipi-physics/task-21.tex) (2) |
| 3.5.4 | Переменный ток, производство, передача и потребление электроэнергии | — | [№21](../output/fipi-physics/task-21.tex) (28) |
| 3.5.5 | Свойства электромагнитных волн и ориентация векторов в волне | — | [№18](../output/fipi-physics/task-18.tex) (2, 20) |
| 3.5.6 | Шкала и применение электромагнитных волн | — | [№18](../output/fipi-physics/task-18.tex) (12, 16, 19) |
| 3.6.1 | Прямолинейное распространение света, точечный источник и луч | [4.1.1](../output/topics/task-4-1-1.tex), [4.1.2](../output/topics/task-4-1-2.tex) | — |
| 3.6.2 | Законы отражения света | [4.2.2](../output/topics/task-4-2-2.tex) | [№13](../output/fipi-physics/task-13.tex) (11, 12, 14) |
| 3.6.3 | Построение изображения в плоском зеркале | [4.2.2](../output/topics/task-4-2-2.tex) | [№13](../output/fipi-physics/task-13.tex) (13, 15) |
| 3.6.4 | Законы преломления света и показатель преломления | — | [№14](../output/fipi-physics/task-14.tex) (20), [№15](../output/fipi-physics/task-15.tex) (8, 9), [№21](../output/fipi-physics/task-21.tex) (12), [№25](../output/fipi-physics/task-25.tex) (30) |
| 3.6.5 | Полное внутреннее отражение | [4.3.4](../output/topics/task-4-3-4.tex) | [№25](../output/fipi-physics/task-25.tex) (22) |
| 3.6.6 | Собирающая и рассеивающая тонкие линзы, фокусное расстояние | [4.6](../output/topics/task-4-6.tex) | [№25](../output/fipi-physics/task-25.tex) (20, 21) |
| 3.6.7 | Формула тонкой линзы, увеличение и оптическая сила | [4.6](../output/topics/task-4-6.tex) | [№13](../output/fipi-physics/task-13.tex) (16, 17, 18, 19, 20), [№25](../output/fipi-physics/task-25.tex) (13, 15, 17, 19, 21, …) |
| 3.6.8 | Ход лучей и построение изображений в линзах и системах линз | [4.6](../output/topics/task-4-6.tex) | [№15](../output/fipi-physics/task-15.tex) (6, 7), [№21](../output/fipi-physics/task-21.tex) (12), [№25](../output/fipi-physics/task-25.tex) (20) |
| 3.6.9 | Фотоаппарат и глаз как оптические системы | — | **Не подтверждено** |
| 3.6.10 | Интерференция света, когерентность, максимумы и минимумы | — | [№18](../output/fipi-physics/task-18.tex) (18) |
| 3.6.11 | Дифракция света, решётка и её главные максимумы | — | [№25](../output/fipi-physics/task-25.tex) (4, 8) |
| 3.6.12 | Дисперсия света | — | **Не подтверждено** |
| 4.1.1 | Квантовая гипотеза и формула Планка | [6.2.1](../output/topics/task-6-2-1.tex) | [№17](../output/fipi-physics/task-17.tex) (1, 4) |
| 4.1.2 | Фотоны, энергия и импульс фотона | [6.2.1](../output/topics/task-6-2-1.tex), [6.2.2](../output/topics/task-6-2-2.tex) | [№17](../output/fipi-physics/task-17.tex) (1, 2) |
| 4.1.3 | Фотоэффект, опыты Столетова и законы фотоэффекта | [6.1.3](../output/topics/task-6-1-3.tex) | [№17](../output/fipi-physics/task-17.tex) (4), [№18](../output/fipi-physics/task-18.tex) (5) |
| 4.1.4 | Уравнение Эйнштейна для фотоэффекта, красная граница и задерживающее напряжение | [6.1.2](../output/topics/task-6-1-2.tex), [6.1.6](../output/topics/task-6-1-6.tex) | [№17](../output/fipi-physics/task-17.tex) (4) |
| 4.1.5 | Давление света на отражающую и поглощающую поверхности | [6.2.3](../output/topics/task-6-2-3.tex) | — |
| 4.2.1 | Планетарная модель атома | [6.5.3](../output/topics/task-6-5-3.tex) | [№16](../output/fipi-physics/task-16.tex) (13) |
| 4.2.2 | Постулаты Бора, излучение и поглощение при переходах | [6.6.1](../output/topics/task-6-6-1.tex) | [№17](../output/fipi-physics/task-17.tex) (8, 10, 11, 13, 14, …) |
| 4.2.3 | Линейчатые спектры и уровни энергии атома водорода | [6.4.3](../output/topics/task-6-4-3.tex), [6.6.1](../output/topics/task-6-6-1.tex) | [№18](../output/fipi-physics/task-18.tex) (6) |
| 4.3.1 | Нуклонная модель ядра, его заряд, массовое число и изотопы | [6.8.1](../output/topics/task-6-8-1.tex), [6.8.2](../output/topics/task-6-8-2.tex) | [№16](../output/fipi-physics/task-16.tex) (1, 2, 3, 14) |
| 4.3.2 | Радиоактивность, альфа- и бета-распады, гамма-излучение | [6.9.2](../output/topics/task-6-9-2.tex) | [№16](../output/fipi-physics/task-16.tex) (7), [№17](../output/fipi-physics/task-17.tex) (5, 9) |
| 4.3.3 | Закон радиоактивного распада и период полураспада | [6.9.3](../output/topics/task-6-9-3.tex) | [№16](../output/fipi-physics/task-16.tex) (8, 9, 10, 11, 12, …), [№17](../output/fipi-physics/task-17.tex) (3) |
| 4.3.4 | Ядерные реакции, деление и синтез ядер | [6.11](../output/topics/task-6-11.tex) | [№16](../output/fipi-physics/task-16.tex) (4, 5, 6, 15, 16, …) |

## Что ещё не собрано в отдельные подборки

По 22 кодам ниже найдены задачи в номерном банке, но отдельной тематической подборки с подтверждённой привязкой пока нет. Ссылки на примеры — в таблице кодификатора выше.

- **1.1.2** Материальная точка, траектория, радиус-вектор, перемещение и путь.
- **1.1.9** Поступательное и вращательное движение твёрдого тела.
- **1.2.2** Масса и плотность.
- **1.2.3** Сила, суперпозиция сил и равнодействующая.
- **2.1.4** Диффузия и броуновское движение.
- **2.1.11** Закон Дальтона.
- **2.2.3** Теплопередача и её виды.
- **3.1.3** Электрическое поле и его действие на заряд.
- **3.2.2** Условия существования тока, напряжение и ЭДС.
- **3.2.5** Источники тока, ЭДС и внутреннее сопротивление.
- **3.2.10** Носители заряда, проводимость сред, полупроводники и диод.
- **3.3.1** Магниты, магнитная индукция, линии поля и суперпозиция.
- **3.3.2** Опыт Эрстеда, магнитные поля проводника и катушки с током.
- **3.4.4** ЭДС индукции в движущемся проводнике.
- **3.4.5** Правило Ленца.
- **3.4.6** Индуктивность, самоиндукция и ЭДС самоиндукции.
- **3.5.4** Переменный ток, производство, передача и потребление электроэнергии.
- **3.5.5** Свойства электромагнитных волн и ориентация векторов в волне.
- **3.5.6** Шкала и применение электромагнитных волн.
- **3.6.4** Законы преломления света и показатель преломления.
- **3.6.10** Интерференция света, когерентность, максимумы и минимумы.
- **3.6.11** Дифракция света, решётка и её главные максимумы.

## Подборки, в которых пока меньше десяти задач

| Подборка | Есть | Не хватает до 10 |
|---|---:|---:|
| [1.13.2](../output/topics/task-1-13-2.tex) | 7 | 3 |
| [1.13.3](../output/topics/task-1-13-3.tex) | 2 | 8 |
| [1.13.4](../output/topics/task-1-13-4.tex) | 9 | 1 |
| [1.14.1](../output/topics/task-1-14-1.tex) | 8 | 2 |
| [1.14.2](../output/topics/task-1-14-2.tex) | 5 | 5 |
| [1.14.5](../output/topics/task-1-14-5.tex) | 9 | 1 |
| [1.17.2](../output/topics/task-1-17-2.tex) | 8 | 2 |
| [1.17.3](../output/topics/task-1-17-3.tex) | 8 | 2 |
| [1.17.4](../output/topics/task-1-17-4.tex) | 7 | 3 |
| [1.18.1](../output/topics/task-1-18-1.tex) | 8 | 2 |
| [2.4.1](../output/topics/task-2-4-1.tex) | 1 | 9 |
| [2.4.3](../output/topics/task-2-4-3.tex) | 8 | 2 |
| [2.6.1](../output/topics/task-2-6-1.tex) | 2 | 8 |
| [3.2.1](../output/topics/task-3-2-1.tex) | 4 | 6 |
| [3.4.8](../output/topics/task-3-4-8.tex) | 8 | 2 |
| [3.4.9](../output/topics/task-3-4-9.tex) | 3 | 7 |
| [3.5.1](../output/topics/task-3-5-1.tex) | 6 | 4 |
| [3.5.2](../output/topics/task-3-5-2.tex) | 6 | 4 |
| [3.5.3](../output/topics/task-3-5-3.tex) | 5 | 5 |
| [3.5.4](../output/topics/task-3-5-4.tex) | 5 | 5 |
| [3.5.5](../output/topics/task-3-5-5.tex) | 5 | 5 |
| [3.6.2](../output/topics/task-3-6-2.tex) | 1 | 9 |
| [3.8.4](../output/topics/task-3-8-4.tex) | 1 | 9 |
| [3.11.1](../output/topics/task-3-11-1.tex) | 5 | 5 |
| [3.13.4](../output/topics/task-3-13-4.tex) | 1 | 9 |
| [4.1.1](../output/topics/task-4-1-1.tex) | 7 | 3 |
| [4.1.2](../output/topics/task-4-1-2.tex) | 6 | 4 |
| [6.1.2](../output/topics/task-6-1-2.tex) | 5 | 5 |
| [6.2.4](../output/topics/task-6-2-4.tex) | 1 | 9 |
| [6.4.1](../output/topics/task-6-4-1.tex) | 7 | 3 |
| [6.4.2](../output/topics/task-6-4-2.tex) | 7 | 3 |
| [6.4.3](../output/topics/task-6-4-3.tex) | 1 | 9 |
| [6.5.3](../output/topics/task-6-5-3.tex) | 2 | 8 |
| [6.6.2](../output/topics/task-6-6-2.tex) | 8 | 2 |

## Темы и подтемы каталога проекта

Внутренние номера отличаются от кодов ФИПИ. Здесь перечислены все пункты README. Для связанных подтем указан существующий файл, только если проверенная карта подтем указывает на карточки, которые всё ещё есть в этом файле. Для родительского пункта указаны подборки дочерних пунктов, если для самого пункта отдельного файла нет. Без прямой привязки внутреннего пункта проверяйте вышестоящую таблицу ФИПИ: у номерного банка в основном проставлены официальные коды. Вспомогательные пункты и темы вне ЕГЭ оставлены для полноты каталога.

| Пункт | Тема | Где есть задачи |
|---|---|---|
| 0.1 | Решение в общем виде | Не подтверждено |
| 0.2 | Векторы в физике | Не подтверждено |
| 0.2.1 | Скалярные и векторные величины | Не подтверждено |
| 0.2.2 | Сложение векторов | Не подтверждено |
| 0.2.2.1 | Правило треугольника | Не подтверждено |
| 0.2.2.2 | Правило параллелограмма | Не подтверждено |
| 0.2.2.3 | Свойства сложения векторов | Не подтверждено |
| 0.2.2.4 | Вычитание векторов | Не подтверждено |
| 0.2.3 | Умножение скаляра на вектор | Не подтверждено |
| 0.2.3.1 | Что такое умножение скаляра на вектор? | Не подтверждено |
| 0.2.3.2 | Свойства умножения скаляра на вектор | Не подтверждено |
| 0.2.4 | Угол между векторами | Не подтверждено |
| 0.2.4.1 | Что такое угол между векторами? | Не подтверждено |
| 0.2.4.2 | Угол между вектором и осью | Не подтверждено |
| 0.2.5 | Проекция вектора на ось | Не подтверждено |
| 0.2.5.1 | Что такое проекция вектора на ось? | Не подтверждено |
| 0.2.5.2 | Свойства проектирования вектора на ось | Не подтверждено |
| 0.2.5.3 | Операция проектирования в физике | Не подтверждено |
| 0.2.6 | Векторы и координаты на плоскости | Не подтверждено |
| 0.2.6.1 | Разложение вектора по базису | Не подтверждено |
| 0.2.6.2 | Нахождение модуля вектора по его проекциям | Не подтверждено |
| 0.2.7 | Векторы и координаты в пространстве | Не подтверждено |
| 0.2.7.1 | Разложение вектора по базису | Не подтверждено |
| 0.2.7.2 | Нахождение модуля вектора по его проекциям | Не подтверждено |
| 0.2.8 | Скалярное произведение векторов | Не подтверждено |
| 0.2.8.1 | Что такое скалярное произведение? | Не подтверждено |
| 0.2.8.2 | Свойства скалярного произведения | Не подтверждено |
| 0.2.8.3 | Скалярное произведение в физике | Не подтверждено |
| 0.2.8.4 | Вычисление скалярного произведения в координатах | Не подтверждено |
| 0.3 | Производные и дифференцирование | Не подтверждено |
| 0.3.1 | Предел | Не подтверждено |
| 0.3.2 | Мгновенная скорость | Не подтверждено |
| 0.3.3 | Определение производной | Не подтверждено |
| 0.3.4 | Табличные производные | Не подтверждено |
| 0.3.5 | Правила дифференцирования | Не подтверждено |
| 0.3.6 | Обозначения производной в физике | Не подтверждено |
| 0.3.7 | Предел векторной величины (не ЕГЭ) | Не подтверждено |
| 0.3.8 | Дифференцирование векторов (не ЕГЭ) | Не подтверждено |
| 0.4 | Интегрирование (не ЕГЭ) | Не подтверждено |
| 0.5 | Метод вспомогательного угла | Не подтверждено |
| 1.1 | Механическое движение | В подпунктах [1.1.1](../output/topics/task-1-1-1.tex), [1.1.5](../output/topics/task-1-1-5.tex), [1.1.6](../output/topics/task-1-1-6.tex), [1.1.8](../output/topics/task-1-1-8.tex) |
| 1.1.1 | Относительность движения | [1.1.1](../output/topics/task-1-1-1.tex) (10 задач) |
| 1.1.2 | Основная задача механики | Не подтверждено |
| 1.1.3 | Материальная точка | Не подтверждено |
| 1.1.4 | Траектория, путь, перемещение | Не подтверждено |
| 1.1.5 | Скорость | [1.1.5](../output/topics/task-1-1-5.tex) (10 задач) |
| 1.1.6 | Ускорение | [1.1.6](../output/topics/task-1-1-6.tex) (10 задач) |
| 1.1.7 | Примеры вычисления скорости и ускорения | Не подтверждено |
| 1.1.8 | Закон сложения скоростей | [1.1.8](../output/topics/task-1-1-8.tex) (10 задач) |
| 1.1.9 | Виды механического движения | Не подтверждено |
| 1.2 | Равномерное прямолинейное движение | В подпунктах [1.2.1](../output/topics/task-1-2-1.tex) |
| 1.2.1 | Закон движения | [1.2.1](../output/topics/task-1-2-1.tex) (10 задач) |
| 1.3 | Равноускоренное движение | В подпунктах [1.3.5](../output/topics/task-1-3-5.tex), [1.3.6](../output/topics/task-1-3-6.tex) |
| 1.3.1 | Зависимость скорости от времени | Не подтверждено |
| 1.3.2 | Закон движения | Не подтверждено |
| 1.3.3 | Прямолинейное равноускоренное движение | Не подтверждено |
| 1.3.4 | Свободное падение | Не подтверждено |
| 1.3.5 | Горизонтальный бросок | [1.3.5](../output/topics/task-1-3-5.tex) (10 задач) |
| 1.3.6 | Бросок под углом к горизонту | [1.3.6](../output/topics/task-1-3-6.tex) (10 задач); [№6](../output/fipi-physics/task-06.tex) (3), [№22](../output/fipi-physics/task-22.tex) (6), [№26](../output/fipi-physics/task-26.tex) (4) |
| 1.4 | Равномерное движение по окружности | В подпунктах [1.4.3](../output/topics/task-1-4-3.tex) |
| 1.4.1 | Угловая скорость | Не подтверждено |
| 1.4.2 | Закон движения | Не подтверждено |
| 1.4.3 | Центростремительное ускорение | [1.4.3](../output/topics/task-1-4-3.tex) (10 задач) |
| 1.4.4 | Почему ускорение направлено к центру окружности? | Не подтверждено |
| 1.5 | Путь при неравномерном движении | Не подтверждено |
| 1.6 | Первый закон Ньютона | Не подтверждено |
| 1.6.1 | Инерциальные системы отсчёта | Не подтверждено |
| 1.6.2 | Принцип относительности | Не подтверждено |
| 1.7 | Масса и плотность | Не подтверждено |
| 1.8 | Второй и третий законы Ньютона | В подпунктах [1.8.2](../output/topics/task-1-8-2.tex), [1.8.3](../output/topics/task-1-8-3.tex) |
| 1.8.1 | Принцип суперпозиции | Не подтверждено |
| 1.8.2 | Второй закон Ньютона | [1.8.2](../output/topics/task-1-8-2.tex) (10 задач) |
| 1.8.3 | Третий закон Ньютона | [1.8.3](../output/topics/task-1-8-3.tex) (10 задач) |
| 1.8.4 | Как найти закон движения? | Не подтверждено |
| 1.9 | Сила упругости | В подпунктах [1.9.2](../output/topics/task-1-9-2.tex) |
| 1.9.1 | Деформация | Не подтверждено |
| 1.9.2 | Закон Гука | [1.9.2](../output/topics/task-1-9-2.tex) (10 задач) |
| 1.9.3 | Модуль Юнга (не ЕГЭ) | Не подтверждено |
| 1.10 | Сила тяготения | В подпунктах [1.10.1](../output/topics/task-1-10-1.tex), [1.10.4](../output/topics/task-1-10-4.tex) |
| 1.10.1 | Закон всемирного тяготения | [1.10.1](../output/topics/task-1-10-1.tex) (10 задач) |
| 1.10.2 | Сила тяжести | Не подтверждено |
| 1.10.3 | Вес тела. Невесомость | Не подтверждено |
| 1.10.4 | Искусственные спутники | [1.10.4](../output/topics/task-1-10-4.tex) (10 задач) |
| 1.11 | Сила трения | В подпунктах [1.11.1](../output/topics/task-1-11-1.tex) |
| 1.11.1 | Сухое трение | [1.11.1](../output/topics/task-1-11-1.tex) (10 задач) |
| 1.11.2 | Вязкое трение (не ЕГЭ) | Не подтверждено |
| 1.12 | Статика твёрдого тела | В подпунктах [1.12.1](../output/topics/task-1-12-1.tex), [1.12.2](../output/topics/task-1-12-2.tex) |
| 1.12.1 | Момент силы | [1.12.1](../output/topics/task-1-12-1.tex) (10 задач) |
| 1.12.2 | Условия равновесия | [1.12.2](../output/topics/task-1-12-2.tex) (10 задач) |
| 1.13 | Статика жидкостей и газов | В подпунктах [1.13.1](../output/topics/task-1-13-1.tex), [1.13.2](../output/topics/task-1-13-2.tex), [1.13.3](../output/topics/task-1-13-3.tex), [1.13.4](../output/topics/task-1-13-4.tex), [1.13.5](../output/topics/task-1-13-5.tex) |
| 1.13.1 | Гидростатическое давление | [1.13.1](../output/topics/task-1-13-1.tex) (10 задач) |
| 1.13.2 | Закон Паскаля | [1.13.2](../output/topics/task-1-13-2.tex) (7 задач) |
| 1.13.3 | Гидравлический пресс | [1.13.3](../output/topics/task-1-13-3.tex) (2 задач) |
| 1.13.4 | Закон Архимеда (9 задач; одно опубликованное решение содержит ошибку) | [1.13.4](../output/topics/task-1-13-4.tex) (9 задач) |
| 1.13.5 | Плавание тел | [1.13.5](../output/topics/task-1-13-5.tex) (10 задач) |
| 1.14 | Импульс | В подпунктах [1.14.1](../output/topics/task-1-14-1.tex), [1.14.2](../output/topics/task-1-14-2.tex), [1.14.3](../output/topics/task-1-14-3.tex), [1.14.4](../output/topics/task-1-14-4.tex), [1.14.5](../output/topics/task-1-14-5.tex) |
| 1.14.1 | Второй закон Ньютона в импульсной форме | [1.14.1](../output/topics/task-1-14-1.tex) (8 задач) |
| 1.14.2 | Пример вычисления силы | [1.14.2](../output/topics/task-1-14-2.tex) (5 задач) |
| 1.14.3 | Импульс системы тел | [1.14.3](../output/topics/task-1-14-3.tex) (10 задач) |
| 1.14.4 | Закон сохранения импульса | [1.14.4](../output/topics/task-1-14-4.tex) (12 задач) |
| 1.14.5 | Закон сохранения проекции импульса | [1.14.5](../output/topics/task-1-14-5.tex) (9 задач) |
| 1.15 | Энергия | В подпунктах [1.15.1](../output/topics/task-1-15-1.tex), [1.15.2](../output/topics/task-1-15-2.tex), [1.15.3](../output/topics/task-1-15-3.tex), [1.15.4](../output/topics/task-1-15-4.tex), [1.15.5](../output/topics/task-1-15-5.tex), [1.15.6](../output/topics/task-1-15-6.tex), [1.15.7](../output/topics/task-1-15-7.tex), [1.15.8](../output/topics/task-1-15-8.tex) |
| 1.15.1 | Работа | [1.15.1](../output/topics/task-1-15-1.tex) (10 задач) |
| 1.15.2 | Мощность | [1.15.2](../output/topics/task-1-15-2.tex) (10 задач) |
| 1.15.3 | Механическая энергия | [1.15.3](../output/topics/task-1-15-3.tex) (10 задач) |
| 1.15.4 | Кинетическая энергия | [1.15.4](../output/topics/task-1-15-4.tex) (10 задач) |
| 1.15.5 | Потенциальная энергия тела вблизи поверхности Земли | [1.15.5](../output/topics/task-1-15-5.tex) (10 задач) |
| 1.15.6 | Потенциальная энергия деформированной пружины | [1.15.6](../output/topics/task-1-15-6.tex) (10 задач) |
| 1.15.7 | Закон сохранения механической энергии | [1.15.7](../output/topics/task-1-15-7.tex) (10 задач); [№26](../output/fipi-physics/task-26.tex) (11) |
| 1.15.8 | Закон изменения механической энергии | [1.15.8](../output/topics/task-1-15-8.tex) (10 задач) |
| 1.16 | Простые механизмы | В подпунктах [1.16.1](../output/topics/task-1-16-1.tex) |
| 1.16.1 | Рычаг | [1.16.1](../output/topics/task-1-16-1.tex) (10 задач) |
| 1.16.2 | Неподвижный блок | Не подтверждено |
| 1.16.3 | Подвижный блок | Не подтверждено |
| 1.16.4 | Наклонная плоскость | Не подтверждено |
| 1.16.5 | Золотое правило механики | Не подтверждено |
| 1.16.6 | КПД механизма | Не подтверждено |
| 1.17 | Механические колебания | В подпунктах [1.17.1](../output/topics/task-1-17-1.tex), [1.17.2](../output/topics/task-1-17-2.tex), [1.17.3](../output/topics/task-1-17-3.tex), [1.17.4](../output/topics/task-1-17-4.tex), [1.17.5](../output/topics/task-1-17-5.tex) |
| 1.17.1 | Гармонические колебания | [1.17.1](../output/topics/task-1-17-1.tex) (10 задач) |
| 1.17.2 | Уравнение гармонических колебаний | [1.17.2](../output/topics/task-1-17-2.tex) (8 задач) |
| 1.17.3 | Пружинный маятник | [1.17.3](../output/topics/task-1-17-3.tex) (8 задач) |
| 1.17.4 | Математический маятник | [1.17.4](../output/topics/task-1-17-4.tex) (7 задач) |
| 1.17.5 | Свободные и вынужденные колебания | [1.17.5](../output/topics/task-1-17-5.tex) (10 задач) |
| 1.18 | Механические волны | В подпунктах [1.18.1](../output/topics/task-1-18-1.tex), [1.18.2](../output/topics/task-1-18-2.tex) |
| 1.18.1 | Продольные и поперечные волны | [1.18.1](../output/topics/task-1-18-1.tex) (8 задач) |
| 1.18.2 | Звук | [1.18.2](../output/topics/task-1-18-2.tex) (10 задач) |
| 2.1 | Основные положения МКТ | В подпунктах [2.1.1](../output/topics/task-2-1-1.tex), [2.1.2](../output/topics/task-2-1-2.tex), [2.1.3](../output/topics/task-2-1-3.tex) |
| 2.1.1 | Атомы и молекулы | [2.1.1](../output/topics/task-2-1-1.tex) (10 задач); В [2.3](../output/topics/task-2-3.tex) (4) |
| 2.1.2 | Тепловое движение атомов и молекул | [2.1.2](../output/topics/task-2-1-2.tex) (10 задач) |
| 2.1.3 | Взаимодействие частиц вещества | [2.1.3](../output/topics/task-2-1-3.tex) (10 задач); В [2.2](../output/topics/task-2-2.tex) (5) |
| 2.2 | Газы, жидкости и твёрдые тела | [2.2](../output/topics/task-2-2.tex) (16 задач) |
| 2.2.1 | Газы | [2.2.1](../output/topics/task-2-2-1.tex) (10 задач); В [2.2](../output/topics/task-2-2.tex) (7) |
| 2.2.2 | Твёрдые тела | [2.2.2](../output/topics/task-2-2-2.tex) (10 задач); В [2.2](../output/topics/task-2-2.tex) (7) |
| 2.2.3 | Жидкости | [2.2.3](../output/topics/task-2-2-3.tex) (10 задач); В [2.2](../output/topics/task-2-2.tex) (4) |
| 2.3 | Основные формулы молекулярной физики | [2.3](../output/topics/task-2-3.tex) (10 задач) |
| 2.4 | Температура | В подпунктах [2.4.1](../output/topics/task-2-4-1.tex), [2.4.2](../output/topics/task-2-4-2.tex), [2.4.3](../output/topics/task-2-4-3.tex) |
| 2.4.1 | Термодинамическая система | [2.4.1](../output/topics/task-2-4-1.tex) (1 задач); В [2.4.2](../output/topics/task-2-4-2.tex) (1) |
| 2.4.2 | Тепловое равновесие | [2.4.2](../output/topics/task-2-4-2.tex) (10 задач) |
| 2.4.3 | Температурная шкала. Абсолютная температура | [2.4.3](../output/topics/task-2-4-3.tex) (8 задач) |
| 2.5 | Уравнение состояния идеального газа | В подпунктах [2.5.1](../output/topics/task-2-5-1.tex), [2.5.2](../output/topics/task-2-5-2.tex), [2.5.3](../output/topics/task-2-5-3.tex), [2.5.4](../output/topics/task-2-5-4.tex) |
| 2.5.1 | Средняя кинетическая энергия частиц газа | [2.5.1](../output/topics/task-2-5-1.tex) (10 задач) |
| 2.5.2 | Основное уравнение МКТ идеального газа | [2.5.2](../output/topics/task-2-5-2.tex) (10 задач) |
| 2.5.3 | Энергия частиц и температура газа | [2.5.3](../output/topics/task-2-5-3.tex) (10 задач); В [2.5.1](../output/topics/task-2-5-1.tex) (10) |
| 2.5.4 | Уравнение Менделеева | [2.5.4](../output/topics/task-2-5-4.tex) (10 задач) |
| 2.6 | Изопроцессы | В подпунктах [2.6.1](../output/topics/task-2-6-1.tex), [2.6.2](../output/topics/task-2-6-2.tex), [2.6.4](../output/topics/task-2-6-4.tex), [2.6.6](../output/topics/task-2-6-6.tex) |
| 2.6.1 | Термодинамический процесс | [2.6.1](../output/topics/task-2-6-1.tex) (2 задач); В [2.6.2](../output/topics/task-2-6-2.tex) (2) |
| 2.6.2 | Изотермический процесс | [2.6.2](../output/topics/task-2-6-2.tex) (10 задач) |
| 2.6.3 | Графики изотермического процесса | Не подтверждено |
| 2.6.4 | Изобарный процесс | [2.6.4](../output/topics/task-2-6-4.tex) (10 задач) |
| 2.6.5 | Графики изобарного процесса | Не подтверждено |
| 2.6.6 | Изохорный процесс | [2.6.6](../output/topics/task-2-6-6.tex) (10 задач) |
| 2.6.7 | Графики изохорного процесса | Не подтверждено |
| 2.7 | Насыщенный пар | В подпунктах [2.7.3](../output/topics/task-2-7-3.tex), [2.7.4](../output/topics/task-2-7-4.tex) |
| 2.7.1 | Испарение и конденсация | Не подтверждено |
| 2.7.2 | Динамическое равновесие | Не подтверждено |
| 2.7.3 | Свойства насыщенного пара | [2.7.3](../output/topics/task-2-7-3.tex) (10 задач) |
| 2.7.4 | Влажность воздуха | [2.7.4](../output/topics/task-2-7-4.tex) (10 задач) |
| 2.8 | Внутренняя энергия | В подпунктах [2.8.1](../output/topics/task-2-8-1.tex) |
| 2.8.1 | Внутренняя энергия одноатомного идеального газа | [2.8.1](../output/topics/task-2-8-1.tex) (10 задач) |
| 2.8.2 | Функция состояния | Не подтверждено |
| 2.8.3 | Изменение внутренней энергии: совершение работы | Не подтверждено |
| 2.8.4 | Изменение внутренней энергии: теплопередача | Не подтверждено |
| 2.8.5 | Теплопроводность | Не подтверждено |
| 2.8.6 | Конвекция | Не подтверждено |
| 2.8.7 | Тепловое излучение | Не подтверждено |
| 2.9 | Количество теплоты | В подпунктах [2.9.1](../output/topics/task-2-9-1.tex), [2.9.2](../output/topics/task-2-9-2.tex) |
| 2.9.1 | Удельная теплоёмкость вещества | [2.9.1](../output/topics/task-2-9-1.tex) (10 задач) |
| 2.9.2 | Уравнение теплового баланса | [2.9.2](../output/topics/task-2-9-2.tex) (10 задач) |
| 2.10 | Фазовые переходы | В подпунктах [2.10.5](../output/topics/task-2-10-5.tex) |
| 2.10.1 | Плавление и кристаллизация | Не подтверждено |
| 2.10.2 | График плавления | Не подтверждено |
| 2.10.3 | Удельная теплота плавления | Не подтверждено |
| 2.10.4 | График кристаллизации | Не подтверждено |
| 2.10.5 | Парообразование и конденсация | [2.10.5](../output/topics/task-2-10-5.tex) (10 задач) |
| 2.10.6 | Кипение | Не подтверждено |
| 2.10.7 | График кипения | Не подтверждено |
| 2.10.8 | График конденсации | Не подтверждено |
| 2.11 | Первый закон термодинамики | В подпунктах [2.11.1](../output/topics/task-2-11-1.tex), [2.11.2](../output/topics/task-2-11-2.tex), [2.11.4](../output/topics/task-2-11-4.tex) |
| 2.11.1 | Работа газа в изобарном процессе | [2.11.1](../output/topics/task-2-11-1.tex) (10 задач) |
| 2.11.2 | Работа газа в произвольном процессе | [2.11.2](../output/topics/task-2-11-2.tex) (10 задач) |
| 2.11.3 | Работа, совершаемая над газом | Не подтверждено |
| 2.11.4 | Первый закон термодинамики | [2.11.4](../output/topics/task-2-11-4.tex) (10 задач) |
| 2.11.5 | Применение первого закона термодинамики к изопроцессам | Не подтверждено |
| 2.11.6 | Адиабатный процесс | Не подтверждено |
| 2.12 | Тепловые машины | В подпунктах [2.12.1](../output/topics/task-2-12-1.tex), [2.12.3](../output/topics/task-2-12-3.tex) |
| 2.12.1 | Тепловые двигатели | [2.12.1](../output/topics/task-2-12-1.tex) (10 задач) |
| 2.12.2 | Холодильные машины | Не подтверждено |
| 2.12.3 | Тепловая машина Карно | [2.12.3](../output/topics/task-2-12-3.tex) (10 задач) |
| 2.12.4 | Тепловые двигатели и охрана окружающей среды | Не подтверждено |
| 2.13 | Второй закон термодинамики | Не подтверждено |
| 2.13.1 | Необратимость процессов в природе | Не подтверждено |
| 2.13.2 | Постулаты Клаузиуса и Кельвина | Не подтверждено |
| 2.13.3 | Эквивалентность постулатов Клаузиуса и Кельвина (не ЕГЭ) | Не подтверждено |
| 2.13.4 | Обратимые процессы | Не подтверждено |
| 2.13.5 | Обратимость машины Карно (не ЕГЭ) | Не подтверждено |
| 3.1 | Электрический заряд | В подпунктах [3.1.1](../output/topics/task-3-1-1.tex), [3.1.2](../output/topics/task-3-1-2.tex), [3.1.3](../output/topics/task-3-1-3.tex) |
| 3.1.1 | Два вида заряда | [3.1.1](../output/topics/task-3-1-1.tex) (10 задач); В [3.1.2](../output/topics/task-3-1-2.tex) (9) |
| 3.1.2 | Электризация тел | [3.1.2](../output/topics/task-3-1-2.tex) (10 задач) |
| 3.1.3 | Закон сохранения заряда | [3.1.3](../output/topics/task-3-1-3.tex) (10 задач); В [3.1.2](../output/topics/task-3-1-2.tex) (8) |
| 3.2 | Закон Кулона | [3.2](../output/topics/task-3-2.tex) (10 задач) |
| 3.2.1 | Принцип суперпозиции | [3.2.1](../output/topics/task-3-2-1.tex) (4 задач); В [3.2](../output/topics/task-3-2.tex) (4) |
| 3.2.2 | Закон Кулона в диэлектрике | Не подтверждено |
| 3.3 | Напряжённость электрического поля | Не подтверждено |
| 3.3.1 | Дальнодействие и близкодействие | Не подтверждено |
| 3.3.2 | Электрическое поле | Не подтверждено |
| 3.3.3 | Напряжённость поля точечного заряда | Не подтверждено |
| 3.3.4 | Принцип суперпозиции электрических полей | Не подтверждено |
| 3.3.5 | Поле равномерно заряженной плоскости | Не подтверждено |
| 3.3.6 | Линии напряжённости электрического поля | Не подтверждено |
| 3.4 | Потенциал электрического поля | [3.4](../output/topics/task-3-4.tex) (11 задач) |
| 3.4.1 | Консервативные силы | Не подтверждено |
| 3.4.2 | Потенциальность электростатического поля | Не подтверждено |
| 3.4.3 | Потенциальная энергия заряда в однородном поле | Не подтверждено |
| 3.4.4 | Потенциальная энергия взаимодействия точечных зарядов | Не подтверждено |
| 3.4.5 | Потенциал | [3.4.5](../output/topics/task-3-4-5.tex) (10 задач); В [3.4](../output/topics/task-3-4.tex) (11) |
| 3.4.6 | Разность потенциалов | [3.4.6](../output/topics/task-3-4-6.tex) (10 задач); В [3.4](../output/topics/task-3-4.tex) (10) |
| 3.4.7 | Принцип суперпозиции для потенциалов | Не подтверждено |
| 3.4.8 | Однородное поле: связь напряжения и напряжённости | [3.4.8](../output/topics/task-3-4-8.tex) (8 задач); В [3.4](../output/topics/task-3-4.tex) (8) |
| 3.4.9 | Эквипотенциальные поверхности | [3.4.9](../output/topics/task-3-4-9.tex) (3 задач); В [3.4](../output/topics/task-3-4.tex) (3) |
| 3.5 | Проводники в электрическом поле | [3.5](../output/topics/task-3-5.tex) (10 задач) |
| 3.5.1 | Поле внутри проводника | [3.5.1](../output/topics/task-3-5-1.tex) (6 задач); В [3.5](../output/topics/task-3-5.tex) (6) |
| 3.5.2 | Заряд внутри проводника | [3.5.2](../output/topics/task-3-5-2.tex) (6 задач); В [3.5](../output/topics/task-3-5.tex) (6) |
| 3.5.3 | Поле вне проводника | [3.5.3](../output/topics/task-3-5-3.tex) (5 задач); В [3.5](../output/topics/task-3-5.tex) (5) |
| 3.5.4 | Потенциал проводника | [3.5.4](../output/topics/task-3-5-4.tex) (5 задач); В [3.5](../output/topics/task-3-5.tex) (5) |
| 3.5.5 | Напряжённость и потенциал поля проводящей сферы | [3.5.5](../output/topics/task-3-5-5.tex) (5 задач); В [3.5](../output/topics/task-3-5.tex) (5) |
| 3.6 | Диэлектрики в электрическом поле | [3.6](../output/topics/task-3-6.tex) (10 задач) |
| 3.6.1 | Диэлектрическая проницаемость | [3.6.1](../output/topics/task-3-6-1.tex) (10 задач); В [3.6](../output/topics/task-3-6.tex) (10) |
| 3.6.2 | Полярные диэлектрики | [3.6.2](../output/topics/task-3-6-2.tex) (1 задач); В [3.6](../output/topics/task-3-6.tex) (2) |
| 3.6.3 | Неполярные диэлектрики | Не подтверждено |
| 3.7 | Конденсатор. Энергия электрического поля | В подпунктах [3.7.2](../output/topics/task-3-7-2.tex), [3.7.3](../output/topics/task-3-7-3.tex), [3.7.4](../output/topics/task-3-7-4.tex) |
| 3.7.1 | Ёмкость уединённого проводника | Не подтверждено |
| 3.7.2 | Ёмкость плоского конденсатора | [3.7.2](../output/topics/task-3-7-2.tex) (10 задач) |
| 3.7.3 | Энергия заряженного конденсатора | [3.7.3](../output/topics/task-3-7-3.tex) (10 задач); [№25](../output/fipi-physics/task-25.tex) (7) |
| 3.7.4 | Энергия электрического поля | [3.7.4](../output/topics/task-3-7-4.tex) (10 задач); В [3.7.3](../output/topics/task-3-7-3.tex) (10) |
| 3.8 | Постоянный электрический ток | В подпунктах [3.8.3](../output/topics/task-3-8-3.tex), [3.8.4](../output/topics/task-3-8-4.tex) |
| 3.8.1 | Направление электрического тока | Не подтверждено |
| 3.8.2 | Действие электрического тока | Не подтверждено |
| 3.8.3 | Сила и плотность тока | [3.8.3](../output/topics/task-3-8-3.tex) (10 задач) |
| 3.8.4 | Скорость направленного движения зарядов | [3.8.4](../output/topics/task-3-8-4.tex) (1 задач); В [3.8.3](../output/topics/task-3-8-3.tex) (1) |
| 3.8.5 | Стационарное электрическое поле | Не подтверждено |
| 3.9 | Закон Ома | В подпунктах [3.9.1](../output/topics/task-3-9-1.tex), [3.9.2](../output/topics/task-3-9-2.tex), [3.9.3](../output/topics/task-3-9-3.tex) |
| 3.9.1 | Закон Ома для участка цепи | [3.9.1](../output/topics/task-3-9-1.tex) (10 задач) |
| 3.9.2 | Электрическое сопротивление | [3.9.2](../output/topics/task-3-9-2.tex) (11 задач) |
| 3.9.3 | Удельное сопротивление | [3.9.3](../output/topics/task-3-9-3.tex) (10 задач); В [3.9.2](../output/topics/task-3-9-2.tex) (10) |
| 3.10 | Соединения проводников | В подпунктах [3.10.2](../output/topics/task-3-10-2.tex) |
| 3.10.1 | Резисторы и подводящие провода | Не подтверждено |
| 3.10.2 | Последовательное соединение | [3.10.2](../output/topics/task-3-10-2.tex) (10 задач) |
| 3.10.3 | Параллельное соединение | Не подтверждено |
| 3.10.4 | Смешанное соединение | Не подтверждено |
| 3.11 | Работа и мощность тока | В подпунктах [3.11.1](../output/topics/task-3-11-1.tex), [3.11.2](../output/topics/task-3-11-2.tex), [3.11.3](../output/topics/task-3-11-3.tex) |
| 3.11.1 | Работа тока | [3.11.1](../output/topics/task-3-11-1.tex) (5 задач) |
| 3.11.2 | Мощность тока | [3.11.2](../output/topics/task-3-11-2.tex) (10 задач) |
| 3.11.3 | Закон Джоуля–Ленца | [3.11.3](../output/topics/task-3-11-3.tex) (10 задач) |
| 3.12 | ЭДС. Закон Ома для полной цепи | В подпунктах [3.12.2](../output/topics/task-3-12-2.tex) |
| 3.12.1 | Сторонняя сила | Не подтверждено |
| 3.12.2 | Закон Ома для полной цепи | [3.12.2](../output/topics/task-3-12-2.tex) (10 задач) |
| 3.12.3 | КПД электрической цепи | Не подтверждено |
| 3.12.4 | Закон Ома для неоднородного участка | Не подтверждено |
| 3.13 | Электрический ток в металлах | В подпунктах [3.13.4](../output/topics/task-3-13-4.tex) |
| 3.13.1 | Свободные электроны | Не подтверждено |
| 3.13.2 | Опыт Рикке (не ЕГЭ) | Не подтверждено |
| 3.13.3 | Опыт Стюарта–Толмена (не ЕГЭ) | Не подтверждено |
| 3.13.4 | Зависимость сопротивления от температуры | [3.13.4](../output/topics/task-3-13-4.tex) (1 задач); В [3.9.2](../output/topics/task-3-9-2.tex) (1) |
| 3.14 | Электрический ток в электролитах | Не подтверждено |
| 3.14.1 | Электролитическая диссоциация | Не подтверждено |
| 3.14.2 | Ионная проводимость | Не подтверждено |
| 3.14.3 | Электролиз | Не подтверждено |
| 3.15 | Электрический ток в газах | Не подтверждено |
| 3.15.1 | Свободные заряды в газе | Не подтверждено |
| 3.15.2 | Несамостоятельный разряд | Не подтверждено |
| 3.15.3 | Вольт-амперная характеристика газового разряда | Не подтверждено |
| 3.15.4 | Самостоятельный разряд | Не подтверждено |
| 3.16 | Полупроводники | Не подтверждено |
| 3.16.1 | Ковалентная связь | Не подтверждено |
| 3.16.2 | Кристаллическая структура кремния | Не подтверждено |
| 3.16.3 | Собственная проводимость | Не подтверждено |
| 3.16.4 | Примесная проводимость | Не подтверждено |
| 3.16.5 | p–n-переход | Не подтверждено |
| 3.17 | Магнитное поле. Линии | Не подтверждено |
| 3.17.1 | Взаимодействие магнитов | Не подтверждено |
| 3.17.2 | Линии магнитного поля | Не подтверждено |
| 3.17.3 | Опыт Эрстеда | Не подтверждено |
| 3.17.4 | Магнитное поле прямого провода с током | Не подтверждено |
| 3.17.5 | Магнитное поле витка с током | Не подтверждено |
| 3.17.6 | Магнитное поле катушки с током | Не подтверждено |
| 3.17.7 | Гипотеза Ампера. Элементарные токи | Не подтверждено |
| 3.18 | Магнитное поле. Силы | В подпунктах [3.18.1](../output/topics/task-3-18-1.tex), [3.18.2](../output/topics/task-3-18-2.tex) |
| 3.18.1 | Сила Лоренца | [3.18.1](../output/topics/task-3-18-1.tex) (10 задач) |
| 3.18.2 | Сила Ампера | [3.18.2](../output/topics/task-3-18-2.tex) (10 задач) |
| 3.18.3 | Рамка с током в магнитном поле | Не подтверждено |
| 3.19 | Электромагнитная индукция | В подпунктах [3.19.3](../output/topics/task-3-19-3.tex) |
| 3.19.1 | Магнитный поток | Не подтверждено |
| 3.19.2 | ЭДС индукции | Не подтверждено |
| 3.19.3 | Закон электромагнитной индукции Фарадея | [3.19.3](../output/topics/task-3-19-3.tex) (10 задач) |
| 3.19.4 | Правило Ленца | Не подтверждено |
| 3.19.5 | Взаимодействие магнита с контуром | Не подтверждено |
| 3.19.6 | Закон Фарадея + Правило Ленца = Снятие модуля | Не подтверждено |
| 3.19.7 | Вихревое электрическое поле | Не подтверждено |
| 3.19.8 | ЭДС индукции в движущемся проводнике | Не подтверждено |
| 3.20 | Самоиндукция | Не подтверждено |
| 3.20.1 | Индуктивность | Не подтверждено |
| 3.20.2 | Электромеханическая аналогия | Не подтверждено |
| 3.20.3 | Энергия магнитного поля | Не подтверждено |
| 3.21 | Электромагнитные колебания | В подпунктах [3.21.1](../output/topics/task-3-21-1.tex) |
| 3.21.1 | Колебательный контур | [3.21.1](../output/topics/task-3-21-1.tex) (10 задач) |
| 3.21.2 | Энергетические превращения в колебательном контуре | Не подтверждено |
| 3.21.3 | Электромеханические аналогии | Не подтверждено |
| 3.21.4 | Гармонический закон колебаний в контуре | Не подтверждено |
| 3.21.5 | Вынужденные электромагнитные колебания | Не подтверждено |
| 3.22 | Переменный ток. 1 | Не подтверждено |
| 3.22.1 | Условие квазистационарности (не ЕГЭ) | Не подтверждено |
| 3.22.2 | Резистор в цепи переменного тока | Не подтверждено |
| 3.22.3 | Конденсатор в цепи переменного тока | Не подтверждено |
| 3.22.4 | Катушка в цепи переменного тока | Не подтверждено |
| 3.23 | Переменный ток. 2 | Не подтверждено |
| 3.23.1 | Колебательный контур с резистором | Не подтверждено |
| 3.23.2 | Резонанс в колебательном контуре | Не подтверждено |
| 3.24 | Мощность переменного тока | Не подтверждено |
| 3.24.1 | Мощность тока через резистор | Не подтверждено |
| 3.24.2 | Мощность тока через конденсатор | Не подтверждено |
| 3.24.3 | Мощность тока через катушку | Не подтверждено |
| 3.24.4 | Мощность тока на произвольном участке | Не подтверждено |
| 3.25 | Электроэнергия | Не подтверждено |
| 3.25.1 | Производство электроэнергии | Не подтверждено |
| 3.25.2 | Передача электроэнергии | Не подтверждено |
| 3.25.3 | Трансформатор | Не подтверждено |
| 3.26 | Электромагнитное поле | Не подтверждено |
| 3.26.1 | Гипотеза Максвелла | Не подтверждено |
| 3.26.2 | Понятие электромагнитного поля | Не подтверждено |
| 3.26.3 | Об уравнениях Максвелла (не ЕГЭ) | Не подтверждено |
| 3.27 | Электромагнитные волны | Не подтверждено |
| 3.27.1 | Открытый колебательный контур | Не подтверждено |
| 3.27.2 | Свойства электромагнитных волн | Не подтверждено |
| 3.27.3 | Плотность потока излучения | Не подтверждено |
| 3.27.4 | Виды электромагнитных излучений | Не подтверждено |
| 4.1 | Световые лучи | В подпунктах [4.1.1](../output/topics/task-4-1-1.tex), [4.1.2](../output/topics/task-4-1-2.tex) |
| 4.1.1 | Законы геометрической оптики | [4.1.1](../output/topics/task-4-1-1.tex) (7 задач) |
| 4.1.2 | Геометрическая тень | [4.1.2](../output/topics/task-4-1-2.tex) (6 задач); В [4.1.1](../output/topics/task-4-1-1.tex) (6) |
| 4.2 | Отражение света | В подпунктах [4.2.2](../output/topics/task-4-2-2.tex) |
| 4.2.1 | Закон отражения | Не подтверждено |
| 4.2.2 | Плоское зеркало | [4.2.2](../output/topics/task-4-2-2.tex) (10 задач) |
| 4.3 | Преломление света | В подпунктах [4.3.4](../output/topics/task-4-3-4.tex) |
| 4.3.1 | Закон преломления (частный случай) | Не подтверждено |
| 4.3.2 | Обратимость световых лучей | Не подтверждено |
| 4.3.3 | Закон преломления (общий случай) | Не подтверждено |
| 4.3.4 | Полное внутреннее отражение | [4.3.4](../output/topics/task-4-3-4.tex) (10 задач); [№25](../output/fipi-physics/task-25.tex) (22) |
| 4.4 | Линзы. Ход лучей | Не подтверждено |
| 4.4.1 | Двояковыпуклая линза | Не подтверждено |
| 4.4.2 | Двояковогнутая линза | Не подтверждено |
| 4.4.3 | Виды собирающих и рассеивающих линз | Не подтверждено |
| 4.5 | Тонкие линзы. Ход лучей | Не подтверждено |
| 4.5.1 | Понятие тонкой линзы | Не подтверждено |
| 4.5.2 | Оптический центр и фокальная плоскость | Не подтверждено |
| 4.5.3 | Ход луча через оптический центр | Не подтверждено |
| 4.5.4 | Ход лучей в собирающей линзе | Не подтверждено |
| 4.5.5 | Ход лучей в рассеивающей линзе | Не подтверждено |
| 4.6 | Тонкие линзы. Построение изображений | [4.6](../output/topics/task-4-6.tex) (10 задач) |
| 4.6.1 | Собирающая линза: действительное изображение точки | Не подтверждено |
| 4.6.2 | Собирающая линза: действительное изображение предмета | Не подтверждено |
| 4.6.3 | Собирающая линза: мнимое изображение точки | Не подтверждено |
| 4.6.4 | Собирающая линза: мнимое изображение предмета | Не подтверждено |
| 4.6.5 | Собирающая линза: предмет в фокальной плоскости | Не подтверждено |
| 4.6.6 | Рассеивающая линза: мнимое изображение точки | Не подтверждено |
| 4.6.7 | Рассеивающая линза: мнимое изображение предмета | Не подтверждено |
| 4.7 | Глаз человека | Не подтверждено |
| 4.7.1 | Строение глаза | Не подтверждено |
| 4.7.2 | Аккомодация | Не подтверждено |
| 4.7.3 | Угол зрения | Не подтверждено |
| 4.7.4 | Расстояние наилучшего зрения | Не подтверждено |
| 4.7.5 | Близорукость | Не подтверждено |
| 4.7.6 | Дальнозоркость | Не подтверждено |
| 4.8 | Оптические приборы | Не подтверждено |
| 4.8.1 | Невооружённый глаз | Не подтверждено |
| 4.8.2 | Лупа (не ЕГЭ) | Не подтверждено |
| 4.8.3 | Микроскоп (не ЕГЭ) | Не подтверждено |
| 4.8.4 | Труба Кеплера (не ЕГЭ) | Не подтверждено |
| 4.8.5 | Труба Галилея (не ЕГЭ) | Не подтверждено |
| 4.9 | Принцип Гюйгенса (не ЕГЭ) | Не подтверждено |
| 4.9.1 | Волновые поверхности и лучи (не ЕГЭ) | Не подтверждено |
| 4.9.2 | Сферическая волна (не ЕГЭ) | Не подтверждено |
| 4.9.3 | Плоская волна (не ЕГЭ) | Не подтверждено |
| 4.9.4 | Вторичные волны (не ЕГЭ) | Не подтверждено |
| 4.9.5 | Вывод закона отражения (не ЕГЭ) | Не подтверждено |
| 4.9.6 | Вывод закона преломления (не ЕГЭ) | Не подтверждено |
| 4.10 | Интерференция волн | Не подтверждено |
| 4.10.1 | Сложение колебаний | Не подтверждено |
| 4.10.2 | Интенсивность волны | Не подтверждено |
| 4.10.3 | Когерентные источники | Не подтверждено |
| 4.10.4 | Условие максимума и минимума | Не подтверждено |
| 4.10.5 | Интерференционная картина | Не подтверждено |
| 4.10.6 | Схема Юнга | Не подтверждено |
| 4.11 | Интерференция света | Не подтверждено |
| 4.11.1 | Усреднение интенсивности | Не подтверждено |
| 4.11.2 | Некогерентность независимых источников | Не подтверждено |
| 4.11.3 | Зеркала Френеля (не ЕГЭ) | Не подтверждено |
| 4.11.4 | Интерференция в тонких плёнках (не ЕГЭ) | Не подтверждено |
| 4.11.5 | Кольца Ньютона (не ЕГЭ) | Не подтверждено |
| 4.11.6 | Просветление оптики (не ЕГЭ) | Не подтверждено |
| 4.12 | Дифракция света | Не подтверждено |
| 4.12.1 | Принцип Гюйгенса–Френеля (не ЕГЭ) | Не подтверждено |
| 4.12.2 | Опыт Юнга | Не подтверждено |
| 4.12.3 | Дифракционная решётка | Не подтверждено |
| 4.12.4 | Дифракционная решётка как спектральный прибор | Не подтверждено |
| 4.13 | Дисперсия света | Не подтверждено |
| 4.13.1 | Опыт Ньютона | Не подтверждено |
| 4.13.2 | Хроматическая аберрация (не ЕГЭ) | Не подтверждено |
| 5.1 | Принцип относительности Галилея | Не подтверждено |
| 5.1.1 | Наблюдатель на корабле | Не подтверждено |
| 5.1.2 | Инвариантность законов механики | Не подтверждено |
| 5.2 | Принципы СТО (не ЕГЭ) | Не подтверждено |
| 5.2.1 | Гипотеза о мировом эфире (не ЕГЭ) | Не подтверждено |
| 5.2.2 | Постулаты Эйнштейна (не ЕГЭ) | Не подтверждено |
| 5.3 | Релятивистская кинематика (не ЕГЭ) | Не подтверждено |
| 5.3.1 | Одновременность событий (не ЕГЭ) | Не подтверждено |
| 5.3.2 | Относительность одновременности (не ЕГЭ) | Не подтверждено |
| 5.3.3 | Относительность промежутков времени (не ЕГЭ) | Не подтверждено |
| 5.3.4 | Относительность расстояний (не ЕГЭ) | Не подтверждено |
| 5.3.5 | Преобразования Лоренца (не ЕГЭ) | Не подтверждено |
| 5.3.6 | Релятивистский закон сложения скоростей (не ЕГЭ) | Не подтверждено |
| 5.4 | Релятивистская динамика (не ЕГЭ) | Не подтверждено |
| 5.4.1 | Релятивистская энергия (не ЕГЭ) | Не подтверждено |
| 5.4.2 | Релятивистский импульс (не ЕГЭ) | Не подтверждено |
| 5.4.3 | Связь энергии и импульса (не ЕГЭ) | Не подтверждено |
| 5.4.4 | Релятивистское уравнение движения (не ЕГЭ) | Не подтверждено |
| 6.1 | Фотоэффект | В подпунктах [6.1.2](../output/topics/task-6-1-2.tex), [6.1.3](../output/topics/task-6-1-3.tex), [6.1.6](../output/topics/task-6-1-6.tex) |
| 6.1.1 | Опыты Столетова | Не подтверждено |
| 6.1.2 | Зависимость фототока от напряжения | [6.1.2](../output/topics/task-6-1-2.tex) (5 задач) |
| 6.1.3 | Законы фотоэффекта | [6.1.3](../output/topics/task-6-1-3.tex) (10 задач) |
| 6.1.4 | Трудности классического объяснения фотоэффекта | Не подтверждено |
| 6.1.5 | Гипотеза Планка о квантах | Не подтверждено |
| 6.1.6 | Уравнение Эйнштейна для фотоэффекта | [6.1.6](../output/topics/task-6-1-6.tex) (10 задач) |
| 6.2 | Фотоны | В подпунктах [6.2.1](../output/topics/task-6-2-1.tex), [6.2.2](../output/topics/task-6-2-2.tex), [6.2.3](../output/topics/task-6-2-3.tex), [6.2.4](../output/topics/task-6-2-4.tex) |
| 6.2.1 | Энергия фотона | [6.2.1](../output/topics/task-6-2-1.tex) (10 задач) |
| 6.2.2 | Импульс фотона | [6.2.2](../output/topics/task-6-2-2.tex) (10 задач) |
| 6.2.3 | Давление света | [6.2.3](../output/topics/task-6-2-3.tex) (10 задач) |
| 6.2.4 | Двойственная природа света | [6.2.4](../output/topics/task-6-2-4.tex) (1 задач) |
| 6.3 | Корпускулярно-волновой дуализм | Не подтверждено |
| 6.3.1 | Гипотеза де Бройля (не ЕГЭ) | Не подтверждено |
| 6.3.2 | Дифракция электронов (не ЕГЭ) | Не подтверждено |
| 6.3.3 | Соотношение неопределённостей (не ЕГЭ) | Не подтверждено |
| 6.4 | Линейчатые спектры | В подпунктах [6.4.1](../output/topics/task-6-4-1.tex), [6.4.2](../output/topics/task-6-4-2.tex), [6.4.3](../output/topics/task-6-4-3.tex) |
| 6.4.1 | Спектр испускания | [6.4.1](../output/topics/task-6-4-1.tex) (7 задач); В [6.6.1](../output/topics/task-6-6-1.tex) (7) |
| 6.4.2 | Спектр поглощения | [6.4.2](../output/topics/task-6-4-2.tex) (7 задач); В [6.6.1](../output/topics/task-6-6-1.tex) (7) |
| 6.4.3 | Спектральный анализ | [6.4.3](../output/topics/task-6-4-3.tex) (1 задач) |
| 6.5 | Строение атома | В подпунктах [6.5.3](../output/topics/task-6-5-3.tex) |
| 6.5.1 | Модель Томсона | Не подтверждено |
| 6.5.2 | Опыты Резерфорда | Не подтверждено |
| 6.5.3 | Планетарная модель атома | [6.5.3](../output/topics/task-6-5-3.tex) (2 задач) |
| 6.6 | Атом Бора | В подпунктах [6.6.1](../output/topics/task-6-6-1.tex), [6.6.2](../output/topics/task-6-6-2.tex) |
| 6.6.1 | Постулаты Бора | [6.6.1](../output/topics/task-6-6-1.tex) (20 задач) |
| 6.6.2 | Атом водорода | [6.6.2](../output/topics/task-6-6-2.tex) (8 задач); В [6.6.1](../output/topics/task-6-6-1.tex) (8) |
| 6.6.3 | Достоинства и недостатки теории Бора (не ЕГЭ) | Не подтверждено |
| 6.7 | Лазер (не ЕГЭ) | Не подтверждено |
| 6.7.1 | Индуцированное излучение (не ЕГЭ) | Не подтверждено |
| 6.7.2 | Инверсная населённость (не ЕГЭ) | Не подтверждено |
| 6.7.3 | Трёхуровневая система рубина (не ЕГЭ) | Не подтверждено |
| 6.7.4 | Устройство лазера (не ЕГЭ) | Не подтверждено |
| 6.8 | Строение ядра | В подпунктах [6.8.1](../output/topics/task-6-8-1.tex), [6.8.2](../output/topics/task-6-8-2.tex) |
| 6.8.1 | Нуклонная модель ядра | [6.8.1](../output/topics/task-6-8-1.tex) (10 задач) |
| 6.8.2 | Изотопы | [6.8.2](../output/topics/task-6-8-2.tex) (10 задач) |
| 6.9 | Радиоактивность | В подпунктах [6.9.2](../output/topics/task-6-9-2.tex), [6.9.3](../output/topics/task-6-9-3.tex) |
| 6.9.1 | Виды радиоактивных излучений | Не подтверждено |
| 6.9.2 | Радиоактивные превращения | [6.9.2](../output/topics/task-6-9-2.tex) (10 задач) |
| 6.9.3 | Закон радиоактивного распада | [6.9.3](../output/topics/task-6-9-3.tex) (10 задач) |
| 6.10 | Энергия связи ядра (не ЕГЭ) | Не подтверждено |
| 6.10.1 | Ядерные силы (не ЕГЭ) | Не подтверждено |
| 6.10.2 | Атомная единица массы (не ЕГЭ) | Не подтверждено |
| 6.10.3 | Удельная энергия связи (не ЕГЭ) | Не подтверждено |
| 6.10.4 | Насыщение ядерных сил (не ЕГЭ) | Не подтверждено |
| 6.11 | Ядерные реакции | [6.11](../output/topics/task-6-11.tex) (10 задач) |
| 6.11.1 | Энергетический выход ядерной реакции | Не подтверждено |
| 6.11.2 | Деление ядер | Не подтверждено |
| 6.11.3 | Цепная ядерная реакция | Не подтверждено |
| 6.11.4 | Термоядерная реакция | Не подтверждено |

[Каталог проекта](../knowledge/README.md) · [Манифест тематических подборок](../output/topics/_run/current-topics.json) · [Карта по кодификатору](../.scratch/theme-coverage/official-numbered.json) · [Полный индекс номерного банка](../.scratch/theme-coverage/numbered.json)
