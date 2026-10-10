# How a window runs the work

[Русский](work.md) · **English**

> **Reader:** an agent window and the person running it.

The rulebook ([`CLAUDE.md`](../../CLAUDE.md)) says what must not be done. This is
the order of work: where the next task comes from and how a window hands part of
the work to agents. The rules are kept as a document: the machine does not hold
them, whoever runs the window does (the `document` answers in
[`.rules/bindings.json`](../../.rules/bindings.json)).

## Where the work comes from

The sources are ordered, and the first non-empty one is the plan (catalogue
rule 091). The next source is not opened while the previous one has work.

1. **Own red.** A red `main`, an own change that is red or in conflict.
2. **Work on the catalogue rules.** An `unreviewed` answer, a rule without
   analysis, an outdated "not applicable" answer — in `.rules/bindings.json`.
3. **Tracker issues**, starting with those that have a consumer — the grader or
   a showcase reader.
4. **The content queue in machine form:** `make objections`, then
   `make completeness`, then `whatsnew.json`.
5. **Undecided consumer proposals** — `pending` in `consumer-verdicts.json`.

## Agent waves

A window hands agents work that splits into independent pieces: module cards,
an audit of a section, re-reading catalogue answers.

- **The wave size is fixed: no more than five agents at once** (031). The next
  wave starts after the previous one is reviewed, not alongside it.
- **The pace is computed from what is left, not from wishes** (033). Before a
  wave the window checks the remaining Claude limit and GitHub quota
  (`/rate_limit`, the REST transport) and picks the number of waves so the work
  fits the remainder with a margin.
- **One agent's zone is small, and its task carries numbers** (034, 117): no
  more than 20 cards per writing agent and no more than 40 per auditing one, one
  output file, its format and a limit on the report length. A task without
  numbers is a finding.
- **Environment restrictions are written into the task** (061): "change nothing
  in the tree", "write only to your own scratch folder", which interpreters are
  available, that the network is open to git only. An agent does not know the
  window's rules unless they are repeated to it in words.
- **Agents return data — the host edits files** (015). An agent's output is JSON
  in the scratch folder. The window makes the edits in `data/cards/` and
  `.rules/`, in one change.
- **Collecting and analysing are separate passes** (054). Agents collect: card
  drafts, findings, verdicts. What to accept is decided by the window in a
  separate pass using the `card-audit` skill.
- **The collector checks what arrived against what was expected** (116). Before
  applying, the window checks how many units were expected and how many came,
  whether there are duplicate `id`s, whether all links resolve. A discrepancy is
  named, not smoothed over.
- **A review after every wave, and quality over mechanics** (060). The window
  reads a sample of the output against stage 1 of the skill and runs the example
  matrix; a green gate without reading is mechanics, not a review.
- **A failure means re-running the delta** (020). An agent that failed or
  returned defective output is re-run on its own part, not the whole wave.
