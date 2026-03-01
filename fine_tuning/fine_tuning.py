#!/usr/bin/env python3

"""
Complete Fine-Tuning Script for Mistral-Small

This script fine-tunes Mistral-Small using the generated emergency call data.
It includes data loading, preprocessing, model setup, training, and evaluation.
"""

import os
import json
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling
)
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
import wandb
from datetime import datetime


def load_and_preprocess_data(train_file: str, val_file: str = None):
    """Load and preprocess data from JSONL files"""
    
    def load_jsonl(file_path):
        """Load JSONL file and return list of dictionaries"""
        data = []
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return data
    
    # Load raw data
    train_data = load_jsonl(train_file)
    val_data = load_jsonl(val_file) if val_file else None
    
    print(f"📊 Loaded {len(train_data)} training samples")
    if val_data:
        print(f"📊 Loaded {len(val_data)} validation samples")
    
    # Convert to Hugging Face Dataset format
    def process_item(item):
        """Convert our format to instruction-tuning format"""
        messages = item['messages']
        user_message = messages[0]['content']  # Full conversation
        assistant_message = messages[1]['content']  # Scores
        
        return {
            "text": f"<s>[INST] {user_message} [/INST] {assistant_message} </s>"
        }
    
    # Process datasets
    train_dataset = Dataset.from_list([process_item(item) for item in train_data])
    val_dataset = Dataset.from_list([process_item(item) for item in val_data]) if val_data else None
    
    return train_dataset, val_dataset


def setup_wandb():
    """Initialize Weights & Biases for experiment tracking"""
    try:
        # Import W&B config
        from wandb_config import WANDB_API_KEY, WANDB_PROJECT, WANDB_CONFIG
        
        # Login to W&B
        import wandb
        wandb.login(key=WANDB_API_KEY)
        
        # Initialize run
        run = wandb.init(
            project=WANDB_PROJECT,
            config=WANDB_CONFIG,
            entity=WANDB_CONFIG.get('entity')
        )
        return run
    except Exception as e:
        print(f"⚠️  W&B initialization failed: {e}")
        print("   Continuing without W&B tracking")
        return None


def setup_model_and_tokenizer():
    """Load model and tokenizer with QLoRA configuration"""
    
    model_name = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    
    print("🔧 Setting up model and tokenizer...")
    
    # Quantization config for 4-bit training
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    
    # Load model with HF token
    print("   Loading model...")
    try:
        from hf_config import HF_API_TOKEN
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            token=HF_API_TOKEN
        )
    except ImportError:
        # Fallback to environment variable
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
    
    # Load tokenizer
    print("   Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    
    # Prepare model for training
    model = prepare_model_for_kbit_training(model)
    
    return model, tokenizer


def setup_peft_config():
    """Setup PEFT (QLoRA) configuration"""
    return LoraConfig(
        lora_alpha=16,
        lora_dropout=0.1,
        r=64,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )


def train_model(
    train_dataset,
    val_dataset=None,
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=10,
    save_steps=100,
    max_seq_length=512,
    use_wandb=True
):
    """Train the model using SFTTrainer"""
    
    # Initialize W&B if requested
    wandb_run = setup_wandb() if use_wandb else None
    
    # Setup model and tokenizer
    model, tokenizer = setup_model_and_tokenizer()
    
    # Setup PEFT
    peft_config = setup_peft_config()
    model = get_peft_model(model, peft_config)
    
    print("🚀 Starting training...")
    print(f"   Model: {model.config._name_or_path}")
    print(f"   Epochs: {num_train_epochs}")
    print(f"   Batch size: {per_device_train_batch_size}")
    print(f"   Learning rate: {learning_rate}")
    print(f"   Max sequence length: {max_seq_length}")
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        logging_steps=logging_steps,
        save_steps=save_steps,
        evaluation_strategy="steps" if val_dataset else "no",
        eval_steps=save_steps if val_dataset else None,
        save_total_limit=2,
        fp16=True,
        optim="paged_adamw_8bit",
        report_to="wandb" if wandb_run else "none",
        run_name=f"mistral-emergency-{datetime.now().strftime('%Y%m%d-%H%M')}"
    )
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    # Create SFTTrainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        packing=False
    )
    
    # Train the model
    trainer.train()
    
    # Save results
    output_dir = os.path.join(output_dir, "final_model")
    os.makedirs(output_dir, exist_ok=True)
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    if wandb_run:
        wandb_run.finish()
    
    print(f"✅ Training complete!")
    print(f"💾 Model saved to {output_dir}")
    
    return model, tokenizer


def main():
    """Main execution function"""
    
    # File paths
    train_file = "output/emergency_call_finetune_train.jsonl"
    val_file = "output/emergency_call_finetune_test.jsonl"
    
    print("🔧 Mistral-Small Fine-Tuning")
    print("=" * 50)
    
    try:
        # Load and preprocess data
        print("📋 Loading and preprocessing data...")
        train_dataset, val_dataset = load_and_preprocess_data(train_file, val_file)
        
        # Train the model
        model, tokenizer = train_model(
            train_dataset=train_dataset,
            val_dataset=val_dataset,
            output_dir="./mistral_finetune_results",
            num_train_epochs=3,
            per_device_train_batch_size=2,  # Adjust based on your GPU memory
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            max_seq_length=512,
            use_wandb=True
        )
        
        print("\n🎉 Fine-tuning complete!")
        print("   Model saved to ./mistral_finetune_results/final_model")
        print("   You can now use this model for inference")
        
        # Save sample predictions
        print("\n🧪 Testing model with sample input...")
        sample_text = "What is the anxiety score for this emergency call?"
        input_ids = tokenizer(sample_text, return_tensors="pt").input_ids.cuda()
        outputs = model.generate(input_ids, max_new_tokens=50)
        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"   Input: {sample_text}")
        print(f"   Output: {prediction}")
        
    except Exception as e:
        print(f"❌ Training failed: {e}")
        print("\n💡 Common issues and solutions:")
        print("   - CUDA out of memory: Reduce batch size or use gradient accumulation")
        print("   - Installation issues: pip install -r fine_tuning/requirements.txt")
        print("   - Data format issues: Check your JSONL files")
        print("   - GPU requirements: Ensure you have a CUDA-compatible GPU with sufficient VRAM")
        
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()