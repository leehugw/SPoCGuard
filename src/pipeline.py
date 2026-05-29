import os
import sys
import json
import subprocess
import logging
import shutil
import re

from model import Chat
from halmos_engine import run_halmos
from template_manager import get_template

logger = logging.getLogger(__name__)

class AuditPipeline:
    def __init__(self, sol_dir, output_dir, foundry_dir):
        self.sol_dir = sol_dir
        self.output_dir = output_dir
        self.foundry_dir = foundry_dir
        self.foundry_src = os.path.join(foundry_dir, "src")
        self.foundry_test = os.path.join(foundry_dir, "test")
        self.foundry_script = os.path.join(foundry_dir, "script")
        
        self.final_results_dir = os.path.join(self.foundry_dir, "archive")
        
        self.chat = Chat()

        for directory in [self.output_dir, self.final_results_dir, self.foundry_src, self.foundry_test, self.foundry_script]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                
        logger.info("[*] Global Setup: Cleaning environment and linking sources...")
        
        directories_to_clean = [
            self.output_dir, 
            self.final_results_dir, 
            self.foundry_src, 
            self.foundry_test, 
            self.foundry_script
        ]
        for d in directories_to_clean:
            if os.path.exists(d):
                for item in os.listdir(d):
                    file_path = os.path.join(d, item)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        
        for item in os.listdir(self.sol_dir):
            if item.endswith(".sol"):
                shutil.copy2(os.path.join(self.sol_dir, item), os.path.join(self.foundry_src, item))

    def process_all(self):
        for filename in os.listdir(self.sol_dir):
            if filename.endswith(".sol"):
                self.process_single_file(filename)
        logger.info(f"\n[🚀 DONE] Check '{self.final_results_dir}' for Final Detection JSON and PoCs.")

    def process_single_file(self, filename):
        logger.info(f"\n{'='*50}\n========== PROCESSING: {filename} ==========\n{'='*50}")
        base_name, _ = os.path.splitext(filename)
        
        for item in os.listdir(self.foundry_test):
            if item.endswith(".sol"):
                os.remove(os.path.join(self.foundry_test, item))

        target_sol_path = os.path.join(self.foundry_src, filename)
        slither_json_path = os.path.join(self.output_dir, f"temp_slither_{base_name}.json")
        final_detect_path = os.path.join(self.final_results_dir, f"final_detect_{base_name}.json")
        
        logger.info(f"[*] Running Slither static analysis on {filename}...")
        subprocess.run(["slither", target_sol_path, "--json", slither_json_path], capture_output=True, text=True)
        
        if not os.path.exists(slither_json_path):
            logger.warning(f"[-] Slither failed to analyze {filename}. Skipping.")
            return
            
        with open(slither_json_path, 'r', encoding='utf-8') as f:
            try:
                slither_data = json.load(f)
            except Exception:
                slither_data = {}
        
        if os.path.exists(slither_json_path):
            os.remove(slither_json_path)
                
        with open(target_sol_path, 'r', encoding='utf-8') as f:
            sol_code = f.read()
            
        detectors_found = []
        if "results" in slither_data and "detectors" in slither_data["results"]:
            for det in slither_data["results"]["detectors"]:
                impact = det.get("impact", "Unknown")
                check_type = det.get("check")
                
                if impact in ["High", "Medium"]:
                    vuln_function = "UnknownFunction"
                    contract_name = "UnknownContract"
                    affected_locations = []
                    
                    for elem in det.get("elements", []):
                        if "name" in elem and "source_mapping" in elem:
                            lines = elem["source_mapping"].get("lines", [])
                            if lines:
                                loc = f"{elem.get('type', 'element')} '{elem['name']}' (lines: {lines[0]}-{lines[-1]})"
                                affected_locations.append(loc)
                                
                        if elem.get("type") == "function":
                            vuln_function = elem.get("name")
                            parent = elem.get("type_specific_fields", {}).get("parent", {})
                            if parent.get("type") == "contract":
                                contract_name = parent.get("name")
                    
                    if vuln_function == "UnknownFunction":
                        for loc in affected_locations:
                            func_match = re.search(r"function '([A-Za-z0-9_]+)'", loc)
                            if func_match:
                                vuln_function = func_match.group(1)
                                break
                                
                    if contract_name == "UnknownContract":
                        contracts = re.findall(r"contract\s+([A-Za-z0-9_]+)", sol_code)
                        valid_contracts = [c for c in contracts if "Mock" not in c]
                        if valid_contracts:
                            contract_name = valid_contracts[-1]

                    detectors_found.append({
                        "vulnerability": check_type,
                        "severity": impact,
                        "contract_name": contract_name,
                        "function_name": vuln_function,
                        "locations": affected_locations
                    })
        
        if not detectors_found:
            logger.info(f"[+] No critical vulnerabilities found in {filename} by Slither. Skipping.")
            return
        
        # 3
        verified_vulnerabilities = []
        ai_suspected_vulnerabilities = []
        halmos_context = ""
        generated_halmos_files = [] 
        
        logger.info(f"[*] Filtering vulnerabilities through Halmos (Two-Tier System)...")
        for det in detectors_found:
            check_type = det["vulnerability"]
            contract_name = det["contract_name"].strip()
            vuln_function = det["function_name"].strip()
            
            template_str = get_template(check_type)
            
            if template_str and contract_name != "UnknownContract" and vuln_function != "UnknownFunction":
                logger.info(f"[!] Generating dynamic Halmos test for: {check_type} in {contract_name}.{vuln_function}()")
                
                dynamic_code = template_str \
                    .replace("{TARGET_FILENAME}", filename) \
                    .replace("{TARGET_CONTRACT}", contract_name) \
                    .replace("{TARGET_FUNCTION}", vuln_function)
                
                halmos_test_path = os.path.join(self.foundry_test, f"DynamicHalmos_{base_name}_{check_type}.t.sol")
                with open(halmos_test_path, "w", encoding="utf-8") as f:
                    f.write(dynamic_code)
                
                generated_halmos_files.append(halmos_test_path)
                
                logger.info("[*] Flushing Foundry cache...")
                subprocess.run(["forge", "clean"], cwd=self.foundry_dir, capture_output=True)
                
                halmos_contract_name = f"HalmosPropertyTest_{contract_name}"
                params = run_halmos(contract_name=halmos_contract_name, foundry_dir=self.foundry_dir)
                
                if params:
                    logger.info(f"[+] TIER 1: Halmos CONFIRMED vulnerability: {check_type}")
                    det["halmos_math_proof"] = params 
                    verified_vulnerabilities.append(det)
                    halmos_context += f"- Vulnerability: {check_type} in {contract_name}.{vuln_function}() | Params: {params}\n"
                else:
                    logger.warning(f"[-] TIER 2: Halmos failed to prove {check_type}. Downgrading to AI Suspected.")
                    ai_suspected_vulnerabilities.append(det)
            else:
                logger.info(f"[*] TIER 2: No template available for {check_type}. Sending directly to AI.")
                det["status"] = "AI_SUSPECTED"
                ai_suspected_vulnerabilities.append(det)

        if not verified_vulnerabilities and not ai_suspected_vulnerabilities:
            logger.info(f"[+] All findings dropped. Contract is likely safe. Stopping pipeline.")
            return

        # 3.5
        ai_filtered_vulnerabilities = []
        
        if ai_suspected_vulnerabilities:
            logger.info(f"[*] TIER 2: AI is analyzing {len(ai_suspected_vulnerabilities)} suspected findings to filter False Positives...")
            self.chat.newSession()
            
            detect_prompt = f'''
            You are a Senior Smart Contract Auditor.
            Analyze this Solidity Source Code:
            ---
            {sol_code}
            ---
            Static analysis flagged the following suspected vulnerabilities, but our formal verification engine could not prove them:
            {json.dumps(ai_suspected_vulnerabilities, indent=2)}
            
            Task:
            1. Review each suspected vulnerability against the source code.
            2. Determine if it is a TRUE POSITIVE (a real exploit) or a FALSE POSITIVE (safe/unexploitable).
            3. Return ONLY a JSON array containing the TRUE POSITIVES. 
            4. For each true positive, add a new field "explanation" explaining exactly how it can be exploited.
            5. If all are false positives, return an empty array [].
            
            CRITICAL: Output ONLY valid JSON. No markdown, no conversational text. Start with [ and end with ].
            '''
            
            raw_ai_detect = self.chat.sendMessages(detect_prompt)
            
            cleaned_json_str = raw_ai_detect.replace("```json\n", "").replace("```", "").strip()
            
            try:
                ai_filtered_vulnerabilities = json.loads(cleaned_json_str)
                logger.info(f"[+] AI successfully filtered Tier 2. Kept {len(ai_filtered_vulnerabilities)} real vulnerabilities.")
            except Exception as e:
                logger.error(f"[-] AI returned invalid JSON during detection: {e}. Defaulting to original Slither findings.")
                ai_filtered_vulnerabilities = ai_suspected_vulnerabilities

        # 4
        final_detect_data = {
            "target_file": filename,
            "tier_1_verified_findings": verified_vulnerabilities,
            "tier_2_odel_detected_findings": ai_filtered_vulnerabilities
        }
        with open(final_detect_path, 'w', encoding='utf-8') as f:
            json.dump(final_detect_data, f, indent=4)
        logger.info(f"[+] Saved AI-Verified Two-Tier Results to: {final_detect_path}")
        
        # 5
        if not verified_vulnerabilities and not ai_filtered_vulnerabilities:
            logger.info("[+] Contract is secure. No PoC needed.")
            return

        logger.info(f"[*] Sending verified context to AI for PoC Generation...")
        
        poc_prompt = f'''
        Task: Generate a single Foundry Proof of Concept (PoC) script exploiting the vulnerabilities found in {filename}.
        
        TIER 1 (Math Verified - MUST USE THESE PARAMS):
        {halmos_context if halmos_context else "None"}
        
        TIER 2 (AI Verified):
        {json.dumps(ai_filtered_vulnerabilities, indent=2)}
        
        CRITICAL: Output ONLY the raw Solidity PoC code. Start directly with "pragma solidity". No explanations.
        '''
        
        raw_poc_code = self.chat.sendMessages(poc_prompt)
        poc_code = raw_poc_code.replace("```solidity\n", "").replace("```", "").strip()
        
        poc_file_path = os.path.join(self.foundry_test, f"poc_{base_name}.t.sol")
        with open(poc_file_path, 'w', encoding='utf-8') as f:
            f.write(poc_code)
            
        logger.info(f"[+] AI Generated PoC successfully!")

        logger.info(f"[*] Moving ALL artifacts to: {self.final_results_dir}")
        shutil.move(poc_file_path, os.path.join(self.final_results_dir, f"poc_{base_name}.t.sol"))
        for h_file in generated_halmos_files:
            if os.path.exists(h_file):
                filename_only = os.path.basename(h_file)
                shutil.move(h_file, os.path.join(self.final_results_dir, filename_only))
                
        logger.info(f"========== COMPLETED PROCESSING FOR: {filename} ==========\n")