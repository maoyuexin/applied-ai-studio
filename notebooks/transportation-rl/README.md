# Learning by Reward: Three Transportation Cases

Transportation lesson. Three reinforcement-learning cases, each with a guided browser lesson, a free
training lab, and an executed notebook that reproduces every number the lesson shows:

| Case | Question | Data |
|---|---|---|
| 1 · Warehouse robot | Can a robot learn a route to the packing station from points alone? | Invented floor |
| 2 · Traffic light | When should a signal keep green or switch, inside timing rules it cannot break? | Simulated arrivals |
| 3 · Ride-hail driver | Where should an empty car wait, and who does a driver-earnings reward leave behind? | Real NYC trip summary |

All three use the same recipe: a **state**, a few **actions**, **points** after each action, and a
table of scores that moves toward what actually happened. Training is seeded, so every run gives the
same numbers.

## Files

| File | What it is |
|---|---|
| `backup/warehouse-robot.html`, `backup/traffic-signal.html`, `backup/ride-hail.html` | Single-file browser lessons (guided steps plus a lab). Nothing loads from the network. |
| `01_warehouse_robot.ipynb`, `02_traffic_signal.ipynb`, `03_ride_hail_dispatch.ipynb` | Executed notebooks: the same engines in Python, with checks against the lesson's numbers. |
| `backup/01_warehouse_robot.html`, `backup/02_traffic_signal.html`, `backup/03_ride_hail_dispatch.html` | Offline HTML reports of those notebooks. |
| `artifacts/*_lab_facts.json` | The numbers each browser lesson shows. Each notebook checks it reproduces them. |
| `artifacts/nyc_borough_summary.json` | Borough-level summary of the NYC trip records (case 3). No trip rows. |

The lesson site publishes these under the names the slides link to (`M7_Robot_Training_Lab.html`,
`M7_Notebook_Warehouse_Robot.html`, and so on); see [`lessons/lessons.json`](../../lessons/lessons.json).

## Results the notebooks reproduce

- **Robot.** After 20 practice trips the test drive from A3 takes the shortest route: 4 moves, the
  same as a map search. When a pallet blocks it, the old table gets stuck; 10 more trips find an
  8-move detour. On a 52-square floor every square has a shortest route after 130 trips.
- **Traffic light.** On five fixed test hours the average wait is 20.7 s with the best fixed timer,
  13.8 s with a serve-the-longer-line rule and 12.6 s with the learned light (30 practice hours).
  Counting only Main St cars raises the average wait to 41.6 s; without the timing rules as well,
  Side St waits up to 59 minutes.
- **Ride-hail.** Over 2,000 test shifts the learned where-to-wait rule earns $181.40 a shift, the
  same as the best of all 3,125 possible rules, against $134.95 for never moving and $176.37 for
  always heading to Manhattan. A $25 Bronx pickup bonus changes the rule.

## Data and assumptions

- **Robot:** an invented floor; +20 points for a delivery, −1 per move.
- **Traffic light:** simulated arrivals (about 4.8 cars a minute on Main St, 1.8 on Side St), 5-second
  ticks, −1 point per waiting car per tick. Yellow, all-red, a 10-second minimum green and a
  60-second maximum green (when a car waits on red) are rules outside the learner.
- **Ride-hail:** [NYC TLC High Volume For-Hire Vehicle trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page),
  January 2024 (19,663,930 trips; 18,799,627 kept with pickup and drop-off in the five boroughs and
  positive time, miles and pay), reduced to borough totals, average driver pay and median trip times
  and miles. Two named assumptions: the chance of a request while waiting 15 minutes (80% in
  Manhattan, scaled by pickups per hour elsewhere) and $0.50 a mile for driving empty.

One learner, replayed or simulated demand: these are teaching models, not forecasts of how real
riders, drivers or traffic would respond, and not safety evidence for a real facility, signal or fleet.

## Rerun a notebook

Open the repository in Codespaces (or use the Studio's `.venv`) and run a notebook from this folder;
it reads `artifacts/` beside it. Each notebook ends by checking its results against the lesson's
facts file.

## Update the files

The lessons, notebooks and facts are built together in the course materials folder. Copy them in
byte for byte, then check:

```sh
TRANSPORT_LABS_SOURCE=/path/to/module-folder node scripts/sync-transportation-labs.mjs
TRANSPORT_LABS_SOURCE=/path/to/module-folder node scripts/sync-transportation-labs.mjs --check
```

The script refuses pages that are incomplete, load a remote resource or miss a lesson step, and
notebooks that are not fully executed or contain an error.
