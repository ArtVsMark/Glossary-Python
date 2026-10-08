# How to contribute

[Русский](contributing.md) · **English**

Thank you for your interest in the project. Below is everything you need to know
for your changes to pass review on the first try.

## Setting up the environment

```bash
git clone https://github.com/ArtVsMark/Glossary-Python.git
cd Glossary-Python
make install     # venv, package in development mode, dev dependencies, pre-commit
```

`make install` installs the pre-commit hooks: before every commit they run ruff,
mypy, data validation and the showcase sync check. The full set of checks
(the same as in CI) is `make check`.

## The main rule

**Glossary content is edited in `data/cards/`.** Cards live one file per
colour group; `data/glossary.json` is assembled from them, and `site/python_glossary.html`
from the assembly. Both files are derived: an edit made in them lives until the next build.

```
data/cards/*.json ──► data/glossary.json ──► site/python_glossary.html
 (edited here)           (assembly)             (showcase)
```

Stepik-Python-Grader receives the final content as an export and does not edit
cards itself: the same card kept in two places drifts apart on the very first
sync.

## What to do about an error in a card

Fix it in `data/cards/<group>.json`, then run `make assemble`. The validator already
counts such findings, and the report shows where to start:

```bash
make objections            # report: rule, number of cards, which ones exactly
make objections --limit 0  # the full list, for when it is worked through as a whole
```

If the validator has no rule for it, add one: a single function in
`src/glossary/validation.py` and a line in `RULES`. That turns the defect into a
list of cards instead of words, and its return is caught automatically.
Content and tooling ship as separate changes.

## Building

```bash
make assemble                                            # data/cards/ → data/glossary.json
make validate                                            # check quality
make build                                               # rebuild the showcase
git add data/cards data/glossary.json site/python_glossary.html
```

The build is idempotent: the same input produces a byte-identical file. It
includes cards with status `ready`, ordered by section, then by `id`.
`make assemble-check` compares the assembly with the cards without writing anything.
A card's group is set by the file name; the card itself has no `color_group` field.

### Card fields

The shape is inherited from the grader's knowledge base, where the cards came from,
and matches what the grader reads: the export needs no schema conversion.
The full description is in `data/glossary.schema.json`.

| Field | Requirement |
| --- | --- |
| `id` | Unique, without spaces or the characters `#/?&=%"'<>` — it is used as a URL anchor |
| `title` | `{ru, en}`, the display name: `str.strip()`, `ValueError`, `match`. A name from code is not translated — the halves are identical |
| `kind` | `term`, `function`, `exception` or `construct` |
| `summary` | `{ru, en}`, 30–200 characters: fits in a list without expanding |
| `body` | `{ru, en}`, a detailed explanation of at least 60 characters |
| `section` | The section — a navigation key; labels in both languages are set by `glossary/taxonomy.py` |
| `subcat` | `{ru, en}`, a subcategory within the section |
| `color_group` | One of ten groups; set by the file name in `data/cards/` |
| `aliases` / `keywords` | Synonyms and keywords — search works on them |
| `examples` | Self-contained examples: an array of blocks, each block an array of code lines with the result in `# →` comments. Every block runs on its own — the imports and definitions it needs are written in the block itself |
| `related` / `related_errors` | Identifiers of existing cards |
| `added` | Available since which version: `N.N`; `<3.0` — appeared back in Python 2; `3.0` — came with Python 3 |
| `deprecated` | Deprecated since which version: `N.N` or an empty string |
| `removed` | The version in which it was or will be removed — the last one it works in: `N.N` or an empty string |
| `platforms` | `["AllOS"]` — everywhere; otherwise a subset of `Linux`, `macOS`, `Windows`. Per the documentation's `availability` directive: Unix and POSIX mean `Linux` and `macOS` |
| `docs_url` | A specific section or anchor on docs.python.org, not the root |

### Quality ratchet

`tests/quality_baseline.json` records how many warnings are allowed for
each rule. The test does not let that number grow. The baseline may be lowered only
after editing cards in `data/cards/` — if an edit **reduced** the number of
objections, the test fails with a hint saying exactly which number to lower.
This is a deliberate step: data quality moves in one direction only.
<!--предмет:направление планок качества данных-->

## Changing code

- Python 3.14+ is the project's floor; the package code is also parsed by the lowest
  language-measurement version (the `inventory` matrix in `badges.yml`, held by `tests/test_measured_versions.py`).
  Type annotations are mandatory, mypy in strict mode.
