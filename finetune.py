"""
Fine-tuning module for the BEMS Troubleshooting Assistant.

Converts BEMS ticket data into training pairs (problem -> resolution) and
fine-tunes a sentence-transformer embedding model to improve retrieval
accuracy for domain-specific BEMS terminology.
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime

from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
    evaluation,
)
from torch.utils.data import DataLoader

from config import settings

logger = logging.getLogger(__name__)

FINETUNE_OUTPUT_DIR = os.getenv("FINETUNE_OUTPUT_DIR", "./finetuned_model")
FINETUNE_WARMUP_RATIO = float(os.getenv("FINETUNE_WARMUP_RATIO", "0.1"))


def _load_tickets(data_path: str | None = None) -> list[dict]:
    if data_path is None:
        data_path = os.path.join("sample_data", "bems_tickets.json")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_training_pairs(tickets: list[dict]) -> list[InputExample]:
    """Generate contrastive training pairs from ticket data.

    Positive pairs: description <-> resolution, description <-> title,
                    title <-> resolution (same ticket)
    Negative pairs: description <-> resolution across different component families
    """
    examples: list[InputExample] = []

    for ticket in tickets:
        desc = ticket.get("description", "")
        resolution = ticket.get("resolution", "")
        title = ticket.get("title", "")

        if not desc:
            continue

        if resolution:
            examples.append(InputExample(texts=[desc, resolution], label=0.9))
        if title:
            examples.append(InputExample(texts=[desc, title], label=0.85))
        if title and resolution:
            examples.append(InputExample(texts=[title, resolution], label=0.8))

    for i, ticket_a in enumerate(tickets):
        desc_a = ticket_a.get("description", "")
        comp_a = ticket_a.get("component", "")
        if not desc_a or not comp_a:
            continue

        family_a = comp_a.split(" - ")[0].strip()
        for ticket_b in tickets[i + 1:]:
            comp_b = ticket_b.get("component", "")
            resolution_b = ticket_b.get("resolution", "")
            if not comp_b or not resolution_b:
                continue

            family_b = comp_b.split(" - ")[0].strip()
            if family_a != family_b:
                examples.append(InputExample(texts=[desc_a, resolution_b], label=0.15))

    random.shuffle(examples)
    return examples


def _build_eval_pairs(tickets: list[dict]) -> list[InputExample]:
    """Build evaluation set from held-out ticket pairs."""
    return [
        InputExample(texts=[t["description"], t["resolution"]], label=0.9)
        for t in tickets
        if t.get("description") and t.get("resolution")
    ]


def finetune(
    data_path: str | None = None,
    output_dir: str | None = None,
    epochs: int = 3,
    batch_size: int = 16,
) -> dict:
    """Fine-tune the embedding model on BEMS ticket data.

    Uses CosineSimilarityLoss so that descriptions and resolutions from
    the same ticket are close, while cross-component pairs are far apart.
    """
    if output_dir is None:
        output_dir = FINETUNE_OUTPUT_DIR

    tickets = _load_tickets(data_path)
    if len(tickets) < 5:
        return {"status": "error", "message": "Need at least 5 tickets for fine-tuning"}

    logger.info("Loaded %d tickets for fine-tuning", len(tickets))

    random.seed(42)
    random.shuffle(tickets)
    split_idx = max(1, int(len(tickets) * 0.8))
    train_tickets = tickets[:split_idx]
    eval_tickets = tickets[split_idx:]

    train_examples = _build_training_pairs(train_tickets)
    eval_examples = _build_eval_pairs(eval_tickets)

    if not train_examples:
        return {"status": "error", "message": "No training pairs could be generated"}

    logger.info("Training pairs: %d, Eval pairs: %d", len(train_examples), len(eval_examples))
    logger.info("Loading base model: %s", settings.embedding_model)

    model = SentenceTransformer(settings.embedding_model)

    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)
    train_loss = losses.CosineSimilarityLoss(model=model)

    evaluator = None
    if eval_examples:
        evaluator = evaluation.EmbeddingSimilarityEvaluator(
            [e.texts[0] for e in eval_examples],
            [e.texts[1] for e in eval_examples],
            [e.label for e in eval_examples],
            name="bems-eval",
        )

    warmup_steps = int(len(train_dataloader) * epochs * FINETUNE_WARMUP_RATIO)

    logger.info(
        "Starting fine-tuning: %d epochs, batch_size=%d, warmup_steps=%d",
        epochs, batch_size, warmup_steps,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(output_dir, f"bems_ft_{timestamp}")

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        evaluator=evaluator,
        epochs=epochs,
        warmup_steps=warmup_steps,
        output_path=run_output_dir,
        show_progress_bar=True,
        evaluation_steps=max(1, len(train_dataloader) // 2),
    )

    logger.info("Fine-tuning complete. Model saved to %s", run_output_dir)

    return {
        "status": "success",
        "base_model": settings.embedding_model,
        "output_dir": run_output_dir,
        "training_pairs": len(train_examples),
        "eval_pairs": len(eval_examples),
        "epochs": epochs,
        "batch_size": batch_size,
        "message": (
            f"Fine-tuned model saved. To use it, update EMBEDDING_MODEL "
            f"in your .env to: {run_output_dir}"
        ),
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    data_file = sys.argv[1] if len(sys.argv) > 1 else None
    result = finetune(data_path=data_file)
    print(json.dumps(result, indent=2))
