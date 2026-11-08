"""The fine-tuning loop shared by the intent classifier and the NER model.

Written as an explicit PyTorch loop rather than with the Trainer class, so
every step (optimizer, schedule, early stopping, checkpointing) is visible.
The two tasks differ only in how a batch is built, how the loss is computed
and how validation is scored; those three things are passed in.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import get_linear_schedule_with_warmup

from backend.core.config import EncoderTrainingConfig

log = logging.getLogger(__name__)


@dataclass
class TrainResult:
    output_dir: Path
    best_epoch: int
    best_score: float
    seconds: float
    history: list[dict] = field(default_factory=list)


def pick_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _build_optimizer(model, config: EncoderTrainingConfig) -> torch.optim.Optimizer:
    # Weight decay pulls weights towards zero as a regulariser. It is not
    # applied to biases and LayerNorm weights, which is standard practice.
    no_decay = ("bias", "LayerNorm.weight")
    decay = [p for n, p in model.named_parameters() if not any(k in n for k in no_decay)]
    plain = [p for n, p in model.named_parameters() if any(k in n for k in no_decay)]
    return torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": config.weight_decay},
            {"params": plain, "weight_decay": 0.0},
        ],
        lr=config.learning_rate,
    )


def fine_tune(
    model,
    tokenizer,
    loader: DataLoader,
    loss_fn: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    score_fn: Callable[[], dict],
    config: EncoderTrainingConfig,
    output_dir: Path,
    device: torch.device,
    label: str = "",
) -> TrainResult:
    """Train until validation stops improving; save the best epoch.

    `loss_fn(logits, labels)` returns the training loss for one batch.
    `score_fn()` evaluates the model on validation data and returns a dict
    whose "score" entry is the number to maximise.

    The saved folder contains the model weights, the tokenizer and the label
    map, so it can be loaded with nothing but its path.
    """
    model.to(device)
    optimizer = _build_optimizer(model, config)
    total_steps = len(loader) * config.max_epochs
    # Learning rate climbs from 0 during warm-up, then falls linearly to 0.
    # The warm-up avoids large, damaging updates to pretrained weights while
    # the new output layer is still random.
    scheduler = get_linear_schedule_with_warmup(
        optimizer, int(total_steps * config.warmup_ratio), total_steps
    )
    # Mixed precision roughly halves GPU memory use; it does nothing on CPU.
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler(enabled=use_amp)

    best_score, best_epoch, stale_epochs = -1.0, 0, 0
    history: list[dict] = []
    started = time.perf_counter()

    for epoch in range(1, config.max_epochs + 1):
        model.train()
        running_loss = 0.0
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            labels = batch.pop("labels")

            optimizer.zero_grad()
            with torch.autocast(device_type=device.type, enabled=use_amp):
                logits = model(**batch).logits
                loss = loss_fn(logits.float(), labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running_loss += loss.item()

        scores = score_fn()
        entry = {"epoch": epoch, "train_loss": running_loss / len(loader), **scores}
        history.append(entry)
        log.info("%s epoch %d: %s", label, epoch,
                 ", ".join(f"{k} {v:.4f}" for k, v in entry.items() if k != "epoch"))

        if scores["score"] > best_score:
            best_score, best_epoch, stale_epochs = scores["score"], epoch, 0
            output_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
        else:
            stale_epochs += 1
            if stale_epochs >= config.patience:
                log.info("early stopping: no improvement for %d epochs", stale_epochs)
                break

    return TrainResult(
        output_dir=output_dir,
        best_epoch=best_epoch,
        best_score=best_score,
        seconds=time.perf_counter() - started,
        history=history,
    )
