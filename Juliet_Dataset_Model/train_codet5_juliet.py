import os
import json
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import TensorDataset
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq
)
import warnings
warnings.filterwarnings("ignore")


def prepare_dataset(data, tokenizer, max_input_length, max_target_length):
    inputs = []
    targets = []
    for item in data:
        inputs.append(item["input_text"])
        targets.append(item["target_text"])

    model_inputs = tokenizer(
        inputs,
        max_length=max_input_length,
        truncation=True,
        padding="max_length"
    )

    labels = tokenizer(
        targets,
        max_length=max_target_length,
        truncation=True,
        padding="max_length"
    )

    model_inputs["labels"] = labels["input_ids"]
    return Dataset.from_dict(model_inputs)

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.where(predictions != -100, predictions, tokenizer.pad_token_id)

    decoded_preds = tokenizer.batch_decode(predictions, skip_special_tokens=True)
    decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)

    exact_matches = sum(1 for p, l in zip(decoded_preds, decoded_labels) if p.strip() == l.strip())
    accuracy = exact_matches / len(decoded_preds)
    return {
        "accuracy": accuracy,
        "exact_matches": exact_matches,
        "total_samples": len(decoded_preds)
    }

def CodeT5_Model_Training(training_cfg, data_path):
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}")
        return 1
    
    tokenizer = AutoTokenizer.from_pretrained(training_cfg["model_name"])
    model = AutoModelForSeq2SeqLM.from_pretrained(training_cfg["model_name"])
    
    special_tokens = ["<vuln_detect>", "<lang>", "<cwe>", "<line>", "<safe>"]
    tokenizer.add_special_tokens({'additional_special_tokens': special_tokens})
    model.resize_token_embeddings(len(tokenizer))
    
    data = []
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
                
    train_data, test_data = train_test_split(data, test_size=0.1, random_state=42)
    
    train_dataset = prepare_dataset(train_data, tokenizer, training_cfg["max_input"], training_cfg["max_target"])
    test_dataset = prepare_dataset(test_data, tokenizer, training_cfg["max_input"], training_cfg["max_target"])
    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model, padding=True)
    
    training_args = Seq2SeqTrainingArguments(
        output_dir=training_cfg["model_out"],
        do_train=True,
        eval_strategy="steps",
        eval_steps=training_cfg["eval_steps"],
        logging_steps=training_cfg["log_steps"],
        save_steps=training_cfg["save_steps"],
        save_total_limit=training_cfg["save_limit"],
        per_device_train_batch_size=training_cfg["batch"],
        per_device_eval_batch_size=training_cfg["batch"],
        gradient_accumulation_steps=2,
        learning_rate=training_cfg["learning_rate"],
        num_train_epochs=training_cfg["epochs"],
        weight_decay=training_cfg["decay"],
        warmup_steps=training_cfg["warmup"],
        predict_with_generate=True,
        fp16=torch.cuda.is_available(),
        dataloader_pin_memory=False,
        remove_unused_columns=False,
        report_to=None
    )
    
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics
    )
    
    print("Starting training...")
    trainer.train()
    
    trainer.save_model()
    tokenizer.save_pretrained(training_cfg["model_out"])
    print(f"Training completed. Model saved to {training_cfg['model_out']}")


# training_cfg = {
#     "model_name": "Salesforce/codet5-small",
#     "max_input": 512,
#     "max_target": 128,
#     "epochs": 3,
#     "batch": 4,
#     "learning_rate": 5e-5,
#     "warmup": 100,
#     "decay": 0.01,
#     "eval_steps": 500,
#     "save_steps": 500,
#     "log_steps": 100,
#     "save_limit": 3,
#     "model_out": "./output/juliet_codet5_model_more_data",
#     "eval_out": "./output/evaluation_results_more_data.json",
# }

# CodeT5_Model_Training(training_cfg, "./output/juliet_training_data.jsonl")