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
| VD4 | Video (prompt only, 4-shot story) | 25 min | 12 Sora takes, plus regenerations (22 in the reference run) | Mac + server |

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

### VD4 · Little League anime: home run, game-saving catch, win *(Mac + server)*

**Shows:** a four-shot story written as your own prompts; how many takes realistic sports action costs and
why a person checks every one; keeping players and style consistent across shots that Sora generates
separately; an end card the app draws itself; checking a kids' video before you share it.

**Reference run:** *Little League · home run and the catch* (Oct 6, `run_2026-10-06_164926_8952`). Its
review notes (each starting *Copilot review:*) say why every rejected take failed.

**Style without naming a show:** the look is a cute, chibi-leaning Japanese sports anime. The prompts
describe it (cel shading, bold ink outlines, screentone, big eyes, manga speed lines) instead of naming a
series or artist. Naming a copyrighted work invites a content-filter block and is exactly the IP question
Module 8 asks students to think about.

**Why the drawing is not attached:** every shot shows people, and Sora rejects input images with faces, so
shots with people go to Sora as text → video (the Reference images field is hidden when prompt helper is
off). The player's look is written into the prompts instead. Expect a cartoon player in that uniform, not a
particular child's face.

**Privacy:** keep real children's names and photos out of the prompts. If you want a player's name in the
video, put it on the **End card title**: the app draws the card itself, so the spelling is exact and the
name never goes to Sora.

Before you start: **Settings → Daily caps → Video takes** needs **12** free, plus room for regenerations
(the cap was raised to 100 on Oct 6).

1. **New video run** → **Shot prompts**: *Off: one shot per line, sent to Sora as written*. Paste these four
   lines into **Shot prompts (one per line)**: the swing, the ball over the fence, the catch, the celebration.

   ```text
   Cute Japanese sports-anime style: clean cel-shaded 2D animation, bold ink outlines, bright colors, screentone shading, chibi-leaning kids with big sparkling eyes, manga speed lines, sunny sky with white clouds. One continuous shot, no cuts. Little League, last inning, tie game. Camera: steady medium shot at the batter's height from the first-base side, framed on the batter alone; the pitcher is off-screen to the right and the catcher is out of frame. Our batter, a cute right-handed boy with short spiky black hair and big determined eyes, wears a navy batting helmet with an orange tiger-head emblem, an orange "Bellaire" jersey and white pants, and stands in the batter's box facing the camera with the bat raised. In order: a white baseball streaks in from the right; in slow motion he steps forward and swings, and the bat meets the ball squarely in front of home plate with a bright impact flash and manga speed lines; the ball shoots back out to the right and high into the sky. He follows through, watches it fly with a huge grin, drops the bat and runs toward first base. Sound: a sharp metallic bat ping, a crowd gasp then a roar, upbeat brass music, no dialogue.
   Cute Japanese sports-anime style: clean cel-shaded 2D animation, bold ink outlines, bright colors, screentone shading, chibi-leaning kids with big sparkling eyes, manga speed lines, sunny sky with white clouds. One continuous shot, no cuts. Camera: flies right behind the white baseball as it soars up and away from a Little League field, always following it: first the green outfield grass and the visiting center fielder in a gray uniform and green cap pass far below, then the low green chain-link outfield fence, then the trees beyond, while the ball keeps climbing into the blue sky and finally becomes a tiny twinkling star, a classic anime home-run moment. Sound: wind rush, a rising crowd roar and cheering far below, the same upbeat brass music, no dialogue.
   Cute Japanese sports-anime style: clean cel-shaded 2D animation, bold ink outlines, bright colors, screentone shading, chibi-leaning kids with big sparkling eyes, manga speed lines, sunny sky with white clouds. One continuous shot, no cuts. Bottom of the last inning, two outs. Camera: side tracking shot in deep center field. A long fly ball arcs toward the low green chain-link outfield fence. Our center fielder, a cute player with curly brown hair under a navy cap with an orange tiger-head emblem, orange "Bellaire" jersey with a big number 7 on the back and a brown leather glove, sprints back to the fence, leaps, and catches the ball just above the top of the fence; the ball clearly lands in the glove and stays there. The fielder lands on the grass on the field side of the fence, holds up the glove to show the ball and grins. The fence, field and sky stay the same throughout. Sound: running footsteps on grass, a crowd gasp then a huge cheer, the same upbeat brass music, no dialogue.
   Cute Japanese sports-anime style: clean cel-shaded 2D animation, bold ink outlines, bright colors, screentone shading, chibi-leaning kids with big sparkling eyes, manga speed lines, sunny sky with white clouds. One continuous shot, no cuts. The game is over and the Tigers win. Camera: eye-level slow push-in at the pitcher's mound. The whole home team in orange "Bellaire" jerseys, white pants and navy caps with an orange tiger-head emblem runs in, cheering in a circle around our batter with short spiky black hair and the center fielder number 7 with curly brown hair, who share a big double high-five. A smiling coach in a navy polo laughs as a teammate tips a bucket of water over him. It ends on a happy group pose with caps raised; the art style stays the same throughout. Sound: cheering kids and parents, a splash and laughter, the brass music landing on a final triumphant note, no dialogue.
   ```

   Fill in the rest of the form:

   | Field | Value |
   |---|---|
   | Run title / Tags | `Little League · home run and the catch` / `Module 8, example` |
   | Seconds per shot / Takes per shot / Frame | `8 s` / `3` / `16:9 · 1280×720` |
   | Must not include | `brand or MLB logos, other real team names, injuries or rough collisions, captions or extra on-screen text` |
   | Visible label | `Made with AI` |
   | End card title / tagline | `TIGERS WIN!` / `One swing. One catch. Bellaire Little League.` |
   | Voiceover | leave empty (see the note below) |

   **Expect:** **Shots** reads `4 (one per line)`; the preview shows
   `12 video generations · 96 s video generated · ~9.7 min`.
