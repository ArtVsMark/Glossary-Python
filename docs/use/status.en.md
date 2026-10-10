# Glossary status

[Русский](status.md) · **English**

The glossary is open and published, but **not widely announced**: one class of
defects has not yet been checked against real material (catalogue rule 106).

## Checked

- **By machine, on every change.** Examples run on every version in the matrix,
  and their output matches what they promise; versions of introduction are
  checked against the language measurement; links lead to the official
  documentation; completeness is measured against Python itself. A headless
  browser opens the showcase: the counter is full, and following an anchor leads
  to the card (`make showcase`).
- **By reading, section by section.** The cards of the teaching core and the
  standard library were read through and checked against the CPython
  documentation and the interpreter's behaviour on 3.12–3.15; what was found has
  been fixed in `data/cards/` — the list of fixes is in
  [`CHANGELOG.md`](../../CHANGELOG.md). The reader was an agent, not a human
  subject-matter expert: an error the agent believes to be correct is not caught
  by this reading.

## Not checked

- **The showcase in human hands.** Nobody has gone through what is done by hand:
  searching for a term from an error message, filters and following links — on a
  phone and offline. A headless browser does not produce taps and typing.
- **Examples on other OSes.** The matrix runs the card examples on Linux, on six
  Python versions; Windows and macOS are not checked — CI on them was declined on
  purpose (rule 018). A card with `platforms: ["AllOS"]` promises more than was
  checked.

## Condition for wide announcement

Written down in advance and observable: a person has gone through the reader's
scenario on the showcase — from search to a linked card, on a phone and offline —
and what was found has been fixed.
