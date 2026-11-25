"""Cheap link detector (Amendment 5b): does a paper's text state a link between concepts A and B?

Masks mentions of A and B as [A] and [B], then combines TF-IDF n-grams of the masked text with
structural features, and fits a logistic regression. The threshold is chosen by cross-validation on
the training data only (maximise F1 subject to precision >= 0.90).

    python -m discovery.link_detector train          # J4 (templates) and J5 (templates + weak + v1 real)
    python -m discovery.link_detector predict --set selection
    python -m discovery.link_detector grouped_cv     # C05: CV grouped by concept pair (frozen models untouched)
"""
from __future__ import annotations

import argparse
import json
import pickle
import re

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, StratifiedKFold

from .study import DATA, RESULTS, jload

STOP = {"of", "and", "the", "in", "on", "for", "to", "a", "an", "with", "by"}
CUE = re.compile(r"\b(effect|impact|affect|influenc|determin|predict|associat|relationship|relation|link|caus|"
                 r"increas|decreas|reduc|lead|driv|explain|using|use|appl|model|measur|estimat|forecast|optimi)", re.I)
MODELS = DATA / "link_detectors.pkl"


def _stem(w: str) -> str:
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _same(x: str, y: str) -> bool:
    """Loose token match: equal, or one is a prefix of the other differing by <= 2 chars (tax/taxe, analys/analyz)."""
    if x == y:
        return True
    if min(len(x), len(y)) < 4:
        return False
    return (x.startswith(y) or y.startswith(x)) and abs(len(x) - len(y)) <= 2


def _content(c: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", re.sub(r"\(.*?\)", " ", c.lower())) if w not in STOP]


def find_mentions(text: str, concept: str) -> list[tuple[int, int]]:
    """Token spans where all content words of the concept occur within a short window."""
    toks = re.findall(r"[A-Za-z0-9]+", text)
    st = [_stem(t) for t in toks]
    cw = _content(concept)
    if not cw:
        return []
    spans, win = [], len(cw) + 2
    for i in range(len(st)):
        if not any(_same(st[i], c) for c in cw):
            continue
        window = st[i:i + win]
        if all(any(_same(t, c) for t in window) for c in cw):
            j = max(k for k in range(len(window)) if any(_same(window[k], c) for c in cw))
            spans.append((i, i + j + 1))
    return spans


def mask(text: str, a: str, b: str) -> tuple[str, dict]:
    toks = re.findall(r"[A-Za-z0-9]+|[.!?;,]", text)
    plain = " ".join(t for t in toks)
    labels = [None] * len(toks)
    for name, concept in (("[A]", a), ("[B]", b)):
        word_idx = [i for i, t in enumerate(toks) if re.match(r"[A-Za-z0-9]", t)]
        words = [toks[i] for i in word_idx]
        for s, e in find_mentions(" ".join(words), concept):
            for k in range(s, e):
                if labels[word_idx[k]] is None:
                    labels[word_idx[k]] = name
    out, prev = [], None
    for t, l in zip(toks, labels):
        if l:
            if prev != l:
                out.append(l)
            prev = l
        else:
            out.append(t.lower()); prev = None
    masked = " ".join(out)
    feats = structural(masked)
    return masked, feats


def structural(masked: str) -> dict:
    sents = [s.split() for s in re.split(r"\s[.!?]\s?", masked) if s.strip()]
    has_a = any("[A]" in s for s in sents); has_b = any("[B]" in s for s in sents)
    same = [s for s in sents if "[A]" in s and "[B]" in s]
    dmin, cue_between, listy = 99, 0, 0
    for s in same:
        ia = [i for i, t in enumerate(s) if t == "[A]"]; ib = [i for i, t in enumerate(s) if t == "[B]"]
        for x in ia:
            for y in ib:
                lo, hi = min(x, y), max(x, y)
                dmin = min(dmin, hi - lo)
                between = s[lo + 1:hi]
                if any(CUE.match(w) for w in between):
                    cue_between = 1
                if hi - lo <= 2 and all(w in {"and", ",", "or", ";"} for w in between):
                    listy = 1
        if any(CUE.match(w) for w in s):
            cue_between = max(cue_between, 0.5)
    return {"has_both": float(has_a and has_b), "same_sentence": float(bool(same)),
            "min_dist": float(min(dmin, 30)) / 30.0, "cue_between": float(cue_between),
            "list_pattern": float(listy), "n_same": float(len(same))}


FEATS = ["has_both", "same_sentence", "min_dist", "cue_between", "list_pattern", "n_same"]


def featurize(rows, vec=None):
    masked, dense = [], []
    for r in rows:
        m, f = mask(r["text"], r["a"], r["b"])
        masked.append(m); dense.append([f[k] for k in FEATS])
    if vec is None:
        vec = TfidfVectorizer(ngram_range=(1, 3), min_df=2, max_features=50000, token_pattern=r"\[[AB]\]|[a-z0-9]+")
        X = vec.fit_transform(masked)
    else:
        X = vec.transform(masked)
    return sparse.hstack([X, sparse.csr_matrix(np.array(dense) * 3.0)]).tocsr(), vec


def pick_threshold(y, p, min_precision=0.90):
    best, best_f1 = 0.5, -1
    for t in np.linspace(0.05, 0.95, 91):
        pred = p >= t
        tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
        if tp == 0:
            continue
        prec, rec = tp / (tp + fp), tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec)
        if prec >= min_precision and f1 > best_f1:
            best, best_f1 = float(t), f1
    return best, best_f1


