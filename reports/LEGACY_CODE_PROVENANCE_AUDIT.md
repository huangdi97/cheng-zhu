# Legacy code provenance audit (`interview-assistant`)

**Status: SELF_AUTHORED_CONFIRMED** (maintainer confirmation, 2026-09-30)

## Forensic evidence (agent)

| Check | Command | Finding |
|---|---|---|
| Earliest commit | `git log --all --reverse` | `6dfa475` 2026-09-25 "Initial public release: Cheng Zhu" — one import of 424 files / 102,652 lines |
| Commit authors | `git log --all --format="%an <%ae>\|%cn <%ce>"` | 38 of 38 commits authored and committed by `huangdi97 <34648621+huangdi97@users.noreply.github.com>` |
| Copied headers | `git grep -i -E "copyright\|@author\|SPDX-License\|licensed under\|all rights reserved" 6dfa475` (excl. lockfiles/markdown) | only `LICENSE: Copyright (c) 2026 huangdi97 / Cheng Zhu`; no third-party file headers |
| Foreign repository references | `git grep -i "github.com/" 6dfa475` in source | only a link to nvm-windows in a launcher hint (not code) |
| Legacy name | `git grep -i "interview-assistant"` | only NOTICE.md's own provenance sentence; package names in the import are `cheng-zhu-*` |
| License history | NOTICE.md / CHANGELOG | v1.0–v1.1 published under CC BY-NC 4.0 by the same maintainer; v1.2 relicensed to MIT |
| Local context | working directory | the development checkout lives in a folder named `面试助手` ("interview assistant"), consistent with the maintainer's own earlier project name |

The history before `6dfa475` is not in this repository, so git alone cannot prove authorship of
the pre-import code. The agent therefore did not claim it.

## Maintainer confirmation

Asked in the release-closure session on 2026-09-30; the maintainer (`huangdi97`) answered:
**"All my own code"** — the earlier `interview-assistant` code line was written by the maintainer
and no third-party-owned code remains. NOTICE.md and THIRD_PARTY_NOTICES.md were updated to say so.

## Result

`SELF_AUTHORED_CONFIRMED` — the MIT relicensing of the whole tree rests on the maintainer's own
copyright. Third-party dependencies keep their own licenses (`THIRD_PARTY_NOTICES.md`).
