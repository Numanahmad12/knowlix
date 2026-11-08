# Frontend Skills for Knowlix

Installed 2026-11-08. Six frontend engineering skills, discovered from
reputable public sources, vetted, installed project-level in this repo,
and validated. Nothing in the application UI or business logic was changed
by this installation.

## A note on tooling: there is no `muse` skills CLI here

The install prompt referenced `muse skills list / install / validate /
inspect`. **No `muse` binary exists in this environment** (`muse: command
not found`), so those commands do not exist here and were not run. The
equivalent steps were done directly and are documented below:

- **Discovery:** local skill catalog searched first (no matches for any of
  the six), then web/GitHub search for canonical sources.
- **Installation:** `git clone --depth 1 --filter=blob:none --sparse` of
  each source repo, then copying the skill folder verbatim.
- **Validation:** `docs/validate_frontend_skills.py` (runnable) checks
  every skill in both locations: `SKILL.md` present with `name` +
  `description` frontmatter matching the folder, `skill.yaml` present in
  the runtime mirror, every file path referenced from `SKILL.md` exists,
  no name collisions with system skills — plus functional spot checks
  (the `ui-ux-pro-max` search script runs against its data; the
  `web-design-guidelines` live-rules URL returns HTTP 200). Re-run it
  with `python3 docs/validate_frontend_skills.py`. The runtime mirror was
  additionally confirmed discoverable via the agent's skill search.

## Installation locations

Two copies of each skill exist. The **repo copy is canonical**; the
mirror exists only so this Muse runtime discovers the skills in future
Knowlix work. If a skill is updated, re-copy from the repo copy and
re-run the validator. Do not edit the vendored files in place — upstream
fixes come from re-copying the source.

| Location | Path | Purpose |
|---|---|---|
| Project-level (canonical) | `.claude/skills/<name>/` in this repo | Versioned with Knowlix; loaded by Claude Code / Muse Code style agents working in this project. |
| Runtime mirror | `~/workspace/custom-skills/<name>/` (plus `skill.yaml` beside each `SKILL.md`) | Discovered by this Muse agent's skill search. `include_in_prompt: false`, so they load on search, not in every conversation. |

## Installed skills

### 1. UI/UX Pro Max — `ui-ux-pro-max`

- **Purpose:** Professional SaaS UI/UX design: design systems, typography,
  colour palettes, layouts, dashboard and app interfaces, responsive
  design. Searchable local database (84 styles, 192 palettes, 74 font
  pairings, 99 UX guidelines, 105 icons, 16 GSAP presets, 25 chart types,
  22 stacks including Next.js and Three.js).
- **Source:** https://github.com/nicohodt/claude-code-ui-ux-skill —
  `.claude/skills/ui-ux-pro-max/`. Dedicated single-skill repo.
- **License:** MIT (Copyright (c) 2026 Nicolay Hodt).
- **Contents:** `SKILL.md` (196 lines), `scripts/` (`search.py`,
  `core.py`, `design_system.py`, `validate_data.py`), `references/`
  (`quick-reference.md`, `pro-rules.md`), `data/` (13 CSVs, 2,989 lines;
  `stacks/` with 22 stack files).
- **How to invoke:** read `.claude/skills/ui-ux-pro-max/SKILL.md`, then
  run the search script by full path:
  `python3 .claude/skills/ui-ux-pro-max/scripts/search.py "<query>"
  [--domain <style|color|typography|ux|product|...>] [--stack nextjs]
  [--design-system]`. Requires Python 3, stdlib only, no network. The
  SKILL.md's `${CLAUDE_PLUGIN_ROOT}` placeholder means this skill's own
  directory. `--persist` writes `design-system/<slug>/MASTER.md` into the
  project — only with explicit approval, and it must never overwrite the
  Knowlix brand palette in `CLAUDE.md`.
- **Dependencies:** Python 3 (verified 3.12.3 here).
- **Validation status:** Passed. Search script verified live (`--help`
  and a real query against the installed copy).

### 2. Frontend Design — `frontend-design`

- **Purpose:** Modern React/Next.js interfaces: high-quality component
  design, visual hierarchy, polished layouts, distinctive (non-generic)
  aesthetic direction and typography.
- **Source:** https://github.com/anthropics/skills —
  `skills/frontend-design/`. Official Anthropic skill.
- **License:** Apache-2.0 (`LICENSE.txt` in the folder).
- **Contents:** `SKILL.md` (71 lines) + `LICENSE.txt`. Instruction-only,
  no scripts.
