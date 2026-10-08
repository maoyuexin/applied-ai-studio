# Design Studio: end-to-end test cases

Fifteen manual tests, run in the browser exactly as a user would: three per pipeline for article, voice and
image, and six for video. Each one checks a feature you may show in class: review steps, revisions, automatic
checks, labels, run history. A3, V3, I3, VD5 and VD6 (added Oct 8) were run end to end on the Mac first; their
"Expect" lines and reference runs come from those runs.
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
| A3 | Article (two sources, explainer) | 4 min | 4 text | Mac + server |
| V1 | Voice | 4 min | 1 text, ~14 voice | Mac + server |
| V2 | Voice | 3 min | 1 text, ~10 voice | Mac |
| V3 | Voice (interview, delivery styles) | 4 min | 1 text, ~16 voice | Mac + server |
| I1 | Image | 5 min | 2 text, 4 images | Mac + server |
| I2 | Image | 2 min | 1–2 images | Mac |
| I3 | Image (character sheet, no reference) | 4 min | 2 text, 3 images | Mac + server |
| VD1 | Video | 12 min | 1–2 text, 1–2 images, 5–6 Sora takes | Mac |
| VD2 | Video | 6 min | 1 text, 1 Sora take | Mac → server |
| VD3 | Video (prompt only) | 5 min | 2 Sora takes, no text model | Mac + server |
| VD4 | Video (prompt only, 2-shot story) | 15 min | 6 Sora takes, plus a remix or two | Mac + server |
| VD5 | Video (keyframes from your own character, multi-step) | 15 min | 1 text, 3–4 images, 6–7 Sora takes | Mac |
| VD6 | Video (people, text → video, Japanese dialogue) | 10 min | 1 text, 6 Sora takes | Mac + server |

Sora takes are the only expensive calls (daily cap: **Settings → Daily caps**, 100 since Oct 6). Run the video tests
before **Oct 15**, when Sora 2 retires in Foundry.
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

### A3 · Explainer from two sources: a plan is not a fact *(Mac + server)*

**Shows:** more than one source, a different format and audience, and the fact check catching a **subtle**
error: turning a scheduled event into a confirmed one. It's the classic newsroom mistake when a prelaunch
advisory and a launch-day report disagree in tense.

**Sources** (both in the course folder `Module_08_AI_Media_Content_Creative/artifacts/case1/sources/`):

| # | Title | Published | File |
|---|---|---|---|
| 1 | NASA Sets Crew-13 Launch, Docking Coverage | 2026-09-29 | `nasa_04_nasa-sets-crew-13-launch-docking-coverage.txt` |
| 2 | NASA's SpaceX Crew-13 Launches to International Space Station | 2026-10-01 | `nasa_03_nasas-spacex-crew-13-launches-to-international-space-station.txt` |

1. **New article run**. **Format** *Explainer*, **Length** *about 250 words* (or 200), **Audience**
   `first-year college students`, **Tone** `clear, friendly, specific`. **Fact check** on.
   Brief: `Explain what NASA's SpaceX Crew-13 mission is: who is on board, when and where it launched, what it
   docks to, and two kinds of research the crew will do. Use both sources and cite them.`
2. **+ Paste a source** twice: paste each file's text, its title, URL (`https://www.nasa.gov/news-release/…`)
   and **Published** date. The date matters: it lets the checker resolve "Thursday" and "this year".
   **Start run**.
3. **Expect** (~10 s): an outline of 5–7 points where each point cites `[1]`, `[2]` or both. In the reference
   run the launch time cites only `[2]` (the launch-day report) and the crew list cites both.
   **Approve & continue**.
4. **Expect v1** (~30 s): about 210 words with inline `[1][2]` tags and `Claims: 22 supported · 0 partly ·
   0 unsupported`. Read the docking sentence: the reference draft wrote *"Dragon was scheduled to dock … at
   approximately 7 p.m. That was the planned arrival—not a confirmed docking in these sources."* The model
   kept the tense honest by itself.
5. Plant the classic error: **Edit it myself**, add at the end
   `Crew-13 docked with the station at 7 p.m. on Oct. 1, the fastest launch-to-docking in station history.`
   → **Save as new version**.
6. **Expect v2** (~25 s): `1 unsupported` and `1 partly`. The reference check said:
   - **unsupported** *"Crew-13 docked with the station at 7 p.m. on Oct. 1"*: *"converts an approximate future
     target into a confirmed event."*
   - **partly** *"fastest launch-to-docking in station history"*: *"The record is predicted, not confirmed, and
     is limited to U.S. spacecraft."* The source says "the fastest **by a U.S. spacecraft**"; the planted
     sentence dropped that qualifier.
