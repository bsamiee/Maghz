# [TOPOLOGY]

The coupling map: editing a `[SURFACE]` obligates its `[OBLIGATED_COUNTERPARTS]` in the same change. Heavy workflow runs re-prove rows against the live tree — a row whose coupling no longer exists is culled in the same pass, and a coupling discovered mid-run lands as a new row.

## [01]-[ROWS]

| [INDEX] | [SURFACE]                              | [OBLIGATED_COUNTERPARTS]                         | [WHY]                                        |
| :-----: | :------------------------------------- | :----------------------------------------------- | :------------------------------------------- |
|  [01]   | `admin/profile.py` extension catalog   | the `[CATALOG:*]` blocks it regenerates          | four surfaces project from one catalog       |
|  [02]   | `db/schema.sql` table or enum shape    | `db/routines.sql` + `admin/rails.py` projections | routine and projection SQL compose the names |
|  [03]   | `db/search/` dictionary file           | `db/schema.sql` dictionary rows + a re-stage     | `kb_english` binds dictionaries by name      |
|  [04]   | `maghz` verb or `Envelope` surface     | `admin/README.md` verb table + `AGENTS.md` prose | the CLI contract lands at its acting readers |
|  [05]   | `admin/infra.py` service or port row   | the Forge `vpsTunnels` and `maghz` host rows     | the tunnel projects VPS ports onto loopback  |
|  [06]   | automation-substrate admission         | its `docs/.api/` catalog                         | rails compose mined evidence, never raw APIs |
|  [07]   | `docs/stacks` or `docs/standards` page | `.greptile/rules.md` + `.coderabbit.yaml`        | reviewer prose derives from doctrine         |
|  [08]   | `.claude/skills/` tree                 | the Forge and Rasm master trees                  | propagation is byte-identical copy           |
|  [09]   | `CLAUDE.md` fact                       | `AGENTS.md` cross-reference                      | one fact lands at its acting reader          |

The `[CATALOG:<tag>]` sentinel blocks rewrite only through `admin.profile.regenerate()`, landing in `image/Dockerfile`, `db/schema.sql`, and `db/cron.sql`. Skill and stack masters live in `Parametric_Forge` (harness) and `Rasm` (methodology and stacks); an edit lands at the master first and arrives here by copy. A host-side counterpart — a tunnel, firewall, or identity row — lands at the Forge flake, never in this repo.
