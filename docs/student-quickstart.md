# Student Quickstart — run Applied AI Studio in your browser

You do not need to install anything on your computer. GitHub Codespaces gives
you your own private copy of this application, running in the cloud, that only
you can see. It is free within GitHub's monthly allowance, which is far more
than this course needs.

## 1. One-time setup (about 5 minutes)

1. Create a free GitHub account at <https://github.com> if you do not have one.
   You need one for this course anyway — your portfolio lives there.
2. Recommended: apply for the free
   [GitHub Student Developer Pack](https://education.github.com/pack) with your
   HCC email. It upgrades your account and includes GitHub Copilot at no cost.
   Approval can take a few days, so do this in week 1.

## 2. Start the app (about 3 minutes the first time)

1. Open this repository on GitHub and click the green **Code** button.
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

## 3. Optional: enable Ask Studio (Copilot)

The workflows, AI-fit scoring, and the Online Order demo all work without this
step. Ask Studio — the chat feature — uses **your own** GitHub Copilot, which
is free for verified students through the Student Developer Pack.

In the codespace terminal:

```bash
npm install -g @github/copilot
copilot
```

Follow the sign-in prompts once, then restart the app with `npm run dev`.

## 4. When you are done

Codespaces stop by themselves after you close the tab and go idle, so normally
you do nothing. To be tidy: <https://github.com/codespaces> lists your
codespaces — stop or delete them there. Deleting one loses nothing; you can
always create a fresh one from the repository.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Page shows nothing / connection refused | Make sure `npm run dev` is still running in the terminal; restart it if not. |
| "Port 5173" notification never appeared | Ports tab → port 5173 → globe icon. |
| Everything is broken and you don't know why | Delete the codespace and create a new one. This is a normal move, not a failure. |
| Ask Studio says Copilot is unavailable | That feature needs step 3, or your Student Pack is still pending. Everything else works without it. |

## Running it on your own computer instead

Codespaces is the supported path for this course. If you want to run the app
locally later in the semester, follow the **Quick Start** in the main
[README](../README.md) — it requires Git, Node.js 22, and Python 3.11.
