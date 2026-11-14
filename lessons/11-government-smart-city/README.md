# 11 · AI in Government and the Smart City

A smart city senses, predicts, decides, acts, and tells residents what it did. The lesson explains how that works
today (five layers from sensor to street, real systems in Pittsburgh, New York, Houston and Chula Vista, and what is
new since 2024), then runs two Houston cases on the same storm data: one predictive, one generative.

Key question: **when the city's AI sees something, who decides what happens next, and how does the public know it
was right?** Both cases are scored with the same four tests: does it work, is it fair, can the public see it, and
can people challenge it?

- **Case 1 · Flood Watch (predictive AI):** real USGS gauges on Brays Bayou from Hurricane Harvey (2017) and Beryl
  (2024). A gradient-boosting model forecasts the water level two hours ahead and is compared with two baselines
  ("stays the same", "keeps rising"). Students set the alert line, switch upstream gauges off, and open a false
  alarm: the threshold is a policy choice, and a gauge that goes dark is the failure that matters most.
- **Case 2 · Storm Desk (generative AI):** the same readings become a 160-character public alert and a 311 answer
  in four languages. Five automatic checks run on every draft (facts match the data, nothing invented,
  back-translation agrees, reading level, an "AI-assisted" line), and students approve, edit or reject each one
  before seeing what the checks and a human reviewer found.
- **Can the public trust it?** Cameras that can count cars or track people, explanations a resident can check,
  appeals, and the rules (OMB M-25-21 and M-25-22, Texas TRAIGA and SB 1964), plus buying and running the system.

| Material | Format | Where |
|---|---|---|
| Slides | PDF | [M11_Deck_AI_in_Government_Smart_City.pdf](M11_Deck_AI_in_Government_Smart_City.pdf) |
| Flood Watch | Guided lesson and "replay any storm" | [file](../../notebooks/smart-city/flood-watch.html) |
| Storm Desk | Sign-off desk and "what we found" | [file](../../notebooks/smart-city/storm-desk.html) |
| Synthetic residents | A recorded experiment: can AI residents answer a city survey for real ones? | [file](../../notebooks/smart-city/synthetic-residents.html) |
| City Operations | Studio console | `/city-operations` |

## In the Studio app

| Route | What it shows |
|---|---|
| `/city-operations` | A flood operations console under Industry Workflows: gauge replay with the 2-hour forecast and alert line, a camera wall of vision-model readings, the alert sign-off desk in four languages, and an activity log. It replays recorded data, so no model is needed in class |
| `/design-studio` | The **Inspect** pipeline (ask vision models questions about images and check them against your labels) and the **Alerts** pipeline (draft alerts from facts, check them, sign off) that produced the console's recordings; needs your Foundry resource ([docs](../../docs/design-studio/README.md)) |

Data: USGS water-level readings are public domain. The alert drafts are recorded model output, labeled as teaching
drafts; none was sent to the public. Page notes: [notebooks/smart-city](../../notebooks/smart-city/README.md).
