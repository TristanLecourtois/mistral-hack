#!/usr/bin/env python3
"""
Mistral-7B Fine-tuning with LoRA for Emergency Call Analysis
With Weave Scorers Regularization
Supports conversation format with scoring output
"""
import weave
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
import re
from torch.nn import CrossEntropyLoss
import torch.nn.functional as F
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
import wandb
from typing import Dict, List
import argparse

# Import Weave Scorers
from weave.scorers import (
    WeaveHallucinationScorerV1,
    WeaveContextRelevanceScorerV1,
    WeaveCoherenceScorerV1,
    WeaveFluencyScorerV1,
    WeaveToxicityScorerV1,
    WeaveBiasScorerV1
)

# Initialize Weave
weave.init("emergency-finetune-with-regularization")

class WeaveRegularizedTrainer(Trainer):
    """
    Custom trainer that applies:
    1. Weighted loss to score tokens (from original WeightedScoreTrainer)
    2. Weave scorers regularization based on model outputs
    """
    
    # Score weights for token-level loss (as specified)
    SCORE_WEIGHTS = {
        'anxiety': 8,
        'severity': 9,
        'coherence': 7,
        'seriousness': 10
    }
    
    # Weave scorer weights for regularization (tune these based on your needs)
    WEAVE_SCORER_WEIGHTS = {
        'coherence': 0.3,      # Weight for WeaveCoherenceScorer
        'fluency': 0.2,        # Weight for WeaveFluencyScorer  
        'toxicity': 0.25,      # Weight for WeaveToxicityScorer (penalty)
        'bias': 0.15,          # Weight for WeaveBiasScorer (penalty)
        'hallucination': 0.1   # Weight for WeaveHallucinationScorer (penalty)
    }
    
    def __init__(self, *args, tokenizer=None, regularization_lambda=0.1, 
                 use_weave_regularization=True, **kwargs):
        self.tokenizer = tokenizer
        self.regularization_lambda = regularization_lambda  # Overall regularization strength
        self.use_weave_regularization = use_weave_regularization
        
        # Initialize Weave scorers
        if self.use_weave_regularization:
            print("Initializing Weave Scorers for regularization...")
            self.coherence_scorer = WeaveCoherenceScorerV1()
            self.fluency_scorer = WeaveFluencyScorerV1()
            self.toxicity_scorer = WeaveToxicityScorerV1()
            self.bias_scorer = WeaveBiasScorerV1()
            self.hallucination_scorer = WeaveHallucinationScorerV1()
            print("Weave Scorers initialized successfully!")
        
        super().__init__(*args, **kwargs)
    
    def decode_outputs(self, logits, labels):
        """
        Decode model outputs to text for Weave scorer evaluation.
        """
        # Get predicted tokens
        predicted_ids = torch.argmax(logits, dim=-1)
        
        # Decode to text (only decode non-padding tokens)
        batch_texts = []
        for i in range(predicted_ids.shape[0]):
            # Mask padding tokens
            mask = labels[i] != -100
            valid_ids = predicted_ids[i][mask]
            
            # Decode
            text = self.tokenizer.decode(valid_ids, skip_special_tokens=True)
            batch_texts.append(text)
        
        return batch_texts
    
    def compute_weave_regularization(self, decoded_outputs, context=None):
        """
        Compute regularization term using Weave scorers.
        Returns a weighted average of scores.
        """
        if not self.use_weave_regularization:
            return torch.tensor(0.0, device=self.args.device)
        
        total_score = 0.0
        total_weight = 0.0
        
        for output_text in decoded_outputs:
            # Skip empty outputs
            if not output_text or len(output_text.strip()) == 0:
                continue
            
            batch_scores = []
            batch_weights = []
            
            # Coherence Scorer (higher is better, so we want to maximize)
            try:
                coherence_result = self.coherence_scorer.score(
                    query="",  # You may want to extract query from conversation
                    output=output_text
                )
                # Convert passed boolean to score (1.0 if passed, 0.0 if failed)
                coherence_score = 1.0 if coherence_result.passed else 0.0
                # If metadata has detailed score, use that
                if hasattr(coherence_result, 'metadata') and 'score' in coherence_result.metadata:
                    coherence_score = coherence_result.metadata['score']
                batch_scores.append(coherence_score)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['coherence'])
            except Exception as e:
                print(f"Coherence scorer error: {e}")
                batch_scores.append(0.5)  # Neutral score on error
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['coherence'])
            
            # Fluency Scorer (higher is better)
            try:
                fluency_result = self.fluency_scorer.score(output=output_text)
                fluency_score = 1.0 if fluency_result.passed else 0.0
                if hasattr(fluency_result, 'metadata') and 'score' in fluency_result.metadata:
                    fluency_score = fluency_result.metadata['score']
                batch_scores.append(fluency_score)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['fluency'])
            except Exception as e:
                print(f"Fluency scorer error: {e}")
                batch_scores.append(0.5)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['fluency'])
            
            # Toxicity Scorer (lower is better, so we penalize high toxicity)
            try:
                toxicity_result = self.toxicity_scorer.score(output=output_text)
                # Invert: we want low toxicity, so passed (not toxic) = 1.0, failed (toxic) = 0.0
                toxicity_score = 1.0 if toxicity_result.passed else 0.0
                if hasattr(toxicity_result, 'metadata') and 'scores' in toxicity_result.metadata:
                    # If we have detailed scores, compute inverse toxicity
                    scores = toxicity_result.metadata['scores']
                    if isinstance(scores, dict):
                        max_score = max(scores.values()) if scores else 0
                        toxicity_score = 1.0 - (max_score / 3.0)  # Normalize assuming max is 3
                batch_scores.append(toxicity_score)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['toxicity'])
            except Exception as e:
                print(f"Toxicity scorer error: {e}")
                batch_scores.append(0.5)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['toxicity'])
            
            # Bias Scorer (lower is better)
            try:
                bias_result = self.bias_scorer.score(output=output_text)
                bias_score = 1.0 if bias_result.passed else 0.0  # passed = not biased
                if hasattr(bias_result, 'metadata') and 'score' in bias_result.metadata:
                    bias_score = 1.0 - bias_result.metadata['score']  # Invert if score is bias level
                batch_scores.append(bias_score)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['bias'])
            except Exception as e:
                print(f"Bias scorer error: {e}")
                batch_scores.append(0.5)
                batch_weights.append(self.WEAVE_SCORER_WEIGHTS['bias'])
            
            # Hallucination Scorer (lower is better - penalize hallucinations)
            if context:
                try:
                    # Extract query from output or use empty
                    halluc_result = self.hallucination_scorer.score(
                        query="",  # Extract from conversation if possible
                        context=context,
                        output=output_text
                    )
                    # passed = not hallucinated, so we want this to be True
                    halluc_score = 1.0 if halluc_result.passed else 0.0
                    if hasattr(halluc_result, 'metadata') and 'score' in halluc_result.metadata:
                        halluc_score = 1.0 - halluc_result.metadata['score']  # Invert
                    batch_scores.append(halluc_score)
                    batch_weights.append(self.WEAVE_SCORER_WEIGHTS['hallucination'])
                except Exception as e:
                    print(f"Hallucination scorer error: {e}")
                    batch_scores.append(0.5)
                    batch_weights.append(self.WEAVE_SCORER_WEIGHTS['hallucination'])
            
            # Compute weighted average for this sample
            if batch_scores:
                weights = torch.tensor(batch_weights, dtype=torch.float32)
                scores = torch.tensor(batch_scores, dtype=torch.float32)
                
                # Normalize weights
                weights = weights / weights.sum()
                weighted_score = (scores * weights).sum().item()
                
                total_score += weighted_score
                total_weight += 1.0
        
        # Average across batch
        if total_weight > 0:
            avg_score = total_score / total_weight
        else:
            avg_score = 0.5  # Neutral default
        
        # Regularization term: we want to maximize quality scores
        # Convert to loss (lower is better), so we use (1 - score)
        regularization_loss = (1.0 - avg_score) * self.regularization_lambda
        
        return torch.tensor(regularization_loss, device=self.args.device)
    
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        """
        Custom loss computation with:
        1. Weighted cross-entropy for score tokens
        2. Weave scorers regularization
        """
        # Remove unexpected kwargs
        inputs = {k: v for k, v in inputs.items() 
                 if k in ['input_ids', 'attention_mask', 'labels']}
        
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        
        # === 1. Compute weighted cross-entropy loss (original logic) ===
        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = labels[..., 1:].contiguous()
        
        batch_size, seq_len = shift_labels.shape
        shift_logits_flat = shift_logits.view(-1, shift_logits.size(-1))
        shift_labels_flat = shift_labels.view(-1)
        
        # Default low weight for all tokens
        loss_weights = torch.ones_like(shift_labels_flat, dtype=torch.float32) * 0.1
        
        if self.tokenizer is not None:
            # Pre-compute token IDs for score names and digits
            score_tokens = {}
            for name in self.SCORE_WEIGHTS.keys():
                tokens = self.tokenizer.encode(name, add_special_tokens=False)
                score_tokens[name] = tokens
            
            digit_tokens = [self.tokenizer.encode(str(i), add_special_tokens=False)[0] 
                          for i in range(10)]
            equal_token = self.tokenizer.encode('=', add_special_tokens=False)[0]
            
            # Find score patterns in each sequence
            for b in range(batch_size):
                seq = labels[b].cpu().tolist()
                
                for score_name, name_token_ids in score_tokens.items():
                    name_len = len(name_token_ids)
                    
                    # Slide through sequence looking for score name
                    for i in range(len(seq) - name_len - 1):
                        if seq[i:i+name_len] == name_token_ids:
                            # Found name, check for = and digit
                            if i + name_len < len(seq) and seq[i + name_len] == equal_token:
                                digit_pos = i + name_len + 1
                                if (digit_pos < len(seq) and 
                                    seq[digit_pos] in digit_tokens):
                                    # This is a score value! Apply weight
                                    shifted_pos = digit_pos - 1
                                    if 0 <= shifted_pos < seq_len:
                                        flat_idx = b * seq_len + shifted_pos
                                        loss_weights[flat_idx] = self.SCORE_WEIGHTS[score_name]
        
        # Move weights to same device as logits
        loss_weights = loss_weights.to(shift_logits.device)
        
        # Mask padding tokens
        loss_weights = loss_weights * (shift_labels_flat != -100).float()
        
        # Compute weighted cross entropy
        loss_fct = CrossEntropyLoss(reduction='none')
        ce_losses = loss_fct(shift_logits_flat, shift_labels_flat)
        weighted_ce_losses = ce_losses * loss_weights
        
        total_weight = loss_weights.sum()
        if total_weight > 0:
            ce_loss = weighted_ce_losses.sum() / total_weight
        else:
            ce_loss = weighted_ce_losses.sum()
        
        # === 2. Compute Weave regularization ===
        reg_loss = torch.tensor(0.0, device=ce_loss.device)
        if self.use_weave_regularization and self.tokenizer is not None:
            # Decode outputs for regularization (only every N steps to save compute)
            # You can adjust this frequency based on training speed needs
            if self.state.global_step % 1 == 0:  # Every 10 steps
                with torch.no_grad():
                    decoded = self.decode_outputs(logits, labels)
                    # Extract context from labels if possible, or pass None
                    reg_loss = self.compute_weave_regularization(decoded, context=None)
                    
                    # Log to wandb
                    if wandb.run is not None:
                        wandb.log({
                            "weave_reg_loss": reg_loss.item(),
                            "ce_loss": ce_loss.item(),
                            "total_loss": (ce_loss + reg_loss).item()
                        }, step=self.state.global_step)
        
        # === 3. Combine losses ===
        total_loss = ce_loss + reg_loss
        
        if return_outputs:
            return (total_loss, outputs)
        return total_loss


