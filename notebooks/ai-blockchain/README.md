# AI and blockchain lessons (Module 13)

Single-file, offline lesson pages built in the course module folder and copied here byte for byte by
`scripts/sync-blockchain-labs.mjs`. Every number on a page comes from a facts file that the page's build checks.

| File | Lesson | Data | In this repository |
|---|---|---|---|
| `backup/blockchain-explorer.html` | Blockchain Explorer | Real bitcoin blocks 0, 170, 840,000 and one from Oct 13, 2026; Ethereum blocks 15,537,393–15,537,394 (public chains) | Yes |
| `backup/agent-wallet.html` | Agent Wallet | Real USGS 15-minute gage heights, four Brays Bayou gauges, Aug 26, 2017 (public domain); 18 recorded agent runs | Yes |
| `backup/recall-desk.html` | Recall Desk | Fictional, FSMA 204-shaped supply chain; real signatures and Merkle roots on a local chain; three recorded vision-model runs | Yes |
| `local/ledger-watch.html` | Ledger Watch | Elliptic Data Set (Weber et al., 2019), **CC BY-NC-ND 4.0** | **No**: git-ignored local teaching copy |
| `local/M13_Deck_AI_Blockchain.pdf` | Slides | Includes Elliptic-derived figures | **No**: git-ignored local teaching copy |

## Limits stated on the pages

- **Agent Wallet:** recorded on a local Ethereum development chain (one machine, no distributed consensus) with a
  stand-in test token. The payments follow x402's messages (HTTP 402, price, seller, one-time reference, `X-PAYMENT`)
  but settle through the agent's own `SpendingPolicy` contract rather than x402's signed USDC authorization and
  facilitator. Approvals in the recordings were automatic and are marked as such.
- **Recall Desk:** the AI read the paper log correctly in all three runs, so the wrong-record story is a labeled
  what-if; its chain steps are real local transactions.
- **Ledger Watch:** 85% of the model's flags were never labeled; the agent drafts notes and never files them.

## Update

```sh
BLOCKCHAIN_LABS_SOURCE=/path/to/Module_13_AI_Blockchain_Integration node scripts/sync-blockchain-labs.mjs
BLOCKCHAIN_LABS_SOURCE=/path/to/Module_13_AI_Blockchain_Integration node scripts/sync-blockchain-labs.mjs --check
```

The script refuses to copy a page that loads a remote resource, misses a lesson step, mentions Elliptic outside
`local/`, or contains a key from the test wallet file.
