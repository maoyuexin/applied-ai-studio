"""Build the undergraduate Module 6 Next Best Product notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_recommendation_build.ipynb"


def build_notebook() -> nbf.NotebookNode:
    notebook = nbf.v4.new_notebook()
    cells: list[nbf.NotebookNode] = []
    original_cell_number = 0

    def metadata(language: str, cell_id: str | None = None) -> tuple[str, dict[str, str]]:
        nonlocal original_cell_number
        if cell_id is None:
            original_cell_number += 1
            cell_id = f"recommendation-classroom-{original_cell_number:03d}"
        return cell_id, {"id": cell_id, "language": language}

    def md(text: str, cell_id: str | None = None) -> None:
        cell_id, meta = metadata("markdown", cell_id)
        cells.append(nbf.v4.new_markdown_cell(text.strip(), id=cell_id, metadata=meta))

    def code(text: str, cell_id: str | None = None) -> None:
        cell_id, meta = metadata("python", cell_id)
        cells.append(nbf.v4.new_code_cell(text.strip(), id=cell_id, metadata=meta))

    def guide(marks: str, finding: str, action: str, cell_id: str | None = None) -> None:
        md(f"""
### How to read this plot

- **Marks:** {marks}
- **Finding:** {finding}
- **Workflow meaning:** {action}
""", cell_id)

    md("""
# Next Best Product

**ITAI 2372 - Module 6 - AI in Retail and Supply Chain**

**Business question:** Which ten products should appear in a recommendation area for this
customer?

This is a **ranking** problem. The model does not predict one category or one number. It assigns
scores to eligible products, sorts them, and fills a limited number of slots.

### See how the recommendation engine works

[Open the visual walkthrough](M6_Explainer_How_Recommendations_Work.html) for a short,
step-by-step example: purchases become a matrix, product similarities become saved links,
and those links produce a recommendation list. Play the 2:53 walkthrough or choose **All steps**.

Keep `M6_Explainer_How_Recommendations_Work.html` in the same folder as this notebook or its
exported HTML so the link works offline.

| Stage | Question |
|---|---|
| 1. Data Ingestion | Which baskets and customers can we use? |
| 2. Feature Engineering | How do purchases become a customer-product matrix? |
| 3. Model Training | How does item-item similarity learn related products? |
| 4. Model Validation | Does personalization beat the same list for everyone? |
| 5. Model Prediction | What list is shown, and what happens without history? |

**Important boundary:** transaction history supports a product ranking. It does not show which
offers caused a purchase, so this is not a causal offer-selection system.
""")

    code("""
import warnings

import pandas as pd
import plotly.io as pio

from reclab import config, data, policy
from reclab import teaching

warnings.filterwarnings("ignore")
pd.set_option("display.width", 160)
pd.set_option("display.max_colwidth", 70)
pio.renderers.default = "notebook"
""")

    md("""
---
# 1 - Data Ingestion

**Question:** What is one row, whose behavior is represented, and how do we avoid training on
future purchases?

The source is **UCI Online Retail II**, DOI `10.24432/C5CG6D`, licensed CC BY 4.0. It contains
two years of transactions from one UK online gift wholesaler. The same source powers the demand
forecasting case, but this lesson keeps customer identity and basket history.

The committed file has one row per product in one basket. Guest checkouts remain in the source
file but cannot be personalized because they have no customer identity.
""")

    code("""
lesson = teaching.load_lesson()
print(teaching.lesson_summary(lesson).to_string(index=False))
print(f"\\nSource: {config.DATASET_CITATION}")
""")

    md("""
## 1.1 One real basket

The rows below share an invoice and timestamp. Each row means that one product appeared in that
basket. Product quantity is not used in this introductory recommender; a filled matrix cell means
"this customer bought this product at least once before the split."
""")

    code("""
basket = data.one_row_example(lesson.interactions, lesson.descriptions)
print(basket.to_string(index=False))
""")

    md("""
## 1.2 Split globally by time

Everything on or before September 9, 2011 is training data. Everything later is test data. A
random split could place December purchases in training and September purchases in test, which
would let the model learn from the future.
""")

    code("""
figure_1 = teaching.time_split_figure(lesson)
figure_1.show()
""")

    guide(
        "The line is registered-customer baskets per week; the dashed line is the time split.",
        "Training activity is always earlier than test activity.",
        "Evaluate the ranking on later purchases, as it would be used in practice.",
    )

    md("""
---
# 2 - Feature Engineering

**Question:** How do transaction rows become model inputs?

We create a **customer-product interaction matrix**:

- one row per registered customer;
- one column per product;
- `1` if that customer bought that product before the split;
- `0` if no purchase is recorded.

A zero means "not observed in this history," not "the customer dislikes it." The full matrix is
98.228% empty, which is called **sparse**.
""")

    code("""
figure_2 = teaching.matrix_figure(lesson)
figure_2.show()
""")

    guide(
        "Rows are customers, columns are products, and blue cells are recorded purchases.",
        "Even active customers touch only a small part of the catalog.",
        "A recommender tries to rank useful empty cells without calling them known preferences.",
    )

    md("""
