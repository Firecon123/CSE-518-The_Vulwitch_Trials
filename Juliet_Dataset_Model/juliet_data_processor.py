import os
import time
import re
import json
import random

cwe_mapping = {
    "CWE15": "External Control of System or Configuration Setting",
    "CWE121": "Stack Based Buffer Overflow",
    "CWE122": "Heap Based Buffer Overflow",
    "CWE123": "Write What Where Condition",
    "CWE124": "Buffer Underwrite",
    "CWE126": "Buffer Overread",
    "CWE127": "Buffer Underread",
    "CWE134": "Uncontrolled Format String",
    "CWE190": "Integer Overflow",
    "CWE191": "Integer Underflow",
    "CWE369": "Divide by Zero",
    "CWE401": "Memory Leak",
    "CWE415": "Double Free",
    "CWE416": "Use After Free",
    "CWE457": "Use of Uninitialized Variable",
    "CWE476": "NULL Pointer Dereference",
    "CWE590": "Free Memory Not on Heap",
    "CWE761": "Free Pointer Not at Start of Buffer",
    "CWE762": "Mismatched Memory Management Routines",
    "CWE775": "Missing Release of File Descriptor or Handle",
    "CWE789": "Uncontrolled Memory Allocation",
    "CWE835": "Infinite Loop"
}

def extract_cwe_info(file_path, content=""):
    filename = os.path.basename(file_path)
    match = re.search(r'(CWE\d+)', filename)
    if match:
        cwe_id = match.group(1)
        cwe_name = cwe_mapping.get(cwe_id, "Unknown Vulnerability")
        if content:
            desc_match = re.search(r'CWE:\s*(\d+)\s+([^\n]+)', content)
            if desc_match:
                cwe_name = desc_match.group(2).strip()
        return cwe_id, cwe_name
    return "UNKNOWN", "Unknown Vulnerability"

def find_vulnerable_function(content):
    code = []
    in_bad = False
    brace_count = 0
    for line in content.splitlines():
        if in_bad or re.search(r'void.*bad\(\)', line, re.IGNORECASE):
            in_bad = True
            code.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and '{' in line:
                break
    return '\n'.join(code).strip()

def find_safe_function(content):
    code = []
    in_good = False
    brace_count = 0
    for line in content.splitlines():
        if in_good or re.search(r'void.*good\(\)', line, re.IGNORECASE):
            in_good = True
            code.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and '{' in line:
                break
    return '\n'.join(code).strip()

def extract_vulnerability_description(content, cwe_id):
    description_parts = []
    for line in content.split('\n'):
        if re.search(r'@description|CWE:', line, re.IGNORECASE):
            clean_line = re.sub(r'^\s*/\*|\*/.*$|^\s*\*', '', line).strip()
            description_parts.append(clean_line)
    if description_parts:
        return ' '.join(description_parts)
    return f"{cwe_id}: {cwe_mapping.get(cwe_id, 'Vulnerability detected')}"

def process_file(file_path):
    results = []
    try:
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        cwe_id, cwe_name = extract_cwe_info(file_path, content)
        language = "C++" if file_path.endswith('.cpp') else "C"

        if 'bad()' in content:
            code = find_vulnerable_function(content)
            desc = extract_vulnerability_description(content, cwe_id)
            results.append({"cwe_id": cwe_id, "cwe_name": cwe_name, "vulnerable_code": code, "file_path": file_path, "language": language, "description": desc})

        if 'good()' in content:
            code = find_safe_function(content)
            results.append({"cwe_id": "SAFE", "cwe_name": "Safe Code", "vulnerable_code": code, "file_path": file_path, "language": language, "description": "This code appears to be safe based on training data"})
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return results

def process_dataset(juliet_path, number_of_files):
    files = []
    testcases_dir = os.path.join(juliet_path, "testcases")
    if not os.path.exists(testcases_dir):
        print(f"Testcases directory not found: {testcases_dir}")
        return []

    for root, _, filenames in os.walk(testcases_dir):
        for filename in filenames:
            if filename.endswith(('.c', '.cpp')):
                files.append(os.path.join(root, filename))

    random.shuffle(files)
    files = files[:number_of_files]

    training_examples = []
    for file in files:
        details = process_file(file)
        for function_info in details:
            input_text = f"<vuln_detect> <lang> {function_info['language']}\n{function_info['vulnerable_code']}"
            target_text = "SAFE - No vulnerability detected" if function_info['cwe_id'] == "SAFE" else f"{function_info['cwe_id']} - {function_info['cwe_name']}"
            # print(target_text)
            training_examples.append({
                "input_text": input_text,
                "target_text": target_text
            })
    print(f"Successfully processed {len(training_examples)} examples")
    return training_examples

def save_dataset(training_examples, output_path):
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(output_path, 'w', encoding='utf-8', errors="ignore") as f:
        for data in training_examples:
            json.dump({"input_text": data["input_text"], "target_text": data["target_text"]}, f, ensure_ascii=False)
            f.write('\n')
    print(f"Dataset saved to {output_path}")

def run_juliet_processing(juliet_path, number_of_files, output_file):
    if not os.path.exists(juliet_path):
        print(f"Cannot find Juliet test suite at {juliet_path}")
        return 1
    start = time.time()
    print("Starting Juliet dataset processing...")
    training_examples = process_dataset(juliet_path, number_of_files)
    if training_examples:
        save_dataset(training_examples, output_file)
        print("DATASET SUMMARY")
        print(f"Total examples: {len(training_examples)}")
        print(f"Number of files requested: {number_of_files}")
    else:
        print("No training examples generated. Check your Juliet test suite path.")
    print(f"\nPipeline completed in {time.time() - start:.2f} seconds")
    return 0

# run_juliet_processing("../Datasets/C", 2000, "output/juliet_training_data_test.jsonl")