2. **Start run** → **Approve & continue**. Takes take about 10 minutes, 2 at a time.
3. Open each take and **watch all 8 seconds**, then step through the action. A take is usable only if it would
   pass in a real game:
   - **Swing:** the ball reaches the bat *before* anything else touches it, the bat meets it in front of
     the plate, the ball leaves, and only then does the batter drop the bat and run to first.
   - **Over the fence:** the ball keeps moving the whole time (no freezing, no sudden size jumps, no loops)
     and clearly passes over the outfield fence.
   - **Catch:** the ball goes into the glove and stays there; the fielder stays on the field side of the fence.
   - **Celebration:** same orange and navy uniforms; nobody gets hurt; the style is still anime, not a
     Western TV cartoon.
4. **Reject** each failed take with a short note saying why, and **Regen** that shot. Expect to regenerate
   shots 1 and 2. In the reference run, 22 takes gave 4 keepers:

   | Shot | Takes | Kept | Failures seen |
   |---|---|---|---|
   | 1 · swing | 6 | 1 | ball flew before the swing; catcher's mitt first, then a second swing; pitcher beside home plate; ball hanging next to the batter |
   | 2 · over the fence | 10 | 1 (+1 backup) | ball fell in the infield; frozen ball; looping trail; ball size jump; batter running the wrong way |
   | 3 · catch | 3 | 1 | ball sailed past the glove; fielder ended up behind the fence |
   | 4 · celebration | 3 | 1 (+1 backup) | switched to a Western TV-cartoon style |

   The prompts above are the versions that worked. Shot 1 is the second version: the first filmed the swing
   from center field with the catcher in frame, and none of its 3 takes passed; framing the batter alone fixed
   it. Shot 2 is the fourth version: a high view from behind home plate (3 takes), a view behind the center
   fielder (3), and a fixed camera with a twinkling-star exit (2) all failed before the camera *chasing* the
   ball worked. The lesson for class: the more cause-and-effect physics a shot needs, the more takes it costs.
   Simplify the shot instead of adding words.
5. Keep one take per shot → **Approve & continue**. **Expect:** a **Final cut** of 32.9 s: four takes joined
   by 0.5 s crossfades, *Made with AI* in the corner, and the *TIGERS WIN!* end card for the last 3 s. The
   checks list the label and *End card: TIGERS WIN!*.
6. **Download MP4**. To copy it to the server: **Export bundle** on the Mac, then **Import bundle…** on the
   server (as in VD2).

**Voiceover note:** a play-by-play would be fun, but in two test reads of nearly the same script MAI-Voice
took 24.8 s for 38 words and 21.6 s for 41 words. The pacing changes from read to read, so calls such as
*what a catch!* can drift into the wrong shot. The kept takes already carry Sora's own bat ping, crowd and
music, which stay in sync with the action.

Variations:
- **Phone version for family:** **Frame** `9:16 · 720×1280`, same lines.
- **Let the text model write it:** **Shot prompts**: *Text model writes the shot list*, **Shots** `4`, brief:
  `A cute Japanese sports-anime highlight for a Bellaire Little League team, the Tigers: a young batter hits
  the go-ahead home run in the last inning, the center fielder makes a leaping catch at the fence for the
  final out, and the team celebrates.` Do its shots avoid the failure patterns in the table? Tick both runs in
  **Run history** → **Compare 2 runs** to watch the cuts side by side.

**Pass if:** every kept take passes the step 3 checks (watched frame by frame, not just at full speed), the
four shots read as one story in one style, the label and end card are burned in, and nothing in the prompts
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
