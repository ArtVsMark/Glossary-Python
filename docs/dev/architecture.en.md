# Architecture

[Русский](architecture.md) · **English**

This document records the decisions taken and what they cost. Its purpose is to
avoid revisiting the same questions a second time six months from now.

## The big picture

```
data/cards/<group>.json
   (source, edited here)
        │  glossary assemble
        ▼
data/glossary.json ──► loader ──► Glossary ──┬─► validation ──┬─► report / exit codes
   (assembly)                                │                └─► objections (work queue)
                                             └─► exporters ──┬─► HTML showcase
                                                             ├─► JSON ──► export ──► Stepik-Python-Grader
                                                             ├─► Markdown
                                                             └─► CSV
```

Content flows one way: cards are edited in `data/cards/`, everything else is
assembled, and the grader reads the export. Validator objections are the work
queue for the cards, kept here as well. Models are immutable
(`frozen=True, slots=True`), so exporters cannot diverge in how they interpret
the same cards.
<!--предмет:обратный поток к источнику-->

## Decisions taken

### Data is separated from presentation

**Before.** The only artifact was a 599-line `python_glossary.html` holding CSS,
JavaScript and the card JSON as a single 532 KB line.
<!--предмет:нет-->

**After.** `data/glossary.json` is a separate data file, and the HTML is built from it.

**Why.** The data became fit for automated checking, export and transfer
between projects; a git diff reflects meaningful edits rather than bytes
shifting inside one giant line.

**Cost.** A build step appeared. It is enforced by `glossary build --check`
in CI and in a pre-commit hook, so it cannot be forgotten.

### Content has one owner, and it lives here

**Before.** The source was the knowledge base of `ArtVsMark/Stepik-Python-Grader`;
this repository held a snapshot of it, re-read by `scripts/import_from_grader.py`,
and card errors were sent there as a letter (`glossary objections`) and waited
to be fixed.

**After.** Cards are maintained here, in `data/cards/<group>.json` — one file per
colour group, the same layout the grader used. `data/glossary.json` is assembled
from them by `glossary assemble`, and CI checks the assembly against the cards.
The grader receives the final content as an export and reads it itself
(catalogue rule 174: the publisher computes, the consumer reads). Owner's
decision of 05.10, issue #76; the last import from the grader is #77.

**Why.** In the grader every card edit runs the whole project's full CI — slow
and expensive — while the checks the glossary needs (validator, completeness,
showcase build) live here. An owner who cannot check their own edit without
someone else's pipeline rarely edits. The flow is still one-way — the direction
changed, not the number of owners.

