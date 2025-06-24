import torch
import ccxt
import json
import time
import pandas as pd
from datetime import datetime
import requests
from transformers import AutoTokenizer
from llama_cpp import Llama
import re
import json
from huggingface_hub import hf_hub_download
import os
from pathlib import Path
import torch.nn as nn
import torch.nn.functional as F

BASE_DIR = Path(__file__).parent.parent.parent
MODELS_DIR = os.path.join(BASE_DIR, "..", "llm", "models")

MODEL_PATHS = {
    "qwen": {
        "repo_id": "Qwen/Qwen1.5-7B-Chat-GGUF", # dummer "Qwen/Qwen1.5-1.8B-Chat-GGUF"
        "file_name": "qwen1_5-7b-chat-q4_k_m.gguf", #  "qwen1_5-1_8b-chat-q3_k_m.gguf"
        "dest_dir": os.path.join(MODELS_DIR, "Qwen_model"),
        "model_path": os.path.join(MODELS_DIR, "Qwen_model", "qwen1_5-7b-chat-q4_k_m.gguf") # "qwen1_5-1_8b-chat-q3_k_m.gguf"
    },
    "ppo_agent": {
        "repo_id": "benstaf/Trading_agents",
        "file_name": "agent_cppo_100_epochs_20k_steps.pth",
        "dest_dir": os.path.join(MODELS_DIR, "FinRL_Models"),
        "model_path": os.path.join(MODELS_DIR, "FinRL_Models", "agent_cppo_100_epochs_20k_steps.pth")
    }
}

def download_model(REPO_ID, FILENAME, SAVE_PATH):
    """
    Downloads a model from a Hugging Face repository if it doesn't already exist locally.

    Args:
        REPO_ID (str): The repository ID on Hugging Face Hub.
        FILENAME (str): The name of the model file to download.
        SAVE_PATH (str): The local directory to save the model.

    Returns:
        str: The full local path to the model file.
    """
    # Construct the full path where the model is expected to be
    full_model_path = os.path.join(SAVE_PATH, FILENAME)

    # Check if the model file already exists at the destination
    if os.path.exists(full_model_path):
        print(f"El modelo ya existe en: {full_model_path}")
        return full_model_path
    else:
        print(f"El modelo no se encuentra. Descargando de {REPO_ID}...")
        
        # Ensure the target directory exists before downloading
        os.makedirs(SAVE_PATH, exist_ok=True)
        
        # If it doesn't exist, download the model
        model_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            local_dir=SAVE_PATH,
            local_dir_use_symlinks=False
        )
        print(f"Modelo descargado en: {model_path}")
        return model_path
class PPOAgent(nn.Module):
    def __init__(self, input_dim, output_dim):
        super().__init__()
        # Definir la estructura para coincidir con el state_dict
        # Capas para la política (pi)
        self.pi_mu_net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, output_dim)
        )
        # Capas para el valor (v)
        self.v_v_net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 1)
        )
        # Parámetro de desviación estándar para la política
        self.log_std = nn.Parameter(torch.zeros(output_dim))

    def forward(self, x):
        # Solo necesitamos la parte de la política para la inferencia
        return self.pi_mu_net(x)
      
class QwenTradingAssistant:
    def __init__(self, model_path, tokenizer_name="Qwen/Qwen1.5-1.8B-Chat"):
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.llm = Llama(model_path=model_path, n_ctx=4096, n_threads=6)
    
    def generate_strategy(self, current_market, strategy_prompt, orders_made=[]):
        prompt = self.tokenizer.apply_chat_template(
            [
                # Rol principal: Muy directo.
                {"role": "system", "content": "You are a concise trading decision assistant."},

                # Formato de respuesta: Ahora solo con 'action'. Súper claro.
                {"role": "system", "content": "Your response MUST be a JSON object with a single key: 'action' (values: 'buy', 'sell', 'wait'). Example: {\"action\": \"buy\"}."},

                # La estrategia: Sigue siendo la instrucción central y estricta.
                {"role": "system", "content": f"Strictly apply this trading strategy: {strategy_prompt}"},

                # Datos del mercado: Directo al grano.
                {"role": "system", "content": f"Current market data: {current_market}"},

                # Órdenes previas: Da contexto sin pedirle que "razone" sobre ellas.
                {"role": "system", "content": f"Just for your context here are the Previously made orders: {str(orders_made)}"},

                # La instrucción final para el usuario:
                # Pídele que aplique la estrategia y determine la acción, enfatizando solo el JSON.
                {"role": "user", "content": "Taking into consideration the current market data, the previously made orders and the trading strategy. What is the best trading action ('buy', 'sell', or 'wait')? Provide ONLY the JSON output as specified."},
            ],
            tokenize=False,
            add_generation_prompt=True
        )
        
        print(f"LLM thinking...")
        output = self.llm.create_completion(
            prompt=prompt,
            max_tokens=300,
            temperature=0.5,
            stop=["<|im_end|>"]
        )
        
        texto_estrategia = output["choices"][0]["text"].strip()
        print(f"LLM Respuesta: {texto_estrategia}")
        return texto_estrategia
    
    def parse_strategy(self, strategy_text):
        try:
            return json.loads(strategy_text)
        except Exception as e:
            # Try to get the response as a JSON object
            res = self.extract_json_from_llm_response(strategy_text)
            return res
        
    def extract_json_from_llm_response(self, llm_response_string):
        """
        Manually extracts and parses a JSON object from a string that might contain
        additional conversational text before and after the JSON.

        Args:
            llm_response_string (str): The full string response received from the LLM.

        Returns:
            dict or None: The parsed JSON object as a Python dictionary,
                        or None if no valid JSON object is found.
        """
        # Regex to find a JSON block, optionally wrapped in markdown code blocks (```json ... ```)
        # It looks for the first occurrence of '{' and tries to match until '}'
        # This regex is relatively robust but might fail on very complex nested JSON
        # or malformed JSON where curly braces don't match.
        json_match = re.search(r'```json\s*(\{.*\})\s*```|(\{.*\})', llm_response_string, re.DOTALL)

        if json_match:
            # Prioritize the content within ```json ... ``` if found, otherwise take the raw JSON
            json_str = json_match.group(1) if json_match.group(1) else json_match.group(2)
            try:
                # Parse the extracted JSON string into a Python dictionary
                parsed_json = json.loads(json_str)
                return parsed_json
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Attempted to decode: {json_str}")
                return None
        else:
            print("No JSON object found in the LLM response.")
            return None


class DeepSeekPPOAgent:
    def __init__(self, model_path, input_dim, output_dim):
        self.action_map = {0: "buy", 1: "sell", 2: "wait"}

        agent_state_dict = torch.load(model_path, map_location=torch.device('cpu'))  # o 'cuda' si GPU

        self.agent = PPOAgent(input_dim, output_dim)
        self.agent.load_state_dict(agent_state_dict, strict=False)
        self.agent.eval()
            
    def execute_action(self, qwen_output, estado_ambiente):
        """Ejecuta la acción de trading basada en el estado actual"""
        estado_tensor = torch.tensor(estado_ambiente, dtype=torch.float32).unsqueeze(0)  # batch=1
        logits = self.agent(estado_tensor)
        action = torch.argmax(logits, dim=1).item()

        print(f"Acción DeepSeek tomada: {self.action_map.get(action, 'Desconocida')}")
        print(f"🚀 Acción ejecutada: {action} | Señal: {qwen_output['action']}")

        return action
        