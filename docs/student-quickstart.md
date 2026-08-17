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

Once your Student Pack is approved, come back and do step 4 below.

## 4. Optional: enable Ask Studio (Copilot)

Ask Studio — the chat feature — uses **your own** GitHub Copilot, which
is free for verified students through the Student Developer Pack.

In the codespace terminal:

```bash
npm install -g @github/copilot
copilot
```

Follow the sign-in prompts once, then restart the app with `npm run dev`.

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
| "Starter outline — written without AI" appears | Nothing is wrong. Copilot is not connected yet. Keep going; the outline is editable and scorable. |
| Ask Studio says Copilot is unavailable | Your Student Pack is still pending, or you have not done step 4. Every other page works without it. |
| **"You appear to be offline" / codespace will not connect** | Usually GitHub itself, not you. Check <https://www.githubstatus.com> first. If something there is red or orange, wait — there is nothing to fix on your side. |
| Codespace will not finish setting up | Delete it and create a new one. If a second one fails the same way, send your instructor the last 20 lines from the terminal. |
| Everything is broken and you don't know why | Delete the codespace and create a new one. This is a normal move, not a failure. |

## Running it on your own computer instead

Codespaces is the supported path for this course. If you want to run the app
locally later in the semester, follow the **Quick Start** in the main
[README](../README.md) — it requires Git, Node.js 22, and Python 3.11.
