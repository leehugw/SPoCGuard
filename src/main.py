import os
import sys
import json
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from chatgpt_api import Chat
except ImportError:
    logger.error("Cannot find model.py.")
    sys.exit(1)

def welcome():
    print(r"""
  ____  ____         ____  ____                     _ 
 / ___||  _ \  ___  / ___|/ ___| _   _  __ _ _ __  | |
 \___ \| |_) |/ _ \| |   | |  _ | | | |/ _` | '__| | |
  ___) |  __/| (_) | |___| |_| || |_| | (_| | |    |_|
 |____/|_|    \___/ \____|\____| \__,_|\__,_|_|    (_)
    """)
    logger.info("SPoCGuard: Starting Smart Contract Analysis Pipeline...\n")

def main():
    welcome()
    
    SOL_DIR = os.path.join(BASE_DIR, "sourcecode", "obj")
    OUTPUT_DIR = os.path.join(BASE_DIR, "sourcecode", "res")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    chat = Chat()

    for filename in os.listdir(SOL_DIR):
        if not filename.endswith(".sol"):
            continue

        sol_path = os.path.join(SOL_DIR, filename)
        slither_json_path = os.path.join(OUTPUT_DIR, f"slither_{filename}.json")
        final_res_path = os.path.join(OUTPUT_DIR, f"final_{filename}.json")
        
        logger.info(f"Running Slither static analysis on: {filename}...")
        
        subprocess.run([
            "slither", sol_path, "--json", slither_json_path
        ], capture_output=True, text=True)
        
        if not os.path.exists(slither_json_path):
            logger.warning(f"Slither failed to generate JSON for {filename}. Skipping.")
            continue
            
        logger.info("Parsing Slither analysis results...")
        with open(slither_json_path, 'r', encoding='utf-8') as f:
            try:
                slither_data = json.load(f)
            except Exception:
                slither_data = {}
                
        with open(sol_path, 'r', encoding='utf-8') as f:
            sol_code = f.read()
            
        detectors_found = []
        if "results" in slither_data and "detectors" in slither_data["results"]:
            for det in slither_data["results"]["detectors"]:
                detectors_found.append({
                    "vulnerability": det.get("check"),
                    "description": det.get("description")
                })
        
        logger.info("Sending AST and Code to Qwen3-Coder for validation and PoC generation...")
        
        prompt = f'''
Please analyze the following Solidity Smart Contract:

--- SOURCE CODE ---
{sol_code}
-------------------

The Slither static analyzer detected the following potential vulnerabilities:
{json.dumps(detectors_found, indent=2)}

Based on the above information, please perform the following tasks:
1. Validate if these suspected vulnerabilities are true positives.
2. Provide a detailed explanation of the attack scenario (HOW to exploit).
3. Provide a brief Proof of Concept (PoC) script using Foundry.
Ensure your response strictly follows the JSON format requested.
'''
        
        chat.newSession()
        ai_response = chat.sendMessages(prompt)
        
        final_result = {
            "target_file": filename,
            "slither_raw_findings": detectors_found,
            "llm_expert_analysis_and_poc": ai_response
        }
        
        with open(final_res_path, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=4)
            
        logger.info(f"Successfully processed {filename}! Results saved to: {final_res_path}\n")

    logger.info("DONE: All files have been processed successfully!")

if __name__ == '__main__':
    main()