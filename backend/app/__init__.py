
import os as _os

# LiteLLM calls load_dotenv() on import unless it runs in PRODUCTION mode, which would
# copy every secret in .env into os.environ. Settings reads .env itself, so opt out.
_os.environ.setdefault("LITELLM_MODE", "PRODUCTION")
