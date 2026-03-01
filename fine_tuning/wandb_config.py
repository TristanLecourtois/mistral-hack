#!/usr/bin/env python3

"""
W&B Configuration for Mistral Fine-Tuning

This file contains the W&B API key and configuration for the fine-tuning project.
"""

# W&B API Key (from user)
WANDB_API_KEY = "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"

# Project configuration
WANDB_PROJECT = "mistral-emergency-finetune"
WANDB_ENTITY = None  # Set to your W&B team name if applicable

# Configuration for the fine-tuning runs
WANDB_CONFIG = {
    "model": "mistralai/Mistral-Small-3.1-24B-Base-2503",
    "dataset": "emergency_calls",
    "method": "QLoRA",
    "learning_rate": 2e-4,
    "batch_size": 4,
    "epochs": 3,
    "optimization": "paged_adamw_8bit",
    "quantization": "4bit_nf4"
}