"""
Fine-tuning module for the BEMS Troubleshooting Assistant.

Converts BEMS ticket data into training pairs (problem → resolution) and
fine-tunes a sentence-transformer embedding model to improve retrieval
accuracy for domain-specific BEMS terminology.

This module is currently DISABLED. To enable:
  1. Uncomment the fine-tune endpoint in app.py
  2. Uncomment the fine-tune tab in templates/index.html
  3. Run: python finetune.py
"""

# from __future__ import annotations
#
# import json
# import os
# import random
# import logging
# from datetime import datetime
#
# from sentence_transformers import (
#     SentenceTransformer,
#     InputExample,
#     losses,
#     evaluation,
# )
# from torch.utils.data import DataLoader
#
# from config import settings
#
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
#
# FINETUNE_OUTPUT_DIR = os.getenv("FINETUNE_OUTPUT_DIR", "./finetuned_model")
# FINETUNE_EPOCHS = int(os.getenv("FINETUNE_EPOCHS", "3"))
# FINETUNE_BATCH_SIZE = int(os.getenv("FINETUNE_BATCH_SIZE", "16"))
# FINETUNE_WARMUP_RATIO = float(os.getenv("FINETUNE_WARMUP_RATIO", "0.1"))
#
#
# def load_tickets(data_path: str | None = None) -> list[dict]:
#     """Load ticket data from JSON file."""
#     if data_path is None:
#         data_path = os.path.join("sample_data", "bems_tickets.json")
#     with open(data_path, "r", encoding="utf-8") as f:
#         return json.load(f)
#
#
# def build_training_pairs(tickets: list[dict]) -> list[InputExample]:
#     """
#     Generate training pairs from ticket data for contrastive learning.
#
#     Creates three types of pairs:
#       - Positive: description <-> resolution (same ticket, high similarity)
#       - Positive: description <-> title (same ticket, high similarity)
#       - Negative: description from one ticket <-> resolution from a
#         different component (cross-component, low similarity)
#     """
#     examples = []
#
#     for ticket in tickets:
#         desc = ticket.get("description", "")
#         resolution = ticket.get("resolution", "")
#         title = ticket.get("title", "")
#         component = ticket.get("component", "")
#
#         if not desc:
#             continue
#
#         # Positive pair: description <-> resolution
#         if resolution:
#             examples.append(InputExample(
#                 texts=[desc, resolution],
#                 label=0.9,
#             ))
#
#         # Positive pair: description <-> title
#         if title:
#             examples.append(InputExample(
#                 texts=[desc, title],
#                 label=0.85,
#             ))
#
#         # Positive pair: title <-> resolution
#         if title and resolution:
#             examples.append(InputExample(
#                 texts=[title, resolution],
#                 label=0.8,
#             ))
#
#     # Negative pairs: cross-component mismatches
#     for i, ticket_a in enumerate(tickets):
#         desc_a = ticket_a.get("description", "")
#         comp_a = ticket_a.get("component", "")
#         if not desc_a or not comp_a:
#             continue
#
#         for ticket_b in tickets[i + 1:]:
#             comp_b = ticket_b.get("component", "")
#             resolution_b = ticket_b.get("resolution", "")
#             if not comp_b or not resolution_b:
#                 continue
#
#             # Only pair tickets from different component families
#             family_a = comp_a.split(" - ")[0].strip()
#             family_b = comp_b.split(" - ")[0].strip()
#             if family_a != family_b:
#                 examples.append(InputExample(
#                     texts=[desc_a, resolution_b],
#                     label=0.15,
#                 ))
#
#     random.shuffle(examples)
#     return examples
#
#
# def build_eval_pairs(tickets: list[dict]) -> list[InputExample]:
#     """Build a small evaluation set from held-out ticket pairs."""
#     eval_examples = []
#     for ticket in tickets:
#         desc = ticket.get("description", "")
#         resolution = ticket.get("resolution", "")
#         if desc and resolution:
#             eval_examples.append(InputExample(
#                 texts=[desc, resolution],
#                 label=0.9,
#             ))
#     return eval_examples
#
#
# def finetune(
#     data_path: str | None = None,
#     output_dir: str | None = None,
#     epochs: int | None = None,
#     batch_size: int | None = None,
# ) -> dict:
#     """
#     Fine-tune the embedding model on BEMS ticket data.
#
#     Uses CosineSimilarityLoss to train the model so that:
#       - Descriptions and resolutions from the same ticket are close
#       - Descriptions and resolutions from unrelated components are far apart
#
#     Returns a summary dict with training details and output path.
#     """
#     if output_dir is None:
#         output_dir = FINETUNE_OUTPUT_DIR
#     if epochs is None:
#         epochs = FINETUNE_EPOCHS
#     if batch_size is None:
#         batch_size = FINETUNE_BATCH_SIZE
#
#     tickets = load_tickets(data_path)
#     if len(tickets) < 5:
#         return {"status": "error", "message": "Need at least 5 tickets for fine-tuning"}
#
#     logger.info(f"Loaded {len(tickets)} tickets for fine-tuning")
#
#     # Split: 80% train, 20% eval
#     random.seed(42)
#     random.shuffle(tickets)
#     split_idx = max(1, int(len(tickets) * 0.8))
#     train_tickets = tickets[:split_idx]
#     eval_tickets = tickets[split_idx:]
#
#     train_examples = build_training_pairs(train_tickets)
#     eval_examples = build_eval_pairs(eval_tickets)
#
#     if not train_examples:
#         return {"status": "error", "message": "No training pairs could be generated"}
#
#     logger.info(f"Training pairs: {len(train_examples)}, Eval pairs: {len(eval_examples)}")
#
#     # Load base model
#     logger.info(f"Loading base model: {settings.embedding_model}")
#     model = SentenceTransformer(settings.embedding_model)
#
#     train_dataloader = DataLoader(
#         train_examples,
#         shuffle=True,
#         batch_size=batch_size,
#     )
#
#     train_loss = losses.CosineSimilarityLoss(model=model)
#
#     evaluator = None
#     if eval_examples:
#         eval_sentences_1 = [e.texts[0] for e in eval_examples]
#         eval_sentences_2 = [e.texts[1] for e in eval_examples]
#         eval_scores = [e.label for e in eval_examples]
#         evaluator = evaluation.EmbeddingSimilarityEvaluator(
#             eval_sentences_1,
#             eval_sentences_2,
#             eval_scores,
#             name="bems-eval",
#         )
#
#     warmup_steps = int(len(train_dataloader) * epochs * FINETUNE_WARMUP_RATIO)
#
#     logger.info(f"Starting fine-tuning: {epochs} epochs, batch_size={batch_size}, "
#                 f"warmup_steps={warmup_steps}")
#
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     run_output_dir = os.path.join(output_dir, f"bems_ft_{timestamp}")
#
#     model.fit(
#         train_objectives=[(train_dataloader, train_loss)],
#         evaluator=evaluator,
#         epochs=epochs,
#         warmup_steps=warmup_steps,
#         output_path=run_output_dir,
#         show_progress_bar=True,
#         evaluation_steps=max(1, len(train_dataloader) // 2),
#     )
#
#     logger.info(f"Fine-tuning complete. Model saved to {run_output_dir}")
#
#     return {
#         "status": "success",
#         "base_model": settings.embedding_model,
#         "output_dir": run_output_dir,
#         "training_pairs": len(train_examples),
#         "eval_pairs": len(eval_examples),
#         "epochs": epochs,
#         "batch_size": batch_size,
#         "message": (
#             f"Fine-tuned model saved. To use it, update EMBEDDING_MODEL "
#             f"in your .env to: {run_output_dir}"
#         ),
#     }
#
#
# if __name__ == "__main__":
#     import sys
#     data_file = sys.argv[1] if len(sys.argv) > 1 else None
#     result = finetune(data_path=data_file)
#     print(json.dumps(result, indent=2))
