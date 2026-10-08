# Витрина и опубликованные данные

**Русский** · [English](outputs.en.md)

Витрина — один самодостаточный HTML-файл: данные, стили и скрипт встроены
в страницу, внешних запросов при работе нет — ни шрифтов, ни CDN. Кнопка
**«Скачать»** отдаёт сам этот файл: страница сохраняет свою исходную копию,
а не текущее состояние с чужим поиском и открытыми карточками.

Опубликованные адреса:

| Адрес | Что отдаёт |
| --- | --- |
| [`/Glossary-Python/`](https://artvsmark.github.io/Glossary-Python/) | Витрина: поиск, фильтры, тёмная тема |
| [`/Glossary-Python/glossary.json`](https://artvsmark.github.io/Glossary-Python/glossary.json) | Сборка карточек (`data/glossary.json`) обычным HTTP — без клона и без токена; для чтения людьми и разовых скриптов, договор наружу у `delivery.json` |
| [`badges/.github/badges/facts.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/facts.json) | Числа о проекте: карточки, разделы, замечания, состав ответа каталогу |
| [`badges/.github/badges/objections.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/objections.json) | Замечания к содержанию: правило, уровень, область, полный список карточек |
| [`badges/.github/badges/completeness-report.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/completeness-report.json) | Полнота относительно официального Python: чего в глоссарии нет вовсе |
| [`badges/.github/badges/whatsnew.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/whatsnew.json) | Что появилось и исчезло между версиями Python — и что из нового не описано |
| [`badges/.github/badges/delivery.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/delivery.json) | Сами карточки по группам в форме `data/cards/` — их забирает Stepik-Python-Grader |
| [Вложения выпуска](https://github.com/ArtVsMark/Glossary-Python/releases/latest) | Закреплённое за выпуском: `delivery.json`, его схема и сама витрина `python_glossary.html` — файл того выпуска, а не текущего `main` |

Это контракты, а не удобство. Глоссарий забирают выгрузкой, а не копированием
файла из репозитория. `objections.json` — очередь работы над содержанием в
машинном виде: какие карточки неверны и по какому правилу.

```jsonc
{
  "schema": 1,
  "producer": "ArtVsMark/Glossary-Python",
  "source": "ArtVsMark/Glossary-Python",
  "snapshot": { "cards": 1349, "schema_version": 2 },
  "totals": { "errors": 0, "warnings": 746, "cards_affected": 421 },
  "findings": [
    { "rule": "example-indent", "severity": "warning",
      "message": "пример открывает блок, но ни одна строка не имеет отступа…",
      "count": 97, "cards": ["бинарный-поиск", "…"] }
  ]
}
```

Отметки времени в файле нет намеренно: она меняла бы его на каждом прогоне, и
ветка копила бы коммиты «ничего не изменилось». Дата есть у самого коммита.