The model also excludes products already purchased by the customer from this **discovery** list.
Previously purchased products can appear in a separate "Buy it again" area, but they are not
counted as new-product recommendations here.
""")

    md("""
---
# 3 - Model Training

**Question:** Which products are related because many of the same customers bought them?

Yes, this is a **recommendation engine**. More precisely, it is a memory-based
**item-item collaborative-filtering recommender**: it learns from shared purchase patterns,
not from product descriptions or an LLM.

Here, **training** means counting shared buyers, calculating product-to-product similarities,
and saving the strongest links. There is no neural network or sequence of error-correcting trees.

We compare three candidates on the discovery test:

1. **Popularity baseline:** count training customers per product and show the same top products
   to everyone. It uses no customer history.
2. **Full item-item:** retain every non-zero product-to-product similarity.
3. **Top-15 item-item:** keep only each product's 15 strongest neighbors.

For one customer, the engine adds the similarity scores contributed by products already in that
customer's history, masks products already bought, sorts the remaining products, and takes ten:

```text
candidate score = sum(similarity to each product already bought)
```
""")

    code("""
fitted = teaching.fit_models(lesson.split)
selection = teaching.model_selection_table(lesson.split, fitted)
selection_display = selection.copy()
selection_display["HR@10"] = selection_display["HR@10"].map("{:.1%}".format)
selection_display["Coverage"] = selection_display["Coverage"].map("{:.1%}".format)
print(selection_display.drop(columns="Fit seconds").to_string(index=False))
""")

    md("""
## 3.1 Which product are we comparing against?

Our reference product is **JUMBO BAG RED RETROSPOT**, stock code **85099B**: the red-patterned
shopping bag. Every bar below compares another product with this same reference product.

The strongest neighbor is **JUMBO BAG PINK POLKADOT (22386)**, with similarity about **0.611**.
The engine discovered overlapping buyers, not matching colors or product names. This is a list
of product neighbors, not yet a personalized customer's recommendation list.

We display ten neighbors for readability; the model stores up to fifteen.
""", "recommendation-source-context")

    code("""
source_product = "85099B"
figure_3 = teaching.similar_products_figure(
    lesson, fitted[teaching.MODEL_LABEL], code=source_product,
)
figure_3.show()
neighbors = teaching.similar_product_table(
    lesson, fitted[teaching.MODEL_LABEL], code=source_product)
print("\\nReal example: nearest products to JUMBO BAG RED RETROSPOT")
print(neighbors.round({"Cosine similarity": 3}).to_string(index=False))
""")

    guide(
        "Each bar is another product; length is its similarity to JUMBO BAG RED RETROSPOT (85099B).",
        "Higher scores mean more overlap in the customers who bought both products.",
        "Similarity creates candidates; merchandising rules still control eligibility and placement.",
    )

    md("""
The score is used only for ranking. A similarity of 0.40 is not a 40% purchase probability, and
it does not explain why customers bought either item.
""")

    md("""
## 3.2 Where does the 0.611 similarity come from?

Compare the red bag (**85099B**) with the pink polka-dot bag (**22386**) using only the training
matrix. Count distinct customers, not units or baskets. Someone buying a bag three times still
counts once. The three groups below do not overlap; each customer is counted in only one bar.
""", "recommendation-overlap-context")

    code("""
pair = teaching.product_pair_summary(lesson, source_product, "22386").iloc[0]
print(f"Red bag buyers: {pair['Source buyers']:,}")
print(f"Pink bag buyers: {pair['Other buyers']:,}")
print(f"Shared buyers: {pair['Shared buyers']:,}")
print(f"Cosine = {pair['Shared buyers']} / sqrt("
      f"{pair['Source buyers']} x {pair['Other buyers']})"
      f" = {pair['Cosine similarity']:.3f}")
figure_3a = teaching.buyer_overlap_figure(lesson, source_product, "22386")
figure_3a.show()
""", "recommendation-overlap-code")

    guide(
        "Bars count red-only, shared, and pink-only buyers: 431, 413, and 128.",
        "Red buyers = 431 + 413 = 844; pink buyers = 413 + 128 = 541. "
        "Cosine = 413 / sqrt(844 x 541) = 0.611. The denominator adjusts for group size.",
        "Similarity 1 means identical buyer groups; 0 means no shared buyers. "
        "Shared non-purchases do not add evidence, and 0.611 is not a 61.1% purchase chance.",
        "recommendation-overlap-guide",
    )

    md("""
## 3.3 What does the model actually save?

For the red bag, compare its twenty strongest links before filtering. The model retains the
first fifteen and drops the others. The same operation runs for every product in the catalog;
a product's link to itself is excluded.
""", "recommendation-retention-context")

    code("""
