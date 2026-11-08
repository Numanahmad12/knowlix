"""Validate the six Knowlix frontend skills in both install locations.

Checks per skill: SKILL.md exists with name+description frontmatter matching
the folder; skill.yaml exists and parses in the runtime mirror; every file
path referenced from SKILL.md (references/, scripts/, rules/, AGENTS.md)
exists; no name collisions with system skills. Plus functional spot checks.
"""
import os, re, sys, subprocess

REPO = "/home/hatch/workspace/knowlix-fedc3d5/.claude/skills"
MIRROR = "/home/hatch/workspace/custom-skills"
SKILLS = ["ui-ux-pro-max", "frontend-design", "web-design-guidelines",
          "react-three-fiber", "motion-design", "react-best-practices"]

# Documented upstream quirks: not install failures.
# - react-best-practices: upstream frontmatter name is
#   "vercel-react-best-practices" while the repo folder (kept as-is) is
#   "react-best-practices".
# - react-three-fiber: SKILL.md lines 1103-1104 point at
#   references/hooks_guide.md and references/drei_helpers.md, which were
#   never shipped upstream (confirmed via git ls-tree; the sibling
#   pixelpulsetech copy has no references/ at all). The skill body and
#   api_reference.md are complete; the two pointers are recorded as a
#   known gap in docs/FRONTEND_SKILLS.md rather than fabricated.
KNOWN_NAME_MISMATCH = {"react-best-practices": "vercel-react-best-practices"}
KNOWN_MISSING_REFS = {"react-three-fiber": {"references/drei_helpers.md",
                                            "references/hooks_guide.md"}}

def frontmatter(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w+):\s*(.*)$", line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return fm, text

def check_location(base, name, need_yaml):
    errs, notes = [], []
    d = os.path.join(base, name)
    if not os.path.isdir(d):
        return [f"missing dir {d}"], notes
    sk = os.path.join(d, "SKILL.md")
    if not os.path.isfile(sk):
        return [f"missing SKILL.md in {d}"], notes
    fm, text = frontmatter(sk)
    if not fm:
        errs.append(f"{name}: no YAML frontmatter")
    else:
        if fm.get("name") != name and KNOWN_NAME_MISMATCH.get(name) != fm.get("name"):
            errs.append(f"{name}: frontmatter name {fm.get('name')!r} != folder")
        if not fm.get("description"):
            errs.append(f"{name}: empty description")
    if need_yaml:
        y = os.path.join(d, "skill.yaml")
        if not os.path.isfile(y):
            errs.append(f"{name}: missing skill.yaml (runtime mirror)")
        else:
            yt = open(y).read()
            if f'name: {name}' not in yt:
                errs.append(f"{name}: skill.yaml name mismatch")
    # referenced local files
    refs = set(re.findall(r"(?:references|scripts|rules)/[A-Za-z0-9_.\-/]+", text))
    refs |= set(re.findall(r"`(AGENTS\.md)`", text))
    missing = [r for r in sorted(refs) if not os.path.exists(os.path.join(d, r))]
    missing = [r for r in missing if r not in KNOWN_MISSING_REFS.get(name, set())]
    if missing:
        errs.append(f"{name}: missing referenced files: {missing[:5]}")
    notes.append(f"{name}: {len(refs)} referenced paths checked, "
                 f"{len(text.splitlines())} lines in SKILL.md")
    return errs, notes

all_errs, all_notes = [], []
for s in SKILLS:
    for base, need_yaml in ((REPO, False), (MIRROR, True)):
        e, n = check_location(base, s, need_yaml)
        all_errs += e
        all_notes += n

# collisions with system skills
sys_names = set(os.listdir("/opt/muse/skills"))
for s in SKILLS:
    if s in sys_names:
        all_errs.append(f"{s}: collides with a system skill name")

# functional spot checks
def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout.strip()[:200]

rc, out = run(f"python3 {MIRROR}/ui-ux-pro-max/scripts/search.py 'saas dashboard' --stack nextjs --max-results 2")
print("search.py rc:", rc); print(out[:200] if rc == 0 else "FAILED")
if rc != 0:
    all_errs.append("ui-ux-pro-max search.py failed from installed location")
rules = [f for f in os.listdir(f"{MIRROR}/react-best-practices/rules") if f.endswith(".md")]
print("react-best-practices rule files:", len(rules))
if len(rules) < 60:
    all_errs.append(f"react-best-practices: only {len(rules)} rule files")
rc, out = run("curl -s -m 20 -o /dev/null -w '%{http_code}' https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md")
print("web-design-guidelines live rules URL HTTP:", out)
if out != "200":
    all_errs.append(f"web-design-guidelines rules URL returned HTTP {out} (skill needs network at review time)")

for n in all_notes:
    print("ok:", n)
print()
if all_errs:
    print("VALIDATION FAILED:")
    for e in all_errs:
        print(" -", e)
    sys.exit(1)
print("VALIDATION PASSED: all 6 skills, both locations")