- **How to invoke:** read `.claude/skills/frontend-design/SKILL.md`
  before starting a new UI or reshaping an existing one. Its
  ground-in-subject-matter method and token-system plan apply; the
  Knowlix brand palette in `CLAUDE.md` is the pinned direction and wins
  over any generic suggestion.
- **Dependencies:** None.
- **Validation status:** Passed.

### 3. Web Design Guidelines — `web-design-guidelines`

- **Purpose:** Accessibility, responsive layouts, UI consistency, design
  best practices, usability and interaction patterns — as a **review**
  skill: it audits UI code and reports violations.
- **Source:** https://github.com/vercel-labs/agent-skills —
  `skills/web-design-guidelines/`. Official Vercel skill (repo README
  states MIT; last updated 28 Oct 2026).
- **License:** MIT (per repo README).
- **Contents:** `SKILL.md` (39 lines) only. It holds no rules itself.
- **How to invoke:** read the `SKILL.md`, then fetch the live rules
  before every review from
  `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`
  (verified HTTP 200 on install day) and report findings as terse
  `file:line` lines. Needs network at review time; if the fetch fails,
  do not review from memory.
- **Dependencies:** Network access at review time.
- **Validation status:** Passed (structure + live-rules URL reachable).

### 4. Three.js / React Three Fiber — `react-three-fiber`

- **Purpose:** Interactive 3D experiences, 3D object integration, WebGL
  optimization, React Three Fiber implementation, performance-conscious
  3D interfaces.
- **Source:** https://github.com/greysquirr3l/claudedesignskills —
  `.claude/skills/react-three-fiber/`. MIT licensed (Copyright 2025
  Claude Skills Project). Audit date 2026-09-23; current version covered
  is R3F 9.8.0.
- **License:** MIT.
- **Contents:** `SKILL.md` (1,187 lines), `scripts/` (`scene_setup.py`,
  `component_generator.py`), `references/api_reference.md`,
  `assets/starter_r3f`, `assets/examples`.
- **How to invoke:** read the `SKILL.md` (and `references/api_reference.md`
  for API detail) before any 3D work.
- **Version constraint (important):** Knowlix is React 18 + `three@0.187`
  with **no** `@react-three/fiber` installed. R3F v9 requires React 19;
  React 18 pairs with R3F **v8** (maintenance line). Do not install v9
  here. The existing orb is raw `three`; prefer raw `three` for small
  scenes and add R3F only for larger declarative scenes, with the user's
  approval.
- **Dependencies:** None to install the skill; R3F itself is not
  installed in the project.
- **Validation status:** Passed with one documented upstream gap (below).

### 5. Animation Design — `motion-design`

- **Purpose:** Motion design: smooth page transitions, micro-interactions,
  scroll-triggered animations, loading animations; Framer Motion / Motion
  and GSAP patterns; CSS transitions and keyframes.
- **Source:** https://github.com/ligj1706/ProSkills —
  `dev-skills/ui-ux-design/motion-design/`. MIT (Copyright (c) 2026
  ProSkills).
- **License:** MIT.
- **Contents:** `SKILL.md` (498 lines), `references/easing-library.md`,
  `evals.json`.
- **How to invoke:** read the `SKILL.md` (and `references/easing-library.md`
  when the task needs easing/spring detail) before adding motion. CSS
  first; Framer Motion / GSAP only if the dependency is approved — neither
  is installed in Knowlix today. Always respect `prefers-reduced-motion`.
- **Dependencies:** None to install the skill; animation libraries are
  not installed in the project.
- **Validation status:** Passed.
- **Quirks:** the SKILL.md asks the agent to start its first response with
  a 🧢 emoji when the skill activates, and its companion check looks for
  recommended skills under `~/.claude/skills/` (Claude Code paths) and
  suggests `npx skills add AbsolutelySkilled/...`. Both are harmless here;
  the recommended companion skills (`responsive-design`,
  `design-systems`, `figma-to-code`, `ultimate-ui`) were not installed —
  out of scope for this task.

### 6. React Best Practices — `react-best-practices`

- **Purpose:** Component architecture, React performance optimization,
  state management, hooks best practices, Next.js rendering and
  optimization, avoiding unnecessary re-renders.
- **Source:** https://github.com/vercel-labs/agent-skills —
  `skills/react-best-practices/`. Vercel Engineering, MIT (repo README).
- **License:** MIT.
- **Contents:** `SKILL.md` (149-line index), `AGENTS.md` (compiled
  70-rule document, 3,810 lines), `README.md`, `metadata.json`,
  `rules/` (72 rule files across 8 categories: waterfalls, bundle size,
  server-side, client fetching, re-renders, rendering, JS performance,
  advanced patterns).
