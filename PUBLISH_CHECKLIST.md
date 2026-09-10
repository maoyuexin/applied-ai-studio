# Publish checklist — applied-ai-studio → public

Work through this top to bottom. Everything before "Flip to public" happens
while the repo is still private. Delete this file before or after publishing —
it is for you, not for students.

## 1. Scan the history, not just the tree

The current tree is clean, but Git keeps everything ever committed. Either
scan the full history:

```bash
# from the repo root
brew install gitleaks          # or: brew install trufflehog
gitleaks git . --verbose
```

…or skip the scan entirely by publishing with fresh history (recommended —
simpler and provably safe):

```bash
# Fresh single-commit publish. Your existing repo stays as your private archive.
cd /Users/yuexinmao/Documents/customer_workshop/applied-ai-studio
git ls-files -z | rsync -a --files-from=- --from0 . /tmp/applied-ai-studio-public/
cd /tmp/applied-ai-studio-public
git init -b main
git add -A
git commit -m "Applied AI Studio — initial public release"
gh repo create maoyuexin/applied-ai-studio --public --source . --push
```

Note: `git ls-files` copies only tracked files, so `.env`, `.venv`, databases,
and `node_modules` never travel. Verify with `git status` before pushing.

## 2. Files to add before the first public commit

- [ ] `LICENSE` (MIT — provided)
- [ ] `.devcontainer/devcontainer.json` + `.devcontainer/post-create.sh` (provided)
- [ ] `docs/student-quickstart.md` (provided)
- [ ] README: add one line near the top —
      *"Students: see [docs/student-quickstart.md](docs/student-quickstart.md)
      to run this in your browser with GitHub Codespaces — no installation."*
- [ ] README: fix the clone URL if the public repo name/owner differs.
- [ ] Make the post-create script executable before committing:
      `chmod +x .devcontainer/post-create.sh`

## 3. Repository settings after publishing (github.com → Settings)

- [ ] **Code security** → enable **Secret scanning** and **Push protection**
- [ ] **Code security** → enable **Dependabot alerts** and **security updates**
- [ ] **Security** tab → enable **Private vulnerability reporting**
      (SECURITY.md already tells reporters to use it)
- [ ] **General** → disable Wikis/Projects if unused (fewer surfaces to moderate)
- [ ] Branch protection on `main`: require PRs if you ever accept student PRs;
      otherwise at minimum block force-pushes
- [ ] **Codespaces**: nothing to configure — students use their own quota on a
      public repo, not yours

## 4. Things deliberately NOT to do

- Do **not** deploy the agent service to a shared server with your Copilot
  identity — ADR-0002 already rules this out. Codespaces gives each student
  their own identity instead.
- Do **not** commit slides/PPTX here — they go to the course-materials repo.
- Do **not** grant students write access to this repo. They fork or open
  codespaces; contributions, if you want them, arrive as PRs.

## 5. Known advisories

SECURITY.md documents two moderate Mermaid/DOMPurify advisories with
mitigations. Before publishing, re-run:

```bash
npm audit --audit-level=high
```

…and update the "As of" date in SECURITY.md if the situation changed.

## 6. Announce to students

The only link students need is the repo URL. Their instruction is:
**Code → Codespaces → Create codespace on main**, then `npm run dev`.
Point them at `docs/student-quickstart.md` in week 1, alongside the
Student Developer Pack application (approval takes days).
