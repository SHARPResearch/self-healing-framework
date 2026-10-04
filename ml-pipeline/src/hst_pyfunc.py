"""
hst_pyfunc.py — MLflow pyfunc wrapper so a registered HST version is loadable on its own.

`mlflow.pyfunc.load_model("models:/hst-<entity>@production").predict(df)` rebuilds the tree
structure from the stored config + feature names (~16 s for the tuned model, once per load),
applies the sparse state snapshot, and returns one anomaly score per row (model frozen, scoring
only, clamped to [0, 1] like src.hst_model.score_dataset).
"""

import json

import mlflow.pyfunc


class HSTStatePyfunc(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        from src.config import HSTConfig
        from src.hst_model import build_model
        from src.hst_state import HSTState, apply, materialize

        with open(context.artifacts["config"]) as f:
            config = json.load(f)
        with open(context.artifacts["state"], "rb") as f:
            state = HSTState.from_bytes(f.read())
        self.threshold = config["threshold"]
        self.model = build_model(HSTConfig(**config["hst_params"]), with_scaler=config["with_scaler"])
        materialize(self.model, config["feature_names"])
        apply(self.model, state)

    def predict(self, context, model_input, params=None):
        rows = model_input.to_dict(orient="records")
        return [float(min(max(self.model.score_one(r), 0.0), 1.0)) for r in rows]
