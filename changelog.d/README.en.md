# Changelog fragments

[Русский](README.md) · **English**

Every change puts **its own file** here instead of a line in the shared
`CHANGELOG.md`. Two files with different names never conflict — so parallel
changes stop fighting over one file.

This matters more than it seems: a conflicted change is left **with no checks at
all**. The run goes against a merge commit that does not exist while there is a
conflict, and an empty list of checks reads as “CI is broken” rather than “cannot
merge”.

## How to add an entry

```
changelog.d/<slug>.<section>.md
```

- `slug` — anything unique, usually the branch name without its prefix;
- section — one of `added`, `changed`, `fixed`, `removed`, `internal`;
- inside — **one line**: no leading dash and no section name, the build adds
  them.

The changelog itself is kept in Russian, so the line is written in Russian; an
external contributor may write it in English, and the person merging translates
it.

Example — the file `bilingual-cards.added.md`:

```
карточка несёт описание на двух языках, витрина переключает их без перезагрузки (#42)
```

## Commands

```bash
make changelog-check     # entry shape (the same gate as in CI)
make changelog-preview   # how it will be assembled, changing nothing
make changelog-collect   # move into [Unreleased] and delete the fragments
make changelog-rotate    # releases beyond the window — into docs/dev/changelog-archive.md
```

The changelog keeps the last three releases (catalogue rule 108): a fourth turns
`make changelog-check` red. Old ones are moved by `make changelog-rotate` — by a
machine and therefore verbatim; the archive is never written by hand.

The format deliberately follows the convention of the neighbouring project
`ArtVsMark/Stepik-Python-Grader`: two implementations of one algorithm would
diverge at the very first edit.
