import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from pipeline import AuditPipeline
from preprocessor import DatasetPreprocessor

def welcome():
    print(r"""
 ███████╗██████╗  ██████╗  ██████╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗ 
 ██╔════╝██╔══██╗██╔═══██╗██╔════╝██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗
 ███████╗██████╔╝██║   ██║██║     ██║  ███╗██║   ██║███████║██████╔╝██║  ██║
 ╚════██║██╔═══╝ ██║   ██║██║     ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║
 ███████║██║     ╚██████╔╝╚██████╗╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
 ╚══════╝╚═╝      ╚═════╝  ╚═════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ 
    """)
    logger.info("SPoCGuard: Starting...\n")

def main():
    welcome()

    SOL_DIR = os.path.join(BASE_DIR, "sourcecode") 
    OUTPUT_DIR = os.path.join(BASE_DIR, "res") 
    FOUNDRY_DIR = os.path.join(PROJECT_ROOT, "foundry_workspace")

    pipeline = AuditPipeline(
        sol_dir=SOL_DIR, 
        output_dir=OUTPUT_DIR, 
        foundry_dir=FOUNDRY_DIR
    )
    
    pipeline.process_all()

if __name__ == '__main__':
    main()