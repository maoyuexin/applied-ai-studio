"""Build 01_pneumonia_build.ipynb in the five Session 2 teaching stages."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_pneumonia_build.ipynb"

notebook = nbf.v4.new_notebook()
cells = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_id = f"pneumonia-build-{len(cells) + 1:03d}"
    return cell_id, {"id": cell_id, "language": language}


def md(text: str) -> None:
    cell_id, metadata = cell_metadata("markdown")
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n"), id=cell_id, metadata=metadata))


def code(text: str) -> None:
    cell_id, metadata = cell_metadata("python")
    cells.append(nbf.v4.new_code_cell(text.strip("\n"), id=cell_id, metadata=metadata))


md(r"""
# From chest X-ray pixels to a review queue

**ITAI 2372 - Module 3 - AI in Healthcare**

Last session we built a fraud model in five stages. Tonight we use the same structure for
an image model, then place its score inside a healthcare workflow.

| | Stage | What happens |
|---|---|---|
| **1** | **Data Ingestion** | Verify provenance, labels, and source-defined splits |
| **2** | **Image EDA and Preparation** | Inspect pixels, prepare tensors, and test image quality |
| **3** | **Model Training** | Compare with a baseline and train a compact CNN |
| **4** | **Model Validation** | Choose a policy on validation data and evaluate untouched test patients |
| **5** | **Model Prediction** | Route packaged examples and hand the exact model to the app |

> **The model does not diagnose pneumonia.** It produces a score from a packaged,
> de-identified benchmark image. A policy may place the study in **priority review** or
> **standard review**. A radiologist still interprets the image, and a clinician combines
> that interpretation with the patient context.

### The case

A pediatric imaging queue contains chest X-rays waiting for interpretation. The narrow
question is:

> **Should this study receive earlier review because its pixels resemble images carrying
> the dataset's pneumonia label?**

### The data

- **5,856 pediatric chest X-rays** in PneumoniaMNIST 128
- **1,583 normal labels** and **4,273 pneumonia labels**
- Source-defined training, validation, and test splits
- CC BY 4.0; archive checksum verified before loading
- MedMNIST states that the benchmark is **not intended for clinical use**

The archive is committed beside this notebook. Running the notebook requires no download
and accepts no arbitrary image upload.
""")

code(r"""
# ===============================================================
# SETUP
# ===============================================================
import warnings

import numpy as np
import pandas as pd
import plotly.io as pio

from pneumonialab import charts, config, data, evaluation, explain, handoff, metrics, models

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 30)
pio.renderers.default = "notebook"
print(config.describe())
""")

md(r"""
---
# 1 - Data Ingestion and Provenance

**Question:** Do we know what this archive contains, who it represents, and how its labels
and splits were created?

An image file is not trustworthy merely because it opens. We first verify the exact source
archive, then inspect its arrays and source-defined splits.
""")

md(r"""
## 1.1 Verify the archive before loading it

The expected MD5 checksum comes from the official MedMNIST+ release. A checksum is a file
fingerprint: if one byte changes, the fingerprint changes.