def train_one(rows, seed=0):
    y = np.array([r["label"] for r in rows])
    cv_p = np.zeros(len(rows))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(rows, y):
        Xtr, vec = featurize([rows[i] for i in tr])
        Xte, _ = featurize([rows[i] for i in te], vec)
        m = LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced").fit(Xtr, y[tr])
        cv_p[te] = m.predict_proba(Xte)[:, 1]
    thr, f1 = pick_threshold(y, cv_p)
    X, vec = featurize(rows)
    model = LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced").fit(X, y)
    pred = cv_p >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    cv = {"n": len(rows), "threshold": thr, "cv_f1": f1, "cv_precision": tp / max(1, tp + fp), "cv_recall": tp / max(1, tp + fn)}
    return {"vec": vec, "model": model, "threshold": thr, "cv": cv}


def grouped_cv() -> dict:
    """Review finding C05: row-wise CV lets the same concept pair (and near-identical template text) sit in
    both train and test folds. Re-estimate with 5-fold CV grouped by concept pair, at the frozen thresholds.
    Template ids were not stored per row, so template-family grouping is not possible; pair grouping is a
    lower bound on the leakage removed. The frozen J4/J5 models and thresholds are not changed."""
    with MODELS.open("rb") as fh:
        frozen = pickle.load(fh)
    tmpl, weak, real = jload(DATA / "scenarios_template.json"), jload(DATA / "scenarios_weak.json"), v1_real_rows()
    out = {}
    for name, rows in (("J4", tmpl), ("J5", tmpl + weak + real)):
        y = np.array([r["label"] for r in rows])
        groups = np.array([" || ".join(sorted((r["a"], r["b"]))) for r in rows])
        p = np.zeros(len(rows))
        for tr, te in GroupKFold(5).split(rows, y, groups):
            Xtr, vec = featurize([rows[i] for i in tr])
            Xte, _ = featurize([rows[i] for i in te], vec)
            m = LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced").fit(Xtr, y[tr])
            p[te] = m.predict_proba(Xte)[:, 1]
        thr = frozen[name]["threshold"]
        pred = p >= thr
        tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
        out[name] = {"n": len(rows), "n_pairs": int(len(set(groups))), "frozen_threshold": thr,
                     "grouped_cv_precision": tp / max(1, tp + fp), "grouped_cv_recall": tp / max(1, tp + fn),
                     "rowwise_cv": frozen[name]["cv"]}
    (RESULTS / "link_detector_grouped_cv.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def v1_real_rows() -> list[dict]:
    """Amendment 4 adjudicated units (disjoint from v2): explicit -> 1, mention_only -> 0."""
    U = jload(DATA / "units.json")
    rows = [{"a": u["a"], "b": u["b"], "text": f"{u['source']['title']}. {u['source']['abstract']}", "label": 1,
             "source": "v1_real"} for u in U["positive_controls"]]
    rows += [{"a": u["a"], "b": u["b"], "text": f"{u['paper']['title']}. {u['paper']['abstract']}", "label": 0,
              "source": "v1_real"} for u in U["hard_negatives"]]
    return rows


def train() -> dict:
    tmpl = jload(DATA / "scenarios_template.json")
    weak = jload(DATA / "scenarios_weak.json")
    real = v1_real_rows()
    J4 = train_one(tmpl)
    J5 = train_one(tmpl + weak + real)
    with MODELS.open("wb") as fh:  # local artifact built by this module only
        pickle.dump({"J4": J4, "J5": J5}, fh)
    summary = {"J4": {"train": {"template": len(tmpl)}, **J4["cv"]},
               "J5": {"train": {"template": len(tmpl), "weak": len(weak), "v1_real": len(real)}, **J5["cv"]}}
    (RESULTS / "link_detector_training.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return summary


def predict(rows: list[dict], which: str) -> list[tuple[float, bool]]:
    with MODELS.open("rb") as fh:  # our own artifact; never load one from elsewhere
        M = pickle.load(fh)[which]
    X, _ = featurize(rows, M["vec"])
    p = M["model"].predict_proba(X)[:, 1]
    return [(float(x), bool(x >= M["threshold"])) for x in p]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "grouped_cv"])
    a = ap.parse_args()
    train() if a.cmd == "train" else grouped_cv()
