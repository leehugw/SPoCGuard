import os
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class DatasetPreprocessor:
    def __init__(self, dataset_dir: str, output_dir: str):
        self.dataset_dir = dataset_dir
        self.output_dir = output_dir
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def process_all(self):
        logger.info(f"[*] Starting dataset preprocessing from: {self.dataset_dir}")
        processed_count = 0
        
        for filename in os.listdir(self.dataset_dir):
            if filename.endswith(".sol"):
                file_path = os.path.join(self.dataset_dir, filename)
                self._process_single_file(file_path, filename)
                processed_count += 1
                
        logger.info(f"[+] Successfully preprocessed {processed_count} files. Saved to: {self.output_dir}")

    def _process_single_file(self, file_path: str, filename: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = self._inject_spdx(content)
        
        content = self._lock_pragma(content)
        
        content = self._mock_constructor(content)

        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _inject_spdx(self, content: str) -> str:
        if "SPDX-License-Identifier" not in content:
            logger.debug("Injecting SPDX License...")
            return "// SPDX-License-Identifier: MIT\n" + content
        return content

    def _lock_pragma(self, content: str) -> str:
        pattern = r'pragma solidity\s+\^([^;]+);'
        def replacer(match):
            version = match.group(1)
            logger.debug(f"Locking pragma to {version}")
            return f"pragma solidity {version};"
        
        return re.sub(pattern, replacer, content)

    def _mock_constructor(self, content: str) -> str:
        pattern = r'constructor\s*\((.*?)\)\s*([^\{]*)\{'
        
        def replacer(match):
            args_str = match.group(1).strip()
            modifiers = match.group(2)
            
            if not args_str:
                return match.group(0)
            
            logger.info(f"Mocking constructor args: {args_str}")
            
            injections = []
            args = [a.strip() for a in args_str.split(',')]
            
            for arg in args:
                parts = arg.split()
                if len(parts) >= 2:
                    var_type = parts[0]
                    var_name = parts[-1]
                    
                    if 'address' in var_type:
                        injections.append(f"{var_type} {var_name} = address(0xDEADBEEF);")
                    elif 'uint' in var_type:
                        injections.append(f"{var_type} {var_name} = 1000000;")
                    elif 'bool' in var_type:
                        injections.append(f"{var_type} {var_name} = true;")
                    elif 'string' in var_type:
                        injections.append(f'{var_type} {var_name} = "MockString";')
                    else:
                        injections.append(f"// TODO: Unsupported type mock for {var_type} {var_name}")
            
            injection_str = "\n        ".join(injections)
            return f'constructor() {modifiers}{{\n        {injection_str}'

        return re.sub(pattern, replacer, content)


if __name__ == "__main__":
    INPUT_DATASET = "dataset_raw"       # Thư mục chứa code chưa xử lý
    OUTPUT_DATASET = "dataset_clean"    # Thư mục chứa code đã được "làm sạch"
    
    preprocessor = DatasetPreprocessor(INPUT_DATASET, OUTPUT_DATASET)
    preprocessor.process_all()