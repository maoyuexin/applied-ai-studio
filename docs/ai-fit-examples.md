# AI Fit Analyzer Examples

Use these scenarios in **AI Fit Analyzer**. For each example, enter the problem
context, generate the five-stage workflow, select the specified decision, set the
six readiness values, and run the fit analysis.

Copilot may vary the wording of generated stages and decisions. Select by the
decision's output shape and responsibility, not by an exact sentence match.

## Example 1: Predictive Maintenance Triage

This example tests a future-event prediction with human-controlled maintenance
action.

### Problem context

| Field | Value |
| --- | --- |
| Industry | Manufacturing |
| Current problem | A manufacturing plant receives noisy motor and pump sensor alerts. Technicians cannot inspect every asset, unexpected failures cause downtime, and the team manually decides which equipment needs attention. |
| Desired outcome | Identify equipment likely to fail within the next 48 hours and prioritize inspection without automatic equipment shutdown. |

Select the generated decision resembling **Is the asset likely to fail within 48
hours?** It should be marked **AI · prediction**. Do not select the inspection
allocation decision marked optimization or the shutdown decision marked human.

### Readiness scores

| Dimension | Value |
| --- | ---: |
| Business value | 5 |
| Data readiness | 4 |
| Process repeatability | 5 |
| Integration readiness | 3 |
| Human oversight | 5 |
| Error tolerance | 3 |

Expected deterministic score: **84/100**, calculated as
`20 + 16 + 15 + 9 + 15 + 9`.

### Expected design

- Readiness: **Strong fit**
- AI method: **Prediction**
- Solution pattern: **Decision support**
- Human boundary: the model estimates failure risk; a qualified reviewer decides
  whether to inspect, schedule maintenance, or take equipment action.
- Representative technical metrics: MAE, RMSE, calibration, coverage, and latency.
- Representative business metrics: inspection prioritization value, unplanned
  downtime, reviewer acceptance, and unsafe automation rate.
- The result includes a detailed blueprint and a second AI-level workflow.

## Example 2: KYC Packet Exception Review

This example tests present-state classification over extracted document evidence,
with regulated case disposition retained by a compliance analyst.

### Problem context

| Field | Value |
| --- | --- |
| Industry | Financial Services |
| Current problem | Compliance analysts manually reconcile identity documents, onboarding forms, beneficial ownership records, and policy requirements. Packets frequently contain missing or inconsistent evidence, which slows review and creates an uneven queue. |
| Desired outcome | Extract the relevant evidence and identify whether each packet is complete or requires exception review, including the exact missing or inconsistent fields, without automatically approving or rejecting a customer. |

Select the generated decision resembling **Can required evidence fields be
reliably extracted?** It should be marked **AI · classification**. Do not select
policy completeness checks, which should remain rules, or packet exception review
and final customer disposition, which should remain human.

If Copilot does not set it from the selected decision, choose **Document
processing** as the primary workload before running the assessment.

### Readiness scores

| Dimension | Value |
| --- | ---: |
| Business value | 5 |
| Data readiness | 4 |
| Process repeatability | 5 |
| Integration readiness | 4 |
| Human oversight | 5 |
| Error tolerance | 3 |

Expected deterministic score: **87/100**, calculated as
`20 + 16 + 15 + 12 + 15 + 9`.

### Expected design

- Readiness: **Strong fit**
- AI method: **Classification**
- Solution pattern: **Document intelligence**
- Human boundary: the system extracts evidence and classifies packet readiness;
  a compliance analyst resolves exceptions and owns case disposition.
- Validated technical metrics: field precision, field recall, packet
  classification accuracy, and grounded citation rate.
- Validated business metrics: review time, exception rework, and reviewer
  acceptance.
- The result should include a detailed blueprint and a second AI-level workflow.

## Comparison

| Example | Question shape | AI method | Solution pattern | Human authority |
| --- | --- | --- | --- | --- |
| Predictive maintenance | Will an asset fail within 48 hours? | Prediction | Decision support | Inspection and equipment action |
| KYC exception review | Which present-state packet class applies? | Classification | Document intelligence | Exception resolution and case disposition |