7. Click **v1** → **Approve & continue**. **Expect:** *Approved: v1*, the label *AI-assisted draft, reviewed
   by an editor.*, `214 words (target 200)`, and **Download .md** lists both sources.

**Pass if:** the checker separated "planned" from "happened" and caught the dropped "U.S." qualifier, and the
approved text is v1. **Reference run:** *Crew-13 explainer · two sources* (`run_2026-10-08_141631_5e8f`).

**Ask the class:** both planted claims are *almost* right. Which one would a reader be more likely to repeat?

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

### V3 · Interview with delivery styles: what listen-back can't hear *(Mac + server)*

**Shows:** the interview format, two different voices, choosing a delivery **style** for one line and
re-recording only that line, and the limit of the listen-back check (it checks words, not tone).

1. **New voice run**. **Format** *Interview*, **Target length** 45 s, **Language** English (US).
   **Speakers:** `Olivia` with voice *Olivia* and `Grant` with voice *Grant* (Olivia has delivery styles;
   Grant has none, so his style menu reads *no styles*).
2. Brief: `A short interview for a college AI class. The host asks how an AI video ad keeps the same car in
   every shot. The guest explains it in plain words: a design sheet, a keyframe made from it, the video model
   starting from that keyframe, and why a person still watches every take. Curious host, calm expert.`
3. **Start run**. **Expect** (~10 s): about 7 short lines alternating Olivia (questions) and Grant (answers),
   ending with Olivia's *These voices are AI-generated.* The reference script explained keyframes correctly:
   *"We make a keyframe from that sheet: one still image for a shot. The video model starts from that image
   and adds motion."* It doubles as a review of slide 25. **Approve & continue**.
4. **Expect** (~10 s): every line *✓ matches the script*. Look at the *heard* text: line 3 came back as
   *"How does that become?Video."* and line 4 heard *"one still image"* as *"1 still image"*, yet both count as
   matches. Listen-back normalizes punctuation and numbers.
5. On Olivia's first line press **Edit**, set **Style** to `whispering` → **Re-record**. **Expect:** only that
   line is re-recorded (`line 1.2`, now kept); the take picker still offers `line 1.1`. In the reference run the
   whispered take ran 6.8 s instead of 4.2 s and **still** showed *✓ matches the script*.
6. Play both takes of line 1. Ask the class which one fits a classroom intro. The checker can't answer that;
   only a person can. Pick the one you prefer in the take picker → **Approve & continue**.
7. **Expect:** a mix of about 38 s, *Loudness normalized to -16 LUFS*, *Listen-back: 0 word difference(s)
   across 7 checked lines*, and *Spoken AI disclosure in the last line*.

**Pass if:** the style change re-recorded one line only, the checker passed both deliveries, and the final
choice was made by ear. **Reference run:** *Keyframes explained · interview* (`run_2026-10-08_141820_3036`).

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

### I3 · Character sheet from words, edited once: the start of VD5 *(Mac + server)*

**Shows:** making your **own** reference with no reference image (text → image), the prompt gate, choosing
between candidates, one targeted edit that must keep everything else identical, and handing the result to a
video run. It's the image half of the multi-step video test VD5.

