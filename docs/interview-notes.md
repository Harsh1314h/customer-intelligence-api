# Interview Notes

Short answers to the design questions this project usually gets asked. Each section is
"what I chose, why, and what I traded away".

---

## Why FastAPI?

**The requirement:** serve three ML models over HTTP with a contract that another team
(frontend, CRM, batch job) can code against without asking me questions.

**Why FastAPI specifically:**

- **The request schema is the validation and the docs.** `app/schemas.py` defines
  `CustomerFeatures` once, and that single definition rejects bad input *before* any
  model code runs and generates the OpenAPI spec at `/openapi.json` and the Swagger UI at
  `/docs`. With Flask I would have written the validation and the docs separately and
  they would have drifted.
- **Bad input fails at the edge, not inside NumPy.** A negative `recency_days` returns a
  `422` naming the exact field. Without schema validation it would reach scikit-learn and
  either produce a silently wrong probability or raise a `500` with a stack trace that
  tells the caller nothing.
- **ASGI/async gives headroom.** The prediction call itself is CPU-bound and synchronous,
  but running on Uvicorn means concurrent requests queue at the event loop rather than
  blocking a thread-per-request worker pool.

**Trade-off:** FastAPI is a younger ecosystem than Flask/Django, and Pydantic v2 was a
breaking migration. For a service whose whole job is "validated JSON in, validated JSON
out", that cost is worth paying.

**What I'd say if pushed:** for a single-model service behind an internal load balancer,
Flask would have been fine. The value shows up at three endpoints and a shared feature
schema — that is where hand-written validation starts to rot.

---

## Why Docker?

**The problem it actually solved:** the models are trained by scikit-learn `1.5.0` and
serialized with `joblib`. A joblib artifact is only reliably loadable by a compatible
scikit-learn/NumPy build. "Works on my machine" is not a joke here — a version drift
between the training box and the serving box produces either a hard unpickling error or,
worse, a model that loads and predicts incorrectly.

Pinning `requirements.txt` and baking it into an image makes the serving environment
reproducible and identical from laptop to ECS.

**Concrete design choices in the `Dockerfile`:**

- `python:3.11-slim` — 3.11 because several ML wheels (XGBoost, SciPy) lag on newer
  Python releases; `slim` to keep the image small.
- `COPY requirements.txt` and `pip install` **before** `COPY app` — dependency install is
  the slow layer, so putting it above the source means a code change rebuilds in seconds
  instead of re-installing the whole ML stack.
- **Non-root user (`apiuser`).** A container running as root that gets RCE'd is a much
  worse day than one running as an unprivileged user. Verified with
  `docker exec <container> whoami` → `apiuser`.
- **Model artifacts are *not* baked into the image.** They arrive at runtime from a
  volume mount locally, or from S3 in production via `CI_MODEL_ARTIFACT_URI`. This is the
  important one — see the next section.

**Trade-off:** the image is ~2.1 GB because of the ML dependency stack. That is slow to
push and slow to cold-start. If cold-start mattered I would move to a multi-stage build,
drop `mlflow` from the runtime image (it is only needed for training), and consider ONNX
runtime instead of shipping all of scikit-learn.

---

## Why are models loaded from S3 instead of baked into the image?

This is the decision I'd most want to defend, because it looks like extra work.

**If models are baked into the image:** retraining requires a rebuild, a repush of a 2 GB
image, and a full redeploy. Model version and code version are welded together — you
cannot roll back a bad model without rolling back the code.

**With `CI_MODEL_ARTIFACT_URI` pointing at S3:** `ModelRegistry.load()` downloads the
artifacts at startup (`app/ml/artifacts.py`). Shipping a new model is an S3 upload plus a
service restart. Code and model have independent lifecycles, which is what you want,
because they change on completely different cadences.

`app/ml/artifacts.py` deliberately handles three schemes behind one config value —
`s3://`, `gs://`, and a plain local directory — so the same serving code runs unchanged
on a laptop, in CI, and on ECS.

**Trade-off:** startup is slower (a ~7.5 MB download) and the service now has a hard
runtime dependency on S3 being reachable and the task role having `s3:GetObject`. If S3
is down, the service will not start. For a stateless service behind an ALB that is
acceptable; for something needing to boot during an S3 outage it would not be.

---

## Why MLflow?

Training is not deterministic across changes to hyperparameters, snapshot counts, or the
dataset. Without tracking, "the ROC AUC was about 0.79 on the run where I used 8
snapshots — or was it 6?" becomes unanswerable within a week.

`scripts/train.py` logs parameters (`prediction_window_days`, `n_clusters`,
`svd_components`, row counts), metrics (ROC AUC, average precision, accuracy, silhouette,
recommender size), and the artifacts themselves to an MLflow run. That makes runs
comparable side by side in the UI at `http://127.0.0.1:5000`, and it makes the numbers in
this repo's README auditable rather than remembered.