**Source:** [MedMNIST v2](https://medmnist.com/) and the
[official Zenodo record](https://zenodo.org/records/10519652).
""")

code(r"""
# ===============================================================
# 1.1 VERIFY PROVENANCE AND FILE IDENTITY
# ===============================================================
verification = data.verify_archive()
pd.DataFrame({
    "Check": ["Archive", "Bytes", "MD5", "License", "Clinical use"],
    "Verified value": [config.DATASET_NAME, f"{verification['bytes']:,}",
                       verification["md5"], config.DATASET_LICENSE,
                       "Not intended for clinical use"],
})
""")

md(r"""
## 1.2 Load the source-defined splits

Each row is one image. The source study reports patient separation between its training
and test sets. We preserve the published splits rather than reshuffling images ourselves.

- **Training:** fit model parameters
- **Validation:** choose the checkpoint and operating cutoff
- **Test:** evaluate once after the policy is frozen
""")

code(r"""
# ===============================================================
# 1.2 LOAD THE VERIFIED ARRAYS
# ===============================================================
splits = data.load_splits()
summary = data.split_summary(splits)

print({name: split.images.shape for name, split in splits.items()})
summary.style.format({"Share of split": "{:.1%}"}).hide(axis="index")
""")

code(r"""
# ===============================================================
# 1.3 CLASS BALANCE BY SPLIT
# ===============================================================
charts.class_balance(splits).show()
""")

md(r"""
### How to read this plot

- **One bar = one dataset split.** The full bar height is the number of images in that
    split. The colored sections divide that total into the two dataset labels.
- **A stacked bar chart** places categories on top of one another so we can see both the
    total and its composition.
- **What to notice:** the orange pneumonia-labeled section is larger in training,
    validation, and test data. The imbalance is therefore not confined to one split.
- **Why it matters:** accuracy alone will be misleading. We will later count false
    positives and false negatives and report sensitivity, specificity, and precision.

### What the label means

The archive stores `0` for **normal** and `1` for **pneumonia**. Those are source dataset
labels, not diagnoses made by our model.

The classes are imbalanced: about 73% of all images carry the pneumonia label. That means
an always-pneumonia rule can look accurate while being useless for queue prioritization.

The model does not receive symptoms, vital signs, laboratory results, age per image,
history, competing diagnoses, or treatment response. It receives only resized grayscale
pixels.
""")

md(r"""
---
# 2 - Image EDA and Preparation

**Question:** What does the model actually see, and what transformations are appropriate
before learning?

EDA still means inspecting the data before modeling. The difference is that one row now
contains a two-dimensional array of pixel values.

We will move through three levels:

1. **Dataset level:** how many examples and labels do we have?
2. **Image level:** what numbers are stored, and how do images vary?
3. **Feature level:** which measurements do we define, and which patterns does the CNN learn?
""")

md(r"""
## 2.1 Look at examples without interpreting them clinically

These are 128 x 128 benchmark images. The titles report the source label only. They do not
claim that we can identify a finding from the thumbnail.
""")

code(r"""
# ===============================================================
# 2.1 EXAMPLES FROM THE TRAINING SPLIT
# ===============================================================
train = splits["train"]
normal_indices = np.flatnonzero(train.labels == 0)[:4]
pneumonia_indices = np.flatnonzero(train.labels == 1)[:4]
example_indices = np.concatenate([normal_indices, pneumonia_indices])
example_titles = [config.CLASS_NAMES[int(train.labels[index])] for index in example_indices]
charts.image_gallery(train.images[example_indices], example_titles,
                     "Training examples labeled by the source dataset").show()
""")

md(r"""
### How to read this plot

- Each square is a different training image. The title above it is the **source dataset
    label**, not a prediction from our model and not our diagnosis.
- All images have been center-cropped and resized to 128 x 128 pixels, so the notebook is
    not showing a diagnostic-quality hospital viewer.
- **What to notice:** images with the same label still vary in brightness, contrast,
    anatomy, positioning, and visible artifacts.
- **Why it matters:** a model must learn from variation within each label rather than
    memorize one example that looks typical to us.

## 2.2 One picture becomes 16,384 numbers

A digital grayscale image is a table with 128 rows and 128 columns. Each cell is one
**pixel**. Its value runs from 0 (black) to 255 (white).

The green square below selects an 8 x 8 patch. The right side shows the 64 stored numbers
inside that tiny area. The model receives all `128 x 128 = 16,384` values; it does
not receive words such as "lung," "opacity," or "pneumonia."
""")

code(r"""
# ===============================================================
# 2.2 ZOOM FROM ONE IMAGE INTO ITS PIXEL VALUES
# ===============================================================
# Training index 7 keeps the later quality demonstration unambiguous:
# the original passes, while all three severe transformations enter quality hold.
example = train.images[7]
charts.pixel_grid(example).show()
""")

md(r"""
### How to read this plot

- The left panel is the complete image. The green square marks the small patch enlarged on
    the right.
- The right panel prints each pixel's **intensity**, or brightness value. `0` is black,
    `255` is white, and values between them are shades of gray.
- Row and column numbers are locations in the array; they are not physical measurements
    such as centimeters.
- **Why it matters:** the CNN starts with numbers and locations. Clinical meaning is not
    stored in any individual pixel.

## 2.3 Individual pixel values overlap

Each pixel is an intensity from 0 (black) to 255 (white). If one brightness cutoff could
separate the labels, we would not need a CNN. The distributions overlap because the model
must learn spatial patterns, not one global number.
""")

code(r"""
# ===============================================================
# 2.3 PIXEL INTENSITY EDA
# ===============================================================
charts.pixel_distribution(splits).show()
""")

md(r"""
### How to read this plot

- The horizontal axis is pixel intensity from dark (`0`) to bright (`255`).
- The vertical axis is **density**, a normalized relative frequency. A higher line means
    that intensity occurs more often within that label's sampled pixels; it is not a patient
    count or disease probability.
- Blue represents pixels from normal-labeled training images; orange represents pixels
    from pneumonia-labeled training images.
- **What to notice:** the curves overlap across most of the range. No single brightness
    cutoff can reliably separate the image labels.
- **Why it matters:** the model needs spatial patterns—where neighboring values occur—not
    merely a list of bright and dark pixels.

## 2.4 Compare simple whole-image summaries

We can compress each image into a few descriptive measurements:

- **Mean brightness:** the average pixel value. Higher means the whole image is brighter.
- **Contrast:** how spread out the pixel values are. Higher means stronger dark/light differences.
- **Edge variation:** how quickly neighboring pixels change. We use it later as a rough
    technical focus check, not as a medical finding.

Each dot below is one training image. The colors overlap: images with different labels can
have similar brightness and contrast. A simple rule based on either axis would make errors.
""")

code(r"""
# ===============================================================
# 2.4 IMAGE-LEVEL EDA: ONE DOT PER TRAINING IMAGE
# ===============================================================
image_stats = data.image_statistics(train)
charts.image_summary_scatter(image_stats).show()
""")

md(r"""
### How to read this plot

- **One dot = one training image.** This is a scatter plot: horizontal and vertical
    position encode two numeric measurements for the same image.
- Moving right means greater mean brightness. Moving up means greater contrast, or a wider
    spread between dark and bright pixels.
- Color shows the source label. Dots that occupy the same area have similar summary
    measurements even when their labels differ.
- **What to notice:** the blue and orange clouds overlap substantially.
- **Why it matters:** brightness and contrast are useful for checking data quality, but
    they are not sufficient features for classifying pneumonia labels.

## 2.5 What "feature engineering" means for an image

A **feature** is a number the system uses to make or control a decision. In Session 2, we
created human-named fraud features such as transaction velocity. Here four kinds of numbers
play different roles:

| Kind of number | Plain-language meaning | Used by |
|---|---|---|
| **Raw pixel** | One location's brightness, from 0 to 255 | CNN input |
| **Prepared pixel** | The same pixel scaled and normalized consistently | CNN input |
| **Quality feature** | Mean brightness or edge variation for a technical check | Workflow gate, not the CNN |
| **Feature map** | A grid of responses produced when a learned convolution filter scans an image | Hidden CNN layers |

The quality features decide whether the ordinary model route should run. They are not
evidence of disease. The CNN learns its own internal features from examples; we will view
some after training, but they do not come with clinical names.
""")

md(r"""
## 2.6 Turn one image into a tensor

A **tensor** is an array arranged for a model. This notebook uses the shape
`channels x height x width`: one grayscale channel, 128 rows, and 128 columns.

First, pixel values are scaled from `0..255` to `0..1`. Then we center them using the
training-set mean and standard deviation. This helps optimization; it does not add medical
knowledge. Looking at test pixels to choose preprocessing would leak evaluation information
backward into training.
""")

code(r"""
# ===============================================================
# 2.6 IMAGE TO TENSOR, USING TRAINING-ONLY NORMALIZATION
# ===============================================================
pixel_mean, pixel_std = data.training_normalization(train)

print(f"Stored image : shape {example.shape}, dtype {example.dtype}")
print(f"Stored range : {example.min()} to {example.max()}")
print(f"Model tensor : shape (1, {config.IMAGE_SIZE}, {config.IMAGE_SIZE})")
print("Scaled range : 0.0 to 1.0")
print(f"Train pixels : mean {pixel_mean:.4f}, standard deviation {pixel_std:.4f}")
""")

md(r"""
## 2.7 Augmentation belongs only in training

Small translations and exposure jitter create plausible variations while the model learns.
We do **not** mirror the X-ray: laterality can matter in medical images. Validation and test
images remain unchanged so the evaluation means what it says.

Common computer-vision augmentation techniques include translation, brightness or contrast
jitter, small rotation, and small zoom/crop. A technique is appropriate only when it
represents plausible variation in the real imaging workflow and preserves the meaning of
the label. More variation is not automatically better.
""")

code(r"""
# ===============================================================
# 2.7 DETERMINISTIC EXAMPLES OF IMAGE-AUGMENTATION TECHNIQUES
# ===============================================================
augmentation_images, augmentation_table = data.augmentation_examples(example)
charts.image_gallery(
    augmentation_images,
    augmentation_table["Technique"].tolist(),
    "Common image augmentations: some are used, some require caution",
).show()
""")

md(r"""
### How to read this plot

- The first panel is the stored training image. Each later panel changes exactly one
    property so the techniques can be compared separately.
- **Augmentation** means creating plausible training variations without creating a new
    patient or changing the label.
- The model may see a different random variation each training epoch. The original file is
    not overwritten.
- Translation and brightness jitter are used in this notebook. Rotation, zoom/crop, and
    contrast are examples that could be used only after checking that their ranges are
    clinically and operationally plausible.
- Horizontal flipping is shown as a counterexample. It is common for ordinary photographs,
    but we avoid it because left-right orientation can carry meaning in medical images.
- **Why it matters:** augmentation can reduce memorization, but unrealistic transformations
    can teach the model patterns it should never see. Applying augmentation to validation or
    test images would also change the evaluation question.

The table below states what changed and whether this notebook uses the technique.
""")

code(r"""
# ===============================================================
# 2.7 WHICH TECHNIQUES DOES THIS NOTEBOOK ACTUALLY USE?
# ===============================================================
augmentation_table.style.hide(axis="index")
""")

md(r"""
## 2.8 Incoming-image quality control: should the model run?

Stage 2.7 and Stage 2.8 answer different questions:

| Stage | Question | Type of change | Result |
|---|---|---|---|
| **2.7 Training augmentation** | What mild, plausible variation should the model learn from? | Small translation and brightness jitter applied only during training | The transformed copy remains a training example with the same label. |
| **2.8 Quality stress test** | Should this incoming image be scored at all? | Deliberately severe blur, underexposure, or overexposure | A failed check stops ordinary scoring and sends the image to recapture or qualified manual handling. |

**The three severe images below are not augmentation techniques used for training.** They
simulate bad incoming images so we can test the workflow's failure path.

Our classroom gate checks only two simple technical signals:

- **Mean intensity:** is the whole image extremely dark or bright?
- **Focus score:** is there enough local pixel variation, or is the image severely blurred?

All original PneumoniaMNIST images pass these simple classroom bounds. That does **not**
prove clinical or diagnostic image quality. A real deployment would require a validated
quality process designed for its equipment, acquisition protocol, and clinical setting.
""")

code(r"""
# ===============================================================
# 2.8 CONTROLLED IMAGE-QUALITY EXAMPLES
# ===============================================================
quality_images, quality_table = evaluation.transformed_examples(example)
quality_table.style.hide(axis="index")
""")

code(r"""
quality_titles = [
    f"{row['Scenario']}<br>technical check: {row['Technical check'].lower()}"
    for _, row in quality_table.iterrows()
]
charts.image_gallery(
    quality_images,
    quality_titles,
    "Severe incoming-image failures are stopped before model scoring",
).show()
""")

md(r"""
### How to read this plot

- The first panel is the original image and passes the simple technical check. The next
    three are deliberately severe incoming-image failures and fail the check.
- Read the gallery with the table above. The table tells you **why** each image passed or
    failed and, more importantly, **what happens next**.
- **Pass:** continue to model scoring, then apply the cutoff to choose priority or standard
    review.
- **Fail:** stop ordinary scoring. Recapture the image or send it to qualified manual
    handling. `Fail` does not mean pneumonia; it means the input is outside this classroom
    model's simple quality bounds.
- **Conclusion:** we do not train on these three severe versions and we do not use their
    model scores for ordinary queue routing.

### What if we remove the quality gate?

The classifier would still return a number for severely blurred, dark, or bright images,
even though those inputs are far outside the conditions we intended to score. A numeric
output does not prove that the input was usable, and severe image changes can move scores
across the cutoff in unpredictable ways.

The gate does not improve the corrupted image or diagnose anything. Its value is
**fail-safe routing**: recognize an unusable input, stop the ordinary model path, and send
the work to a known recovery process. That operational conclusion is enough here; we do not
need to interpret classification metrics for images the gate has already rejected.

---
# 3 - Model Training

**Question:** Can a compact model learn useful ranking signal without turning a classroom
demonstration into an infrastructure project?

We begin with the easiest-looking baseline, then train one small convolutional neural
network (CNN) with fixed seeds and validation-loss checkpointing.
""")

md(r"""
## 3.1 The majority baseline exposes misleading accuracy

Because pneumonia-labeled images are the majority, a rule that sends **every image** to
priority review gets 62.5% test accuracy and 100% sensitivity. It also has 0% specificity
and prioritizes the entire queue. It does not prioritize anything.

Terms used in the baseline table:

- **Accuracy:** share of all routing decisions that match the retrospective labels.
- **Sensitivity**, also called **recall:** share of pneumonia-labeled images sent to
    priority review.
- **Specificity:** share of normal-labeled images left in standard review.
- **Precision:** share of priority-review images that carry the pneumonia label.
- **Review rate:** share of all images sent to priority review.

The always-pneumonia baseline achieves perfect sensitivity only by prioritizing 100% of
the queue. It has zero specificity and no operational ability to prioritize.
""")

code(r"""
# ===============================================================
# 3.1 ALWAYS-PNEUMONIA MAJORITY BASELINE
# ===============================================================
baseline = metrics.majority_baseline(splits["test"].labels)
pd.DataFrame([{key: baseline[key] for key in
               ("accuracy", "sensitivity", "specificity", "precision", "review_rate")}])\
  .style.format("{:.1%}").hide(axis="index")
""")

md(r"""
## 3.2 The selected architecture is deliberately small

The compact CNN contains four convolution blocks, global average pooling, and one output.
It has about 79,000 trainable parameters and runs on CPU. A larger network might improve a
benchmark, but it would also add weight downloads, runtime, and deployment complexity that
do not improve tonight's workflow lesson.

The positive class receives a balancing weight during training because it is the majority
class here. This keeps the loss from treating class prevalence as the decision policy.
""")

code(r"""
# ===============================================================
# 3.2 TRAIN ON CPU WITH A FIXED SEED
# ===============================================================
training = models.fit_small_cnn(splits)
model = training.model

print(f"trainable parameters : {models.model_parameter_count(model):,}")
print(f"epochs run           : {len(training.history)}")
print(f"best checkpoint      : epoch {training.best_epoch}")
print(f"CPU training time    : {training.runtime_seconds:.1f} seconds")
""")

md(r"""
## 3.3 See what the CNN's first learned filters produce

The precise distinction is: the CNN **learns filters**, then an image passing through those
filters **produces feature maps**. A feature map is therefore a temporary response to one
image, not a picture stored inside the model.

| First convolution setting | Value in this CNN | Plain meaning |
|---|---:|---|
| Input | `1 x 128 x 128` | One grayscale image channel |
| Number of filters | `16` | Sixteen different small patterns can be learned |
| Filter window | `3 x 3` | Each filter looks at nine neighboring pixels at a time |
| Stride | `1` | Move the window one pixel before measuring again |
| Padding | `1` pixel | Add a temporary border so the response map remains `128 x 128` |

### From one small window to one feature map

1. Each filter begins with small random numeric weights arranged in a `3 x 3` window.
2. At one image location, the filter combines that `3 x 3` patch into **one response
    number**.
3. The same filter moves one pixel at a time and repeats the calculation. Placing all of
    those response numbers in their image locations creates **one feature map**.
4. During training, the final model output is compared with the dataset label. The error is
    sent backward through the CNN and slightly adjusts the filter weights. Repeating this
    across many images and epochs turns the random filters into learned filters.
5. After training, 16 learned filters applied to one image produce 16 feature maps. The
    gallery below shows the first six.

This sliding calculation happens whenever the CNN processes an image, during both training
and later scoring. It is not a separate "sliding-window training" method; **training** is
the part that updates the filter weights from repeated errors.
""")

code(r"""
# ===============================================================
# 3.3 EARLY LEARNED FEATURES FROM THE TRAINED CNN
# ===============================================================
first_convolution = model.features[0]
displayed_map_count = 6
print(
    f"First convolution: {first_convolution.out_channels} filters | "
    f"window {first_convolution.kernel_size[0]} x {first_convolution.kernel_size[1]} | "
    f"stride {first_convolution.stride[0]} | padding {first_convolution.padding[0]}"
)

learned_maps = explain.early_feature_maps(model, example, count=displayed_map_count)
learned_titles = ["Original image"] + [
    f"Feature map {number}" for number in range(1, displayed_map_count + 1)
]
charts.image_gallery(
    [example, *learned_maps], learned_titles,
    "One image produces 16 first-layer maps; the first six are shown",
).show()
""")

md(r"""
### How to read this plot

- The first panel is the input image. The other six panels are the response maps from six
    of the first layer's 16 learned `3 x 3` filters.
- Each map still has `128 x 128` locations because stride `1` and padding `1` preserve the
    image height and width.
- Within one map, brighter areas mean that filter produced a stronger positive response at
    those locations. Brightness is not disease probability or original X-ray brightness.
- Each map is rescaled separately so its pattern is visible. Compare **where** a filter
    responds within a panel; do not compare brightness levels between different panels.
- The filters learned numeric patterns from training errors. We did not draw them, assign
    them clinical names, or tell any filter to find a particular anatomy.
- **Why it matters:** CNN feature engineering is mostly learned inside the network. These
    early maps can help us inspect behavior, but they are not clinical findings.
""")

code(r"""
# ===============================================================
# 3.4 TRAINING AND VALIDATION LOSS
# ===============================================================
charts.training_history(training.history).show()
""")

md(r"""
### How to read this plot

- The horizontal axis is the **epoch**, one complete pass through the training images.
- The vertical axis is **loss**, the numerical penalty the optimizer tries to reduce.
    Lower is better, but loss is not the same as accuracy or clinical harm.
- The training line measures fit on images used to update the model. The validation line
    measures fit on separate images that do not update the model.
- **Overfitting** would appear when training loss keeps falling while validation loss rises
    persistently: the model improves on familiar data but worsens on unseen data.
- Small up-and-down changes are normal. We save the epoch with the lowest validation loss
    and restore that checkpoint after training.

Neither curve tells us whether the model is safe for a workflow. We still need an operating
policy, an untouched test evaluation, failure analysis, and human authority.
""")

md(r"""
---
# 4 - Model Validation and Operating Policy

**Question:** At what score should the workflow prioritize review, and what happens when
the frozen policy reaches untouched test patients?

Earlier stages introduced the **idea** of a cutoff so we could describe the workflow. No
numeric cutoff has been selected yet. That happens here in three steps:

1. Use validation images to choose the cutoff.
2. Freeze the cutoff so the policy cannot change after seeing test results.
3. Apply the frozen policy once to the untouched test split.

## 4.1 Choose the cutoff on validation data

The model supplies a score; people define what action that score triggers. The saved run
below selects `0.748` as the cutoff. Read that number as a routing rule:

| Incoming study | Workflow route | What happens next |
|---|---|---|
| Technical-quality check fails | **Quality hold** | Stop ordinary scoring; recapture or use qualified manual handling |
| Quality passes and score is **0.748 or higher** | **Priority review** | A radiologist reads it earlier in the queue |
| Quality passes and score is **below 0.748** | **Standard review** | A radiologist still reads it in the standard queue |

**Nothing is automatically approved, diagnosed, or cleared.** The cutoff changes queue
position, not whether a human reads the image. Also, `0.748` is a model score, not a proven
74.8% probability of pneumonia; this model's scores were not calibrated as probabilities.

### Measures used to choose and inspect the policy

In this plot, **percentage**, **rate**, and **share** all mean "a part of a group out of the
whole group." The group changes by measure, so always ask: **percentage of which images?**

| Measure | Group used as 100% | Question answered |
|---|---|---|
| **Sensitivity** | All pneumonia-labeled images | What percentage enters priority review? |
| **Specificity** | All normal-labeled images | What percentage remains in standard review? |
| **Priority-review percentage (workload)** | All images | What percentage of the complete queue enters priority review? |

The workload measure is necessary. A policy can reach 100% sensitivity simply by sending
every image to priority review, but then it has not prioritized anything. The priority-review
percentage reveals that operational cost; it is not another accuracy measure.

For this exercise, the validation objective is at least 90% sensitivity. Among the
candidate cutoffs that meet that target, we select the highest one, which sends the fewest
validation images to priority review. This is an educational policy choice, not a
clinically approved standard. Here **cutoff** and **threshold** mean the same thing.

The 90% target means: **send at least 9 out of every 10 pneumonia-labeled validation images
to the priority queue.** It does not mean that only 90% of all images receive human review;
every image still requires radiologist interpretation.
""")

code(r"""
# ===============================================================
# 4.1 CHOOSE THE POLICY ON VALIDATION DATA ONLY
# ===============================================================
validation_scores = models.predict_scores(model, splits["validation"].images)
validation_policy = metrics.select_threshold(
    splits["validation"].labels,
    validation_scores,
    config.TARGET_VALIDATION_SENSITIVITY,
)
threshold = float(validation_policy["threshold"])
metrics.policy_summary(
    validation_policy, config.TARGET_VALIDATION_SENSITIVITY
).style.hide(axis="index")
""")

code(r"""
# ===============================================================
# 4.2 SEE THE TRADE-OFF AROUND THE SELECTED CUTOFF
# ===============================================================
policy_sweep = metrics.threshold_sweep(
    splits["validation"].labels, validation_scores, threshold
)
charts.threshold_policy(policy_sweep, threshold).show()
""")

md(r"""
### How to read this plot

- The horizontal axis is the candidate cutoff. Moving right requires a higher score before
    an image enters priority review.
- The orange, blue, and gray lines correspond to the three measures defined immediately
    above. Their denominators differ, so they should not be added together.
- At cutoff `0`, every score is at or above the cutoff. Sensitivity and the priority-review
    percentage are therefore `100%`, while specificity is `0%`: the entire queue is marked
    priority, so the policy does not prioritize anything.
- Near cutoff `1`, almost no image reaches priority review. Sensitivity and priority
    workload move toward `0%`, while specificity moves toward `100%`.
- The dashed vertical line is the selected cutoff. Lowering it usually increases
    sensitivity and priority workload. Raising it usually increases specificity and lowers
    workload, but risks leaving more pneumonia-labeled images in standard review.
- **Conclusion:** the selected `0.748` cutoff is a compromise. It meets the validation
    target of prioritizing at least 90% of pneumonia-labeled images without labeling every
    image as priority. It does not decide who is sick; it decides which human-review queue
    receives the image first.

## 4.3 Freeze the cutoff, then touch the test split once

The test split did not choose the architecture, checkpoint, or threshold. It now estimates
how the complete model-plus-policy behaves on source-held-out patients.

For this retrospective benchmark, labels are visible after scoring. A live queue would not
know the outcome before interpretation.
""")

code(r"""
# ===============================================================
# 4.3 FINAL TEST EVALUATION AT THE VALIDATION-SELECTED CUTOFF
# ===============================================================
test = splits["test"]
test_scores = models.predict_scores(model, test.images)
test_result = metrics.evaluate(test.labels, test_scores, threshold)

print(f"Untouched test images : {len(test.labels):,}")
print(f"Frozen cutoff         : {threshold:.3f}")
""")

code(r"""
# ===============================================================
# 4.4 THE COMPLETE CONFUSION MATRIX
# ===============================================================
charts.confusion_matrix(test_result).show()
""")

md(r"""
### How to read this plot

- Rows show the retrospective **dataset label**. Columns show the **queue action** produced
    by the frozen cutoff.
- Each image lands in one cell: **TP** is pneumonia label + priority review, **FN** is
    pneumonia label + standard review, **FP** is normal label + priority review, and
    **TN** is normal label + standard review.
- The table below calculates sensitivity, specificity, and priority-review share from these
    four counts. It also introduces precision and broader ranking summaries.
- **Why it matters:** the four cells expose consequences hidden by a single accuracy
    number. Standard review does not mean cleared, and a false positive still consumes
    limited priority capacity.

The table below substitutes this run's counts into each calculation.
""")

code(r"""
# ===============================================================
# 4.4 METRICS CALCULATED FROM THE SAME FOUR CELLS
# ===============================================================
metrics.metric_summary(test_result).style.hide(axis="index")
""")

md(r"""
### Additional metric terms in the table

- **Precision** asks what share of the priority queue carried the pneumonia label. Unlike
    sensitivity, its denominator is the priority queue rather than all pneumonia labels.
- **Balanced accuracy** averages sensitivity and specificity so both labels receive equal
    weight even when the dataset is imbalanced.
- **ROC AUC** summarizes ranking across all possible cutoffs. `0.5` is random ranking and
    `1.0` is perfect ranking on the evaluation data. It does not measure queue delay or
    patient outcomes.
- **Average precision** summarizes the precision-recall trade-off across cutoffs. It is
    useful when attention is focused on the positive class, but it still does not choose the
    operating cutoff for us.

No single metric contains the whole decision.
""")

code(r"""
# ===============================================================
# 4.5 SCORE DISTRIBUTIONS AND THE FROZEN CUTOFF
# ===============================================================
charts.score_distribution(test.labels, test_scores, threshold).show()
""")

md(r"""
### How to read this plot

- The horizontal axis is the model score from `0` to `1`; the vertical axis is the number
    of test images in each score interval.
- Blue bars are normal-labeled images. Orange bars are pneumonia-labeled images. Where the
    colors overlap, similar scores occur for both labels, so some errors are unavoidable.
- The dashed line is the frozen cutoff. Bars to its right enter priority review; bars to
    its left remain in standard review.
- A score such as `0.80` means a higher ranking score than `0.40`; it is not automatically
    an 80% probability of pneumonia because we did not calibrate it as a probability.
- **Why it matters:** this plot shows why changing the cutoff changes both missed labels and
    review workload.

## 4.6 Inspect cases near the boundary

These retrospective examples sit closest to the cutoff in each confusion-matrix cell.
They show where small score differences become different queue actions. The thumbnails do
not establish why a dataset label is correct or why the model erred.
""")

code(r"""
# ===============================================================
# 4.6 REPRESENTATIVE TRUE AND FALSE CASES
# ===============================================================
case_indices, case_titles = evaluation.representative_cases(
    test.labels, test_scores, threshold, per_group=2
)
charts.image_gallery(test.images[case_indices], case_titles,
                     "Retrospective cases nearest the policy cutoff").show()
""")

md(r"""
### How to read this plot

- Each title names the confusion-matrix outcome and displays the model score.
- These examples are selected because their scores are closest to the cutoff within each
    outcome group. They are **boundary cases**, not random or representative patients.
- Compare false positives with false negatives to see that nearly identical scores can
    produce different workflow consequences when they fall on opposite sides of the cutoff.
- Do not inspect the thumbnails as untrained radiologists. The gallery explains model and
    policy behavior, not why the source label is medically correct.
- **Why it matters:** reviewing individual errors can reveal patterns hidden by aggregate
    metrics, but a few examples cannot estimate overall performance.
""")

md(r"""
---
# 5 - Model Prediction and Handoff

**Question:** Can another system reproduce the score, apply the policy, preserve the
quality failure path, and show who retains authority?

This stage creates the same three-way routing used by the app:

1. **Quality hold** - recapture or qualified manual handling
2. **Priority review** - earlier radiologist review
3. **Standard review** - standard radiologist review
""")

code(r"""
# ===============================================================
# 5.1 BUILD A RETROSPECTIVE TEST QUEUE
# ===============================================================
manifest = data.sample_manifest(test)
manifest["model_score"] = test_scores
manifest["queue_action"] = np.where(
    test_scores >= threshold, "priority review", "standard review"
)
manifest.sort_values("model_score", ascending=False).head(10)\
  .style.format({"model_score": "{:.3f}"}).hide(axis="index")
""")

md(r"""
## 5.2 Score one packaged example

The output is deliberately split into three statements: model estimate, policy test, and
workflow action. The dataset label is shown only because this is an unchanged historical
test example.
""")

code(r"""
# ===============================================================
# 5.2 MODEL SCORE -> POLICY -> QUEUE ACTION
# ===============================================================
sample_index = int(np.argsort(np.abs(test_scores - threshold))[0])
sample_score = float(test_scores[sample_index])
sample_action = "Priority review" if sample_score >= threshold else "Standard review"

print(f"sample          : test-{sample_index:04d}")
print(f"dataset label   : {config.CLASS_NAMES[int(test.labels[sample_index])]}")
print(f"model score     : {sample_score:.3f}")
print(f"policy cutoff   : {threshold:.3f}")
print(f"workflow action : {sample_action} - qualified interpretation still required")
""")

md(r"""
## 5.3 Show regions that influenced the score

### The plain-language idea

The CNN does not produce a sentence explaining its decision. Grad-CAM is a separate
**attribution method** that asks a narrower question:

> **Which broad image locations had the strongest effect on this model score?**

It builds the colored map in four steps:

1. The CNN scans the image and creates many internal pattern maps.
2. Grad-CAM measures how strongly each map affected the pneumonia-label score. In this
    context, a **gradient** is simply a measure of how sensitive the score is to a change.
3. It combines those pattern maps into one influence map.
4. It enlarges that map and lays it over the original X-ray.

### How to read this plot

- **Little or no warm color:** this location had less influence on this particular score.
- **Orange and yellow:** this location had more influence on this particular score.
- **The color is not probability:** yellow does not mean a 100% chance of pneumonia.
- **The color is relative:** compare locations within this image, not colors across patients.

Our final CNN map is only **16 x 16 cells** before it is enlarged to 128 x 128 pixels.
That is why the colored regions are broad and blurry. The map cannot support a precise
box, border, measurement, or lesion location.
""")

code(r"""
# ===============================================================
# 5.3 GRAD-CAM MODEL-INFLUENCE OVERLAY
# ===============================================================
sample_image = test.images[sample_index]
heatmap, explained_score = explain.grad_cam(model, sample_image)
influence_overlay = explain.overlay(sample_image, heatmap)
charts.image_gallery(
    [sample_image, influence_overlay],
    [f"Original image<br>model score {explained_score:.3f}",
     "Warm colors = stronger model influence"],
    "Grad-CAM shows score influence, not a pneumonia location",
).show()
""")

md(r"""
### What can we conclude from this picture?

| Supported by this demonstration | Not supported by this demonstration |
|---|---|
| "These broad regions influenced the model score more." | "Pneumonia is located here." |
| "The model may be using an unexpected part of the image." | "This region caused the patient's condition." |
| "We should investigate whether the model learned a shortcut." | "The heatmap proves the model reasoned like a doctor." |
| "The score and heatmap describe this packaged image." | "The system is safe for clinical use." |

A radiologist may identify and describe an image finding using clinical training, a
diagnostic-quality image, prior studies, and patient context. That professional
interpretation is different from this heatmap. PneumoniaMNIST supplies whole-image labels
only; it does not supply radiologist-drawn boxes or masks against which we could validate
localization.

**Useful classroom sentence:** "The model score was influenced most by these broad image
regions. The map does not tell us whether those regions contain pneumonia."
""")

md(r"""
## 5.4 Hand the exact measured system to the app

Five artifacts leave the notebook:

| Artifact | Contract |
|---|---|
| `model.pt` | The fitted CNN weights and training normalization |
| `model_card.json` | Intended use, measured results, population, and limitations |
| `operating_policy.json` | Quality gate, validation-selected cutoff, and queue routes |
| `evaluation.json` | Training curve, baseline, final metrics, and technical stress-test evidence |
| `sample_manifest.parquet` | Stable test sample IDs, scores, actions, and retrospective labels |

The service imports the same architecture and preprocessing code. It does not copy them.
""")

code(r"""
# ===============================================================
# 5.4 EXPORT THE MODEL, EVIDENCE, POLICY, AND SAMPLE MANIFEST
# ===============================================================
sizes = handoff.export(
    training, splits, validation_scores, test_scores,
    validation_policy, test_result,
)
for name, size in sizes.items():
    print(f"  {name:<28} {size}")
""")

code(r"""
# ===============================================================
# 5.5 RELOAD AND PROVE PREDICTION IDENTITY
# ===============================================================
identity = handoff.verify(splits)
print(identity)
assert identity["decision_changes"] == 0
assert identity["confusion_count_drift"] == 0
print("\nOK - the model on disk is the model that was measured.")
""")

md(r"""
## 5.6 The handoff ends at human authority

```text
image quality -> model score -> triage policy -> queue position
                                              -> radiologist interpretation
                                              -> clinician diagnosis and treatment
```

The classroom model changes queue position. It does not replace interpretation, combine
the whole patient record, make a diagnosis, recommend treatment, or accept real patient
images.
""")

md(r"""
---
## The five stages, and who must be involved

| Stage | What happened | Who is needed |
|---|---|---|
| **1 - Data Ingestion** | Source, checksum, labels, population, and splits were verified | Data team **and clinical/data stewards** |
| **2 - Image EDA and Preparation** | Pixels, augmentation, and the quality failure path were defined | ML team **and imaging workflow experts** |
| **3 - Model Training** | A compact reproducible CNN was fit on CPU | ML team |
| **4 - Model Validation** | A validation objective became a cutoff; aggregate and boundary errors were inspected | ML team **and operational/clinical owners** |
| **5 - Model Prediction** | The score became a bounded queue action with reproducible artifacts | Product team, radiologists, clinicians, safety owners |

**The model is one component. The healthcare system is the thing we have to design.**
""")

notebook["cells"] = cells
notebook.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
notebook.metadata["language_info"] = {"name": "python", "version": "3.11"}
nbf.write(notebook, OUTPUT)
print(f"wrote {OUTPUT} with {len(cells)} cells")