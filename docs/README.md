# Documentation

## Running the application

- [Catalog backend](backend.md): MongoDB import, startup, and local model files.
- [Architecture](architecture.md): responsibilities, storage, and configuration.
- [Commands](commands.md): startup, dataset import, training, and evaluation.
- [Shopify implementation plan](shopify-implementation-plan.md): proposed folder structure, compact catalog sync, semantic indexing, and rollout phases.

- [Shopify setup](shopify-setup.md): credentials, sync worker, webhooks, recovery, and capacity limits.

## Training and learning

- [Colab training](colab-training.md): hosted GPU setup and checkpoints.
- [Search evaluation](typo-search.md): dataset splits, spelling, and retrieval metrics.
- [Study notes](study-notes.md): introductory explanations.

Training guides may describe offline JSON workflows; the live Catalog backend
always reads product records from MongoDB.
