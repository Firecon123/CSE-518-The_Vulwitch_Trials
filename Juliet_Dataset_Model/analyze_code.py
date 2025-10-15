import os
import sys
import time
import json
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_dir = os.path.join(root_dir, "Juliet_Dataset_Model", "output")

training_config = {
    "model_name": "Salesforce/codet5-small",
    "max_input_length": 512,
    "max_target_length": 128,
    "num_epochs": 3,
    "batch_size": 4,
    "learning_rate": 5e-5,
    "warmup_steps": 100,
    "weight_decay": 0.01,
    "eval_steps": 500,
    "save_steps": 500,
    "logging_steps": 100,
    "save_total_limit": 3,
    "model_output_dir": os.path.join(output_dir, "juliet_codet5_model"),
    "evaluation_results_path": os.path.join(output_dir, "evaluation_results.json"),
}

model = None
tokenizer = None

def calculate_simple_confidence(prediction: str) -> float:
    if not prediction.strip():
        return 0.0
    if "CWE" in prediction and "-" in prediction:
        return 0.9
    if prediction.startswith("SAFE"):
        return 0.8
    if len(prediction.split()) < 3:
        return 0.6
    return 0.7


def get_model_metrics():
    try:
        eval_file = training_config["evaluation_results_path"]
        if os.path.exists(eval_file):
            with open(eval_file, 'r') as f:
                data = json.load(f)
            safe_acc = data.get("safe_accuracy", 0)
            vuln_acc = data.get("vulnerable_accuracy", 0)
            overall_acc = data.get("overall_accuracy", 0)
            total_safe = data.get("total_safe", 0)
            total_vuln = data.get("total_vulnerable", 0)
            tp = vuln_acc * total_vuln
            fp = (1 - safe_acc) * total_safe
            fn = (1 - vuln_acc) * total_vuln
            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0
            recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0
            f1 = round(2 * (precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0
            return {
                "overall_accuracy": overall_acc,
                "safe_accuracy": safe_acc,
                "vulnerable_accuracy": vuln_acc,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives": int(tp),
                "true_negatives": int(safe_acc * total_safe),
                "model_version": "retrained"
            }
    except Exception as e:
        print(f"Warning: Could not load metrics: {e}")
    return {
        "overall_accuracy": "unknown",
        "safe_accuracy": "unknown",
        "vulnerable_accuracy": "unknown",
        "precision": "unknown",
        "recall": "unknown",
        "f1_score": "unknown",
        "false_positives": "unknown",
        "false_negatives": "unknown",
        "true_positives": "unknown",
        "true_negatives": "unknown",
        "model_version": "unknown"
    }


def predict_vulnerability_detailed(code: str, language: str = "C") -> dict:
    start = time.time()
    input_text = f"<vuln_detect> <lang> {language}\n{code.strip()}"
    tokenize_start = time.time()
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, padding=True,
                       max_length=training_config["max_input_length"])
    tokenize_time = time.time() - tokenize_start
    inference_start = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=training_config["max_target_length"],
            num_beams=4,
            early_stopping=True,
            do_sample=False
        )
    inference_time = time.time() - inference_start
    prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)
    confidence = calculate_simple_confidence(prediction)
    total = time.time() - start
    return {
        "prediction": prediction,
        "confidence": confidence,
        "method": "neural_network",
        "timing": {
            "total_time_ms": round(total * 1000, 2),
            "tokenize_time_ms": round(tokenize_time * 1000, 2),
            "inference_time_ms": round(inference_time * 1000, 2),
            "pattern_time_ms": 0
        },
        "model_metrics": get_model_metrics()
    }


