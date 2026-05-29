import openai
import openai.error
from typing import List, Dict
import logging
import time
import traceback
import tiktoken
from multiprocessing import Value

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = """You are an elite smart contract security auditor.
Your ONLY task is to write a Foundry Proof of Concept (PoC) exploit script.
CRITICAL RULES:
- Output strictly the raw Solidity code.
- Provide ZERO explanations, ZERO analysis, and ZERO conversational text.
- Do not wrap the code in markdown blocks (like ```solidity). Just the raw code."""

encoder = tiktoken.get_encoding("cl100k_base")
encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")

tokens_sent = Value("d", 0)
tokens_received = Value("d", 0)

class Chat:
    def __init__(self) -> None:
        self.currentSession: List[Dict[str, str]] = []
    
    def newSession(self) -> None:
        self.currentSession = []
    
    def sendMessages(self, message: str) -> str:
        self.currentSession.append({"role": "system", "content": SYSTEM_MESSAGE})
        self.currentSession.append({"role": "user", "content": message})

        openai.api_base = "http://localhost:11434/v1"
        openai.api_key = "KANE"

        while True:
            try:
                response = openai.ChatCompletion.create(
                    model="qwen3-coder:30b",
                    messages=self.currentSession,
                    temperature=0,
                    top_p=1.0
                )
                break
            except openai.error.RateLimitError:
                logger.warning("Trigger rate limit error, sleep 30 sec")
                time.sleep(30)
            except openai.error.InvalidRequestError as e2: 
                if e2.code == 'context_length_exceeded':
                    logger.error("Too long context, skip")
                    return "KeySentence: Context too long."
                else:
                    logger.warning(f"Invalid Request, Retry: {e2}")
            except openai.error.APIConnectionError as e3:
                logger.warning(f"API Connection Error, Retry: {e3}")
                time.sleep(5) 
            except openai.error.Timeout:
                logger.warning("Timeout, Retry")
            except openai.error.APIError as e5:
                if "502" in getattr(e5, '_message', ''):
                    logger.warning("502 Bad Gateway, Retry")
                    logger.warning(traceback.format_exc())
                else:
                    logger.warning(f"API Error: {e5}")

        global tokens_sent
        global tokens_received
        tokens_sent.value += len(encoder.encode(SYSTEM_MESSAGE))
        tokens_sent.value += len(encoder.encode(message))
        
        reply_content = response['choices'][0]['message']['content']
        tokens_received.value += len(encoder.encode(reply_content))

        self.currentSession.append(response['choices'][0]['message'])

        print("\n" + "-"*50)
        print("RESPONSE:")
        print("-"*50)
        print(reply_content)
        print("="*50 + "\n")

        return reply_content
    
    def makeYesOrNoQuestion(self, question: str) -> str:
        return f"{question}. Please answer in one word, yes or no."
    
    def makeCodeQuestion(self, question: str, code: str) -> str:
        return f'Please analyze the following code, and answer the question "{question}"\n{code}'