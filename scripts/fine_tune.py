#!/usr/bin/env python3
"""LoRA Fine-tuning Script for DocuMind.

Fine-tunes Llama 3.1 for legal/financial document analysis.
Uses PEFT with LoRA for efficient training.
"""

import argparse
import json
from pathlib import Path

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fine-tune Llama for DocuMind")

    parser.add_argument(
        "--base-model",
        type=str,
        default="meta-llama/Llama-3.1-8B-Instruct",
        help="Base model to fine-tune",
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default="data/training/legal_summaries.json",
        help="Path to training dataset",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/documind-legal-lora",
        help="Output directory for fine-tuned model",
    )
    parser.add_argument(
        "--num-epochs",
        type=int,
        default=3,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Batch size for training",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-4,
        help="Learning rate",
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=16,
        help="LoRA rank",
    )
    parser.add_argument(
        "--lora-alpha",
        type=int,
        default=32,
        help="LoRA alpha",
    )
    parser.add_argument(
        "--use-4bit",
        action="store_true",
        help="Use 4-bit quantization",
    )

    return parser.parse_args()


def load_training_data(path: str) -> Dataset:
    """Load and prepare training dataset.

    Expected format:
    [
        {
            "instruction": "Summarize the following contract...",
            "input": "Contract text...",
            "output": "Summary..."
        },
        ...
    ]
    """
    if path.endswith(".json"):
        with open(path) as f:
            data = json.load(f)
        return Dataset.from_list(data)
    else:
        return load_dataset("json", data_files=path)["train"]


def format_prompt(example: dict) -> str:
    """Format example into Llama instruction format."""
    instruction = example.get("instruction", "")
    input_text = example.get("input", "")
    output = example.get("output", "")

    if input_text:
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are DocuMind, an expert legal and financial document analyst.<|eot_id|><|start_header_id|>user<|end_header_id|>

{instruction}

{input_text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{output}<|eot_id|>"""
    else:
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are DocuMind, an expert legal and financial document analyst.<|eot_id|><|start_header_id|>user<|end_header_id|>

{instruction}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{output}<|eot_id|>"""

    return prompt


def main():
    """Main fine-tuning function."""
    args = parse_args()

    print(f"Fine-tuning {args.base_model}")
    print(f"Output directory: {args.output_dir}")

    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # Quantization config for 4-bit
    bnb_config = None
    if args.use_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    # Load base model
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    model.config.use_cache = False

    # LoRA configuration
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.1,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
    )

    # Apply LoRA
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load dataset
    if Path(args.dataset_path).exists():
        dataset = load_training_data(args.dataset_path)
        print(f"Loaded {len(dataset)} training examples")
    else:
        print("Dataset not found, using sample data")
        dataset = Dataset.from_list(
            [
                {
                    "instruction": "Summarize the key terms of this contract.",
                    "input": "This Service Agreement is entered into between...",
                    "output": "This is a service agreement that establishes...",
                }
            ]
        )

    # Tokenize dataset
    def tokenize(example):
        prompt = format_prompt(example)
        tokenized = tokenizer(
            prompt,
            truncation=True,
            max_length=2048,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    tokenized_dataset = dataset.map(tokenize, remove_columns=dataset.column_names)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        bf16=True,
        optim="paged_adamw_8bit" if args.use_4bit else "adamw_torch",
        gradient_checkpointing=True,
        report_to="none",
    )

    # Initialize trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        tokenizer=tokenizer,
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Save model
    print(f"Saving model to {args.output_dir}")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    # Save training config
    config = {
        "base_model": args.base_model,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "epochs": args.num_epochs,
        "learning_rate": args.learning_rate,
    }
    with open(f"{args.output_dir}/training_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("Training complete!")


if __name__ == "__main__":
    main()
