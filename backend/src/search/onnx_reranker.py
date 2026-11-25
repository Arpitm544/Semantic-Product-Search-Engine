"""ONNX Runtime export, dynamic INT8 quantization, and inference for cross-encoder rerankers."""

import json
from pathlib import Path

from src.search.relevance import CALIBRATION_FILE, MAX_LENGTH, CalibratedReranker, PlattScaling


class OnnxCrossEncoder:
    """CPU cross-encoder backed by ONNX Runtime with length-sorted smart batching."""

    def __init__(self, model_dir, onnx_filename="model_int8.onnx", threads=2, max_length=MAX_LENGTH):
        import onnxruntime as ort
        from transformers import AutoTokenizer

        directory = Path(model_dir)
        model_path = directory / onnx_filename
        if not model_path.is_file():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True)
        self.max_length = max_length

    def predict(self, pairs, batch_size=32, show_progress_bar=False):
        import numpy as np

        if not pairs:
            return np.array([], dtype=np.float32)

        order = sorted(range(len(pairs)), key=lambda idx: len(pairs[idx][0]) + len(pairs[idx][1]))
        scores = np.empty(len(pairs), dtype=np.float32)
        for start in range(0, len(order), batch_size):
            batch_indices = order[start:start + batch_size]
            batch_pairs = [pairs[idx] for idx in batch_indices]
            encoded = self.tokenizer(
                [pair[0] for pair in batch_pairs],
                [pair[1] for pair in batch_pairs],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="np",
            )
            feed = {name: encoded[name].astype(np.int64) for name in self.input_names}
            logits = self.session.run(["logits"], feed)[0].reshape(-1)
            for idx, value in zip(batch_indices, logits):
                scores[idx] = float(value)
        return scores


def export_onnx_reranker(model_dir, output_dir=None, max_length=MAX_LENGTH, quantize=True):
    """Export a saved HuggingFace CrossEncoder to FP32 ONNX and dynamically quantized INT8 ONNX."""
    import onnx
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    source = Path(model_dir)
    destination = Path(output_dir) if output_dir is not None else source
    destination.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(str(source), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(source), local_files_only=True, attn_implementation="eager",
    )
    model.eval()

    dummy = tokenizer(
        ["wireless earbuds", "running shoes"],
        ["bluetooth earbuds with charging case", "lightweight cushioned running shoes"],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    input_names = [name for name in ("input_ids", "attention_mask", "token_type_ids") if name in dummy]
    fp32_path = destination / "model.onnx"
    torch.onnx.export(
        model,
        tuple(dummy[name] for name in input_names),
        str(fp32_path),
        input_names=input_names,
        output_names=["logits"],
        dynamic_axes={**{name: {0: "batch", 1: "seq"} for name in input_names}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )

    # Inline external weights if any were written separately so single-file sizing/loading is consistent.
    onnx_model = onnx.load(str(fp32_path), load_external_data=True)
    onnx.save_model(onnx_model, str(fp32_path), save_as_external_data=False)

    result = {"fp32": fp32_path}
    if quantize:
        int8_path = destination / "model_int8.onnx"
        quantize_dynamic(
            str(fp32_path),
            str(int8_path),
            weight_type=QuantType.QUInt8,
            op_types_to_quantize=["MatMul"],
        )
        result["int8"] = int8_path
    return result


def load_onnx_reranker(model_dir, onnx_filename="model_int8.onnx", threads=2):
    """Load an OnnxCrossEncoder, wrapping it with Platt scaling if calibration.json is present."""
    directory = Path(model_dir)
    sidecar = directory / CALIBRATION_FILE
    calibration = None
    if sidecar.is_file():
        metadata = json.loads(sidecar.read_text())
        if metadata.get("method") == "platt" and metadata.get("version") == 1:
            calibration = PlattScaling(metadata["slope"], metadata["intercept"])
    model = OnnxCrossEncoder(directory, onnx_filename=onnx_filename, threads=threads, max_length=MAX_LENGTH)
    return CalibratedReranker(model, calibration) if calibration is not None else model
