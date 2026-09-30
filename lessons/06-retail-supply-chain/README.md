# 06 · AI in Retail and Supply Chain

A retailer makes the same five decisions about every product: source, stock, sell, fulfill and
support. Three applied cases use one public retail dataset:

- **Predict a number:** how many units of a product will sell next week (regression).
- **Put things in order:** which ten products deserve a shopper's screen (item-to-item
  recommendations).
- **Read and draft:** turn supplier evidence into catalog fields with an LLM, and hold whatever the
  evidence cannot support (human review).

[Open this lesson in the browser](https://maoyuexin.github.io/applied-ai-studio/#06-retail-supply-chain)

| Material | Format | Link |
|---|---|---|
| Slides | PDF | [M6_Deck_AI_in_Retail.pdf](M6_Deck_AI_in_Retail.pdf) |
| Demand forecasting notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/06-retail-supply-chain/M6_Notebook_Demand_Forecasting.html) · [notebook source](../../notebooks/demand-forecasting/01_forecast_build.ipynb) |
| Product recommendations notebook | Offline report | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/06-retail-supply-chain/M6_Notebook_Product_Recommendations.html) · [notebook source](../../notebooks/product-recommendations/01_recommendation_build.ipynb) |
| Demand forecasting simulator | Interactive demo | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/06-retail-supply-chain/M6_Simulator_Demand_Forecasting.html) |
| Next best product simulator | Interactive demo | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/06-retail-supply-chain/M6_Simulator_Next_Best_Product.html) |
| How recommendations work | Visual explainer | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/06-retail-supply-chain/M6_Explainer_How_Recommendations_Work.html) |
| Catalog onboarding with an LLM | Interactive demo | [Open in browser](https://maoyuexin.github.io/applied-ai-studio/lessons/06-retail-supply-chain/M6_Demo_Catalog_Onboarding.html) · [source](../../notebooks/catalog-onboarding/README.md) |

The slide links to notebooks and demos work when the PDF is opened from the lesson site, because
the site publishes each file under the name the slides use.

**Photographs.** Merchant product photographs have rights separate from the dataset license, so
the public slides show a "product photo not included" placeholder and the demos show product names
and stock codes instead. Model inputs, results and text are unchanged.

## In the Studio app

| Route | What it shows |
|---|---|
| `/forecast` | Demand forecasting demo (runs in the browser) |
| `/recommendations` | Next best product demo (runs in the browser) |
| `/workflow?courseCase=retail-demand-forecasting` | The planner's ordering process |
| `/workflow?courseCase=retail-product-recommendations` | The merchandising process |

Data and limits: [notebooks/demand-forecasting](../../notebooks/demand-forecasting/README.md),
[notebooks/product-recommendations](../../notebooks/product-recommendations/README.md),
[notebooks/retail-simulators](../../notebooks/retail-simulators/README.md) and
[notebooks/catalog-onboarding](../../notebooks/catalog-onboarding/README.md).
