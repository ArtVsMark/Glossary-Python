# Showcase and published data

[Русский](outputs.md) · **English**

The showcase is a single self-contained HTML file: data, styles and script are
embedded in the page, and it makes no external requests while running — no fonts,
no CDN. The **"Download"** button hands over this very file: the page keeps its
original copy, not the current state with someone else's search and open cards.

Published addresses:

| Address | What it serves |
| --- | --- |
| [`/Glossary-Python/`](https://artvsmark.github.io/Glossary-Python/) | Showcase: search, filters, dark theme |
| [`/Glossary-Python/<id>/`](https://artvsmark.github.io/Glossary-Python/functools.reduce/), [`/Glossary-Python/en/<id>/`](https://artvsmark.github.io/Glossary-Python/en/functools.reduce/) | One card's page in Russian and in English: its own address for search and links, with a button that opens the showcase at `#id`. Built at publication from the card build and not kept in `main` (`glossary pages -o DIR`) |
| [`/Glossary-Python/sitemap.xml`](https://artvsmark.github.io/Glossary-Python/sitemap.xml) | The sitemap: the showcase and both pages of every card — it is what gets submitted to search consoles |
| [`/Glossary-Python/glossary.json`](https://artvsmark.github.io/Glossary-Python/glossary.json) | The card build (`data/glossary.json`) over plain HTTP — no clone, no token; for people to read and for one-off scripts, the outward contract belongs to `delivery.json` |
| [`badges/.github/badges/facts.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/facts.json) | Numbers about the project under the showcase facts contract 1.5: version, release, tests, Python, checks; cards, sections and objections are in `exchange.glossary` |
| [`badges/.github/badges/objections.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/objections.json) | Content objections: rule, level, scope, the full list of cards |
| [`badges/.github/badges/completeness-report.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/completeness-report.json) | Completeness against official Python: what the glossary lacks entirely |
| [`badges/.github/badges/whatsnew.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/whatsnew.json) | What appeared and disappeared between Python versions — and which of the new things are not described |
| [`badges/.github/badges/delivery.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/delivery.json) | The cards themselves, by group, in the `data/cards/` form — Stepik-Python-Grader fetches them |
| `badges/.github/badges/consumer-verdicts.json` | The answer to Stepik-Python-Grader's proposals: a verdict for every slug — done, accepted, rejected, pending (published by the nightly run) |
| [`badges/.github/badges/contracts.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/contracts.json) | The family manifest: the latest release, what the glossary gives (`glossary-form` — the card form in the export) and declined links with a reason; the catalogue summary reads it for the family badge |
| [Release assets](https://github.com/ArtVsMark/Glossary-Python/releases/latest) | Pinned to a release: `delivery.json`, its schema and the showcase itself, `python_glossary.html` — the file of that release, not of the current `main` |

These are contracts, not a convenience. The glossary is taken through the export,
not by copying a file from the repository. `objections.json` is the content work
queue in machine form: which cards are wrong and under which rule.

```jsonc
{
  "schema": 1,
  "producer": "ArtVsMark/Glossary-Python",
  "source": "ArtVsMark/Glossary-Python",
  "snapshot": { "cards": 1349, "schema_version": 2 },
  "totals": { "errors": 0, "warnings": 746, "cards_affected": 421 },
  "findings": [
    { "rule": "example-indent", "severity": "warning",
      "message": "the example opens a block, but no line is indented…",
      "count": 97, "cards": ["бинарный-поиск", "…"] }
  ]
}
```

There is deliberately no timestamp in the file: it would change the file on every
run, and the branch would pile up "nothing changed" commits. The commit itself
carries the date.
