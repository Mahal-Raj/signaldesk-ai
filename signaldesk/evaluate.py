import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold

from .data import EXAMPLES
from .engine import IncidentEngine

def evaluate():
    texts, labels = [], []
    for label, examples in EXAMPLES.items():
        texts += examples
        labels += [label] * len(examples)
    predicted = [None] * len(texts)
    folds = StratifiedKFold(5, shuffle=True, random_state=42)
    for train, test in folds.split(texts, labels):
        engine = IncidentEngine([texts[index] for index in train], [labels[index] for index in train])
        for index, prediction in zip(test, engine.predict([texts[index] for index in test])):
            predicted[index] = prediction
    report = {
        "method": "5-fold stratified cross-validation of hybrid statistical + domain model",
        "samples": len(texts),
        "accuracy": round(float(accuracy_score(labels, predicted)), 4),
        "classificationReport": classification_report(labels, predicted, output_dict=True, zero_division=0),
        "labels": sorted(EXAMPLES),
        "confusionMatrix": confusion_matrix(labels, predicted, labels=sorted(EXAMPLES)).tolist(),
    }
    output = Path(__file__).resolve().parents[1] / "reports" / "metrics.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"accuracy": report["accuracy"], "samples": report["samples"], "output": str(output)}))
    return report

if __name__ == "__main__": evaluate()
