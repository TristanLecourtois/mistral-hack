#!/usr/bin/env python3

"""
Simple Hugging Face Fine-Tuning for Mistral-Small-3.1-24B-Base-2503

Minimal skeleton for fine-tuning Mistral models using Hugging Face.
"""

import os
import json
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    BitsAndBytesConfig
)
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training


def load_data(train_file: str, val_file: str = None):
    """Load training and validation data from JSONL files"""
    
    def load_jsonl(file_path):
        data = []
        with open(file_path, 'r') as f:
            for line in f:
                data.append(json.loads(line))
        return data
    
    train_data = load_jsonl(train_file)
    val_data = load_jsonl(val_file) if val_file else None
    
    return train_data, val_data


def preprocess_data(data):
    """Convert data to format expected by the model"""
    
    processed = []
    for item in data:
        # Extract conversation and scores
        messages = item['messages']
        user_message = messages[0]['content']  # Full conversation
        assistant_message = messages[1]['content']  # Scores
        
        processed.append({
            'text': f"<s>[INST] {user_message} [/INST] {assistant_message} </s>"
        })
    
    return processed


def setup_model_and_tokenizer():
    """Load model and tokenizer with QLoRA configuration"""
    
    model_name = "mistralai/Mistral-Small-3.1-24B-Base-2503"
    
    # Quantization configuration
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    
    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto"
    )
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    
    # Prepare model for training
    model = prepare_model_for_kbit_training(model)
    
    return model, tokenizer


def setup_peft(model):
    """Setup PEFT (QLoRA) configuration"""
    
    peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.1,
        r=64,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
    )
    
    return get_peft_model(model, peft_config)


def train_model(
    train_data,
    val_data=None,
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=10,
    save_steps=100,
    evaluation_strategy="steps" if val_data else "no",
    eval_steps=100 if val_data else None,
    save_total_limit=2
):
    """Train the model with given parameters"""
    
    # Setup model and tokenizer
    model, tokenizer = setup_model_and_tokenizer()
    model = setup_peft(model)
    
    # Tokenize data
    def tokenize_function(examples):
        return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=512)
    
    train_dataset = load_dataset("json", data_files={"train": train_data})["train"]
    train_dataset = train_dataset.map(tokenize_function, batched=True)
    
    if val_data:
        val_dataset = load_dataset("json", data_files={"validation": val_data})["validation"]
        val_dataset = val_dataset.map(tokenize_function, batched=True)
    else:
        val_dataset = None
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        logging_steps=logging_steps,
        save_steps=save_steps,
        evaluation_strategy=evaluation_strategy,
        eval_steps=eval_steps,
        save_total_limit=save_total_limit,
        fp16=True,
        optim="paged_adamw_8bit"
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset
    )
    
    print("🚀 Starting training...")
    trainer.train()
    
    print("✅ Training complete!")
    
    # Save the model
    output_dir = os.path.join(output_dir, "final_model")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"💾 Model saved to {output_dir}")
    
    return model, tokenizer


def main():
    """Main training function"""
    
    # File paths
    train_file = "emergency_finetune_data_train.jsonl"
    val_file = "emergency_finetune_data_test.jsonl"
    
    print("🔧 Hugging Face Mistral Fine-Tuning")
    print("=" * 50)
    
    # Load data
    print("📋 Loading data...")
    train_data, val_data = load_data(train_file, val_file)
    print(f"   Training samples: {len(train_data)}")
    print(f"   Validation samples: {len(val_data) if val_data else 0}")
    
    # Preprocess data
    print("✂️  Preprocessing data...")
    processed_train = preprocess_data(train_data)
    processed_val = preprocess_data(val_data) if val_data else None
    
    # Save processed data for reference
    with open("processed_train.json", "w") as f:
        json.dump(processed_train[:5], f, indent=2)  # Save first 5 examples
    print("   Sample processed data saved to processed_train.json")
    
    # Train the model
    try:
        model, tokenizer = train_model(
            train_data="processed_train.json",
            val_data="processed_val.json" if val_data else None,
            output_dir="./mistral_finetune_results",
            num_train_epochs=3,
            per_device_train_batch_size=2,  # Reduce if you get CUDA out of memory
            gradient_accumulation_steps=4,
            learning_rate=2e-4
        )
        
        print("\n🎉 Fine-tuning complete!")
        print("   Model saved to ./mistral_finetune_results/final_model")
        print("   You can now use this model for inference")
        
    except Exception as e:
        print(f"❌ Training failed: {e}")
        print("\n💡 Common issues and solutions:")
        print("   - CUDA out of memory: Reduce batch size or use gradient accumulation")
        print("   - Installation issues: pip install -r requirements.txt")
        print("   - Tokenizer issues: Check your data format")


if __name__ == "__main__":
    main()