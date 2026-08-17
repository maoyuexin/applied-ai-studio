# Student Quickstart — run Applied AI Studio in your browser

**The app lives here:** <https://github.com/maoyuexin/applied-ai-studio>

Open that link, then follow the steps below. Nothing gets installed on your own
computer, and you cannot break anything for anyone else.

GitHub Codespaces gives you your own private copy of this application, running
in the cloud, that only you can see. It is free within GitHub's monthly
allowance, which is far more than this course needs.

## 1. One-time setup (about 5 minutes)

1. Create a free GitHub account at <https://github.com> if you do not have one.
   You need one for this course anyway — your portfolio lives there.
2. Recommended: apply for the free
   [GitHub Student Developer Pack](https://education.github.com/pack) with your
   HCC email. It upgrades your account and includes GitHub Copilot at no cost.
   Approval can take a few days, so do this in week 1.

## 2. Start the app (about 3 minutes the first time)

1. Go to <https://github.com/maoyuexin/applied-ai-studio> and sign in, then
   click the green **Code** button near the top right.
2. Choose the **Codespaces** tab → **Create codespace on main**.
3. Wait for the editor to open and for setup to finish — the terminal will say
   **"Applied AI Studio is ready."** The first time takes a few minutes;
   after that, reopening is fast.
4. In the terminal at the bottom, type:

   ```bash
   npm run dev
   ```

5. A notification appears saying the app is available on **port 5173** — click
   **Open in Browser**. (If you miss it: click the **Ports** tab next to the
   terminal, find port 5173, and click the globe icon.)

That address is private to you. Your codespace is your own copy — nothing you
do in it affects anyone else.

## 3. What you will see in week 1 (this is normal)

In your first week your Student Developer Pack is probably still being approved,
so GitHub Copilot is not connected yet. That is expected, and the app is built
for it.

- **Industry Workflows** — works fully.
- **Online Order** demo — works fully.
- **AI Fit Analyzer** — works. When you press *Generate five-stage workflow*
  you will see a blue-green notice saying **"Starter outline — written without
  AI"**, followed by a normal five-stage outline you can edit and score. That
  notice is information, not an error. Nothing is broken and you did nothing
  wrong.
- **Ask Studio** — the only page that genuinely needs Copilot. It will tell you
  so plainly.

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
