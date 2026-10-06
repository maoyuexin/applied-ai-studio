# Design Studio: end-to-end test cases

Ten manual tests, run in the browser exactly as a user would: two per pipeline, plus two prompt-only
video tests (VD3, VD4). Each one checks a feature you may show in class: review steps, revisions, automatic
checks, labels, run history.
Run them on **your Mac** (http://127.0.0.1:5173/design-studio) and repeat the ones marked *server* on
the **home server** (https://applied-ai-studio.myyclabs.com/design-studio).

> Use the exact button names in **bold**. "Expect" lines are the pass criteria. If a model's wording
> varies, the structure in "Expect" still has to hold.

## Before you start (2 minutes)

1. Open Design Studio. Each card shows green model chips. The Video card shows
   *Sora 2 · retires Oct 15* in yellow.
2. Top right, open **Settings** (gear). Press **Test** on every role. **Expect:** each one turns green
   (`ready · n.n s`).
3. Note the **Daily caps** numbers. VD2 checks one of them.

| Test | Pipeline | Time | Model calls (approx.) | Run on |
|---|---|---|---|---|
| A1 | Article | 4 min | 8 text | Mac + server |
| A2 | Article | 3 min | 6 text | Mac |
| V1 | Voice | 4 min | 1 text, ~14 voice | Mac + server |
| V2 | Voice | 3 min | 1 text, ~10 voice | Mac |
| I1 | Image | 5 min | 2 text, 4 images | Mac + server |
| I2 | Image | 2 min | 1–2 images | Mac |
| VD1 | Video | 12 min | 1–2 text, 1–2 images, 5–6 Sora takes | Mac |
| VD2 | Video | 6 min | 1 text, 1 Sora take | Mac → server |
| VD3 | Video (prompt only) | 5 min | 2 Sora takes, no text model | Mac + server |
| VD4 | Video (prompt only, 3-shot story) | 10 min | 6 Sora takes (3 with 1 take per shot), 1 voice | Mac + server |

Sora takes are the only expensive calls (20 per day cap). Run the video tests before **Oct 15**.
How the video pipeline works, in detail: [VIDEO_GUIDE.md](VIDEO_GUIDE.md).

---

## Article

### A1 · Newsroom summary: fact check, revise, catch a planted error *(Mac + server)*

**Shows:** outline gate, version history with diff, a second model checking claims, human sign-off.

1. Home → **New article run** → **Load example** (NASA Starliner release, 150 words).
2. Check **Text model** = `gpt-6-astra (default)` and **Fact-check model** = `gpt-6.1-sol (default)`.
   **Expect:** the preview shows `gpt-6-astra · checked by gpt-6.1-sol` under step 2.
3. **Start run**. **Expect:** within ~10 s, the outline shows a headline and 3–7 points, each with a
   source tag `[1]`, and the step is marked *Waiting for you*.
4. Change the headline wording. In the redraft box type `Lead with the launch window` and press **Redraft**.
   **Expect:** a new outline; the chip reads `draft 2`.
5. **Approve & continue**. **Expect:** `v1` appears with a **Fact check of v1** panel: a claims count
   (for example `Claims: 15 supported · 0 partly · 0 unsupported`) and one card per claim with a quote
   from the source.
6. In **Revise v1**, type `Say "December 2026" explicitly and add one sentence on why the 2024 test flight
   led to these changes.` and press **Make v2**. **Expect:** `v2` appears; **Show changes from v1** highlights
   removed text in red and added text in green.
7. Plant an error: with v2 selected press **Edit it myself**, add the sentence
   `Starliner-1 will carry four astronauts.` and **Save as new version**.
   **Expect:** `v3 (you)` is checked automatically, and the planted sentence is marked **unsupported**
   with a reason. The v3 tab badge turns red.
8. Click the **v2** tab (the version without the error) → **Approve & continue**.
   **Expect:** *Approved: v2* with the label *AI-assisted summary, reviewed by an editor.*, checks
   `Approved by you: v2`, and the claims line. **Download .md** contains the headline, body, label and a
   *Sources:* list.

**Pass if:** the planted claim was flagged in v3 and the approved text is v2.

### A2 · Fork with other models and a banned phrase, then compare *(Mac)*

**Shows:** forking, per-run model choice, the must-not-include rule check, Compare.

1. Open the A1 run → **Fork**. **Expect:** the New run form is prefilled, with a banner *Forked from …*.
2. Change **Text model** to `gpt-5.4-mini` and **Fact-check model** to `gpt-5.4`. In **Must not include**
   type `Boeing`. **Start run** → **Approve & continue** at the outline.
3. **Expect on v1:** the checks include `Must-not-include: none found` (the prompt told the model not to
   use it), and the writer shown on v1 is `gpt-5.4-mini`.
4. **Edit it myself** and add `Boeing built the capsule.` → **Save as new version**.
   **Expect:** v2's checks show `Must-not-include found: Boeing` in red.
5. Approve v1. Then top right **Run history** (clock icon), tick the A1 run and this run →
   **Compare 2 runs**. **Expect:** both runs side by side. *Text model*, *Fact-check model* and *Must not
   include* carry an orange *changed* tag on the fork, and rows such as *Unsupported claims (v1 → approved)*
   and *Versions* fill in for both.

**Pass if:** the exact-phrase rule caught "Boeing" in v2, and Compare shows both runs.

---

## Voice

### V1 · Two-host intro: listen-back and re-recording one line *(Mac + server)*

**Shows:** script gate, per-line synthesis, the listen-back check, redoing one line, the spoken AI disclosure.

1. **New voice run** → **Load example**. **Expect:** two speakers, Harper and Ethan (en-US), target 35 s.
2. **Start run**. **Expect:** a script of 4–7 lines whose last line says the voices are AI-generated;
   the line count and estimated seconds appear above the editor.
3. Edit one line to include a hard name, for example
   `Tonight the SOLENNE GT ad shows how fast this moves.` → **Approve & continue**.
4. **Expect:** each line gets an audio player, a *heard: "…"* transcript, and a chip that reads either
   *✓ matches the script* or *N word differences* with `script … → heard …` highlighted. The brand name
   is the likely mismatch.
5. On the flagged line press **Edit**, rewrite it (for example `Tonight the Solenne G T ad…`) → **Re-record**.
   **Expect:** a `line n.2` take appears and becomes the kept one; the take picker lists both takes.
6. Press **Again** on another line. **Expect:** only that line is re-recorded.
7. **Approve & continue**. **Expect:** **Final mix** with length ≈ 30–45 s, *Loudness normalized to -16 LUFS*,
   *Listen-back: N word difference(s) across n checked lines*, *Spoken AI disclosure in the last line* (green),
   and a speaker-by-speaker transcript. **Download MP3** plays.

**Pass if:** only the edited lines were re-recorded, and the mix reports the disclosure.

### V2 · Spanish narration, with the disclosure removed on purpose *(Mac)*

**Shows:** another language end to end, and a label check that warns when the disclosure is missing.

1. **New voice run**. **Format:** Narration. **Target length:** 30 s. **Language:** Spanish (Mexico).
   **Speakers:** one speaker, voice `Valeria`, default style `encouraging` (if offered) or none.
2. Brief: `Bienvenida al Módulo 8: cómo la IA genera contenido y por qué una persona revisa cada paso. Tono cálido.`
3. **Start run**. **Expect:** a Spanish script whose last line discloses AI voices (e.g. *…generadas con IA*).
4. Delete the last (disclosure) line with its trash icon → **Approve & continue**.
5. **Expect:** Spanish transcripts under each line (listen-back runs in `es-MX`).
6. **Approve & continue**. **Expect:** the final mix shows a yellow
   *No spoken AI disclosure found in the last line*.

**Pass if:** Spanish synthesis and transcription work, and the missing disclosure is flagged.

---

## Image

### I1 · Campaign poster from the design sheet: iterate on a version tree *(Mac + server)*

**Shows:** reference roles, prompt gate, candidates, revisions with a note, branching, exact title,
Content Credentials before and after labeling.

1. **New image run** → **Load example**. **Expect:** use case *Campaign poster with title*, size 9:16,
   2 candidates, and the SOLENNE design sheet attached as **Subject**.
2. **Start run**. **Expect:** the text model's prompt appears for editing. **Approve & continue**.
3. **Expect:** two portrait candidates `c1`, `c2`, each with *Content Credentials: present, valid
   (Microsoft Corporation)*. **Keep** one → **Approve & continue**.
4. In **Revise c1**: note `Night, rain reflections on the road; keep the car identical`, keep the
   design sheet as *subject*, leave *Let the text model turn my note into a full prompt* ticked →
   **Write the prompt**. **Expect:** an editable *Proposed prompt* appears. Press **Make v1 from c1**.
5. **Expect:** `v1` appears **under** c1 in **Versions**, with *Change asked* and the prompt sent.
   Press **Keep** on v1.
6. Branch: click **c1** in Versions again, note `Golden hour, low camera` → **Write the prompt** →
   **Make v2 from c1**. **Expect:** `v2` is a second child of c1, not of v1.
7. In **Finish**, pick the final image, **Title** `SOLENNE GT`, **Visible label**
   `Fictional vehicle. Made with AI.` → **Approve & continue**.
8. **Expect:** the final poster with the exact title and the label in the top-right corner. Checks:
   *Title set by the app*, *Original: Content Credentials: present, valid*, *Labeled copy: Content Credentials:
   none found* (labeling re-encodes the file). **Use in a video run** opens a New video run with this
   image as the subject reference.

**Pass if:** v1 and v2 branch from c1, and the provenance checks differ between original and labeled copy.

### I2 · Brand guardrail: blocked or not, a person decides *(Mac)*

**Shows:** vendor filters miss things and block things; the human review and Restricted runs.

1. **New image run**. Use case **Social post**, size 1:1, **Candidates** 1, **Prompt helper** *Off*.
   Brief: `A red Ferrari 296 GTB with the prancing horse badge parked outside a café`.
2. **Start run** → **Approve & continue** at the prompt.
3. **Expect one of two outcomes; both pass:**
   - **Blocked:** the candidate shows *Blocked by the content filter*, the event log names the filter
     (for example `BingBlockList`), and Settings → Daily caps did **not** count the call. Click the blocked
     candidate; on its review page replace the prompt with `A red fictional Italian sports coupe, no badges`
     → **Retry with this prompt** → the image is generated.
   - **Not blocked:** open the image; in **Your review** mark *No real brand, logo or face?* as ✗ →
     **Reject**, note `Real brand: guardrail did not stop it`.
4. Top of the run: **Restrict**. **Expect:** a *Restricted* tag; **Export bundle** disappears; in Run
   history the export icon is a lock.

**Pass if:** the outcome is recorded (block event or your rejection), and the run cannot be exported.

---

## Video

### VD1 · Short ad with keyframes, review, remix and assembly *(Mac)*

**Shows:** shot list gate, product keyframes from the design sheet, takes per shot, the review page,
remix, assembly with label and end card, provenance.

1. **New video run** → **Load example** (design sheet attached). Change **Shots** to `2`,
   **Seconds per shot** to `4 s`, **Takes per shot** to `2`. **Expect:** the preview says
   `4 video generations · 16 s video generated`.
2. **Start run**. **Expect:** 2 shots. A car-only shot shows *keyframe → video*; a shot with people
   shows *text → video*, because Sora rejects input images with faces.
3. Edit one shot prompt (add `the camera dollies in slowly`) → **Save edits**, then
   **Approve & continue**.
4. Keyframes (only for keyframe shots). **Expect:** a keyframe of the same car in the shot's setting,
   already kept. Type `make it dawn` → **New keyframe**. **Expect:** a second keyframe, which becomes the kept one.
   **Approve & continue**.
5. Takes (~1–2 min). **Expect:** each take card shows `0:04`, a generation time, and a `motion n.n` chip;
   low motion is flagged.
6. Click a take to open the review page. **Expect:** the player, the prompt sent, the input keyframe, `sora-2 ·
   2025-12-08`, the job id, and automatic checks (motion, sound, *Content Credentials: present, fails check:
   signingCredential.expired*). Tick the checklist, add a note, **Keep**. Use the arrows to move between takes.
7. On another take, **Remix with a note**: `slower camera, warmer light` → **Remix**.
   **Expect:** a new take labeled `…_t3` appears in the same shot; its review page shows *from …_t2*
   (the take it remixed) and only your change as the prompt.
8. Keep one take per shot → **Approve & continue**. **Expect:** **Final cut** (≈ 9–10 s) plays with
   *Made with AI* / your label in the corner and the SOLENNE GT end card. Checks list the label and end
   card; provenance says raw takes have Content Credentials that fail validation and the final has none.
   **Download MP4** works. **Back to takes (re-cut)** reopens the takes step for a different cut.

**Pass if:** only kept takes are in the cut, and the label and end card are burned in.

### VD2 · Restart in the middle of a take, then move the run to the server *(Mac → server)*

**Shows:** jobs survive a restart without being paid for twice; bundles copy runs to the backup.

1. Note **Settings → Daily caps → Video takes** (for example `6 of 20`).
2. **New video run**, no references. Brief:
   `A 4-second shot of rain on a café window at night, city lights blurred behind it.`
   **Shots** 1, **Seconds** 4 s, **Takes** 1 → **Start run** → **Approve & continue**.
3. While the take shows *generating… n%*, restart the service:
   - Mac: in the terminal running the Studio press Ctrl-C, then `npm run dev` (or `npm run dev:design`).
   - Server (alternative): `ssh home-server 'cd /opt/homeserver/apps/applied-ai-studio && docker compose --env-file release.env -f compose.yaml restart design'`.
4. Refresh the page. **Expect:** the event log shows *Resumed after a restart: 1 job(s) continue.*, the take
   finishes, and **Settings → Daily caps → Video takes** went up by **1**, not 2: the app kept polling the same
   Sora job instead of starting a new one.
5. Keep the take → **Approve & continue** → the final cut appears.
6. **Export bundle** (downloads a `.zip`). On the home server: **Run history** → **Import bundle…** → choose
   the zip. **Expect:** *Imported "…"*; the run opens with the same takes, final cut, decisions and events,
   and its event log ends with *Imported from a bundle…*.

**Pass if:** no second Sora job was created, and the server shows the same run.

### VD3 · Prompt only: your words go straight to Sora *(Mac + server)*

**Shows:** end-to-end video from a prompt with no text model and no images in between; why a person
judges the takes, not the motion number.

1. **New video run** → **Shot prompts**: *Off: one shot per line, sent to Sora as written* → **Load example**.
   **Expect:** one line about the silver grand tourer on the coastal highway; **Shots** reads `1 (one per line)`,
   **Seconds per shot** `12 s`, **Takes per shot** `2`. The **Text model** picker and **Reference images** are
   gone. The preview starts with *Your lines → shots* (`no model · your lines as written`) and shows
   `2 video generations · 24 s video generated · ~2.3 min`.
2. **Start run**. **Expect:** within a second, one shot whose prompt is exactly your line, the chip
   *no text model · your lines as written*, and no **Redraft** box. The event log says *no text model was used*.
3. **Approve & continue**. **Expect:** two takes of `0:12` after about 2½ minutes.
4. Open each take and **watch all 12 seconds**. Compare the `motion` numbers, then check the physics: does the
   car stay on the road, does a badge or logo appear? In the reference run, the take with the **highest**
   motion (7.05) drove the car onto the ocean, so it was rejected and the calmer take (5.39) kept.
   **Expect:** the review page's *Prompt sent* is your line, word for word.
5. **Reject** the worse take with a note, **Keep** the better one → **Approve & continue**.
   **Expect:** a 12.0 s final cut with *Made with AI* burned in and no end card (none was set).

Variation: write **two** lines (two shots). **Expect:** `Shots` reads `2 (one per line)`, each line becomes a
shot, and the final cut joins the two kept takes with a 0.5 s crossfade.

**Pass if:** Sora received your line unchanged, and the take you kept is the one that looks right, not the one
with the biggest number.

### VD4 · Little League comic: home run, game-saving catch, win *(Mac + server)*

**Shows:** a three-shot story written as your own prompts; keeping the same players and style across shots
that Sora generates separately (it remembers nothing between shots); a play-by-play voiceover timed to the
shots; an end card the app draws itself; checking a kids' video before you share it.

**Why the drawing is not attached:** every shot shows people, and Sora rejects input images with faces, so
Design Studio sends shots with people as text → video (the Reference images field is hidden when prompt
helper is off). The drawing's look goes into the prompts as words instead: watercolor-and-ink comic,
short black hair, orange *Bellaire* jersey in white script, navy cap with an orange tiger-head emblem,
white pants, navy socks. Expect a cartoon player in that uniform, not the drawing's exact face.

**Privacy:** keep real children's names and photos out of the prompts. If you want a player's name in the
video, put it on the **End card title**: the app draws the card itself, so the spelling is exact and the
name never goes to Sora.

Before you start: **Settings → Daily caps → Video takes** needs **6** free (3 if you choose 1 take per shot).

1. **New video run** → **Shot prompts**: *Off: one shot per line, sent to Sora as written*. Paste these three
   lines into **Shot prompts (one per line)**. Each line is one 8-second shot; the setting, uniform and
   style are repeated on every line on purpose.

   ```text
   Hand-drawn 2D animation in a soft watercolor-and-ink comic style: bold ink outlines, cream paper texture, blue watercolor sky with puffy white clouds, warm sandy infield, comic speed lines on fast motion. A sunny Little League game, top of the last inning. A young batter with short black hair and a determined look, orange jersey with "Bellaire" in white script, navy cap with an orange tiger-head emblem, white pants and navy socks, waits in the batter's box beside the catcher and umpire. Low angle from the first-base side: the pitch arrives, he swings hard, the bat smacks the ball with a flash of speed lines, and the camera whips up to follow the ball soaring over the outfield fence while the catcher's jaw drops. The batter tosses the bat aside and starts a happy trot toward first base. Sound: crisp crack of an aluminum bat, parents cheering, playful upbeat brass-and-whistle music, no dialogue.
   Hand-drawn 2D animation in a soft watercolor-and-ink comic style: bold ink outlines, cream paper texture, blue watercolor sky with puffy white clouds, green outfield grass, comic speed lines on fast motion. Bottom of the last inning, two outs: a batter in a gray uniform hits a long fly ball to deep center field. The center fielder, a young player with curly brown hair, orange "Bellaire" jersey with number 7 on the back, navy cap with an orange tiger-head emblem and a brown leather glove, sprints back toward the chain-link fence. The camera tracks side-on with the runner, then tilts up to a low angle against the sky as the fielder leaps at the fence; the action slows like a comic panel and the ball drops into the glove. The fielder lands and raises the glove high with the ball inside. Sound: running footsteps on grass, a crowd gasp, then a huge cheer; the same playful brass music, no dialogue.
   Hand-drawn 2D animation in a soft watercolor-and-ink comic style: bold ink outlines, cream paper texture, blue watercolor sky with puffy white clouds, warm sandy infield, orange and white comic star bursts. The game is over and the Tigers win: the whole team in orange "Bellaire" jerseys, navy caps with an orange tiger-head emblem and white pants rushes onto the infield, jumping and high-fiving. The young batter with short black hair and the curly-haired center fielder, number 7, meet at the pitcher's mound and leap into a joyful double high-five as teammates circle around them, while a grinning coach in a navy polo gets a playful splash from a water bucket and laughs. Slow push-in at eye level, ending on a happy group pose with caps raised. Sound: cheering kids and parents, the playful brass music landing on a final triumphant note, no dialogue.
   ```

   Fill in the rest of the form:

   | Field | Value |
   |---|---|
   | Run title / Tags | `Little League · home run and the catch` / `Module 8, example` |
   | Seconds per shot / Takes per shot / Frame | `8 s` / `2` / `16:9 · 1280×720` |
   | Must not include | `brand or MLB logos, other real team names, injuries or rough collisions, captions or extra on-screen text` |
   | Visible label | `Made with AI` |
   | End card title / tagline | `TIGERS WIN!` / `One swing. One catch. Bellaire Little League.` |
   | Voiceover (optional) | `Tie game, last inning. Here's the pitch... he crushes it! Gone! Bottom of the inning, two outs, a deep fly to center... what a catch! That's the ballgame! The Tigers win it!` |
   | Voiceover voice | `Ethan · en-US · Male` |

   **Expect:** **Shots** reads `3 (one per line)`; no **Text model** picker and no **Reference images**; the
   preview shows `6 video generations · 48 s video generated · ~4.8 min`.
2. **Start run**. **Expect:** three shots, each exactly your line, each marked *text → video*, no **Redraft**
   box, and the event log says *no text model was used*. **Approve & continue**.
3. Takes (~5 min, 2 at a time). While they render, tell the class: the three shots are generated separately,
   and the only thing tying them together is the description repeated in every line.
4. Open each take and **watch all 8 seconds**. **Expect:** *Prompt sent* is your line followed by
   *Keep it free of: brand or MLB logos, …*, the mode is text → video, and there is no input keyframe.
   Then judge it like an editor:
   - Shot 1: the ball leaves the bat and clears the fence (it doesn't vanish or pass through it); the bat
     doesn't bend; hands and fingers look right.
   - Shot 2: the ball really ends up in the glove; the fielder doesn't pass through the fence.
   - Shot 3: nobody gets hurt in the celebration; the splash stays playful.
   - Across shots: same orange and navy uniforms, same two players (black hair; curly brown hair with number 7),
     the style stays watercolor comic (doesn't switch to 3D or photo-real), and *Bellaire* is spelled right.

   For a take that is right except one detail, **Remix** with one change, for example
   `the jersey reads "Bellaire" in clean white script` or `keep the ball in the glove after the catch`.
   For a take that is wrong overall, **Regen**. Keep one take per shot.
5. **Approve & continue**. **Expect:** the voiceover is recorded (~18 s), then a **Final cut** of about
   25.4 s: three kept takes joined by 0.5 s crossfades, *Made with AI* in the corner, and the
   *TIGERS WIN!* end card for the last 3 s. In the measured MAI-Voice read (Ethan, Oct 6), the calls land on
   the shots: *he crushes it… Gone!* at about 4–6 s (shot 1), *Bottom of the inning* at 7.8 s as shot 2
   starts, *what a catch!* at 12.5 s, and *The Tigers win it!* at about 18 s in the celebration. Sora's own
   crowd sound plays underneath at a lower volume. The checks list shows *End card: TIGERS WIN!*.
6. **Download MP4**. On the server: **Export bundle** on the Mac, **Import bundle…** on the server (as in VD2),
   or repeat steps 1–5 there.

Variations:
- **Fewer Sora calls:** **Takes per shot** `1` makes 3 takes (~3.2 min) and leaves room for a Regen or Remix
  on a day when the cap is nearly used up.
- **Phone version for family:** **Frame** `9:16 · 720×1280`, same lines.
- **Let the text model write it:** **Shot prompts**: *Text model writes the shot list*, **Shots** `3`, brief:
  `A watercolor-and-ink comic highlight for a Bellaire Little League team, the Tigers: a young batter hits the
  go-ahead home run in the last inning, the center fielder makes a leaping catch at the fence for the final
  out, and the team celebrates.` Open its shot list: does the text model repeat the uniform and style in every
  shot, the way your lines do? Then tick both runs in **Run history** → **Compare 2 runs** to watch the two final
  cuts side by side.

**Pass if:** the three kept takes read as one story (same uniforms, same style, the same two players), the
ball physics in the kept takes are believable, the label and end card are burned in, and nothing in the prompts
identifies a real child.

**IP note for class:** "Little League" is a trademark, and team logos belong to their owners. A family clip is
fine; before posting publicly or using it commercially, ask the league. The prompts ask for a generic tiger
emblem and exclude real logos for that reason.

---

## Results log

| Test | Mac | Server | Notes |
|---|---|---|---|
| A1 | ☐ | ☐ | |
| A2 | ☐ | — | |
| V1 | ☐ | ☐ | |
| V2 | ☐ | — | |
| I1 | ☐ | ☐ | |
| I2 | ☐ | — | |
| VD1 | ☐ | — | |
| VD2 | ☐ | ☐ (import) | |
| VD3 | ☐ | ☐ | |
| VD4 | ☐ | ☐ | |

Clean up afterwards: delete test runs you don't want in class from **Run history** (trash icon). Keep the
ones you want to show; they also work as recorded examples if the network fails in class.
