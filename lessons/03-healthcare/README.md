# 03 · AI in Healthcare: Evidence, Workflow and Human Judgment

Healthcare as four connected workflows (patient intake, diagnostics, operations and monitoring),
then one case in depth: a compact image model that **prioritizes** pediatric chest X-rays for
clinician review. It never diagnoses. An optional notebook stage asks a multimodal LLM to read
the same image and shows why generation is not validation.

[Open this lesson in the browser](https://maoyuexin.github.io/applied-ai-studio/#03-healthcare)

| Material | Format | Link |
|---|---|---|
| Slides | PDF | [M3_Deck_AI_in_Healthcare.pdf](M3_Deck_AI_in_Healthcare.pdf) |
| AUC in plain language | PDF reading | [M3_AUC_Plain_Language_Guide.pdf](M3_AUC_Plain_Language_Guide.pdf) |
| Chest X-ray prioritization notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/03-healthcare/01_pneumonia_build.html) · [notebook source](../../notebooks/pneumonia-screening/01_pneumonia_build.ipynb) |

The offline report includes the optional multimodal Stage 6 as a captured replay; the executable
notebook covers Stages 1–5.

## In the Studio app

| Route | What it shows |
|---|---|
| `/pneumonia` | Packaged-sample workbench, retrospective review queue and model card |
| `/workflow?courseCase=healthcare-pediatric-xray-prioritization` | The imaging workflow and who holds authority at each step |

Data, model and safety boundary: [notebooks/pneumonia-screening](../../notebooks/pneumonia-screening/README.md).
