# 13 · AI and Blockchain Integration

A blockchain is a shared record that parties who don't trust each other can all check. The lesson first shows what one
actually does, on real bitcoin blocks, then follows the three directions in which AI and a shared ledger meet:

- **AI reads the ledger (Ledger Watch):** a random forest flags illicit bitcoin transactions, then goes blind after a
  dark market shuts down; an agent drafts the analyst's case note, and the analyst decides.
- **AI acts on the ledger (Agent Wallet):** during Hurricane Harvey, a dispatch agent buys real river-gauge readings
  through HTTP 402, paying from a wallet contract whose limits it cannot change. A note in the data asks it to pay $25.
- **The ledger checks AI (Recall Desk):** a signed, anchored supply chain catches tampering, but a wrong record approved
  from an AI reading is preserved perfectly; the fix is a new record.

The session closes with AI agents attacking and auditing smart contracts, and a "do you need a blockchain?" activity.
Key question: **what does the ledger prove, what does the AI guess, and who decides?**

| Material | Format | Where |
|---|---|---|
| Slides | PDF | Distributed in class. The deck includes figures built from the Elliptic Data Set (CC BY-NC-ND 4.0), so it is not published here |
| Blockchain Explorer | Interactive lesson (8 steps) and "explore any block" | `/blockchain-explorer` · [file](../../notebooks/ai-blockchain/backup/blockchain-explorer.html) |
| Ledger Watch | Interactive lesson (9 steps) and "explore any snapshot" | `/ledger-watch`: **local teaching copy only** (Elliptic license) |
| Agent Wallet | Interactive lesson (9 steps) and every recorded run | `/agent-wallet` · [file](../../notebooks/ai-blockchain/backup/agent-wallet.html) |
| Recall Desk | Interactive lesson (6 steps) and "check any record" | `/recall-desk` · [file](../../notebooks/ai-blockchain/backup/recall-desk.html) |

## In the Studio app

| Route | What it shows |
|---|---|
| `/blockchain-explorer` | Hashes, a real block, the chain link, a Merkle proof, mining and agreement, computed in the browser |
| `/ledger-watch` | Illicit-transaction model, data drift and an investigator agent (shown only where the local copy exists) |
| `/agent-wallet` | An agent pays inside contract-enforced limits: 402, payments on the ledger, a refused payment, prompt injection, owner approval |
| `/recall-desk` | Tamper evidence, an AI reading a paper log, and why corrections are new records |

The live Agent Wallet demo (a local Ethereum chain or the Base Sepolia test network, a paid data desk and a Microsoft
Agent Framework agent) runs from the course module folder, not from this repository; the Studio page replays its 18
recorded runs. Data and limits: [notebooks/ai-blockchain](../../notebooks/ai-blockchain/README.md).
