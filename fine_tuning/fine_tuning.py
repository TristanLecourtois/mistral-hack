#!/usr/bin/env python3
"""
Mistral-7B Fine-tuning with LoRA for Emergency Call Analysis
Supports conversation format with scoring output
"""

import os
import json
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
import wandb
from typing import Dict, List
import argparse



# Configuration
MODEL_NAME = "mistralai/mistral-7b-instruct-v0.2"

# LoRA Configuration
LORA_R = 16  # LoRA attention dimension (rank)
LORA_ALPHA = 32  # Alpha parameter for LoRA scaling
LORA_DROPOUT = 0.05  # Dropout probability for LoRA layers
TARGET_MODULES = [
    "q_proj",
    "k_proj", 
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

# BitsAndBytes Configuration for 4-bit quantization
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)


def format_conversation(messages: List[Dict[str, str]]) -> str:
    """
    Format the conversation messages into a single string.
    Uses Mistral-Instruct chat template format.
    """
    formatted_text = ""
    for message in messages:
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            formatted_text += f"<s>[INST] {content} [/INST]"
        elif role == "assistant":
            formatted_text += f" {content}</s>"
        else:
            formatted_text += f" {content}"
    
    return formatted_text


def load_dataset_from_json(file_path: str) -> Dataset:
    """
    Load and preprocess the JSON dataset.
    Expected format: List of {"messages": [{"role": "...", "content": "..."}, ...]}
    """
    print(f"Loading dataset from {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both single object and list of objects
    if isinstance(data, dict):
        data = [data]
    
    # Format conversations
    formatted_data = []
    for item in data:
        if "messages" in item:
            text = format_conversation(item["messages"])
            formatted_data.append({"text": text})
    
    dataset = Dataset.from_list(formatted_data)
    print(f"Loaded {len(dataset)} examples")
    return dataset


def tokenize_function(examples, tokenizer, max_length=2048):
    """Tokenize the text examples."""
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors=None,
    )


def setup_model_and_tokenizer():
    """Initialize the model and tokenizer with quantization."""
    print(f"Loading model: {MODEL_NAME}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        padding_side="right"
    )
    
    # Set pad token if not present
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Load model with 4-bit quantization
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager"
    )
    
    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)
    
    return model, tokenizer


def setup_lora_model(model):
    """Configure and apply LoRA to the model."""
    print("Setting up LoRA configuration...")
    
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        target_modules=TARGET_MODULES,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        inference_mode=False,
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    return model


def train(
    train_file: str,
    output_dir: str = "./mistral-lora-emergency",
    num_epochs: int = 3,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 4,
    learning_rate: float = 2e-4,
    warmup_steps: int = 100,
    logging_steps: int = 1,
    save_steps: int = 500,
    max_length: int = 2048,
    wandb_project: str = "mistral-emergency-finetune",
):
    """
    Main training function.
    
    Args:
        train_file: Path to JSON training file
        output_dir: Directory to save model outputs
        num_epochs: Number of training epochs
        batch_size: Per-device training batch size
        gradient_accumulation_steps: Gradient accumulation steps
        learning_rate: Learning rate
        warmup_steps: Number of warmup steps
        logging_steps: Logging frequency
        save_steps: Checkpoint save frequency
        max_length: Maximum sequence length
        wandb_project: Weights & Biases project name
    """
    
    # Initialize W&B
    wandb.init(project=wandb_project, name="mistral-7b-emergency-lora")
    
    # Setup model and tokenizer
    model, tokenizer = setup_model_and_tokenizer()
    
    # Setup LoRA
    model = setup_lora_model(model)
    
    # Load and preprocess dataset
    dataset = load_dataset_from_json(train_file)
    
    # Tokenize dataset
    def tokenize_fn(examples):
        return tokenize_function(examples, tokenizer, max_length)
    
    tokenized_dataset = dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=dataset.column_names,
    )
    
    # Split into train/eval if needed (here using full dataset for training)
    # You can modify this to load separate validation data
    if len(tokenized_dataset) > 100:
        split = tokenized_dataset.train_test_split(test_size=0.1)
        train_dataset = split["train"]
        eval_dataset = split["test"]
    else:
        train_dataset = tokenized_dataset
        eval_dataset = None
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        optim="paged_adamw_8bit",  # Memory-efficient optimizer for QLoRA
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        max_grad_norm=0.3,
        weight_decay=0.001,
        logging_steps=logging_steps,
        logging_strategy="steps",
        eval_strategy="steps" if eval_dataset else "no",
        eval_steps=save_steps if eval_dataset else None,
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=3,
        load_best_model_at_end=True if eval_dataset else False,
        metric_for_best_model="eval_loss" if eval_dataset else None,
        greater_is_better=False,
        fp16=False,
        bf16=True,
        report_to="wandb",
        run_name=wandb.run.name,
        remove_unused_columns=False,
    )
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # We're doing causal LM, not masked LM
    )
    
    # Initialize Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )
    
    # Train
    print("Starting training...")
    trainer.train()
    
    # Save final model
    print(f"Saving model to {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    # Save LoRA adapters separately
    model.save_pretrained(os.path.join(output_dir, "lora_adapter"))
    
    print("Training complete!")
    wandb.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune Mistral-7B with LoRA")
    parser.add_argument("--train_file", type=str, required=True, 
                        help="Path to training JSON file")
    parser.add_argument("--output_dir", type=str, default="./mistral-lora-emergency",
                        help="Output directory for model")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4,
                        help="Training batch size per device")
    parser.add_argument("--lr", type=float, default=2e-4,
                        help="Learning rate")
    parser.add_argument("--wandb_project", type=str, default="mistral-emergency-finetune",
                        help="Weights & Biases project name")
    
    args = parser.parse_args()
    
    train(
        train_file=args.train_file,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        wandb_project=args.wandb_project,
    )