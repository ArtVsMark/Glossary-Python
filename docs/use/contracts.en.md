# Outward contracts: what is stable, what is extensible, how new things are added

[Русский](contracts.md) · **English**

> **Reader:** anyone who reads this project's files by machine and wants to know
> what they can rely on here and what will be different tomorrow.

Listing the fields is not enough. A contract that does not state the rules of its
own evolution turns every change into a negotiation from scratch, and its
consumers into people who drift apart silently (catalogue rule
[113](https://github.com/ArtVsMark/Engineering-Incidents-Playbook/blob/main/rules/en/113-a-contract-states-how-it-may-change.md)).

The rules below are the same for all contracts; each contract further down names
only what makes it different.
<!--предмет:состав раздела о контракте-->

## General evolution rules

**Stable.** The file name, its address and the meaning of an already published
field. A field, once named, does not change meaning: a changed meaning gets a new
name. The header (`schema`, `schema_of`, `producer`, `source`, `generated_at`) is
present in every published file and stays in place.

**Extensible.** The set of fields grows forward and only forward. A new field is
added; an old one is neither renamed nor reused. A missing key means "not
measured", not "zero": zero is a measured zero, and the two must not be merged.
<!--предмет:эволюция состава полей-->

**How new things are added.** Adding a field is a minor change: `schema` grows in
its right digit, and the consumer is not obliged to react. Changing a field's
meaning or removing it is a major change: the left digit, and consumers are told
in advance. The number is declared once, in `glossary.contracts.SCHEMA`; the
version is a string, not a number — a numeric form cannot tell `1.0` from `1.10`.

**What these rules do not promise.** No contract promises that a number in it will
change: a file built during a broken run stays yesterday's and looks exactly like
"nothing changed". That is precisely why the header has `generated_at` — freshness
is read from it, not from the fact that the file exists.

## `facts.json` — how much there is

**Difference.** The `rules` and `content` sections entered the contract at this
project's suggestion: the reference had none. A key that could not be measured is
absent from the output altogether.

**The format is set by the consumer.** The file follows the facts contract of the
profile showcase —
[`facts.schema.json`](https://github.com/ArtVsMark/ArtVsMark/blob/main/.rules/facts.schema.json)
— and carries its number in `schema` (`scripts/facts.FACTS_SCHEMA`), not the
shared `glossary.contracts.SCHEMA` number. For every metric in the contract there
is either a value or a reason in `none`; the reason "no releases" lifts itself
with the first tag. The publishing run validates the file against the showcase
schema before publishing.

**The old name is kept.** `python_versions` stays next to `python.supported`: a
published field is not removed, and both have the same source.

**How new things are added.** A section appears together with its source in
`scripts/facts.py`; a number that ends up in the documentation must live inside a
named marker and be rewritten by the build.

## `objections.json` — which cards are wrong

**Difference.** The file is addressed to whoever edits the cards, not to the
showcase reader. A finding has a scope (`scope`): an objection at glossary level
is not lost for a consumer that reads only `cards`.
<!--предмет:нет-->

**How new things are added.** A new objection is a rule in `validation.py`; it
appears in the contract by itself, no separate step is needed. The "error" level
is switched on only after the data conform to it completely.
<!--предмет:перевод правила валидации в ошибку-->

## `completeness-report.json` — which cards are missing

**Difference.** The completeness reference is Python itself, captured by
introspecting a running interpreter. The answer depends on the version, and the
version is named in the report itself: here it is an axis of measurement, not a
setting.

**The boundary is named in the report itself.** Introspection sees objects, not
text: syntax, deprecations and removals are not measured at all.

**How new things are added.** A standard library module is added by an explicit
change to `STDLIB_MODULES` in `inventory.py`, not automatically.

## `whatsnew.json` — what appeared in the language

**Difference.** It is computed by subtracting the inventories of adjacent
versions, with no network and no parsing of someone else's markup.

**The boundary is named in the report itself.** The difference says "appeared in
the inventory", not "appeared in the language": an entity that changed its nature
looks new.

**How new things are added.** A version appears in the run matrix; the inventory
is captured on exactly the versions the project is tested on, and a test guards
against these lists diverging.

## `delivery.json` — cards for consumers

**Difference.** This is not a report about the cards but the cards themselves —
what Stepik-Python-Grader reads instead of editing its own copy (#76). `groups`
mirrors the layout of `data/cards/`: the key is the group file name, the value is
the cards in the file's form and order, without the `color_group` field. The
consumer's import writes each group to its own file, with no schema conversion.
Only cards with status `ready` go into the export. `snapshot.digest` is the
fingerprint of the same build as `data/glossary.json`, and
`snapshot.schema_version` is the version of the card form.
<!--предмет:статус карточек в выгрузке-->

**How new things are added.** A new card field arrives in the export by itself,
together with `schema_version`: the card form here is the same as in
`data/cards/`. A change of card form is a major change for the consumer, and its
task is notified in advance. The form guard is `tests/test_delivery.py`: the
groups, split into files, must assemble into exactly `data/glossary.json`.

**Where an id went.** An id that has been published even once in a release with
an export does not disappear silently: either a card with it exists, or `moved`
says where to point the link. A split card leads to where both parts are
described together (`__str__-__repr__` → `repr-vs-str`). The check against the
build of every release tag is held by `tests/test_delivery.py`; previously, the
move of an id beginning with `_` silently dropped out of the export (#172).

**Release and pinning.** For every release, the `release-delivery.yml` run
attaches immutable `delivery.json` and `delivery.schema.json` — the export of
that tag's tree and its JSON Schema, built from `data/glossary.schema.json`.
`badges/delivery.json` is the moving "latest". A consumer that needs stability
pins a release and compares the pin with the latest release: falling behind by a
major form version is the signal to rebuild the import (#105).

**Form version.** The `form` field is a string `"major.minor"`. The major equals
`snapshot.schema_version` and grows on a new required field, a change of meaning
or the removal of a field. The minor is a new optional field the consumer is
entitled not to know about. Every version is a row in the log below; the guard
`tests/test_delivery.py` does not allow raising the form without a row.

### Form log

| Form | What changed |
| --- | --- |
| `2.0` | The grader's knowledge-base form: bilingual `summary`/`body`, synonyms, links, card kind |
| `3.0` | `title` and `subcat` are `{ru, en}` objects instead of strings (#90) |
| `4.0` | New required field `platforms`: `["AllOS"]` or a subset of `Linux`, `macOS`, `Windows` (#103) |
| `4.1` | Optional export field `moved`: "old id → new" for merged cards, from `data/moved.json`. The new id exists, the old one does not (#79) |
| `5.0` | The `version` field is replaced by three: `added` (required; `<3.0` — appeared before Python 3), `deprecated`, `removed` — up to which version it works (#122) |
| `6.0` | `examples` is an array of standalone blocks, each an array of code lines, instead of one flat array of lines. Each block is read and executed separately (#125) |
| `6.1` | Optional export field `navigation`: the order of section families, their labels `{ru, en}` and section → `{group, ru, en}` — the same table the showcase uses. The consumer needs no copy of the classification of its own (grader's #1573) |

**What the contract does not promise.** That the consumer has already read the
fresh export: when to fetch the data is the consumer's decision, and between
publication and its import its copy lags behind.

## `consumer-verdicts.json` — the answer to the consumer's proposals

Stepik-Python-Grader publishes proposals for the glossary content —
`.glossary/proposals.json` in its repository, each with a stable `slug`. The
nightly run fetches the file over plain HTTPS and answers every slug with a
verdict: `done` (fulfilled — visible in the data), `accepted` (with an issue
number), `rejected` (with a reason), `pending` (not decided yet). Decisions live in
`data/consumer_verdicts.json`; fulfilment is recognised on its own. No proposals
file means the channel is not connected, and no verdicts are published: an empty
answer would look like "everything is decided". The `answers_to` field names the
consumer file this answers.

## `data/glossary.json` — the card build

The showcase publishes this file as is — `/glossary.json` on Pages
(`.github/workflows/pages.yml`) — but it is **not** an outward contract: it has
no shared `glossary.contracts` header, and its form changes together with the
schema. A consumer that needs the cards themselves is served by
[`delivery.json`](#deliveryjson--cards-for-consumers) — with a header, a form log
and pinning to a release. This file is also read by machine (the showcase build,
the export, the reports), so it obeys the same rules. Its form is described by
[`glossary.schema.json`](../../data/glossary.schema.json).

**Difference.** It is **derived**: cards are maintained in
`data/cards/<group>.json` and assembled here by the `glossary assemble` command.
An edit here lasts until the next build, and `assemble --check` in CI rejects any
divergence.

**How new things are added.** A field is introduced in `models.Entry`, in the
schema and in `schema_version` — and agreed with the export format the grader
reads. The schema version is an integer and grows by one: the data form has no
minor changes, because the consumer reads it as a whole.

**What the schema does not promise.** That a non-empty field is meaningful: an
empty half of a bilingual text is syntactically legal, and it is caught by the
validator, not the schema.
