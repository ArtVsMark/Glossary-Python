# Quick start and commands

[Русский](getting-started.md) · **English**

## Repository layout

| Component | Purpose |
| --- | --- |
| `data/cards/<group>.json` | Cards — the source of content, edited here |
| `data/glossary.json` | Assembled from `data/cards/` plus the format version (derived, never edited by hand) |
| `data/glossary.schema.json` | JSON Schema — autocompletion and validation in the IDE |
| `site/python_glossary.html` | The built showcase: search, filters, dark theme, works offline |
| `src/glossary/` | The package: validation, showcase build, export, CLI |
| `tests/` | Tests of the code and of the data contract |

## Where the data comes from

```
data/cards/*.json ──► glossary assemble ──► data/glossary.json ──► site/python_glossary.html
   (source)               (assembly)             (derived)              (showcase)
                                                       │
                                                       └──► export ──► Stepik-Python-Grader
```

Content has one owner, and it lives here: `data/cards/` is edited, everything
else is built. The grader does not edit cards — it reads the export; a card
edited in two places would diverge at the very first sync.
<!--предмет:правка содержания глоссария-->

```bash
make assemble        # build data/glossary.json from data/cards/
make validate        # check quality
make objections      # the content work queue
```

## Quick start

```bash
git clone https://github.com/ArtVsMark/Glossary-Python.git
cd Glossary-Python
make install          # venv + package + dev dependencies + pre-commit
make check            # linter, types, tests, validation, showcase in sync
```

Without `make`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,schema]"
python -m glossary stats
```

## Commands

```bash
glossary stats                          # summary: cards, sections, completeness
glossary validate                       # data quality check
glossary validate --strict              # warnings count as errors
glossary validate --format json         # machine-readable report
glossary build                          # rebuild site/python_glossary.html
glossary build --check                  # is the showcase in sync with the data? (for CI)
glossary export -f markdown -o out.md   # export: html, json, markdown, csv
glossary assemble                       # build data/glossary.json from data/cards/
glossary assemble --check               # is the assembly in sync with the cards? (for CI)
glossary objections                     # content objections — the work queue
glossary objections --format json       # the same list as a machine contract
glossary completeness                   # what the glossary lacks entirely
```

The package also runs as a module: `python -m glossary …`. There are no runtime
dependencies — a Python 3.14+ interpreter is enough. The language measurement
(`glossary inventory`) runs from the tree on older versions too, from 3.11: that is
how the difference between versions is taken.

## How to edit the glossary

A card is edited in `data/cards/<group>.json`; the two other files are derived
and built by commands — see “Where the data comes from”:

```bash
make assemble    # data/cards/ → data/glossary.json
make validate    # what broke?
make build       # rebuild the showcase
git add data/cards data/glossary.json site/python_glossary.html
```

An in-place edit of `data/glossary.json` is lost at the next build, and so is an
edit of `site/python_glossary.html`; CI compares both files with their input and
rejects any mismatch. Details — in [contributing.en.md](contributing.en.md),
architecture decisions — in [architecture.en.md](architecture.en.md).
