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
    from model import Chat
except ImportError:
    logger.error("Cannot find model.py.")
    sys.exit(1)

def welcome():
    print(r"""
███████╗██████╗  ██████╗  ██████╗ ██████╗  █████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗
██╔════╝██╔══██╗██╔═══██╗██╔════╝██╔════╝ ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔══██╗
███████╗██████╔╝██║   ██║██║     ██║  ███╗███████║██║   ██║███████║██████╔╝██║  ██║
╚════██║██╔═══╝ ██║   ██║██║     ██║   ██║██╔══██║██║   ██║██╔══██║██╔══██╗██║  ██║
███████║██║     ╚██████╔╝╚██████╗╚██████╔╝██║  ██║╚██████╔╝██║  ██║██║  ██║██████╔╝
╚══════╝╚═╝      ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
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

        base_name, _ = os.path.splitext(filename)

        sol_path = os.path.join(SOL_DIR, filename)
        slither_json_path = os.path.join(OUTPUT_DIR, f"temp_slither_{base_name}.json")
        final_res_path = os.path.join(OUTPUT_DIR, f"final_{base_name}.json")
        poc_file_path = os.path.join(OUTPUT_DIR, f"poc_{base_name}.t.sol")
        
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
        
        if os.path.exists(slither_json_path):
            os.remove(slither_json_path)
                
        with open(sol_path, 'r', encoding='utf-8') as f:
            sol_code = f.read()
            
        logger.info("Filtering...")
        detectors_found = []
        if "results" in slither_data and "detectors" in slither_data["results"]:
            for det in slither_data["results"]["detectors"]:
                impact = det.get("impact", "Unknown")
                
                if impact in ["High", "Medium"]:
                    affected_locations = []
                    for elem in det.get("elements", []):
                        if "name" in elem and "source_mapping" in elem:
                            lines = elem["source_mapping"].get("lines", [])
                            if lines:
                                location_info = f"{elem.get('type', 'element')} '{elem['name']}' (lines: {lines[0]}-{lines[-1]})"
                                affected_locations.append(location_info)
                    
                    detectors_found.append({
                        "vulnerability": det.get("check"),
                        "severity": impact,
                        "confidence": det.get("confidence"),
                        "description": det.get("description", "").strip(),
                        "locations": affected_locations
                    })
                    
        if not detectors_found:
            logger.info(f"No High/Medium vulnerabilities found in {filename}")
            continue
        
        logger.info("Sending Source Code and Slither Report to Qwen3-Coder for PoC generation...")
        
        prompt = f'''
Please analyze the following Solidity Smart Contract:

--- SOURCE CODE (File: {filename}) ---
{sol_code}
-------------------

The Slither static analyzer detected the following vulnerabilities:
{json.dumps(detectors_found, indent=2)}

Task:
Generate a Foundry Proof of Concept (PoC) script to exploit these vulnerabilities.

CRITICAL INSTRUCTIONS: 
1. Output ONLY the raw Solidity PoC code. Do NOT include any explanations, markdown formatting, or conversational text. Start directly with "pragma solidity".
2. You MUST import the target contract using its actual filename EXACTLY like this: import "../src/{filename}";
3. You MUST import Foundry standard library: import "forge-std/Test.sol"; and your contract MUST inherit from Test (e.g., contract PoC is Test).
4. STRICT FUNCTION RULE: Do NOT assume the target tokens are standard ERC20. You are strictly FORBIDDEN from calling `approve()`, `mint()`, or any other function unless it is EXPLICITLY WRITTEN in the SOURCE CODE above. If `approve` does not exist in the source, DO NOT call it. You must exploit the vulnerability using ONLY the existing functions.
5. MOCKING RULE: If you need to write a Mock contract to simulate an interface, DO NOT use the `override` keyword for functions that are not explicitly defined in the provided interface.
'''
        
        chat.newSession()
        ai_response = chat.sendMessages(prompt)
        
        final_result = {
            "target_file": filename,
            "slither_raw_findings": detectors_found
        }
        with open(final_res_path, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=4)
            
        with open(poc_file_path, 'w', encoding='utf-8') as f:
            f.write(ai_response)
            
        logger.info(f"Successfully processed {filename}!")
        logger.info(f"Vulnerabilities saved to: {final_res_path}")
        logger.info(f"PoC Code saved to: {poc_file_path}\n")
            
        logger.info(f"Successfully processed {filename}! Results saved to: {final_res_path}\n")

    logger.info("ALL DONE!")

if __name__ == '__main__':
    main()