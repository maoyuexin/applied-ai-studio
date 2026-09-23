# Next Best Product

ITAI 2372 Module 6, Case 2. Instructor-led undergraduate lesson.

## The decision

**Question:** Which ten products should appear in a recommendation area for this customer?

This is a ranking problem and a genuine **recommendation engine**. More precisely, it is a
memory-based **item-item collaborative-filtering recommender**. It learns from shared customer
purchase patterns, not product descriptions, embeddings, or an LLM.

The notebook compares:

- a popularity baseline that shows the same products to everyone; and
- full item-item similarity; and
- item-item collaborative filtering that keeps each product's 15 closest neighbors.

Use the name **Next Best Product**. The transaction log does not record offer exposure,
eligibility, treatment, or counterfactual response, so it cannot support a causal Next Best Offer
claim.

## The five stages

1. Data Ingestion
2. Feature Engineering
3. Model Training
4. Model Validation
5. Model Prediction

The classroom notebook contains 37 cells, 14 code cells, and seven instructional plots. Every plot
has a short guide explaining its marks, finding, and workflow consequence.

## The data

The source is **UCI Online Retail II**, dataset 502, DOI `10.24432/C5CG6D`, licensed CC BY 4.0.
It is the same transaction source used in the demand-regression case, reshaped for a different
question.

The committed interaction data produces:

- 992,123 basket-product rows;
- 4,962 eligible training customers;
- 4,443 products;
- a customer-product matrix that is 98.228% empty; and
- 2,168 customers with at least one eligible new product in the later test window.

## How the recommendation engine works

1. Build a binary customer-product matrix from training purchases.
2. Compare product columns with cosine similarity. Products bought by many of the same customers
  receive higher similarity.
3. For one customer, score a candidate by summing its similarities to products already bought.
4. Remove products already bought and any merchandiser exclusions.
5. Sort the remaining scores and fill ten slots.

The score is for ordering only. A similarity of `0.40` is not a 40% purchase probability.

The short model-selection table is:

| Candidate | Hit Rate at 10 | Coverage | Result |
|---|---:|---:|---|
| Popularity | 29.5% | 1.8% | Baseline |
| Full item-item | 36.4% | 15.5% | Not selected |
| Item-item, top 15 neighbors | **41.6%** | **25.8%** | **Selected** |

**Product example.** The strongest neighbors for `JUMBO BAG RED RETROSPOT` are `JUMBO BAG PINK
POLKADOT` (0.611), `JUMBO BAG STRAWBERRY` (0.606), and `JUMBO BAG BAROQUE BLACK WHITE` (0.559).
The reference is stock code `85099B`, explicitly named in the code, chart, and reading guide.
Two additional training plots explain the calculation: distinct buyers of the red bag and pink
bag `22386` (844 and 541 total, with 413 shared) produce cosine `413 / sqrt(844 x 541) = 0.611`;
the top-20 link chart distinguishes the 15 retained links from discarded links. These are learned
product neighbors, not yet a customer's personalized list. All counts use training data only.

**Customer example.** For customer 12349, `DOORMAT FAIRY CAKE` ranks fourth. Its strongest single
history match is `DOORMAT HEARTS` with similarity 0.416, and the customer buys `DOORMAT FAIRY
CAKE` later. The total ranking score also includes smaller contributions from other history items.

## Measured result

Evaluation uses later purchases and excludes products a customer already bought.

| Method | Hit Rate at 10 | Catalog coverage |
|---|---:|---:|
| Popularity | 29.5% | 1.8% |
| Item-item, top 15 neighbors | 41.6% | 25.8% |

Hit Rate at 10 is the share of scored customers whose ten recommendations contain at least one
held-out new product. Catalog coverage is the share of 4,443 products that appear in at least one
customer's list. Neither metric is revenue, customer satisfaction, or proof that a recommendation
caused a purchase.

## View or run

Open `backup/01_recommendation_build.html` for the self-contained offline classroom copy.

From the repository root, regenerate and execute the notebook with:

```bash
node scripts/venv-python.mjs notebooks/product-recommendations/scripts/build_notebook.py
node scripts/venv-python.mjs -m nbconvert --to notebook --execute --inplace \
  notebooks/product-recommendations/01_recommendation_build.ipynb
node scripts/venv-python.mjs notebooks/product-recommendations/scripts/make_backup.py
```

Run the focused teaching checks with:

```bash
node scripts/venv-python.mjs -m pytest -q \
  notebooks/product-recommendations/tests/test_recommendation_teaching.py
```

## Paths

| Path | Purpose |
|---|---|
| `01_recommendation_build.ipynb` | Executed five-stage classroom notebook |
| `backup/01_recommendation_build.html` | Offline classroom HTML |
| `reclab/teaching.py` | Small classroom calculation and plotting API |
| `scripts/build_notebook.py` | Canonical classroom notebook source |
| `tests/test_recommendation_teaching.py` | Structure and frozen-result checks |
| `backup/02_recommendation_reference.ipynb` | Preserved advanced recommendation lesson |
| `backup/02_recommendation_reference.html` | Offline advanced reference |
| `scripts/build_reference_notebook.py` | Advanced reference generator |
| `scripts/prepare_app_artifacts.py` | Existing application-artifact verifier/builder |

## Operating policy

- Ten recommendation slots contain products not seen in the customer's training history.
- Merchandisers own exclusions and placement; the model ranks within those rules.
- A customer without usable history sees **Popular right now**, based on recent revenue.
- Guest baskets are reported separately because they have no customer identity.
- Previously purchased products belong in a separately labeled **Buy it again** area.

## Limits

- Offline replay measures association, not causation.
- A missing matrix cell does not mean dislike.
- Cold-start customers cannot receive a personalized item-item ranking.
- One wholesaler and one 13-week test window do not represent current retail.
- A ranked product is not a statement about what a customer needs.

## Attribution

Chen, D. (2019). *Online Retail II*. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D, CC BY 4.0.