# Configuration
MODEL_NAME = "mistralai/mistral-7b-instruct-v0.2"

# LoRA Configuration
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

# BitsAndBytes Configuration
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)


def format_conversation(messages: List[Dict[str, str]]) -> str:
    """Format conversation messages into Mistral-Instruct format."""
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
    """Load and preprocess JSON dataset."""
    print(f"Loading dataset from {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        data = [data]
    
    formatted_data = []
    for item in data:
        if "messages" in item:
            text = format_conversation(item["messages"])
            formatted_data.append({"text": text})
    
    dataset = Dataset.from_list(formatted_data)
    print(f"Loaded {len(dataset)} examples")
    return dataset


def tokenize_function(examples, tokenizer, max_length=2048):
    """Tokenize text examples."""
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors=None,
    )


def setup_model_and_tokenizer():
    """Initialize model and tokenizer with quantization."""
    print(f"Loading model: {MODEL_NAME}")
    
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        padding_side="right"
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager"
    )
    
    model = prepare_model_for_kbit_training(model)
    
    return model, tokenizer


def setup_lora_model(model):
    """Configure and apply LoRA."""
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
    regularization_lambda: float = 0.1,
    use_weave_reg: bool = True,
):
    """
    Main training function with Weave regularization.
    
    Args:
        regularization_lambda: Weight for Weave regularization term (0 to disable)
        use_weave_reg: Whether to use Weave scorers for regularization
    """
    
    # Initialize W&B
    wandb.init(
        project=wandb_project, 
        name="mistral-7b-emergency-lora-weave-reg",
        config={
            "regularization_lambda": regularization_lambda,
            "use_weave_regularization": use_weave_reg,
            "weave_scorer_weights": WeaveRegularizedTrainer.WEAVE_SCORER_WEIGHTS
        }
    )
    
    # Setup model and tokenizer
    model, tokenizer = setup_model_and_tokenizer()
    
    # Setup LoRA
    model = setup_lora_model(model)
    
    # Load dataset
    dataset = load_dataset_from_json(train_file)
    
    # Tokenize
    def tokenize_fn(examples):
        return tokenize_function(examples, tokenizer, max_length)
    
    tokenized_dataset = dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=dataset.column_names,
    )
    
    # Split train/eval
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
        optim="paged_adamw_8bit",
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
        mlm=False,
    )
    
    # Initialize custom trainer with Weave regularization
    trainer = WeaveRegularizedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        tokenizer=tokenizer,
        regularization_lambda=regularization_lambda,
        use_weave_regularization=use_weave_reg,
    )
    
    # Train
    print("Starting training with Weave regularization...")
    print(f"Regularization lambda: {regularization_lambda}")
    print(f"Weave Scorer Weights: {WeaveRegularizedTrainer.WEAVE_SCORER_WEIGHTS}")
    trainer.train()
    
    # Save
    print(f"Saving model to {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    model.save_pretrained(os.path.join(output_dir, "lora_adapter"))
    
    print("Training complete!")
    wandb.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fine-tune Mistral-7B with LoRA and Weave Regularization"
    )
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
    parser.add_argument("--reg_lambda", type=float, default=0.1,
                       help="Regularization lambda for Weave scorers (0 to disable)")
    parser.add_argument("--no_weave_reg", action="store_true",
                       help="Disable Weave regularization")
    
    args = parser.parse_args()
    
    train(
        train_file=args.train_file,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        wandb_project=args.wandb_project,
        regularization_lambda=args.reg_lambda,
        use_weave_reg=not args.no_weave_reg,
    )
