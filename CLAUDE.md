# CLAUDE.md — Knowlix

Project instructions for any agent working on the Knowlix frontend. The
repo's own docs (`README.md`, `DEVELOPMENT_STATUS.md`, `FRONTEND_DIAGNOSIS.md`,
`DEPLOY.md`) cover architecture and deployment; this file covers how to
design and change the UI. The full skills inventory lives in
`docs/FRONTEND_SKILLS.md`.

## What Knowlix is

AI-powered PDF analyzer with a RAG pipeline. Next.js 14.2 frontend
(`frontend/`, App Router), FastAPI backend (`backend/`). Features: PDF
uploads, document processing, AI chat with page citations, source
inspection, guardrails, semantic caching, and a voice mode (BoloDoc) on a
branch. Live at https://pdf-analyzer-vercel.vercel.app/ (backend on Render).

## Stack facts — read before writing code

- **JavaScript, not TypeScript.** The frontend is `.js` / `.jsx` only
  (`frontend/app/page.js`, `layout.js`, `components/`). Do not convert files
  to TypeScript unasked. Skill examples written in TSX must be adapted to
  JSX when applied here.
- React 18.3, Next.js 14.2, Tailwind CSS 3.4, `lucide-react` icons.
- **Three.js `three@0.187` is already installed** and used raw
  (`components/ThreeSemanticOrb.js`). `@react-three/fiber` and
  `@react-three/drei` are NOT installed. React 18 pairs with R3F **v8**
  (maintenance line); R3F v9 requires React 19 — do not install v9 here.
- **No animation library is installed.** No `framer-motion` / `motion`,
  no `gsap`. CSS + Tailwind animations are the default. Adding a library
  needs the user's approval first.
- Fonts: **Anton** (display) + **Fraunces italic** (accent word) + Plus Jakarta Sans (UI/body) + JetBrains Mono (labels/data), via Google Fonts in `app/layout.js`, with system fallbacks (the sandbox proxy blocks Google Fonts; that is an environment artifact, not a bug). Direction 4 ("Go all out", implemented 2026-11-08) replaced the earlier Sora/Inter claim — that was stale and is corrected here.

## Brand — the brief always wins

Approved Knowlix palette (Direction 4, implemented 2026-11-08 — use these tokens; never invent others):

- Pink field `#F5C9D6` · Navy ink `#1E2A5C` · Vivid orange `#FF4D00`
- Cream background `#FFF9F3` · White `#FFFFFF` · Pink soft `#FDEEF3` · Pink line `#F3B8CA`
- Supporting teal `#2E7D7B` (cache / citation semantics only) · Teal soft `#DCEBE9`
- Primary text `#232B4A` · Muted text `#6B7194` · Faint `#9AA0B8` · Borders `#E8DFE4`

**Never** introduce purple, violet, electric blue, or neon gradients.
Skill suggestions are advisory: the `ui-ux-pro-max` palette database and
the `frontend-design` anti-default guidance must never override this
palette. Where a skill recommends a different look, follow this file.

Drift note (2026-11-08): the pre-redesign palette was Teal `#A8C9C8` / Orange `#F45B0B` on `#F6F8F7`. Direction 4 superseded it with Numan's explicit approval ("go all out, no compulsion on design/colour/font"). The old values survive only in git history.

## Design principles

- Premium, modern AI SaaS aesthetic. Clean, sophisticated layouts.
- Excellent typography and spacing; smooth but purposeful animation.
- Responsive across desktop, tablet and mobile.
- Accessibility and keyboard navigation; visible focus states.
- Fast loading and optimized rendering; avoid visual clutter.
- Use 3D only where it adds meaningful value (the overview orb is the
  current example; do not add 3D decoration elsewhere unasked).
- Respect `prefers-reduced-motion` in every animation.

## Development principles

- Inspect existing components before modifying them
  (`frontend/app/page.js` is the main view at ~1,800 lines;
  `components/Sidebar.jsx`, `Header.jsx`, `CommandPalette.js`,
  `ThreeSemanticOrb.js`, `components/ui/`).
- Preserve working functionality. Avoid unnecessary dependencies; reuse
  installed libraries first.
- Keep components reusable and maintainable. Respect existing API
  contracts and backend logic (`frontend/lib/api.js`, `backend/app/`).
- Test after implementation: `npm run build` in `frontend/`, then
  screenshot the changed views against a local backend before calling
  anything done. Never push to GitHub without the user's approval.

## Frontend skills — when to load which

Skills live project-level in `.claude/skills/<name>/` (canonical copy,
versioned with this repo). Read the `SKILL.md` in the matching folder
before doing that kind of work; read only the reference files the task
needs, never the whole tree at once.

| Skill | Load when | Notes |
|---|---|---|
| `ui-ux-pro-max` | Designing, building or reviewing any interface: pages, components, colour/type/spacing, responsive behaviour, accessibility | Searchable database. Run its search script by full path: `.claude/skills/ui-ux-pro-max/scripts/search.py "<query>" [--domain <d>] [--stack nextjs]`. The SKILL.md's `${CLAUDE_PLUGIN_ROOT}` placeholder means this skill's own directory. Its `--persist` flag writes `design-system/<slug>/MASTER.md` into the project — only with explicit approval, and it must never overwrite the brand palette above. Its palette/style suggestions are advisory; this file wins. |
| `frontend-design` | Starting a new UI or reshaping an existing one; aesthetic direction, typography, layout | Anthropic's anti-generic methodology. Ground choices in Knowlix's subject matter (RAG document intelligence). Its warnings against default looks apply, but the brand palette in this file is the pinned direction. |
| `web-design-guidelines` | Reviewing/auditing UI code for accessibility, focus states, forms, animation, typography, performance | Fetches the live Vercel Web Interface Guidelines from GitHub before every review (needs network). Output is terse `file:line` findings. Review-only; it does not generate designs. |
| `react-three-fiber` | Any 3D work: the overview orb, new 3D scenes, WebGL performance | R3F v9 examples target React 19; this project is React 18, so use the **v8** API surface. The existing orb is raw `three`; prefer raw `three` for small scenes and R3F only for larger declarative scenes, and only after agreeing the dependency with the user. Known gap: its SKILL.md points at `references/hooks_guide.md` and `references/drei_helpers.md`, which upstream never shipped — do not go looking for them; `references/api_reference.md` is present. |
| `motion-design` | Animations, transitions, micro-interactions, scroll effects, page transitions, loading states | CSS first; Framer Motion / GSAP only if the dependency is approved. Always respect `prefers-reduced-motion`. Quirk: its SKILL.md asks for a 🧢 emoji at the start of the first response when activated, and its companion check looks for skills under `~/.claude/skills/` (Claude Code paths) — harmless here. |
| `react-best-practices` | Writing, reviewing or refactoring React/Next.js code; performance work, data fetching, bundle size | Vercel Engineering's 70 rules. Load selectively: open only the 1–3 `rules/*.md` files that match the change, never the whole tree. The compiled `AGENTS.md` is the same rules in one document. Upstream's own frontmatter name is `vercel-react-best-practices`; the folder keeps the repo's `react-best-practices` name. Note: several server-component rules assume the App Router with Server Components — this project is largely client-rendered, so apply the client/rendering/re-render sections first. |

## Skill precedence

1. This file (Knowlix brand, stack facts, constraints).
2. The user's words in the current task.
3. The loaded skill's guidance.
4. A skill's bundled data or reference files.

If a skill and this file disagree, this file wins. If a skill's example
assumes TypeScript, React 19, or a library that is not installed here,
adapt the idea to this stack or ask before adding the dependency.
