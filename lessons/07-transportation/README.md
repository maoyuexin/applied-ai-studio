# 07 · AI in Transportation: Machines That Learn by Reward

Transportation already runs on AI: routing, signal timing, warehouse robots, driver assistance and
robotaxis. The lesson tours where it works today and how a self-driving car's sense, predict,
decide and act loop maps onto the six SAE automation levels. It then teaches **reinforcement
learning**, a model that learns from the points it earns rather than from recorded answers, through
three cases that use the same recipe:

- **Warehouse robot:** learn a route to the packing station from points alone, and retrain when a
  pallet blocks it.
- **Traffic light:** keep green or switch, inside timing rules it cannot break, tested against a
  fixed timer and a simple rule on the same cars.
- **Ride-hail driver:** on a summary of 19.7 million real New York trips, learn where to wait or
  drive empty, then ask who a driver-earnings reward leaves behind.

[Open this lesson in the browser](https://maoyuexin.github.io/applied-ai-studio/#07-transportation)

| Material | Format | Link |
|---|---|---|
| Slides | PDF | [M7_Deck_AI_in_Transportation.pdf](M7_Deck_AI_in_Transportation.pdf) |
| Train a warehouse robot | Interactive lesson and lab | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/07-transportation/M7_Robot_Training_Lab.html) |
| Warehouse robot notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/07-transportation/M7_Notebook_Warehouse_Robot.html) · [notebook source](../../notebooks/transportation-rl/01_warehouse_robot.ipynb) |
| Train a traffic light | Interactive lesson and lab | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/07-transportation/M7_Traffic_Signal_Lab.html) |
| Traffic light notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/07-transportation/M7_Notebook_Traffic_Signal.html) · [notebook source](../../notebooks/transportation-rl/02_traffic_signal.ipynb) |
| Train a ride-hail driver | Interactive lesson and lab | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/07-transportation/M7_Ride_Hail_Lab.html) |
| Ride-hail notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/07-transportation/M7_Notebook_Ride_Hail_Dispatch.html) · [notebook source](../../notebooks/transportation-rl/03_ride_hail_dispatch.ipynb) |

The slide links to lessons and notebooks work when the PDF is opened from the lesson site, because
the site publishes each file under the name the slides use. Lesson links that end in `#step-3`
open that step directly.

Each interactive page has a guided lesson (seven or eight steps) and a lab where the model trains
continuously while its scores, test results and an explanation of each decision update beside it.

## In the Studio app

| Route | What it shows |
|---|---|
| `/warehouse-robot` | Train a warehouse robot (runs in the browser) |
| `/traffic-signal` | Train a traffic light (runs in the browser) |
| `/ride-hail` | Train a ride-hail driver (runs in the browser) |
| `/workflow?courseCase=transportation-fleet-routing` | One day of fleet dispatch: travel prediction, route optimization, safety checks and dispatcher authority |

Data and limits: [notebooks/transportation-rl](../../notebooks/transportation-rl/README.md).
