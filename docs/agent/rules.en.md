# Rule catalogue

[Русский](rules.md) · **English**

The project is connected to the rule catalogue
[Engineering-Incidents-Playbook](https://github.com/ArtVsMark/Engineering-Incidents-Playbook)
— a body of engineering rules, each of which grew out of a specific incident.

How the connection works is not retold here — that knowledge belongs to the
catalogue: the connection procedure is in its
[`CONNECT.md`](https://github.com/ArtVsMark/Engineering-Incidents-Playbook/blob/main/CONNECT.md),
the procedure for moving up to a new export is in its
[`START.md`](https://github.com/ArtVsMark/Engineering-Incidents-Playbook/blob/main/START.md).

| File | What it is |
| --- | --- |
| `.rules/bindings.json` | The project's answer to every catalogue rule: in force and held by what · rejected and why · no subject here · not looked at yet |
| `.rules/proposals.json` | The return channel: a rule born here travels to the catalogue |
| `.github/workflows/rules-inbox.yml` | Daily "inbox": the queue of unanswered rules and what neighbouring projects have already decided |
| `tests/test_rules_bindings.py` | Gate on the shape of the answer: addresses resolve, every `none` has a reason, the ceiling on rules without a mechanism |

The set was assembled by the catalogue's `onboard_consumer.py` command, not
copied by hand: a copy of the generator in every project means N implementations
of one algorithm.

All **<!--m:rules_total-->217<!--/m:rules_total-->** catalogue rules have been reviewed; no `unreviewed` remain:

| Answer | Count | Meaning |
| --- | --- | --- |
| `active` + mechanism | <!--m:rules_mechanised-->145<!--/m:rules_mechanised--> | The rule is in force and held by a gate (<!--m:rules_gate-->84<!--/m:rules_gate-->), a document (<!--m:rules_document-->45<!--/m:rules_document-->) or the pipeline (<!--m:rules_pipeline-->16<!--/m:rules_pipeline-->) |
| `active` + `none` | <!--m:rules_none-->2<!--/m:rules_none--> | The rule is in force but nothing here holds it — each one names a reason |
| `not-applicable` | <!--m:rules_na-->69<!--/m:rules_na--> | The rule's subject does not exist in this project — with an explanation of why |

**<!--m:rules_none-->2<!--/m:rules_none--> is a metric, and it must go down.** The ceiling is fixed in
`tests/test_rules_bindings.py` and moves only downward, like the data-quality
ratchet. A metric dissolved in prose looks like it does not exist.
<!--предмет:потолок правил без механизма-->

The shape of the answer is held by a gate: a mechanism must name a **resolvable
address** — a path that actually exists in the repository. The gate went red on
its very first run, catching an unrecognised address: a check that has never
gone red usually checks nothing.

The catalogue's first finding in this project is rule
[075](https://github.com/ArtVsMark/Engineering-Incidents-Playbook/blob/main/rules/en/075-a-guard-that-finds-nothing-must-fail.md):
the validator on empty data answered "0 errors" and returned success. Closed by
the `non-empty` rule and by refusing to build an empty showcase.
