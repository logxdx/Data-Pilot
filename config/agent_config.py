import os
from dotenv import load_dotenv

load_dotenv()

# Version
Version = "3.1.4"

# Global max turns for agent interactions
MAX_TURNS = 20

# Individual configurations for each agent
ONLINE_CONFIG = {
    "PERSONALITY": "omen",
    "filesystem_agent": {
        "BASE_URL": os.getenv("CEREBRAS_BASE_URL"),
        "API_KEY": os.getenv("FILESYSTEM_API_KEY"),
        "MODEL_NAME": "openai/gpt-oss-120b",
    },
    "analysis_agent": {
        "BASE_URL": os.getenv("CEREBRAS_BASE_URL"),
        "API_KEY": os.getenv("ANALYSIS_API_KEY"),
        "MODEL_NAME": "openai/gpt-oss-120b",
    },
    "context_manager_agent": {
        "BASE_URL": os.getenv("CEREBRAS_BASE_URL"),
        "API_KEY": os.getenv("CONTEXT_API_KEY"),
        "MODEL_NAME": "openai/gpt-oss-120b",
    },
}

# Select configuration based on environment
AGENT_CONFIGS = ONLINE_CONFIG