**Trade-off:** for this project MLflow uses the local-filesystem backend (`mlruns/`),
which is single-machine and not shared. A team would need a tracking server backed by a
database plus S3 artifact storage. I chose not to build that because it would be
infrastructure with no second user.

**Why not just log to a CSV?** The artifact logging is the part that matters — the run
records the exact model files that produced those metrics, so a metric can always be
traced back to a specific artifact.

---

## Why time-based churn labels? (the most important ML decision here)

**The naive approach and why it is broken:** the obvious way to label churn is
"`recency_days > 90` means churned". This produces a model with a beautiful ROC AUC —
near 1.0 — and zero real predictive value, because `recency_days` is also an input
feature. The model has simply learned to read the label off the feature. This is target
leakage, and it is the single most common way a churn model looks great offline and
does nothing in production.

**What this project does instead** (`build_time_based_churn_dataset` in
`app/ml/features.py`):

1. Pick 8 historical cutoff dates across the dataset's time span.
2. At each cutoff, build a customer's features using **only transactions strictly before
   that cutoff**.
3. Look **forward** into the next 90 days (`prediction_window_days`) and label the
   customer `churned = 1` if they made no purchase in that window.
4. Require at least 90 days of prior history (`min_history_days`) so features are not
   computed from one or two orders.

The features and the label are drawn from disjoint time periods, so nothing about the
future leaks into the inputs. This yields 30,823 training rows from 5,281 customers —
more data than one row per customer, because each customer contributes an example at
every cutoff where they qualify.

**The honest result:** ROC AUC `0.7916`. That is a *lower* number than the leaky version
would produce, and it is the correct number. Being able to explain why the lower number
is the better one is the whole point of this section.

`tests/test_features.py::test_time_based_churn_dataset_uses_future_return_behavior`
pins this behavior so a future refactor cannot quietly reintroduce the leak.

**Remaining limitation I'd raise before anyone asks:** the snapshots overlap in time and
the same customer appears in multiple rows, so training examples are not fully
independent. The train/test split is random rather than a strict time-based holdout,
which likely makes the reported AUC slightly optimistic. A stricter evaluation would
train on early cutoffs and test only on the latest one.

---

## Why an ensemble for churn, and why those two models?

`ChurnEnsemble` (`app/ml/churn.py`) is a weighted blend: XGBoost at `0.65`, a
scikit-learn `MLPClassifier` at `0.35`.

- **XGBoost** carries the majority weight because gradient-boosted trees are the strong
  default on small-to-medium tabular data. They handle non-linear thresholds
  ("risk jumps once recency passes ~60 days") and feature interactions natively, and need
  no feature scaling.
- **The MLP** contributes a different inductive bias — smooth interpolation instead of
  axis-aligned splits — so its errors are not perfectly correlated with the trees'. That
  decorrelation is the only reason averaging helps at all.
- **Why 0.65/0.35 and not 50/50?** The trees are the stronger single model on this data;
  the network is a correction term, not an equal partner.

The code falls back to `HistGradientBoostingClassifier` if XGBoost is unavailable, so the
service still trains in a constrained environment.

**Honest caveat:** the weights are a judgement call, not a tuned result — I did not run a
proper weight sweep or stacking meta-learner. With more time, that is the first thing I
would fix, and I would expect the gain over XGBoost alone to be small.

---

## Why K-Means for segmentation, and how are clusters given business names?

Segmentation has no ground-truth labels, so this is genuinely unsupervised. K-Means with
`k=4` on standard-scaled RFM-style features is the conventional, explainable choice — and
explainability matters more than cluster quality here, because a marketing team has to
act on the output.

**Scaling is not optional.** `monetary` spans thousands and `frequency` spans single
digits; without `StandardScaler` in the pipeline, K-Means' Euclidean distance would be
almost entirely driven by `monetary`. The `Pipeline` guarantees the same scaling is
applied at training and at inference.

**Naming the clusters** (`label_clusters` in `scripts/train.py`): raw cluster IDs are
meaningless to a business user, so the code computes each cluster's feature means and
assigns names by rule — highest monetary/frequency → `high-value`; highest recency with
low frequency → `dormant`; lowest tenure → `new`; whatever remains → `at-risk`. This is
deterministic, so cluster `0` means the same thing across retrains.

The API also returns `distance_to_centroid`, which is a useful honesty signal: a large
distance means the customer sits between clusters and the label should be trusted less.

**Trade-off:** `k=4` was chosen for interpretability, not by optimizing the silhouette
score. The silhouette is `0.4061` — moderate cluster separation, which is typical and
honest for real retail behavior data. Real customer behavior is a continuum, not four
tidy groups; the segments are a useful simplification, not a discovered truth.

---

## Why collaborative filtering via Truncated SVD?

