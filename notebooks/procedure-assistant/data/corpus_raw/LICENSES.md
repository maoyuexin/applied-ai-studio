# Corpus provenance and licensing

Every document here is a US Government work, and that is only half of
the question. A work with no copyright can still be restricted from
redistribution by a **distribution statement** printed on its cover.
Copyright and distribution control are independent gates, and a corpus
has to pass both.

Retrieved 2026-09-02. Every eCFR document is date-pinned
to 2025-08-01, so the regulation text cannot change under the
evaluation set.

## What is in the corpus

| Document | Layer | Publisher | Licence | Distribution | In base corpus |
|---|---|---|---|---|---|
| 29 CFR 1910 subpart J | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | yes |
| 29 CFR 1910 subpart N | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | yes |
| 29 CFR 1910 subpart O | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | yes |
| 29 CFR 1910 subpart Q | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | yes |
| 29 CFR 1910 subpart S | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | yes |
| 30 CFR part 56 | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | yes |
| 30 CFR part 57 | regulation | US Office of the Federal Register (eCFR) | US Government edict - public domain (17 USC 105) | Unrestricted | opt-in (duplicate lab only) |
| USBR FIST 1-1 | site_procedure | US Bureau of Reclamation | US Government work - public domain | Unrestricted | yes |
| USBR FIST 2-4 | site_procedure | US Bureau of Reclamation | US Government work - public domain | Unrestricted | yes |
| USBR FIST 2-6 | site_procedure | US Bureau of Reclamation | US Government work - public domain | Unrestricted | yes |
| TM 9-6115-464-12 | equipment | US Army (public mirror: liberatedmanuals.com) | US Government work - public domain | DISTRIBUTION STATEMENT A - verified in the extracted text | yes |
| OSHA 3120 | plain_language | US Occupational Safety and Health Administration | US Government work - public domain | Unrestricted | yes |
| OSHA 3170 | plain_language | US Occupational Safety and Health Administration | US Government work - public domain | Unrestricted | yes |

## What was rejected, and why

| Document | What it looked like | Why it was rejected | The rule it teaches |
|---|---|---|---|
| Army TM 9-6115-641-24 (generator set) | A US Government work: no copyright, 684 pages, real text, ideal content, and already uploaded to a public site | Page 1 carries DISTRIBUTION STATEMENT C - distribution limited to government agencies and their contractors - plus a destruction notice | Public domain does not mean redistributable. Copyright and distribution control are independent gates. |
| iFixit repair guides | An open licence: Creative Commons BY-NC-SA | NonCommercial alone is a problem for a course, and the site terms state that using the data to train a machine learning or AI model violates the terms of use | An open-looking licence can be explicitly closed to this particular use. Read the terms, not the badge. |
| OEM service manuals (Caterpillar, Deere, Siemens, Fanuc, Rockwell, ABB) | Exactly the content a real plant assistant would need | Dealer-portal only; no public licence exists at any price we can accept for a classroom | The most useful corpus is often the one you are not allowed to have. Say so, and build on what you may use. |

## The vetting rule

Check page 1 of the document. Accept **DISTRIBUTION STATEMENT A** -
"Approved for public release; distribution is unlimited" - and nothing
else. Statements B through F all restrict who may hold the document,
and several carry a destruction notice as well.

The corpus is downloaded once by scripts/build_corpus.py --fetch and committed. Nothing in this notebook, in `npm run setup:procedures`, or in the classroom demo touches the network.
