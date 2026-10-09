# Roles

[Русский](roles.md) · **English**

> **Reader:** whoever runs this project — a person or an agent window.

A role here is neither decoration nor a section of documentation. A role is
created when it has **its own question**, **its own artifact** and **its own
objection** to a specific other role. No objection means it is a profile of an
existing role, and it does not need to be created separately.

## What this project is

The home of the glossary. Cards are maintained here (`data/cards/`, #76) and turn
into a single page you download and use — no installation, no network, in two
languages. `ArtVsMark/Stepik-Python-Grader` receives the resulting content as an
export: we author the cards, the grader consumes them.

Hence two leading roles — the **methodologist** and the **designer**. The others
exist because the product has layers that would otherwise be left without an
owner.

## Roles

### 🧠 Methodologist — leads on content

**Question.** Can you learn from this page without looking anywhere else?

**Artifact.** Card completeness criteria, section order, difficulty levels,
bilingual rules: what gets translated and what stays an identifier.

**Objects** to the "Designer" role: density has eaten the distinction between
levels — a beginner cannot see where to start.

### 🎨 Designer — leads on form

**Question.** Does this read well, and will anyone want to open the page a second
time?

**Artifact.** Theme tokens, type scale, density, states, light and dark schemes,
behaviour on a narrow screen.

**Objects** to the "Methodologist" role: completeness has produced a card nobody
reads to the end — split it or cut it.

### 🌐 Frontend engineer

**Question.** Is this still one file you download and open?

**Artifact.** Building the page from data and a template, the size budget,
offline behaviour, time to first render.

**Objects** to the "Designer" role: a font from a third-party address and heavy
animation break the "download and use" promise.

### 🏛 Architect

**Question.** Will this survive a second language, a growing number of cards and
a change of source?

**Artifact.** The data schema, the export format for the grader, extension
points, the format version.

**Objects** to the "Methodologist" role: a new card field is a change to the
export format the grader reads, not an internal matter of the glossary.

### 🧾 Content auditor

**Question.** Is this true, and is it complete?

**Artifact.** Card audit: a finding with a reproduction, a link to the Python
documentation and a fix in `data/cards/`. The procedure is the
[`card-audit`](../../.claude/skills/card-audit/SKILL.md) skill: text, examples, fields.

**Objects** to the "Methodologist" role: something is presented as fact that the
Python documentation does not say.

## Engagement matrix

```
content, completeness, delivery → 🧠  (+ 🧾)
visuals, typography, themes     → 🎨  (+ 🌐)
build, size, offline            → 🌐  (+ 🏛)
schema, contract, languages     → 🏛  (+ 🧠)
content audit                   → 🧾  (+ 🧠)
```

## What is not covered

An uncovered layer is written down as uncovered: a question nobody asks leaves no
trace, and a gap in the roster cannot be seen by reading the list of roles.

| Layer | State |
| --- | --- |
| Accessibility: contrast, keyboard, screen reader | Part of the Designer's profile, no separate role |
| Promotion and audience | **No owner.** While the page is not shown widely, this is not a blind spot; it becomes one at the first announcement |
| Legal standing: licences of texts, origin of examples | **No owner.** The subject will appear once borrowed material makes it into the cards |

## Accepting a new role

A new role goes through three questions in a row:

1. What question of **its own** does no one else ask?
2. What artifact does it bring?
3. Whom exactly does it **object** to, and about what?

Failing the third means it is a profile of an existing role or a section of
documentation. A role that only agrees adds volume to the discussion and changes
nothing in the decision.
<!--предмет:нет-->

The shape of this document is held by `tests/test_roles.py`: every role must have
a question, an artifact and an objection to a role named in this same document.
Objecting to oneself does not count.