- **How to invoke:** read the `SKILL.md`, then open only the 1–3
  `rules/*.md` files matching the change — never the whole tree. Use
  `AGENTS.md` only when a single compiled document is needed.
- **Naming note:** the skill's own frontmatter name is
  `vercel-react-best-practices`; the folder keeps the upstream repo path
  `react-best-practices`. Same skill, two labels — the validator records
  this as a known upstream naming difference, not an error.
- **Dependencies:** None.
- **Validation status:** Passed.

## Skills considered but NOT installed

| Skill | Why not | Alternative in place |
|---|---|---|
| `threejs` (EijunnN/rune, `skills/threejs/`) | No license anywhere in the repo (no `LICENSE`/`COPYING` file at any depth, no license line in the README). Content is otherwise excellent (raw Three.js + R3F + shaders + performance). Vendoring unlicensed code was not safe. | `react-three-fiber` (MIT, above) covers R3F and the Three.js object model underneath it. If the rune repo gains a license, it is the fuller raw-Three.js reference and can replace or complement it. |
| `motion-design` companion skills (`responsive-design`, `design-systems`, `figma-to-code`, `ultimate-ui`) | Out of scope — the task listed six skills, and these are only named as recommendations inside `motion-design`. | None; the six installed skills cover the brief. |

## Known gaps and quirks (recorded, not hidden)

- `react-three-fiber`: its `SKILL.md` (lines 1102–1104) points at
  `references/hooks_guide.md` and `references/drei_helpers.md`, which
  were never shipped upstream (confirmed via `git ls-tree`; a second copy
  of the same skill has no `references/` at all). The skill body and
  `references/api_reference.md` are complete. Do not fabricate the two
  missing files; if upstream adds them, re-copy.
- `react-best-practices`: frontmatter name vs folder name (see above).
- `motion-design`: 🧢 emoji first-response line; companion check targets
  Claude Code paths.
- `ui-ux-pro-max`: `${CLAUDE_PLUGIN_ROOT}` in its examples means the
  skill's own directory — use the real installed path. Its palette/style
  suggestions are advisory; the Knowlix brand palette in `CLAUDE.md`
  always wins.
- `web-design-guidelines`: fetches live rules per review, so two reviews
  of unchanged code can legitimately disagree if Vercel updates the
  guidelines in between.

## Project facts the skills must respect

- **The frontend is JavaScript, not TypeScript.** No `.ts`/`.tsx` in
  `frontend/` source. Skill examples in TSX must be adapted to JSX.
- Stack: Next.js 14.2, React 18.3, Tailwind 3.4, `lucide-react`,
  `three@0.187` (raw). No `@react-three/fiber`, no `framer-motion` /
  `motion`, no `gsap` installed.
- Brand palette (source of truth: `CLAUDE.md`): Direction 4 — Pink field
  `#F5C9D6`, Navy ink `#1E2A5C`, Vivid orange `#FF4D00`, Cream `#FFF9F3`,
  Supporting teal `#2E7D7B` (cache / citation semantics only), Primary text
  `#232B4A`, Muted `#6B7194`, Borders `#E8DFE4`. Never purple, violet,
  electric blue, or neon gradients. (Pre-redesign palette Teal `#A8C9C8` /
  Orange `#F45B0B` on `#F6F8F7` was superseded 2026-11-08 with the user's
  explicit approval.)
- Fonts: Anton (display) + Fraunces italic (accent) + Plus Jakarta Sans (UI/body) + JetBrains Mono (labels/data).
- Project instructions: `CLAUDE.md` at the repo root (brand, principles,
  skill routing, precedence). It outranks every skill.

## Validation summary

- `docs/validate_frontend_skills.py`: **PASSED** — all 6 skills, both
  install locations (frontmatter, referenced files, `skill.yaml`,
  collisions, plus the functional checks above).
- Runtime discovery confirmed: the agent's skill search returns all six
  mirrored skills (`ui_ux_pro_max`, `frontend_design`,
  `web_design_guidelines`, `react_three_fiber`, `motion_design`,
  `react_best_practices`).
- No conflicts with existing project instructions: the repo had no
  `CLAUDE.md` or `AGENTS.md` before this task; `CLAUDE.md` is new.
- No application UI or business logic was modified. New files only:
  `.claude/skills/` (6 skills), `CLAUDE.md`, this file,
  `docs/validate_frontend_skills.py`. Nothing committed or pushed.