def analyze_file(file_path):
    print(f"\nAnalyzing file: {file_path}")
    print("=" * 60)
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            code = f.read()
        language = "C++" if file_path.endswith('.cpp') else "C"
        print(f"Language: {language}")
        print(f"\nCode:\n{'-'*40}")
        print(code)
        print(f"{'-'*40}\nAnalyzing...")
        detailed_result = predict_vulnerability_detailed(code, language)
        prediction = detailed_result["prediction"]
        is_safe = prediction.startswith("SAFE") or "No vulnerability" in prediction
        has_vuln = not is_safe and ("CWE" in prediction or "vulnerability" in prediction.lower())
        result = {
            "file": str(file_path),
            "language": language,
            "code": code,
            "prediction": prediction,
            "has_vulnerability": has_vuln,
            "is_safe": is_safe,
            "detailed_metrics": detailed_result
        }
        # JSON output removed - use analyze_c_code() for main functionality
        print("\nVulnerability Analysis:")
        print(f"  Prediction: {prediction}")
        print(f"  Confidence: {detailed_result['confidence']:.3f}")
        print(f"  Method: {detailed_result['method']}")
        print("  Status:", "[WARNING] VULNERABILITY DETECTED" if has_vuln else "[SAFE] No vulnerability detected" if is_safe else "[UNKNOWN] Unable to determine status")
        
        # Always show detailed metrics
        t = detailed_result["timing"]
        print("\nPerformance Metrics:")
        print(f"  Total: {t['total_time_ms']} ms")
        print(f"  Tokenization: {t['tokenize_time_ms']} ms")
        print(f"  Inference: {t['inference_time_ms']} ms")
        if t["pattern_time_ms"] > 0:
            print(f"  Pattern Matching: {t['pattern_time_ms']} ms")
        
        # Always show model metrics
        model_metrics = detailed_result["model_metrics"]
        print("\nModel Performance:")
        print(f"  Overall Accuracy: {model_metrics['overall_accuracy']}")
        print(f"  Safe Code Accuracy: {model_metrics['safe_accuracy']}")
        print(f"  Vulnerable Code Accuracy: {model_metrics['vulnerable_accuracy']}")
        print(f"  Precision: {model_metrics['precision']}")
        print(f"  Recall: {model_metrics['recall']}")
        print(f"  F1-Score: {model_metrics['f1_score']}")
        print(f"  False Positives: {model_metrics['false_positives']}")
        print(f"  False Negatives: {model_metrics['false_negatives']}")
        print(f"  True Positives: {model_metrics['true_positives']}")
        print(f"  True Negatives: {model_metrics['true_negatives']}")
        print(f"  Model Version: {model_metrics['model_version']}")
        
        return result
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return {"error": str(e)}


def analyze_directory(dir_path):
    results = []
    all_files = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(('.c', '.cpp')):
                all_files.append(os.path.join(root, file))
    print(f"Found {len(all_files)} C/C++ files to analyze")
    for f in all_files:
        results.append(analyze_file(f))
    return results


def load_model(model_path=None):
    global model, tokenizer
    if model is None or tokenizer is None:
        print("Loading model...")
        model_path = model_path or training_config["model_output_dir"]
        model_path = os.path.abspath(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    return model, tokenizer


def analyze_c_code(code_string: str, language: str = "C"):
    load_model()
    
    detailed_result = predict_vulnerability_detailed(code_string, language)
    prediction = detailed_result["prediction"]
    is_safe = prediction.startswith("SAFE") or "No vulnerability" in prediction
    has_vuln = not is_safe and ("CWE" in prediction or "vulnerability" in prediction.lower())
    
    result = {
        "code": code_string,
        "language": language,
        "prediction": prediction,
        "has_vulnerability": has_vuln,
        "is_safe": is_safe,
        "confidence": detailed_result['confidence'],
        "method": detailed_result['method'],
        "timing": detailed_result["timing"],
        "model_metrics": detailed_result["model_metrics"]
    }
    
    print(f"\n{'='*60}")
    print("CODE VULNERABILITY ANALYSIS")
    print(f"{'='*60}")
    print(f"Language: {language}")
    print(f"\nCode:\n{'-'*40}")
    print(code_string)
    print(f"{'-'*40}")
    
    print("\nVulnerability Analysis:")
    print(f"  Prediction: {prediction}")
    print(f"  Confidence: {detailed_result['confidence']:.3f}")
    print(f"  Method: {detailed_result['method']}")
    print("  Status:", "[WARNING] VULNERABILITY DETECTED" if has_vuln else "[SAFE] No vulnerability detected" if is_safe else "[UNKNOWN] Unable to determine status")
    
    t = detailed_result["timing"]
    print("\nPerformance Metrics:")
    print(f"  Total Time: {t['total_time_ms']} ms")
    print(f"  Tokenization: {t['tokenize_time_ms']} ms")
    print(f"  Inference: {t['inference_time_ms']} ms")
    if t["pattern_time_ms"] > 0:
        print(f"  Pattern Matching: {t['pattern_time_ms']} ms")
    
    model_metrics = detailed_result["model_metrics"]
    print("\nModel Performance:")
    print(f"  Overall Accuracy: {model_metrics['overall_accuracy']}")
    print(f"  Safe Code Accuracy: {model_metrics['safe_accuracy']}")
    print(f"  Vulnerable Code Accuracy: {model_metrics['vulnerable_accuracy']}")
    print(f"  Precision: {model_metrics['precision']}")
    print(f"  Recall: {model_metrics['recall']}")
    print(f"  F1-Score: {model_metrics['f1_score']}")
    print(f"  False Positives: {model_metrics['false_positives']}")
    print(f"  False Negatives: {model_metrics['false_negatives']}")
    print(f"  True Positives: {model_metrics['true_positives']}")
    print(f"  True Negatives: {model_metrics['true_negatives']}")
    print(f"  Model Version: {model_metrics['model_version']}")
    
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}")
    
    return result


def analyze_file_contents(code: str):
    """Legacy function for backward compatibility"""
    load_model()
    inputs = tokenizer(code, return_tensors="pt", truncation=True, padding=True)
    outputs = model.generate(**inputs, max_length=training_config["max_target_length"])
    decoded_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return decoded_output
