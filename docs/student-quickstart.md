# Student Quickstart — run Applied AI Studio in your browser

**The app lives here:** <https://github.com/maoyuexin/applied-ai-studio>

Open that link, then follow the steps below. Nothing gets installed on your own
computer, and you cannot break anything for anyone else.

GitHub Codespaces gives you your own private copy of this application, running
in the cloud, that only you can see. It is free within GitHub's monthly
allowance, which is far more than this course needs.

## 1. One-time setup

### Required — a free GitHub account

Create one at <https://github.com> if you do not have one already. You need it
for this course anyway, because your portfolio lives there.

That is the only thing you must have. You can start using the app straight away.

### Optional — the GitHub Student Developer Pack

The [Student Developer Pack](https://education.github.com/pack) is free for
students and is the only way to get GitHub Copilot at no cost. Apply with your
HCC email. Approval usually takes a few days.

**It is optional, and you should not wait for it.** Without Copilot the app
still works — only the Ask Studio chat page is unavailable, and the AI Fit
Analyzer hands you a ready-made outline instead of writing one about your own
problem. Apply in week 1 and carry on in the meantime.

## 2. Start the app (about 3 minutes the first time)

**You do not need to fork or copy anything.** Go straight to the repository and
open a codespace from it — GitHub allows this on any public repository, and it
builds you a private copy that only you can see. You will never be asked to push
anything back.

1. Go to <https://github.com/maoyuexin/applied-ai-studio> and sign in, then
   click the green **Code** button near the top right.
2. Choose the **Codespaces** tab → **Create codespace on main**.
3. Wait for the editor to open and for setup to finish — the terminal will say
   **"Applied AI Studio is ready."** The first time takes a few minutes;
   after that, reopening is fast.

   > **This line is your checkpoint.** If you never see it, setup did not
   > finish, and the next steps will fail. Do not keep going and do not simply
   > close and reopen — a codespace that did not finish setting up will never
   > repair itself, however many times you reconnect. Delete it and create a
   > new one.

4. In the terminal at the bottom, type:

   ```bash
   npm run dev
   ```

5. A notification appears saying the app is available on **port 5173** — click
   **Open in Browser**. (If you miss it: click the **Ports** tab next to the
   terminal, find port 5173, and click the globe icon.)

That address is private to you. Your codespace is your own copy — nothing you
do in it affects anyone else.

### Keep a live demo from timing out

GitHub stops a codespace after its idle timeout, which is 30 minutes by default.
Simply leaving the app open in another browser tab may not count as activity:
this single-page app can sit quietly without producing terminal output. For a
live demo, set **GitHub Settings → Codespaces → Default idle timeout** to 90
minutes before creating the codespace. GitHub applies that setting to new
codespaces.

If the app goes offline after sitting unused, return to the codespace and let it
reconnect. Run `npm run dev` once only if the original command is no longer
running. Always open port **5173**; do not use a second port offered by an older
version of the project.

## 3. Using the app without Copilot (this is normal in week 1)

In your first week your Student Developer Pack is probably still being approved,
so GitHub Copilot is not connected yet. That is expected, and the app is built
for it.

| Page | Without Copilot |
| --- | --- |
| Industry Workflows | Works fully. Six complete business workflows to explore. |
| Online Order demo | Works fully. Place an order and step it through. |
| AI Fit Analyzer | Works. See below for exactly what happens. |
| Ask Studio | The only page that needs Copilot. It will say so plainly. |

### What the AI Fit Analyzer does without Copilot

Fill in the boxes and press **Generate five-stage workflow**. Instead of an
error you get a blue-green note reading **"Starter outline — written without
AI"**, followed by a complete five-stage outline with five decisions already
marked.

Edit any part of it, choose a decision, and score it exactly as you otherwise
would. **Nothing is missing from the exercise.** When Copilot is switched on
later, the same button writes an outline from your own problem description
instead.

Once your Student Pack is approved, Ask Studio starts working on its own — see
section 4. There is nothing for you to install or configure.

## 4. Ask Studio and GitHub Copilot

**There is nothing to install and nothing to sign in to.** The Copilot software
is installed for you during setup, and your codespace already knows who you are.

The only thing that decides whether Ask Studio works is whether your GitHub
account has Copilot:

- **You have Copilot** (Student Pack approved, or a paid plan) — Ask Studio
  works straight away. No setup, no sign-in prompt.
- **You do not have it yet** — Ask Studio says so in plain language. Everything
  else in the app keeps working.

If your Student Pack is approved later, Ask Studio simply starts working the
next time you open a codespace. There is no step to come back and do.

> Your codespace signs in as **you**, not as your instructor. You are using your
> own GitHub account, never somebody else's.

## 5. When you are done

Codespaces stop by themselves after you close the tab and go idle, so normally
you do nothing. To be tidy: <https://github.com/codespaces> lists your
codespaces — stop or delete them there. Deleting one loses nothing; you can
always create a fresh one from the repository.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| **`bash: npm: command not found`** (or `python`, or `node`) | Setup did not finish, so the tools were never installed. Reconnecting will not fix it. Delete the codespace and create a new one. |
| Page shows nothing / connection refused | Make sure `npm run dev` is still running in the terminal; restart it if not. |
| "Port 5173" notification never appeared | Ports tab → port 5173 → globe icon. |
| App stopped after sitting open for about 30 minutes | The codespace reached its idle timeout. Reopen the codespace, then run `npm run dev` once if it is no longer running. For a live demo, set a 90-minute default timeout before creating the codespace. |
| `npm run dev` says ports are already occupied | Do not start another copy. Open port 5173 if the existing app is healthy. Otherwise press Ctrl+C in the original dev terminal, wait for its prompt, and run `npm run dev` once. If that terminal is lost, run **Terminal: Kill All Terminals** from the command palette first. |
| "Starter outline — written without AI" appears | Nothing is wrong. Copilot is not connected yet. Keep going; the outline is editable and scorable. |
| Ask Studio says Copilot is unavailable | Your Student Pack is still pending, or you have not done step 4. Every other page works without it. |
| **"You appear to be offline" / codespace will not connect** | Usually GitHub itself, not you. Check <https://www.githubstatus.com> first. If something there is red or orange, wait — there is nothing to fix on your side. |
| Codespace will not finish setting up | Delete it and create a new one. If a second one fails the same way, send your instructor the last 20 lines from the terminal. |
| Everything is broken and you don't know why | Delete the codespace and create a new one. This is a normal move, not a failure. |

## Running it on your own computer instead

Codespaces is the supported path for this course. If you want to run the app
locally later in the semester, follow the **Quick Start** in the main
[README](../README.md) — it requires Git, Node.js 22, and Python 3.11.
