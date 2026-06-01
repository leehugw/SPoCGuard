import subprocess
import re
import logging

logger = logging.getLogger(__name__)

def run_halmos(contract_name="HalmosPropertyTest", foundry_dir=None):
    logger.info(f"Executing Halmos Symbolic Math Solver for contract: {contract_name}...")
    try:
        result = subprocess.run(
            ["halmos", "--contract", contract_name], 
            capture_output=True, 
            text=True,
            timeout=120, # limit to 2 minutes to prevent hanging
            cwd=foundry_dir  # To make sure it runs in the context of the Foundry workspace
        )
        
        output = result.stdout + result.stderr
        
        match = re.search(r"Counterexample:\s*(.*)", output)
        if match:
            params = match.group(1).strip()
            logger.info(f"Halmos found exploit parameters: {params}")
            return params
        else:
            logger.warning("Halmos could not find a mathematical exploit path.")
            logger.error("============= HALMOS RAW OUTPUT =============")
            print(output) 
            logger.error("=============================================")
            return None
            
    except Exception as e:
        logger.error(f"Halmos engine error: {e}")
        return None