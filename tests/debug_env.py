
import os
from pathlib import Path
from dotenv import load_dotenv

# Base dir is project root (parent of tools/)
base_dir = Path(__file__).parent.parent
env_path = base_dir / ".env"

print(f"Checking {env_path}")
print(f"Exists: {env_path.exists()}")

# Try loading
load_dotenv(dotenv_path=env_path, verbose=True, override=True)

print("Values:")
print(f"HF_TOKEN3: {os.getenv('HF_TOKEN3')}")
print(f"GROQ_KEY: {os.getenv('GROQ_KEY')}")