1. **New image run**. **Use case** *Product hero / key art* (16:9), **Candidates** 2, prompt helper on, no
   reference images. **Must not include** `real brands or logos, agency patches or flags, text, people`.
   Brief (based on OpenAI's Sora 2 "astronaut golden retriever" showcase prompt):
   `Character design sheet for an astronaut golden retriever named Sora: full body, three-quarter view,
   standing on a plain light-gray studio background. A retro-futuristic white spacesuit with orange trim, a
   clear round bubble helmet, and a tiny silver jetpack on his back. Fluffy golden fur clearly visible,
   friendly brown eyes, photoreal, soft even studio light, 35mm film look. This image will be the reference
   for a video, so show the whole dog clearly.`
2. **Start run**. **Expect:** gpt-6-astra's prompt for review (it added layout: *"slightly right of center …
   generous clean negative space on the left"*). **Approve & continue**.
3. **Expect** (~30 s): `c1`, `c2`, both *Content Credentials: present, valid (Microsoft Corporation)*. Check
   the whole dog is in frame (head to boots, tail visible). **Keep** one → **Approve & continue**.
4. In **Revise**: note `Add two small blue jet flames under the jetpack and a mission patch with a paw print
   on the chest; keep the dog and suit identical` → **Write the prompt**. **Expect:** a proposed edit prompt
   that starts *"Edit Image 1, preserving the identical golden retriever, pose, proportions …"* and adds
   *"without lettering or flags"* from your rules. **Make v1**.
5. **Expect** (~22 s): `v1` under the candidate. Compare them side by side: only the patch and the two blue
   flames are new; the face, pose, suit stripes and boots are unchanged. **Keep** v1.
6. **Finish** with the label `Made with AI` → **Approve & continue**. **Expect:** *Original: Content
   Credentials: present, valid* and *Labeled copy: Content Credentials: none found*.
7. **Use in a video run**. **Expect:** a New video run with v1 attached as the **Subject** reference. Continue
   with VD5.

**Pass if:** the edit changed only what the note asked for, and the kept version opened in a video run as the
subject. **Reference run:** *Sora the space dog · character sheet* (`run_2026-10-08_141907_17ce`, kept `v1`).

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

**Shows:** a two-shot story written as your own prompts in the style of OpenAI's own anime showcase prompt;
several camera shots inside one Sora clip; checking sports action frame by frame; fixing one detail with
**Remix**; an end card the app draws itself; checking a kids' video before you share it.

**Reference run:** *Little League · sakuga version* (Oct 6, `run_2026-10-06_223801_df14`), a fork of the
earlier *Little League · home run and the catch*. Tick both in **Run history** → **Compare 2 runs** to see what
changed.

**Why the prompts look like this:** the first version (four 8 s shots, 150–190 words each, "chibi, cel-shaded,
screentone") took 22 takes to get 4 usable ones and still looked like cheap TV animation. OpenAI's official
Sora 2 anime prompt (*"in the style of a japanese anime … film-caliber sakuga japanese animation, close-up
shots … beautiful fluid hand-drawn animation"*) shows a better pattern:
- **Quality words, not technique words:** *film-caliber sakuga*, *beautiful fluid hand-drawn animation*.
- **Mood and stakes first:** a packed small-town ballpark, a tied last inning, everything on one batter.
- **Several shots per clip:** a close-up, a side view, a wide shot. Sora cuts between them inside one 12 s
  clip and keeps the characters the same, so two clips leave only one seam where the style can change.
- **Keep the hard physics simple:** the swing is a side view with *only the batter in frame*, so no catcher
  can "catch first".

The style is described, not named after a series or artist: naming a copyrighted work invites a filter block
and is the IP question Module 8 asks students to think about.

**Why the drawing is not attached:** every shot shows people, and Sora rejects input images with faces, so
shots with people go to Sora as text → video. Expect an anime player in that uniform, not a particular child.

**Privacy:** keep real children's names and photos out of the prompts. A player's name can go on the **End
card title**: the app draws the card itself, so the name never goes to Sora.

Before you start: **Settings → Daily caps → Video takes** needs **6** free, plus a few for remixes.

1. **New video run** → **Shot prompts**: *Off: one shot per line, sent to Sora as written*. Paste these two
   lines: the home run, then the catch and the win.

   ```text
   In the style of a Japanese anime, a hopeful scene at a small-town Little League ballpark on a golden summer evening: the bleachers are packed, the score is tied in the last inning, and everything rests on one young batter. Film-caliber sakuga Japanese animation, beautiful fluid hand-drawn animation, warm sunset light and long shadows. Close-up of the batter's determined eyes under a navy helmet with an orange tiger emblem, his orange "Bellaire" jersey catching the breeze. Side view with only the batter in frame: the pitch arrives and, in one fluid sakuga swing, the bat meets the ball in front of the plate. Wide shot: the ball soars into the sunset sky and clears the outfield fence. He drops the bat and runs toward first base as the crowd rises. Sound: the crack of the bat, the crowd erupting, a swelling orchestral anime score, no dialogue.
   In the style of a Japanese anime, the bottom of the last inning at the same small-town Little League ballpark under a violet dusk sky, two outs, the whole crowd holding its breath. Film-caliber sakuga Japanese animation, beautiful fluid hand-drawn animation. A long fly ball arcs toward deep center field. The center fielder, a young player with curly brown hair, a navy cap with an orange tiger emblem and an orange "Bellaire" jersey with number 7, sprints back to the chain-link fence and leaps; in a breathtaking slow-motion moment the ball drops into the glove. The fielder lands on the field side of the fence and raises the glove with the ball inside. Then the whole team in orange jerseys pours onto the field, the batter with short spiky black hair runs in to hug number 7, and navy caps fly into the sky as the stadium lights flicker on. Sound: a gasp, then the crowd roaring, the anime score swelling to a triumphant finish, no dialogue.
   ```

   | Field | Value |
   |---|---|
   | Run title / Tags | `Little League · sakuga version` / `Module 8, example` |
   | Seconds per shot / Takes per shot / Frame | `12 s` / `3` / `16:9 · 1280×720` |
   | Must not include | `brand or MLB logos, other real team names, injuries or rough collisions, captions or extra on-screen text` |
   | Visible label | `Made with AI` |
   | End card title / tagline | `TIGERS WIN!` / `One swing. One catch. Bellaire Little League.` |
   | Voiceover | leave empty (see the note below) |

   **Expect:** **Shots** reads `2 (one per line)`; the preview shows
   `6 video generations · 72 s video generated · ~7 min`.
2. **Start run** → **Approve & continue**. Six 12 s takes take about 9 minutes, 2 at a time.
3. Watch each take, then step through the action. Usable only if it would pass in a real game:
   - **Home run:** the ball reaches the bat before anything else touches it, the bat meets it in front of
     the plate, the ball is seen leaving the park, and only then does the batter drop the bat and run.
   - **Catch:** the ball is seen going into the glove; the fielder stays on the field side of the fence and
     wears **one** glove.
   - **Teams:** in shot 2 the Tigers are fielding, so the batter and catcher must not wear orange.
   - **Celebration:** same orange-and-navy uniforms; nobody gets hurt.
4. For a take that is right except one detail, **Remix** with only that change. In the reference run, s2_t2 had
   the clearest catch but an orange-uniformed batter; the remix
   `The batter and catcher at the start wear gray visiting-team uniforms with green caps instead of orange;
   everything else stays the same.` fixed the uniforms. A remix re-renders the whole clip, though, so check it
   again: that one briefly gave the fielder two gloves.
5. Keep one take per shot → **Approve & continue**. **Expect:** a **Final cut** of 25.9 s: two takes joined by
   a 0.5 s crossfade, *Made with AI* in the corner, and the *TIGERS WIN!* end card for the last 3 s.
6. **Download MP4**. To copy it to the server: **Export bundle** on the Mac, then **Import bundle…** on the
   server (as in VD2).

**Voiceover note:** a play-by-play would be fun, but in two test reads of nearly the same script MAI-Voice
took 24.8 s for 38 words and 21.6 s for 41 words. The pacing changes from read to read, so calls can drift
into the wrong shot. The takes already carry Sora's own bat crack, crowd and score, in sync with the action.

Variations:
- **Phone version for family:** **Frame** `9:16 · 720×1280`, same lines.
- **Name the visiting team's colors up front:** in line 2, replace `A long fly ball arcs toward deep center
  field.` with `A visiting batter in a gray uniform and green helmet lifts a long fly ball toward deep center
  field.` Take s2_t6 in the reference run used this wording; watch it to judge whether it helps.

**Pass if:** every kept take passes the step 3 checks (watched frame by frame, not only at full speed), the two
clips read as one story in one style, the label and end card are burned in, and nothing in the prompts
identifies a real child.

**IP note for class:** "Little League" is a trademark, and team logos belong to their owners. A family clip is
fine; before posting publicly or using it commercially, ask the league. The prompts ask for a generic tiger
emblem and exclude real logos for that reason.

### VD5 · Space pup: keyframes from your own character, step by step *(Mac)*

**Shows:** the full multi-step route, the same one the SOLENNE car ad uses: **your character sheet (I3) →
text model writes the shot list → MAI-Image keyframes → you review → Sora takes start from those keyframes →
you review → assembled cut**. It also shows the keyframe's limit: Sora starts **from** the picture, so if
the picture shows the dog standing, the take tends to keep him standing.

Based on OpenAI's Sora 2 showcase prompt: *"an astronaut golden retriever named Sora levitates around an
intergalactic pup-themed space station with a tiny jet back that propels him … the doors opening to let him
in … inside the space station, many tennis balls are flying around in zero gravity. the dog's astronaut helmet
opens up so he can grab one. 35mm film …"* OpenAI made it as one prompt; here it is planned as three shots so
each step can be reviewed.

Before you start: finish **I3**, or use its reference run's kept `v1` as the reference image.

1. From I3's finished image press **Use in a video run** (or **New video run** and add the character sheet
   under **Reference images** as **Subject**). **Shot prompts**: *Text model writes the shot list*.
   **Shots** 3, **Seconds per shot** 8 s, **Takes per shot** 2. **Must not include**
   `real brands or logos, agency patches or flags, readable text, people`. **End card title** `SPACE PUP`,
   **tagline** `One tennis ball at a time.`
   Brief:

   ```text
   A 24-second fun teaser in three shots, based on OpenAI's Sora 2 showcase prompt: an astronaut golden retriever named Sora levitates around an intergalactic pup-themed space station with a tiny jet pack that propels him. Gorgeous specular lighting and comets fly through the sky; retro-future astro-themed music plays. Light glimmers off the dog's eyes. The dog first propels toward the space station and its doors open to let him in. Then, inside the station, many tennis balls float in zero gravity; the dog's helmet opens so he can grab one. 35mm film; the fur detail is clearly visible and the comet light shimmers on it. The dog must look exactly like the reference character sheet in every shot: white suit with orange trim, clear bubble helmet, paw-print patch, tiny silver jet pack with blue flames.
   ```

   **Expect:** the preview shows `6 video generations · 48 s video generated · ~4.8 min` and 3 keyframes.
2. **Start run**. **Expect** (~25 s): three shots, **all** *keyframe → video* (the dog is not a person, so
   every shot can start from a picture). Reference shot list: *Incoming Good Boy* (approach the bone-shaped
   door), *Welcome to Fetch Orbit* (float into a playroom full of tennis balls), *One Small Fetch* (helmet
   hinged back, catch a ball). Each shot has a **video prompt** (what moves) and a **keyframe prompt** (the
   opening picture). Read both aloud: this is the step students usually can't see.
   **Approve & continue**.
3. **Keyframes** (~25 s each). **Expect:** three stills of the **same** dog (same suit stripes, paw patch,
   blue flames) in three places, each *Content Credentials: present, valid*. Check each against the
   character sheet.
4. Fix one keyframe with a note. In the reference run shot 3's keyframe showed him standing with the helmet
   **closed**, which contradicts the shot. On shot 3 type
   `the clear bubble helmet is open and tilted back behind his head so his face and nose are uncovered; he floats in mid-air with paws reaching for one tennis ball just in front of his nose`
   → **New keyframe**. **Expect** (~22 s): `s3_k2`, floating, helmet tipped back, ball in reach, kept
   automatically. **Approve & continue**.
5. **Takes** (~6 min). Open each take; frame 1 is the keyframe, and everything after it is Sora's. In the
   reference run:
   - **Shot 2 worked:** he tumbles through the doorway into zero gravity among the tennis balls and steadies.
     The other take had him **standing** on the floor in zero gravity: rejected.
   - **Shot 3 worked:** starting from the fixed keyframe, he grabs the ball **in his mouth**, does a weightless
     somersault and ends facing the camera. The take whose helmet stayed shut couldn't grab it.
   - **Shot 1 failed both times:** the keyframe showed him **standing** on the station's hull, and Sora kept
     him standing; he never flew to the door, and it never opened. A **Remix**
     (`He lifts off and jets forward toward the bone-shaped door with blue flames; the door slides open as he arrives.`)
     added a little motion but not the flight.
6. **The fix for shot 1 (the lesson):** change the **picture**, not the words. Go back to **Keyframes**, type
   `he is already flying toward the open bone-shaped door, body horizontal, blue flames trailing, the door sliding open`
   → **New keyframe**, then **Another take**. (The reference run kept the remix only as a placeholder, so this
   step is yours to try.)
7. Keep one take per shot → **Approve & continue**. **Expect:** a final cut of about 25 s with *Made with AI*
   and the *SPACE PUP* end card.

**Pass if:** the same dog appears in all three shots (the keyframes did their job), at least two shots show the
action the prompt asked for, and you can explain shot 1's failure: a keyframe fixes frame 1, so a standing
picture tends to give a standing take. **Reference run:** *Space pup · keyframes from a character sheet*
(`run_2026-10-08_142156_7f6f`). Every verdict note starts with *Copilot review:*.

### VD6 · Festival fireworks: two people, three shots, Japanese dialogue *(Mac + server)*

**Shows:** the other route, **text → video for people**. Sora rejects input images with faces, so there are
no keyframes, and the shot list has to keep two characters consistent with **words alone**. It also shows
Sora generating spoken dialogue in another language, which the app can check with speech-to-text.

Based on OpenAI's Sora 2 showcase prompt: *"in the style of a japanese anime, a melancholy scene under the
fireworks of a night sky. the world is so happy, but not the two star-crossed protagonists of this gorgeous
japanese town in the middle of a festival. film-caliber sakuga japanese animation, close-up shots of the
characters having a conversation in japanese, beautiful fluid hand-drawn animation."*

1. **New video run**, no reference images. **Shot prompts**: *Text model writes the shot list*. **Shots** 3,
   **Seconds** 8 s, **Takes per shot** 2. **Must not include**
   `real people, real brands or logos, readable text, subtitles`. Leave the end card empty. Brief:

   ```text
   A 24-second three-shot anime scene based on OpenAI's Sora 2 showcase prompt: in the style of a Japanese anime, a melancholy scene under the fireworks of a night sky. The world is so happy, but not the two star-crossed protagonists of this gorgeous Japanese town in the middle of a festival. Film-caliber sakuga Japanese animation, close-up shots of the characters having a conversation in Japanese, beautiful fluid hand-drawn animation. Shot 1 establishes the festival town and the two of them; shot 2 is their quiet conversation in close-ups; shot 3 ends the scene as they part under the last fireworks. The two must look the same in every shot: describe their faces, hair and festival clothes the same way each time.
   ```

   **Expect:** `6 video generations · 48 s` and **0 keyframes**.
2. **Start run**. **Expect** (~20 s): three shots, all *text → video (people)*. The text model named the two
   (Aiko and Ren in the reference) and repeated **the same description word for word in every shot**:
   *"Aiko is a young adult woman with an oval face, brown eyes, chin-length black bob, red hairpin, indigo yukata
   with white cranes, and crimson obi. Ren is … tousled dark-brown hair, charcoal yukata, and slate obi."* That
   repetition is the only thing holding the characters together. Shot 2 includes the actual Japanese lines:
   「もう、行かなきゃ。」 / 「わかってる。」 ("I have to go now." / "I know.").
   **Approve & continue**. **Expect:** keyframes are skipped.
3. **Takes** (~6 min). Review for **character consistency** across shots. In the reference run:
   - Shot 1: one take showed both characters as described; the other was a wide crane shot where they were tiny
     silhouettes: rejected, since it never establishes who they are.
   - Shot 2: both takes **spoke the two Japanese lines**. Speech-to-text (ja-JP) heard exactly
     *もう、行かなきゃ。わかってる。* in both. But one take gave her **brown hair and no hairpin**, which drifts
     from shot 1, so the take with the red hairpin and tears was kept.
   - Shot 3: one take had them walk away **together** (wrong story); the kept one has their fingertips part
     and her walk away alone as the last fireworks fade.
4. Keep one per shot → **Approve & continue**. **Expect:** a 23 s cut with *Made with AI* and no end card.

**Pass if:** the kept takes show the same two characters (bob and red hairpin, crane yukata; dark yukata) in all
three shots, shot 2 speaks the Japanese lines, and the rejections name the drift. **Reference run:** *Festival
fireworks · anime scene in three shots* (`run_2026-10-08_143205_cc50`).

**Compare with VD5 in class:** VD5's dog stayed identical because every shot **started from the same
picture**. VD6's people drifted (hair color in shot 2) because they had only words. Same model, two routes,
and the car ad uses both: keyframes for the car, words for the family.

**IP note:** the prompts describe a style ("film-caliber sakuga Japanese animation") and never name a studio,
series or artist.

---

## Results log

| Test | Mac | Server | Notes |
|---|---|---|---|
| A1 | ☐ | ☐ | |
| A2 | ☐ | — | |
| A3 | ☐ | ☐ | |
| V1 | ☐ | ☐ | |
| V2 | ☐ | — | |
| V3 | ☐ | ☐ | |
| I1 | ☐ | ☐ | |
| I2 | ☐ | — | |
| I3 | ☐ | ☐ | |
| VD1 | ☐ | — | |
| VD2 | ☐ | ☐ (import) | |
| VD3 | ☐ | ☐ | |
| VD4 | ☐ | ☐ | |
| VD5 | ☐ | — | |
| VD6 | ☐ | ☐ | |

Clean up afterwards: delete test runs you don't want in class from **Run history** (trash icon). Keep the
ones you want to show; they also work as recorded examples if the network fails in class.
