# Data quality and completeness

[Русский](quality.md) · **English**

## Data quality

The validator is a registry of independent rules. Errors break the build in CI;
warnings form the content backlog and do not block work.

| Rule | Level | What it checks |
| --- | --- | --- |
| `non-empty` | error | The snapshot is not empty: nothing to check is an input error, not a success |
| `required-fields` | error | The card's required text fields are filled in |
| `id-format` | error | The identifier is usable as a URL anchor |
| `unique-id` | error | Identifiers do not repeat |
| `kind` | error | The card kind is known: concept, function, exception, construct |
| `color-group` | error | The colour group is known to the showcase |
| `translated` | error | Summary and body exist in both languages |
| `label-translated` | error | Title and subcategory are translated into English |
| `platforms` | error | Platforms are named explicitly: `AllOS` means everywhere and stands alone, otherwise `Linux`, `macOS`, `Windows` without repeats |
| `platforms-summary` | error | A summary that names availability («Доступно на Unix», “Availability: Linux”) does not contradict the `platforms` field |
| `docs-url` | error / warning | The link points to docs.python.org and to a specific section |
| `version-format` | error | Versions are written as `N.N` (`added` also allows `<N.N`) and go in order `added ≤ deprecated ≤ removed` |
| `added` | error | The Python version the feature appeared in is named |
| `deprecated-text` | error | If the summary calls the feature deprecated or names a removal version, `deprecated` and `removed` are filled in |
| `inherited-summary` | error | The English summary is not the docstring of someone else's built-in exception (“Base class for arithmetic errors” on a decimal signal) |
| `summary-length` | warning | Summary is 30 to 200 characters: it fits in a list |
| `body-length` | warning | Body is at least 60 characters — otherwise it adds nothing to the summary |
| `examples` | warning | The card has at least one example |
| `example-indent` | warning | An example that opens a block contains an indented line |
| `related-resolves` | warning | A “see also” link points to an existing card |
| `duplicate-title` | error | Two cards about one object: the same title ignoring `()` and case, or a bare and a full name with the same documentation link |
| `function-title` | error | A `function` card describes one function: the title does not list names separated by `/` |
| `title-resolves` | error | The full name in the title (`datetime.datetime.strftime()`) exists among built-ins or the standard library |
| `translation-length` | warning | The English half of summary and body is no shorter than 0.6 and no longer than 1.8 of the Russian one |
| `section-size` | warning | A section does not consist of a single card |

Objections are the work queue for cards in `data/cards/`. `make objections`
collects them into a report: the rule, how many cards are affected and which ones.

## Completeness: what is missing entirely

The validator judges the cards that exist. The ones that do not are counted by
`make completeness`: the language inventory is taken by **introspecting a running
interpreter** — no network and no parsing of documentation — and matched against
the cards by exact full name (`functools.reduce`, `str.split`).

The answer depends on the Python version and is therefore named in the report:
**the version is an axis of measurement, not a setting**. The inventory is taken on
every version in the matrix, and the difference between neighbours answers “what
appeared in 3.14” — the question people usually take to What's New, answered here by
subtraction, with no network and no parsing of someone else's markup:
<!--предмет:нет-->

```bash
glossary inventory -o inventory-3.13.json   # on 3.13
glossary inventory -o inventory-3.14.json   # on 3.14
python scripts/whatsnew.py inventory-*.json # what appeared and what disappeared
```

The value is not the list of new things but its intersection with the glossary:
each new entity carries `documented` — whether there is a card for it. Appeared in
the language and not described — that is tomorrow's queue.

Python 3.15 is measured in a separate run that is allowed to fail: its feature
freeze has passed, so the list is practically final, but there is no reason to
break publishing over a release candidate.

The boundary is stated plainly: introspection sees objects, not text. Syntax
(`match`, walrus, f-string specifiers), deprecations and removals are not captured —
these layers are not measured, and that is written down rather than left unsaid.

**This is not “coverage”.** Coverage means test coverage of the code — counted by
`pytest --cov` and shown by the badge of that name. Two different numbers under one
name once collided in files, so here it is completeness, with its own badge. The
floor is held by `tests/completeness_floor.json`: the undescribed does not grow, and
the number can rise without a single card edit — the language grows on its own.

Current state: **<!--m:errors-->0<!--/m:errors--> errors, <!--m:warnings-->0<!--/m:warnings--> warnings**. The warning count
is fixed in `tests/quality_baseline.json` — the ratchet keeps objections from
growing and reminds you to lower the bar when the data gets cleaner.
