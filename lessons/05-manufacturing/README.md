# 05 · AI in Manufacturing and Industrial Operations

When the model is wrong, someone is under the machine. The lesson follows equipment data from
sensors and controllers to a continuous stream, then detects abnormal compressor hours with
**anomaly detection** on real metro-train compressor telemetry (MetroPT-3). It asks whether each alert helps a
person (alert fatigue and drift) and why safety authority stays with people.

[Open this lesson in the browser](https://maoyuexin.github.io/applied-ai-studio/#05-manufacturing)

| Material | Format | Link |
|---|---|---|
| Slides | PDF | [M5_Deck_AI_in_Manufacturing.pdf](M5_Deck_AI_in_Manufacturing.pdf) |
| Predictive maintenance notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/05-manufacturing/01_pdm_build.html) · [notebook source](../../notebooks/predictive-maintenance/01_pdm_build.ipynb) |
| Compressor telemetry simulator | Interactive demo | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/05-manufacturing/02_pdm_simulator.html) |
| Procedure assistant (RAG) notebook | Offline report (related lab) | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/05-manufacturing/01_procedure_build.html) · [notebook source](../../notebooks/procedure-assistant/01_procedure_build.ipynb) |

## In the Studio app

| Route | What it shows |
|---|---|
| `/maintenance` | Compressor health monitoring and work orders |
| `/maintenance-simulator` | Telemetry arriving hour by hour, scored against the cutoff |
| `/procedures` | Grounded procedure lookup that cites sources and refuses when unsupported |
| `/workflow?courseCase=manufacturing-predictive-maintenance` | The maintenance process around the alert |

Data and limits: [notebooks/predictive-maintenance](../../notebooks/predictive-maintenance/README.md)
and [notebooks/procedure-assistant](../../notebooks/procedure-assistant/README.md).
