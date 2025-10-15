# Run this file from the CSE-518-The_VULWITCH_TRIALS/Juliet_Dataset_Model

import json
import sys
import time
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from juliet_data_processor import run_juliet_processing
from train_codet5_juliet import CodeT5_Model_Training


data_cfg = {
    "testing_limit": 2000, #For testing, I have 1000 here, it takes about 15 mins, increase later
    "train_path": "./output/juliet_training_data.jsonl",
}

training_cfg = {
    "model_name": "Salesforce/codet5-small",
    "max_input": 512,
    "max_target": 128,
    "epochs": 3,
    "batch": 4,
    "learning_rate": 5e-5,
    "warmup": 100,
    "decay": 0.01,
    "eval_steps": 500,
    "save_steps": 500,
    "log_steps": 100,
    "save_limit": 3,
    "model_out": "./output/juliet_codet5_model",
    "eval_out": "./output/evaluation_results.json",
}

dataset_dir = "../Datasets/C"
output_dir = "./output"
os.makedirs(output_dir, exist_ok=True)


def automated_model_training(skip_data_preprocessing: bool, skip_model_training: bool, use_existing_data_file=True):
    print(not os.path.exists(data_cfg["train_path"]))
    if not os.path.exists(dataset_dir):
        print(f"Cannot find dataset at {dataset_dir}. Make sure you're in the juliet_dataset_model folder.")
        return 1

    start = time.time()
    try:
        if not skip_data_preprocessing:
            if not use_existing_data_file or not os.path.exists(data_cfg["train_path"]):
                print("Processing Data...")
                run_juliet_processing(dataset_dir, data_cfg["testing_limit"], data_cfg["train_path"])
            else:
                print("Using existing processed data.")
        else:
            print("skipped preprocessing")
        if not skip_model_training:
            if not os.path.exists(data_cfg["train_path"]):
                print("Missing training data:", data_cfg["train_path"])
                return 1

            print("Training model on processed data...")
            CodeT5_Model_Training(training_cfg, data_cfg["train_path"])

        total = time.time() - start
        print("\n" + "=" * 60)
        print(f'Automation completed in {total:.2f} seconds')
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\nPipeline failed: {e}")
        return 1

# automated_model_training(False, False, False)