figure_3b = teaching.neighbor_retention_figure(
    lesson, fitted[teaching.FULL_MODEL_LABEL],
    fitted[teaching.MODEL_LABEL], code=source_product,
)
figure_3b.show()
""", "recommendation-retention-code")

    guide(
        "Horizontal position is neighbor rank, not time; height is cosine similarity. "
        "The legend separates saved links from links not saved. Hover reveals product names.",
        "The first fifteen links are saved; the dashed line marks the boundary. "
        "Only the top twenty are displayed, not the whole catalog.",
        "Training saves a sparse product-product lookup table. When a shopper arrives, "
        "links from purchased products are added into candidate scores; already-bought products "
        "are removed. A new purchase changes that sum without retraining the links.",
        "recommendation-retention-guide",
    )

    md("""
---
# 4 - Model Validation

**Question:** Does the personalized ranker do better than one popular list on later purchases?

We use two plain-language metrics:

- **Hit Rate at 10:** share of scored customers whose ten recommendations contain at least one
  product they later bought for the first time. Numerator: customers with one or more hits.
  Denominator: customers with at least one eligible new product in the test period.
- **Catalog coverage:** share of the 4,443 training products that appear at least once across all
  customers' ten-slot lists. A high hit rate with tiny coverage can repeatedly expose only a
  handful of products.

Neither metric proves that showing a recommendation caused a purchase or increased revenue.
""")

    code("""
comparison = teaching.comparison_table(lesson.split, fitted)
display_table = comparison.copy()
display_table["HR@10"] = display_table["HR@10"].map("{:.1%}".format)
display_table["Coverage"] = display_table["Coverage"].map("{:.1%}".format)
print(display_table.to_string(index=False))
""")

    code("""
figure_4 = teaching.comparison_figure(comparison)
figure_4.show()
""")

    guide(
        "Left bars show customers with a hit; right bars show products used across all lists.",
        "Item-item ranking improves Hit Rate at 10 and spreads exposure across more of the catalog.",
        "Use both metrics; do not call either one revenue or customer satisfaction.",
    )

    md("""
On this held-out period, popularity reaches about 29.5% of eligible customers and about 1.8% of
the catalog. Item-item ranking reaches about 41.6% of eligible customers and about 25.8% of the
catalog. These results support choosing the item-item model for this classroom workflow.
""")

    md("""
---
# 5 - Model Prediction

**Question:** What does the system show one customer, and what does it do when no useful history
exists?

The operating flow is:

```text
customer history -> score eligible products -> apply exclusions -> rank -> fill ten slots
```

Merchandisers own the exclusion list, page placement, and fallback policy. The model only ranks
eligible products inside those rules.
""")

    code("""
recommendations = teaching.example_recommendations(
    lesson,
    fitted[teaching.MODEL_LABEL],
)
print(recommendations.drop(columns="Score").to_string(index=False))
explanations = teaching.recommendation_explanations(
    lesson, fitted[teaching.MODEL_LABEL], recommendations)
print("\\nWhy the first five products appeared:")
print(explanations.round({"Total score": 3, "Similarity contribution": 3})
      .to_string(index=False))
""")

    code("""
figure_5 = teaching.recommendation_figure(recommendations)
figure_5.show()
""")

    guide(
        "Bars are the ten ranked products; green marks a product observed later in held-out data.",
        "This example has a hit, but most recommended slots are not observed as later purchases.",
        "Show the list as ranked suggestions, not as statements about what the customer needs.",
    )

    md("""
## 5.1 Cold start and fallback

If a registered customer has no usable training history, item-item scores are all zero. The
system must not pretend that an arbitrary list is personalized. It shows the ten products with
the most revenue in the last 28 training days under the honest label **Popular right now**.

Guest baskets are a different population: there is no identity to connect to any history. Their
count is reported separately and never added to the registered-customer percentage.
""")

    code("""
print(teaching.cold_start_summary(lesson).to_string(index=False))
print("\\nFallback list shown as 'Popular right now':")
fallback = policy.fallback_list(lesson.split, lesson.descriptions)
print(fallback[["Slot", "Product"]].to_string(index=False))
""")

    md("""
## What this lesson established

1. A recommender ranks products; it does not classify a customer.
2. A sparse customer-product matrix turns basket history into model inputs.
3. Item-item similarity learns relationships from shared customer patterns.
4. Hit Rate at 10 measures customer-level retrieval; coverage measures catalog exposure.
5. Cold-start lists must be labeled as generic fallback, not personalized recommendations.

**Claim boundary:** offline replay shows association, not causation. A hit does not prove the
recommendation created the purchase, improved revenue, or served the customer's interests.
""")

    notebook["cells"] = cells
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    return notebook


def main() -> None:
    notebook = build_notebook()
    if OUTPUT.exists():
        existing = nbf.read(OUTPUT, as_version=4)
        previous = {cell.id: cell for cell in existing.cells}
        notebook.metadata = existing.metadata
        for index, cell in enumerate(notebook.cells):
            old = previous.get(cell.id)
            if old is not None and old.cell_type == cell.cell_type:
                if old.source == cell.source:
                    notebook.cells[index] = old
                else:
                    cell.metadata.update(old.metadata)
                    cell.metadata.pop("execution", None)
    nbf.write(notebook, OUTPUT)
    print(f"Wrote {OUTPUT} ({len(notebook['cells'])} cells)")


if __name__ == "__main__":
    main()