- Docstrings on every module, public class and public function; Google style.
- A comment explains "why", not "what": the "what" should be visible from the code.
- New behaviour comes with a test. Coverage in CI is at least 90 %.
- Formatting and imports are handled by ruff (`make format`); nothing needs to be
  adjusted by hand.
- A fix names the neighbouring cases — those decided by the same condition — and
  answers for each: did it work before, and does it work now. "There are no
  neighbours" is said, not implied (catalogue rule 195).
- A second finding in the same place — a predicate, a parser, a branch —
  stops fixing one form at a time: first a list of forms with a measurement, and a
  check for each, then the fix (rule 210).

### Changelog entries

Not a single line in `CHANGELOG.md` by hand. An entry arrives as a **separate file**:

```
changelog.d/<slug>.<section>.md
```

Inside is one line, without a leading hyphen. Sections: `added`, `changed`,
`fixed`, `removed`, `internal`. Details are in
[`changelog.d/README.en.md`](../../changelog.d/README.en.md).

Two files with different names never conflict. A shared file conflicts on
every parallel change, and a conflicting change is left **with no checks
at all**: the run goes against the merge commit, which does not exist when there is a conflict.

```bash
make changelog-check     # entry format
make changelog-preview   # how it will be assembled
```

### Numbers in documentation

Not a single digit in the README by hand. A number lives inside a named marker and
is rewritten by the build:

```markdown
**<!--m:cards-->581<!--/m:cards--> cards**
```

```bash
make facts        # recount and rewrite
make facts-check  # check that nothing has drifted
```

The gate fails both when a value is stale and when a marker has been removed: without the third
condition there is no mechanism, just a hand-written number with an extra step. A new number
is a key in `marker_values()` from `scripts/facts.py` and a marker in the README.

### Links in documentation

A broken link between documents is caught by the gate, not by the reader:

```bash
make links   # the same step as in CI
```

The target is found by **markup** — `](address` and `]: address` — not by the address
occurring in the text. The difference is not cosmetic: a substring is found in the label, so
`[docs/dev/architecture.md](nowhere.md)` passes a substring check green and
leads nowhere.

What the gate does not catch is named in the docstring of `scripts/check_links.py`: external
`https://` addresses are not requested (a network step would be non-deterministic),
`#section` anchors are not resolved, code is masked out. The subject is the `DOCUMENTS` list
in the same file; a new document is added to it explicitly.

### How to add a validation rule

1. Write a function in `src/glossary/validation.py` with the signature
   `(Glossary, ValidationConfig) -> Iterator[Issue]`.
2. Add it to the `RULES` tuple.
3. Move threshold values, if any, into `ValidationConfig`.
4. Cover both outcomes with tests — the rule firing and not firing.
5. If the rule finds objections in the current data, add their count
   to `tests/quality_baseline.json` and describe the rule in the README table.

A new rule is introduced as a warning. It becomes an error once the
data fully complies with it — otherwise the `main` branch turns red.

### How to add an export format

1. Create a class in `src/glossary/exporters/` with the attributes `name`, `suffix`
   and a `render(glossary) -> str` method. File system work stays with the
   calling code.
2. Register the class in `_FACTORIES` in `exporters/__init__.py` — the CLI picks up
   the format automatically.
3. The parametrised test `test_every_registered_format_renders` covers the basic
   contract; add tests for the format's specifics.

## Commit and pull request style

Commits follow [Conventional Commits](https://www.conventionalcommits.org/ru/):

```
feat(export): add Anki export
fix(cli): correct exit code when the showcase is missing
data: refine descriptions of the logging module cards
docs: describe how to add validation rules
```

Before submitting a PR:

```bash
make check
```

Fill in the template in the PR description and state what exactly you checked. A PR with red CI
is not reviewed.

Numbers, lists and "what was touched" in the PR body and in the changelog fragment are taken
from a command at the moment of writing — `git diff --stat origin/main`, the output of `make check` —
rather than recalled, and the command is named alongside (catalogue rule 215).

## Where to write

- A new card or a content fix — an issue using the matching template.
- A bug in the tooling or the showcase — the "Tooling bug" template.
- Questions and ideas for development — Discussions.

### Issues for new contributors

The `good first issue` and `help wanted` labels bring English-speaking showcase
readers here, so the body of such an issue is written in two languages: the
Russian text, then a `---` separator and an `## In English` section with the
translation. The rule also applies when a label is put on a long-open issue: the
translation is written first (catalogue rule 065).
