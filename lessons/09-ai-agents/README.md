# 09 · AI Agents and Decision Automation

An agent is a language model that uses tools, over several steps, to reach a goal, and stops to check and ask
where we tell it to. The lesson builds that up in four steps: a model, then tools, then one agent, then a team of
agents, and it ends with how agents fail and the controls that catch each failure.

Key question: **what should the agent be allowed to do without asking?**

- **Building blocks:** the planner (a language model) and the specialists (the predictive models from lessons
  02–08, now called as tools); five kinds of tools; the eight parts of any agent (model, instructions, tools,
  knowledge, memory, guardrails, identity, trace) and where each one lives in Microsoft Foundry; the loop
  Sense → Plan → Act → Check → Ask; six questions for "is this agent-shaped work?"; five levels of who decides.
- **One agent:** *Card Alert* calls the lesson 02 fraud model and waits for approval before holding a card.
  *Trial Finder* searches the live ClinicalTrials.gov registry for one patient: with the same model, a plain chatbot
  named 10 trials and none was recruiting nearby, while the agent shortlisted 4 and confirmed all 4 by code.
- **Teams of agents:** three patterns, each on a recorded run: *sequential* (a machine alert becomes a work order),
  *handoff* (a coding team passes a task along) and *group chat* (a chair runs a holiday promotion brief), with
  what a team costs in time and tokens compared with one agent.
- **Limits and controls:** five failures seen in our own runs, real incidents, and a control map: one control per
  failure, and where each one sits in the demo.

| Material | Format | Where |
|---|---|---|
| Slides | PDF | [M9_Deck_AI_Agents.pdf](M9_Deck_AI_Agents.pdf) |
| Agent Workflows | Studio page: business view, workflow canvas and timeline for every run | `/agent-workflows` |

## In the Studio app

| Route | What it shows |
|---|---|
| `/agent-workflows` | Five scenarios (Card Alert, Trial Finder, Machine Alert to Work Order, Coding Team, Holiday Promotion). Recorded runs replay with no setup; **Live** runs need a Microsoft Foundry model and the model services each scenario calls |

Every action tool (hold a card, send a referral, create a work order, merge a change, submit a brief) waits for a
person's approval and writes only to a per-run outbox. Setup, recording and adding a scenario:
[services/agent-workflow-api](../../services/agent-workflow-api/README.md).
