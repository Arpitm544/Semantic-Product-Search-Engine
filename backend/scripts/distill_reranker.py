"""Distill the fine-tuned ESCI reranker into smaller student cross-encoders and export ONNX."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import PROJECT_ROOT
from src.search.onnx_reranker import export_onnx_reranker
from src.search.relevance import CALIBRATION_FILE, MAX_LENGTH, load_reranker, weights_sha256
from src.semantic.train_reranker import (
    TRAIN_TARGETS, fit_platt, load_splits, predict, ranking_quality,
)

DEFAULT_STUDENTS = (
    ("minilm-l4", "cross-encoder/ms-marco-MiniLM-L4-v2", 2, 3e-5),
    ("minilm-l2", "cross-encoder/ms-marco-MiniLM-L2-v2", 3, 5e-5),
    ("tinybert-l2", "cross-encoder/ms-marco-TinyBERT-L-2-v2", 3, 5e-5),
)


def pick_device(requested):
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def compute_or_load_teacher_logits(teacher_dir, train_rows, cache_path, device, batch_size=128):
    import numpy as np

    if cache_path.is_file():
        logits = np.load(cache_path)
        if len(logits) == len(train_rows):
            print(f"Using cached teacher logits: {cache_path}", flush=True)
            return logits.astype(np.float32)

    print(f"Scoring {len(train_rows):,} training pairs with teacher {teacher_dir} on {device}...", flush=True)
    t0 = time.perf_counter()
    teacher = load_reranker(teacher_dir, device=device)
    logits = predict(teacher, train_rows, batch_size=batch_size).astype(np.float32)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, logits)
    print(f"Teacher scoring finished in {time.perf_counter() - t0:.1f}s.", flush=True)
    return logits


def distill_student(name, base_model, epochs, lr, splits, teacher_logits, output_root, device, batch_size, seed, alpha):
    import copy
    import numpy as np
    from sentence_transformers import CrossEncoder
    import torch
    from transformers import get_linear_schedule_with_warmup

    dest = output_root / name
    if (dest / "model_int8.onnx").is_file() and (dest / CALIBRATION_FILE).is_file():
        print(f"[{name}] Already exists at {dest}, skipping.", flush=True)
        return json.loads((dest / "distill_metrics.json").read_text())

    print(f"\n=== Distilling {name} ({base_model}, epochs={epochs}, lr={lr}) ===", flush=True)
    torch.manual_seed(seed)
    student = CrossEncoder(base_model, device=device, max_length=MAX_LENGTH, activation_fn=torch.nn.Identity())
    cal_rows = splits["calibration"]
    test_rows = splits["test"]
    pre_ndcg = ranking_quality(test_rows, predict(student, test_rows, batch_size=128))
    print(f"[{name}] Pre-distillation ESCI test NDCG@10 = {pre_ndcg:.4f}", flush=True)

    train_items = list(zip(splits["train"], teacher_logits.tolist()))
    rng = random.Random(seed)
    rng.shuffle(train_items)
    train_items.sort(key=lambda item: min(len(item[0]["query"]) + len(item[0]["text"]), MAX_LENGTH * 4))
    batches = [train_items[s:s + batch_size] for s in range(0, len(train_items), batch_size)]

    optimizer = torch.optim.AdamW(student.model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(batches) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, total_steps // 10, total_steps)

    best_cal_ndcg = -1.0
    best_state = None
    t_start = time.perf_counter()
    for epoch in range(1, epochs + 1):
        epoch_batches = list(batches)
        rng.shuffle(epoch_batches)
        student.model.train()
        running_loss = 0.0
        for step, batch in enumerate(epoch_batches, 1):
            rows_b = [item[0] for item in batch]
            t_logits = torch.tensor([item[1] for item in batch], dtype=torch.float32, device=device)
            targets = torch.tensor([TRAIN_TARGETS[r["grade"]] for r in rows_b], dtype=torch.float32, device=device)
            tokens = student.tokenizer(
                [r["query"] for r in rows_b],
                [r["text"] for r in rows_b],
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                pad_to_multiple_of=32,
                return_tensors="pt",
            ).to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = student.model(**tokens).logits.flatten()
            loss_mse = torch.nn.functional.mse_loss(logits, t_logits)
            loss_bce = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets)
            loss = alpha * loss_mse + (1.0 - alpha) * loss_bce
            loss.backward()
            torch.nn.utils.clip_grad_norm_(student.model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running_loss += float(loss.item())
            if step % 200 == 0 or step == len(epoch_batches):
                print(f"[{name}] Epoch {epoch}/{epochs} step {step}/{len(epoch_batches)} "
                      f"loss={running_loss / step:.4f}", flush=True)

        cal_logits = predict(student, cal_rows, batch_size=128)
        cal_ndcg = ranking_quality(cal_rows, cal_logits)
        print(f"[{name}] Epoch {epoch} calibration NDCG@10 = {cal_ndcg:.4f}", flush=True)
        if cal_ndcg > best_cal_ndcg:
            best_cal_ndcg = cal_ndcg
            best_state = copy.deepcopy({k: v.detach().cpu() for k, v in student.model.state_dict().items()})

    if best_state is not None:
        student.model.load_state_dict({k: v.to(device) for k, v in best_state.items()})

    cal_logits = predict(student, cal_rows, batch_size=128)
    scaling = fit_platt(cal_logits, cal_rows)
    test_logits = predict(student, test_rows, batch_size=128)
    post_ndcg = ranking_quality(test_rows, test_logits)
    train_seconds = time.perf_counter() - t_start

    dest.mkdir(parents=True, exist_ok=True)
    student.model.to("cpu")
    student.save_pretrained(str(dest), safe_serialization=True)
    metadata = {
        "method": "platt",
        "version": 1,
        **asdict(scaling),
        "max_length": MAX_LENGTH,
        "relevant_labels": ["E", "S", "C"],
        "weights_sha256": weights_sha256(dest),
    }
    (dest / CALIBRATION_FILE).write_text(json.dumps(metadata, indent=2) + "\n")
    onnx_paths = export_onnx_reranker(dest, dest, max_length=MAX_LENGTH, quantize=True)

    metrics = {
        "name": name,
        "base_model": base_model,
        "epochs": epochs,
        "lr": lr,
        "alpha": alpha,
        "pre_distill_test_ndcg10": float(pre_ndcg),
        "post_distill_test_ndcg10": float(post_ndcg),
        "best_cal_ndcg10": float(best_cal_ndcg),
        "train_seconds": round(train_seconds, 1),
        "safetensors_mb": round((dest / "model.safetensors").stat().st_size / 1e6, 2),
        "onnx_fp32_mb": round(onnx_paths["fp32"].stat().st_size / 1e6, 2),
        "onnx_int8_mb": round(onnx_paths["int8"].stat().st_size / 1e6, 2),
    }
    (dest / "distill_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"[{name}] Done in {train_seconds:.1f}s: ESCI test NDCG@10 {pre_ndcg:.4f} -> {post_ndcg:.4f} "
          f"(INT8 {metrics['onnx_int8_mb']} MB)", flush=True)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "colab/reranker")
    parser.add_argument("--teacher", type=Path, default=PROJECT_ROOT / "models/esci-reranker")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "models/distilled")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--alpha", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    device = pick_device(args.device)
    splits = load_splits(args.data)
    teacher_cache = args.output / "teacher_logits.npy"
    teacher_logits = compute_or_load_teacher_logits(args.teacher, splits["train"], teacher_cache, device)

    # Also ensure teacher ONNX FP32 + INT8 exist under output/teacher-onnx for unified benchmarking.
    teacher_onnx_dir = args.output / "teacher-onnx"
    if not (teacher_onnx_dir / "model_int8.onnx").is_file():
        print(f"Exporting teacher {args.teacher} to ONNX FP32 + INT8...", flush=True)
        teacher_onnx_dir.mkdir(parents=True, exist_ok=True)
        for fname in ("tokenizer.json", "tokenizer_config.json", "vocab.txt", "special_tokens_map.json", CALIBRATION_FILE):
            src_file = args.teacher / fname
            if src_file.is_file():
                (teacher_onnx_dir / fname).write_bytes(src_file.read_bytes())
        export_onnx_reranker(args.teacher, teacher_onnx_dir, max_length=MAX_LENGTH, quantize=True)

    summary = []
    for name, base_model, epochs, lr in DEFAULT_STUDENTS:
        summary.append(distill_student(
            name, base_model, epochs, lr, splits, teacher_logits,
            args.output, device, args.batch_size, args.seed, args.alpha,
        ))
    (args.output / "distillation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("\nDistillation summary written to", args.output / "distillation_summary.json", flush=True)


if __name__ == "__main__":
    main()
