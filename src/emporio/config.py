import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = ''
    llm_model: str = ''
    llm_api_key: str = field(default='', repr=False)
    emporio_now: str | None = None

    @classmethod
    def from_env(cls) -> 'Settings':
        load_dotenv()
        return cls(os.getenv('LLM_BASE_URL', ''), os.getenv('LLM_MODEL', ''), os.getenv('LLM_API_KEY', ''), os.getenv('EMPORIO_NOW') or None)