**Cost.** The grader depends on the export being published here reliably and in
a shape it knows. It is pinned to a release and learns about a new one through
its own drift watchdog; a content edit reaches students together with a release.
The transition window, in which a card edit made in the grader was lost, was
closed by stage 3 of #76 — the export import in the grader
(Stepik-Python-Grader#1573, 08.10); `scripts/import_from_grader.py`, which read
the grader in the opposite direction, has been removed.

**Rejected.** Keeping the grader as owner: every content edit would cost the
full CI of another project. Two-way synchronisation: two live copies have no
arbiter, and no one is there to settle which version is right. Writing into the
grader's repository from here: the consumer knows better when and how to fetch
data, and a publisher with write access to the consumer is a needless coupling.
One monolithic card file instead of one file per group: the diff of an edit
drowns among a thousand neighbours, and parallel changes to different groups
conflict for no reason.

### The card shape mirrors the grader's shape

Schema v2 adopted the grader's knowledge-base fields as they were: `title`, `kind`,
bilingual `summary`/`body`, `aliases`, `keywords`, `related`. The cards moved
here from there (#76), and the shape moved with them.

**Why.** The grader reads the export from here. A matching shape reduces its
import to a download; a third shape of our own would mean a mapping and drift at
the very first new field.

**Exception — `color_group`.** The top-level rubric is expressed not by a field
but by the file layout of `data/cards/` (`builtin.json`, `exc.json`, `str.json`).
Assembly into one file erases that boundary, so it carries the file name into a
card field. Deriving the colour from tags does not work: tags are topical
(`os`, `bytearray`, `collections`) and do not name the group — on real data such
a derivation missed on 667 cards out of 1349.

**Cost.** A new file in `data/cards/` is an unknown colour group. The `color-group` rule raises it as an error rather than substituting a default
colour: a card silently merged into another rubric looks healthy.

**Rejected.** A card shape of our own, different from the grader's: a two-way
mapping drifts at the very first new field, and the grader would have to
transform the export. Deriving the group from tags instead of the file layout:
a miss on 667 cards out of 1349 (measured above).

### Card labels are bilingual, the section is a key (schema v3)

**Before.** In schema v2 the texts (`summary`, `body`) were bilingual, while the
title and subcategory were a single string. 127 titles and 1250 subcategories
were in Cyrillic, and the showcase's English mode stayed half Russian.

**After.** `title` and `subcat` are `{ru, en}`, like the texts (#85). The section
remains a key string: its labels in both languages already live in
`glossary.taxonomy`. During migration the English half was filled for labels
without Cyrillic — names from code (`str.split()`, `namedtuple`) that are not
translated; the rest await a content edit and are counted by the
`label-translated` rule. When a half is empty, the showcase shows the Russian one.

**Why.** The glossary is bilingual throughout, except for code. The grader reads
the export from here (#76, stage 2), so the shape changes before the first
export, not after: otherwise the consumer would have to rebuild twice.

**Cost.** Schema v3 is incompatible with v2: the loader rejects an old file with
a hint, and the grader's import at stage 3 reads the labels as an object. A
subcategory repeats across the cards of one section, and its translation can
drift between them — this is not measured.

**Rejected.** A `{ru, en}` section in every card: 55 labels would multiply into
1349 copies next to the `taxonomy` table, where they already exist — a second
place for one fact (an analogy with rule 214 on a single implementation). A subcategory dictionary instead of a card field:
a card edit would require editing a second file, and the export for the grader
would need stitching. A temporary English half copied from the Russian: the
`language-script` rule would rightly call it untranslated, and the debt would
hide under the guise of a translation.

### Platform availability is a card field (schema v4)

**Before.** Whether a function exists only on Windows or only on Linux was known
to the card text — if at all. The machine did not see it, and the showcase did
not show it.

**After.** The `platforms` field: `AllOS` — everywhere, otherwise a subset of
`Linux`, `macOS`, `Windows` (#83). "Everywhere" is written explicitly, by the
owner's decision: an empty list is indistinguishable from "forgot to fill in".
Values are derived from the `availability` directive of the CPython
documentation: `Unix` and `POSIX` give `Linux` and `macOS`, `not macOS` removes
`macOS`, `Linux >= …` gives `Linux`. The showcase shows a badge on restricted
cards; `AllOS` gets no badge — across a thousand cards it would be noise.

**Why.** A measurement against the documentation: 137 cards have a restriction,
and it does not reduce to Windows — 14 are available on Linux alone, several on
Unix without macOS. The owner decided: if such cards exist, the field is
separate (05.10).

**Cost.** Schema v4: the grader must understand the new shape (Stepik-Python-Grader#1573),
and the loader rejects files of older versions. WASI, Android and iOS from the
documentation do not make it into the field — a learner on a study machine does
not need them, and this is a deliberate loss of precision.

**Rejected.** An empty list as "everywhere": shorter, but silence in the data
reads two ways. A note in the card text: the machine does not see it and has
nothing to check it with. The raw `availability` string from the documentation
(`Unix, not WASI, not Android`): precise, but it does not answer the learner's
question "will it work for me", and it can only be compared by parsing. Three
boolean fields, one per system: three keys on each of 1349 cards for an answer
that is "everywhere" for the overwhelming majority.

### Feature lifecycle — three version fields (schema v5)

**Before.** A single `version` field — "when it appeared". It was empty on 1054
of 1356 cards, and emptiness meant "has been around for ages" — the same as
"not checked". That a feature was deprecated or would be removed was stated by
the text of 28 summaries — and the machine did not see it.

**After.** Three fields (#122): `added` — the version since which the feature
exists; `deprecated` — the version in which it was declared deprecated;
`removed` — the version in which it was removed or is scheduled for removal,
i.e. up to which version it works. For Python 2 features `added` equals `<3.0`,
by the owner's decision: "appeared before 3.0". `3.0` means the feature arrived
with the first Python 3 release. The order `added ≤ deprecated ≤ removed` is
enforced by the `version-format` rule; `<3.0` precedes any 3.x. An empty `added`
is an error of the `added` rule: the field is filled on every card (#126), and
emptiness would again mean "not checked".
A summary that calls its subject deprecated or names the version of its removal
requires the `deprecated` and `removed` fields — the `deprecated-text` rule:
otherwise the showcase and the export present as alive a feature whose death the
text announces.

**Why.** The owner: every card must show from which version a feature exists and
up to which version it works. A single field cannot answer the second question,
and the summary text cannot be checked.

**Cost.** Schema v5 and export shape 5.0 — a major change: `version` changed its
name and meaning, and `added` is mandatory. The grader, pinned to a release,
will migrate following the shape's changelog (Stepik-Python-Grader#1573); the
loader rejects files of older versions. The exact version of appearance within
the Python 2 line is not stored — the `<3.0` boundary is deliberately coarser.

**Rejected.** The exact Python 2 version (`2.4`, `2.6`): there is no reliable
source, the 3.x documentation carries no 2.x annotations, and a learner on
Python 3 does not need it. The value `3.0` for all long-standing features: it
would erase the difference between `str.split` and `nonlocal`, which came with
Python 3. A single string field like `3.4–3.12`: the format would need parsing,
and version order could not be checked by the schema. An
`active/deprecated/removed` status instead of versions: it answers "is it
deprecated", but not "up to which version does it work".

### Examples are standalone blocks (schema v6)

**Before.** `examples` was a flat array of strings, and all of a card's examples
were glued into one chunk of code. The owner: "the examples are mush". The
gluing also hid a defect: on seven cards the demonstration call had slipped into
the body of the preceding function and never executed at all, while the gate
stayed green — after all, the code did not fail (#129).

**After.** An array of blocks, a block being an array of strings (#125). A block
is standalone: `scripts/check_examples.py` executes it in its own process, and
an example that relies on a definition from a neighbouring one becomes a
numbered finding. The showcase draws each block in its own frame with a separate
"Copy" button, and the Markdown export as a separate code block.

**Why.** An example teaches when it can be read and run on its own: the learner
copies one example, not six, and gets exactly the promised output.

**Rejected.** An `output` field next to the code (`{code, output}`): the output
would drift away from the line that prints it, while the `# →` convention at the
call already lives in 1292 cards and is clearer for the learner. The gate checks
`# →` against what is printed by itself, without
changing the shape: a promise on a line with `print` or with a call to the
block's own function is looked up in the block's output, while a REPL-style
value annotation (`re.findall(...)  # → [...]`) is not
checked — it cannot be told apart from printing by syntax alone. A block as one string with `\n`: card JSON
is edited by hand, and escaped newlines make that a torment.

### The showcase is built by substitution, not by a template engine

The template `src/glossary/templates/showcase.html` is the original page in which
the data block is replaced by `{{GLOSSARY_DATA}}`, and the filter table by
`{{NAVIGATION}}`.

**Why.** There are two substitution points, and both are JSON blocks. Jinja2
would add a dependency, a new syntax and the risk of accidental escaping — for
the sake of two `str.replace` operations.
The template stays valid HTML: it can be opened in a browser and edited in any
editor.

**Cost.** The showcase logic (search, filters, language switching, highlighting,
page download) lives in JavaScript inside the template and is not covered by
Python tests. The behaviour is no longer trivial — this is recorded as technical
debt, as a task for browser tests.

### The page can save itself

The "Download" button delivers not the current DOM but a copy of the original
markup, captured before the script changed anything in it.

**Why.** The showcase is downloaded for offline use. Saving the current DOM
would carry along someone else's search query, expanded cards and someone
else's theme — the file would look healthy and behave oddly. The snapshot is
taken once, and a copy of a copy matches the original byte for byte.

**Cost.** The page must stay self-contained: no external fonts, no CDN, no lazy
loading. Hence system fonts instead of web fonts, and inline rather than linked
JavaScript.

### Zero runtime dependencies

The package uses only the standard library: `json`, `csv`, `dataclasses`,
`argparse`, `importlib.resources`, `importlib.metadata`, `pathlib`.
<!--предмет:зависимости пакета-->

**Why.** The tool runs in any environment with Python 3.14+ — in a minimal CI
container, on a contributor's machine, from another project. There is no chain
of updates and no vulnerabilities in transitive dependencies.

**Cost.** A CLI on `argparse` is wordier than one on Typer or Click. For four
commands the difference does not pay for a dependency.

### The version is declared once

**Before.** The version was stated twice, and both entries were manual: the
`version` field in `pyproject.toml` and the `__version__` literal in
`src/glossary/__init__.py`. Agreement relied on attentiveness, and the entries
could diverge silently — the built distribution would carry one number,
`glossary --version` would print another, and this would surface after
publication.

**After.** The number is declared in `pyproject.toml` and nowhere else.
`__version__` reads it from the installed distribution's metadata
(`glossary._version.package_version`), and `tests/test_version.py` fails the
build both when the declared and installed versions differ and when a literal
returns to the package sources.

**Why.** Reducing to one source is cheaper than reconciling two: reconciliation
catches a divergence, while a single source does not allow one. `importlib.metadata`
is the standard library, so zero runtime dependencies is preserved.

**Cost.** A tree without installation carries no metadata, and the version there
is `0+unknown`. This is a deliberate refusal to answer, not a failure: a
plausible number would be a second answer with nothing to check it against.
Another cost: after editing the version in `pyproject.toml` the package must be
reinstalled, otherwise the gate turns red on stale metadata — that is exactly
what it is there for.

**Rejected.** A dynamic version from a git tag: it pulls in a build dependency
(`hatch-vcs` or `setuptools_scm`), and zero dependencies here is a decision
taken, not an accident. Also rejected: comparing two manual entries with a test:
two sources remain two, and the gate merely reports that they have already
diverged.
<!--предмет:нет-->

### The version is computed by the family scheme

**Before.** The version did not go outward at all: `facts.json` carried the
reason "no version", although `pyproject.toml` declared `0.1.0`. There were no
tags, and the sibling projects of the family showed a version while the
glossary showed a blank.

**After.** The scheme is shared with the rule catalogue and the grader: the
release tag `vX.Y.0` plus the number of accepted changes after it
(`scripts/version.py`). The first tag is `v0.1.0` on the commit where `0.1.0`
is declared, so the count runs over the whole history. The `version` field in
`pyproject.toml` remains the starting point and must match `X.Y.0` of the
latest tag — `tests/test_version.py` enforces this. `facts.json` receives
`release` (the `X.Y` series, facts contract 1.3) and `version` (`X.Y.N`), and as badges `release.json` and
`version.json`.

**Why.** The showcase compares the family's projects in one shape; a version
computed by a formula of our own would read next to the siblings' as the same
number.

**Cost.** The version needs history with tags: the publishing run and the tests
take a full clone. Without a tag the answer is a reason in `none` and the third
outcome of `scripts/version.py`, not a plausible `0.1.N`.

**Rejected.** `setuptools_scm` and `hatch-vcs`: a build dependency for a number
the package metadata does not need — the refusal from "The version is declared
once" stands. Also rejected: counting `--first-parent` commits: the shape of
history depends on the clone, while change numbers do not.
<!--предмет:нет-->

### Python 3.14 floor, language measurement wider than the floor

**Before.** A single 3.11–3.14 matrix answered two questions at once: which
versions the project is tested on, and which language versions the inventory
measures.

**After.** The questions are separated (owner's decision of 1 October,
Glossary-Python#53). Project checks run on the 3.14 floor (`ci.yml`) and on the
pre-release 3.15 in a separate `python-next.yml` run, whose red is honest and
does not block merging. Language measurement stays a 3.11–3.14 matrix plus
3.15-rc in `badges.yml`: the "what appeared" difference is built from it. The
measurement runs the package from the tree without installing it —
`requires-python` refuses installation below the floor, and there are no
runtime dependencies. The cost: the package code has to parse under the grammar
of the oldest measured version; `tests/test_measured_versions.py` holds this,
and ruff does not suggest PEP 695 syntax inside the package.

**Rejected.** Shrinking the measurement matrix to 3.14 as well, literally as the
task said: the version difference would be empty, and `whatsnew.json` would stop
answering its question. Also rejected: measuring on 3.14 and 3.15 without the
older versions — the history of "what appeared in 3.12 and 3.13" would vanish
from the report, which changes the meaning of the contract, i.e. a major bump.
<!--предмет:нет-->

### Red on the pre-release version wakes someone with an issue

**Before.** `python-next.yml` ran once a week, and its outcome showed up on a
badge. Since 05.10 the run had been red and nobody noticed: a badge wakes no one,
you have to go and look at it.

**After** (Glossary-Python#154). The run is daily, and the `alarm` job keeps one
issue labelled `python-next` open while the run is red and closes it on green
(`scripts/next_alarm.py`). While the alarm is raised, a repeated red stays
silent. A newly opened issue is re-read from the platform: without the label the
next run would not find it (catalogue rule 188). The transport is the same
`_call` the auto-merge uses; there is no second implementation of talking to the
platform.

**Rejected.** The platform's notification about a failed schedule: it goes to
whoever last edited the `cron` line, and notification settings live outside the
tree — there is no way to check it arrived. Also rejected: a comment on every red
run — a daily "still red" turns into noise people stop reading. And blocking
merges on a red 3.15 — no: it answers a question about someone else's calendar,
not about the quality of the change (catalogue rule 084).
<!--предмет:нет-->

### Red on a schedule — every run has its own addressee

**Before.** Only python-next had an alarm. Daily CI, badges and facts, and the
catalogue inbox also run on a schedule, and their red sits on the runs tab where
nobody goes. The answer to catalogue rule 142 honestly said "held by nothing".

**After.** A separate `schedule-alarm.yml` run is triggered by the completion of
those runs and, if the run was scheduled, reconciles its outcome with an alarm
issue — the same logic as python-next (`scripts/schedule_alarm.py` on top of
`scripts/next_alarm.py`): one issue per run, a repeated red stays silent, green
closes it. `tests/test_schedule_alarm.py` holds that no scheduled run is left
without an addressee.

**Rejected.** An `if: failure()` step in every watched run: it needs permission
to write issues, and the whole run would get it — CI must not have it. Also
rejected: one shared issue for all runs — closing it on one run's green would
clear the alarm about another.
<!--предмет:нет-->

### The owner's token queues the merge — so it wakes main

**Before.** Auto-merge queued a change with the stock `GITHUB_TOKEN`, and the
platform merged it as `github-actions[bot]`. A push made with that token does not
become a push event: after a merge, neither CI on `main`, nor showcase
publishing, nor the badges woke up. Measurement of 07.10: the showcase sat on an
hour-old commit while five changes landed in `main`, and release 1.2.0 shipped
with stale "release" and "version" badges.

**After.** `automerge.yml` takes the token from the `AUTOMERGE_TOKEN` secret (the
owner's PAT), falling back to `MERGE_QUEUE_TOKEN`: the same PAT is registered
under that name in sibling projects of the family, and the second name saves a
duplicate secret. If a token is set, the merge is done as the owner and push
runs wake up as they would after a manual merge. No secret — the stock token and
a warning in plain words in the run. The showcase gained a daily schedule as a
safety net for the no-secret case; its red is watched by `schedule-alarm.yml`.

**Cost.** The secret lives outside the tree, the owner sets it, and a PAT
expires: then the run warns again rather than staying silent.

**Rejected.** A schedule instead of the secret — the showcase would lag by up to
a day, and CI on `main` still would not see the merge. Publishing the showcase on
the CI `workflow_run` event — CI on `main` does not run at all after such a
merge, so there is nothing to wake it. An in-house merge queue over REST — it
existed and was rejected for consistency with the siblings (answer to rule 053).

### Language measurement is separated from the package by imports

**Before.** Below the floor, the whole package was parsed with the 3.11 grammar.
The reason: measurement ran as `python -m glossary inventory`, which loaded the
CLI and everything else with it — 18 modules for one snapshot. 3.14 style was
forbidden across the whole package for the sake of the five modules the
measurement actually needs.

**After.** Owner's decision of 2 October, Glossary-Python#69: the whole project
is written in 3.14 style, and language measurement lives in a separate chain.

- The entry point is `glossary.measure`. The chain consists of it, `glossary`,
  `_version`, `inventory` and `contracts`.
- The package `__init__` exposes public names lazily (PEP 562), so importing the
  package does not pull in the validator, models and loader. On 3.11 the
  measurement loads 5 modules instead of 18, and the snapshot matches item for
  item (1245 entities).
- Only the chain keeps the oldest version's grammar and
  `from __future__ import annotations`. The rest of the code on 3.14 does not
  need that import: annotations are already evaluated lazily (PEP 649).
  <!--предмет:грамматика младшей версии замера-->
- `tests/test_measured_versions.py` guards both sides of the boundary:
  - running the measurement loads exactly the chain;
  - measurement runs call `glossary.measure`;
  - `__future__` is present in the chain and nowhere else.

**Rejected.** Keeping the measurement as a second tree, a separate script
outside the package. The inventory would then live in two places, or the package
would import the script — two implementations of one subject (rule 214). Also
rejected: keeping 3.11 style across the whole package — every module would pay
for a restriction only five need.

### The showcase filter is section families, not card colours

**Before.** The second filter row showed the cards' colour groups: codes `seq`,
`mapset`, `op`. They mean nothing to a reader and were never translated into
Russian. Modules were hidden in a drop-down menu.

**After.** Owner's decision of 5 October. The filter has two levels, as in the
grader's glossary: a family (data types, syntax, built-ins and exceptions, I/O,
modules, algorithms), and within it sections with labels in both languages. The
classification lives in `glossary/taxonomy.py`. The page receives a ready table
from the build and does not repeat the rules itself. A section without an
explicit family falls into "Other", and `tests/test_taxonomy.py` requires "Other"
to be empty in the snapshot.

**Rejected.** Storing the family as a card field. The classification would then
become part of the data schema and require a `schema_version` bump, although it
is a property of navigation, not of content. Also rejected: classification in the
template's JavaScript — that code is not covered by Python tests, and the
empty-"Other" rule would have nothing to check it.

### Validation is a rule registry, not one big pass

Each rule is a pure function `(Glossary, ValidationConfig) -> Iterator[Issue]`
registered in `RULES`.

**Why.** A new check is added as one function and one line; each rule is tested
in isolation; the report can be filtered and aggregated by rule name.

**Cost.** Each rule walks all cards again — ten passes instead of one. On 581
cards this is a fraction of a millisecond; with growth by an order of magnitude
it would make sense to group the per-card rules into a single pass while keeping
the external contract.

### Errors and warnings are separate

Errors break CI, warnings do not.

**Why.** The data came to the project ready-made and contains issues that cannot
be fixed in one commit. If every issue were an error, `main` would have been red
from day one and the check would stop meaning anything.

The tightening mechanism: a rule is introduced as a warning → the issues are
fixed → the rule is promoted to errors. The pace is controlled by the ratchet
`tests/quality_baseline.json`.

### What a card guarantees and how it is checked

The content audit (#79) ended not with a list of fixes but with a set of
mechanisms: every defect class a machine can catch got a rule or a gate, and it
cannot come back unnoticed.

| Guarantee | How it is checked |
| --- | --- |
| The example runs, and its failure is named in the example itself | `scripts/check_examples.py` (`make examples`) |
| The promised `# →` output matches what is printed | the same gate, mismatch ceiling — zero |
| The full name in the title exists in Python | rule `title-resolves` |
| The "added in" version agrees with the language measurement on the matrix | `scripts/check_added.py` in the badges run |
| A deprecation mentioned in the summary is recorded in the fields | rule `deprecated-text` |
| A deprecation reported by the example itself (`DeprecationWarning` on any matrix version) is recorded in `deprecated` | `scripts/check_examples.py` (#154) |
| The English summary is not taken from another class's docstring | rule `inherited-summary` |
| The ru/en halves are proportionate | rule `translation-length` (warning) |
| The English half is translated, not copied | rule `language-script` |
| A word of prose does not mix Cyrillic and Latin — a keyboard-layout typo | rule `mixed-script` |
| A language entity from the inventory is described | `make completeness` and the baseline `tests/completeness_floor.json` |

**What the checks do not see** — and is therefore held by proofreading (#81):

* **semantic correctness.** A rule knows the example ran, but not whether it
  illustrates what the card is about;
* **translation fidelity.** Proportionate lengths and the absence of a foreign
  docstring are signs, not proof: halves of the same length can claim different
  things;
* **versions older than the earliest snapshot.** Measurement starts at 3.11, so
  it cannot tell "2.7" from "3.5";
* **syntax and concepts.** The inventory sees objects, not language constructs;
  gaps there are found by comparing against `keyword.kwlist` and by manual
  review.

**Rejected.** Checking the meaning of the halves and the correctness of the body
with a machine judge in CI. Such a judge's answer changes from run to run, so the
gate would go red on unchanged data, and a dependency on an external model breaks
the zero-runtime-dependencies decision. Nor do we take the "added in" version by
parsing `versionadded` from the documentation: it is an external document that
has to be downloaded, and its markup changes — measuring the interpreter answers
the same question without a network.

### The project owns the data, the grader consumes it

**Before.** The project was a module of the grader: content arrived from there
already processed, and objections went back.

**After.** The project maintains the content and publishes it; the grader is one
of the consumers of the export. The decision and its cost are in the section "One
owner for the content, and it lives here".

**Why.** Data has one owner, and that owner must be able to check its own edit
without someone else's pipeline. The roles that review content are listed in
[`docs/agent/roles.en.md`](../agent/roles.en.md).

**Rejected.** Staying a module: content improvements would go through the
grader's full CI. Two-way synchronisation: there is no arbiter to resolve
conflicts.

### The lead roles are the methodologist and the designer

**Decision.** The set of roles is built around two: the methodologist and the
designer. The other roles exist because the product has layers that would
otherwise be left without an owner.

**Why.** The project exists so that the processed data reads and sticks **better
than in the source**. Remove methodology and visuals, and what is left is a JSON
to HTML export — which already exists and adds no value.

**Cost.** The two lead roles constantly push back on each other: completeness
versus readability. That is not a defect of the set but its point — a role that
only agrees is not created (catalogue rule 062).
<!--предмет:нет-->

### The list of names in force is the one at the base of the change

**Before.** `scripts/check_attribution.py` checked the branch's commit authors
against `.github/authors.txt` from the working tree — that is, against a file
edited by the very change being guarded. A session that signed with someone
else's identity added it to the list in one line and went green on its own
signature. The limitation was stated in the gate's docstring as "the gate does
not judge whether the list is legitimate", and on 7 September it proved real:
thirteen commits landed in `main` under the environment's identity instead of
the owner's.

**After.** The list is read twice — as it is at the base of the range
(`git show origin/main:.github/authors.txt`) and as it is in the working tree.
The intersection is in force: an addition takes effect from the next session, a
removal in this one. A third line state was added alongside: the `закрыто:`
prefix marks an identity that is present in history and accepts no new commits.

**Why.** The mechanism answers the question the convention did not: the list is
extended by a human in a separate change, not by the same session that needs the
extension. The third state was needed because the line could not be deleted —
there are already commits under that name in `main`, shared-branch history is not
rewritten, and the claim about existing history would have gone red.

**Cost.** Adding an identity costs two changes instead of one: first the line,
then the commits under that name. A range without a left side and the
three-dot notation do not define a base — the gate refuses them with a third
outcome rather than falling back to the working tree: a silent fallback would
reopen the same hole. Finally, the mechanism makes an extension separate and
visible, not impossible: a session willing to spend two changes on a forgery will
get through.

**Rejected.** Relying on `CODEOWNERS`: it already covers the whole tree
(`* @ArtVsMark`) and does nothing here — the file assigns an owner, but requiring
review is a branch-protection setting that does not exist: changes go in by
auto-merge on green CI. A review requirement is stronger than intersecting the
lists, but it lives outside the tree, and relying on it would mean declaring
someone else's setting a mechanism. Also rejected: a second gate forbidding
changes to the list together with code — it would forbid a combination that no
longer matters once the lists are intersected, and would cost a second check of
the change's contents.
<!--предмет:нет-->

### The changelog keeps three releases; a machine moves the old ones

**Before.** `CHANGELOG.md` grew without limit: each release added a section at
the top and none ever left. The answer to catalogue rule 108 said "nothing" and
waited for the changelog to get crowded; by release 1.2.0 it already held three
versions, and 1.3.0 would have been the fourth.

**After.** The window is `WINDOW = 3` in `scripts/changelog.py`. An extra release
turns `--check` red — the same CI step that checks the fragment format. Moving is
done by `--rotate`: everything below the third release goes to
`docs/dev/changelog-archive.md` as whole sections, newest on top. A release
present in both the changelog and the archive is a finding too.

**Why.** The rule requires moving verbatim, and verbatim cannot be checked:
comparing against the previous revision also flags a legitimate typo fix. So it
is held by construction — a machine that cannot abridge does the moving — and the
gate watches what is checkable: the number and position of sections.

**Cost.** The window is measured in releases, not lines: one section with a
hundred entries will not break it. A hand that edits the archive bypassing the
command is invisible to the gate — it sees a duplicated version, not a
paraphrase.

**Rejected.** A separate gate `scripts/check_changelog_window.py`: changelog
parsing already lives in `scripts/changelog.py`, and a second parser of the same
file would drift from the first (rule 214). Also rejected: a line limit — it
turns a release with a long list of entries red, i.e. punishes detail, while what
gets in the reader's way is the number of sections to scroll past.

### Documentation — an original and an English twin, compared by structure

**Before.** The documentation was Russian only, while the showcase and the cards
are bilingual: a reader who came through the English half of a card hit a README
they could not read.

**After.** A document has two files: the Russian original `name.md` and the
English twin `name.en.md`, with a language switcher under the title. The list of
pairs is `PAIRS` in `scripts/check_translations.py`; the gate compares the
switchers, the levels and order of headings, and the number of table rows and
code blocks. Numbers inside markers are rewritten by `scripts/facts.py` in both
halves.

**Why.** A translation drifts from its original silently: an edit goes into one
file and the other stays green. A machine cannot compare meaning, but it can
compare structure, so a new section or table row added to one half becomes a
finding.

**Cost.** Every document edit is two edits. Text rewritten inside a paragraph is
invisible to the gate: whether the translation says the same thing is checked by
a reader. The `CLAUDE.md` rulebook, the changelog and its archive are not
translated: the rulebook is the window's working document, and the changelog is
written once.

**Rejected.** One file with both languages in a row: the document is twice as long
for every reader, and drift between halves inside one file is no easier to spot
than between files. A `docs/en/` folder with a mirrored tree is rejected too:
relative links would have to run through two roots, while a pair side by side is
visible in any listing.

## Current technical debt

| What | Why it is debt | When to address |
| --- | --- | --- |
| 132 examples fail when run, not by design | Code from the glossary does not run | Epic #79, task #82 |
| 309 cards without an expanded body | The card stops at the summary | Epic #79, task #84 (`translated`) |
| 29 summaries outside the 30–200 character range | Does not fit in the list, or explains nothing | Epic #79, task #84 (`summary-length`) |
| `title`, `section` and `subcat` are monolingual | In English mode the showcase stays half Russian | Epic #79, task #85: schema decision before the export for the grader |
| Mixed alphabets in `id` (Latin and Cyrillic) | Not a defect, but the convention is not stated | Needs a decision |
| The showcase JavaScript is not covered by tests | A regression in search, language or download would go unnoticed | Next showcase change |
| The showcase weighs 2.7 MB | First load over a mobile network is noticeable | When speed complaints arrive |
| The version difference says "appeared in the inventory" but reads as "appeared in the language" | `typing.Union` has existed since 3.5, but became a class in 3.14 — and landed in the list of new items | Named in `scripts/whatsnew.py`; introspection cannot separate "new" from "changed its nature" |

The content rows are the work of epic #79: cards are edited here, in
`data/cards/`. Until fixed, they are held by validation rules and the ratchet,
and `glossary objections` gives the list of defective cards.

## Possible directions

- **Export for the grader.** Stage 2 of #76: `glossary.json` with the common
  `glossary.contracts` header is published, and the grader fetches it with its own
  import.
- **New export formats.** An Anki deck, JSON Lines for indexing, embeddings for
  an LLM assistant. The exporter registry is designed for such extension.
- **Bilingual all the way.** Card texts are bilingual, but titles, section names
  and subcategories are not. The schema decision is task #85.
- **Browser tests for the showcase.** Search, language switching and page
  download are checked by hand. Playwright would cover this without runtime
  dependencies in the package itself.