The dataset has customer-product purchase history and nothing else — no product images,
no text embeddings, no session logs. Collaborative filtering is what that data supports.

- The interaction matrix is 5,878 customers × 4,631 products and is extremely sparse, so
  it is built as a `scipy.sparse` matrix rather than dense.
- Quantities are `log1p`-transformed so a single bulk order of 500 units does not
  dominate the signal.
- `TruncatedSVD` with 50 components factorizes it into latent user and item vectors.
  Truncated SVD (not plain PCA) because it operates on sparse matrices directly without
  mean-centering, which would destroy sparsity and blow up memory.

**The cold-start problem, and how it degrades:** `_score_items` has three tiers —

1. Known customer → score from their learned latent vector.
2. Unknown customer but recognizable `recent_product_ids` → build a profile from the
   mean of those item vectors (content-free item-item similarity).
3. Nothing recognizable → fall back to global popularity.

So `/recommend` **always** returns results and never errors on an unknown customer.
Verified: an unknown ID returns the global top sellers.
`tests/test_recommender.py` pins this.

**Trade-off:** no evaluation metric. There is no precision@k or recall@k here, because
offline recommendation evaluation on implicit purchase data is genuinely hard to do
honestly and the real answer is an A/B test. I would rather say "unevaluated" than quote
a metric I do not trust.

---

## Why ECS Express Mode, not App Runner / Lambda / EKS?

**Why not App Runner (the original plan):** AWS stopped accepting new App Runner
customers after **April 30, 2026**. The project was designed for it and had to pivot. ECS
Express Mode is the closest replacement — it provisions the ALB, target groups, security
groups, and autoscaling for you from a single API call, which is exactly the App Runner
value proposition on top of ECS.

**Why not Lambda:** the container is ~2.1 GB with a ~7.5 MB model download at startup.
Lambda's cold starts would be brutal, and the model would reload on every cold container.
A long-lived process that loads models once at startup is the right shape for this
workload.

**Why not plain ECS Fargate or EKS:** both mean hand-writing task definitions, an ALB,
listeners, target groups, and security groups — or a Kubernetes control plane at \$70+/month.
That is a lot of YAML to serve three endpoints.

**Why ECR:** ECS pulls from it with IAM auth rather than registry credentials, and it is
in-region so pulls are fast and free of egress cost.

**Deployment behavior worth knowing:** Express Mode defaults to a **canary rollout** — 5%
of traffic with a 3-minute bake. At `desiredCount=1`, 5% of one task rounds to zero, so
the service legitimately shows **0 running tasks for several minutes** before promoting
to 100%. Total time from `create` to serving traffic was about 6 minutes. This looks like
a stuck deploy and is not one.

**The cost decision:** the service was deployed, verified end-to-end against the live URL
(`/health` with `demo_mode: false` and all three models loaded from S3, `/docs`, and a
real `/predict/churn` returning `0.1117`), and then **deliberately torn down**. The ALB
alone is roughly \$16–18/month to keep an idle portfolio demo alive. Evidence was captured
instead, and `docs/architecture.md` documents the exact redeploy command. Knowing what
to leave running is part of the engineering.

---

## What would you do differently / what is missing?

Worth volunteering before being asked:

- **No authentication.** The endpoints are open. Production needs an API key or JWT, plus
  per-caller rate limiting.
- **No structured logging or tracing.** There is no request ID, no latency histogram, no
  per-endpoint error rate. This is the first thing I would add for anything real.
- **No model monitoring.** Nothing detects feature drift or a collapse in the churn score
  distribution. A model that silently degrades is the standard failure mode of deployed ML.
- **No stricter time-based holdout.** See the churn-label caveat above — the reported AUC
  is probably slightly optimistic.
- **No retraining schedule.** Training is manual. It should be a scheduled job that
  retrains, gates on a metric threshold, and only then promotes artifacts to S3.
- **Ensemble weights are untuned.** 0.65/0.35 is a judgement call.
- **Image is 2.1 GB.** A multi-stage build dropping MLflow from the runtime image would
  cut it substantially.

---

## The 60-second version

> It is a FastAPI service exposing three ML endpoints — churn, segmentation, and
> recommendations — trained on about 1 million real retail transactions. The part I care
> about most is the churn labeling: instead of labeling churn from current inactivity,
> which leaks the target into the features, it builds features from a historical cutoff
> and labels from whether the customer actually returned in the following 90 days. That
> gives an honest ROC AUC of 0.79 rather than a fake 0.99. Models are trained offline,
> tracked in MLflow, and loaded at startup from S3 rather than baked into the image, so
> models and code deploy independently. It is containerized, tested in CI, and was
> deployed live on AWS ECS Express Mode and verified end-to-end — then torn down,
> because leaving an idle load balancer running for a portfolio demo costs about \$17 a
> month and the evidence is captured.
