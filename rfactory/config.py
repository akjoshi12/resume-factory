from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RF_", env_file=".env", extra="ignore")

    master_resume: Path = ROOT / "data" / "master_resume.json"
    templates_dir: Path = ROOT / "templates"

    # Runtime artifacts live in a dot-directory, not in out/ or data/. Reflex's hot
    # reloader watches the whole repo root, so writing a PDF or a DB page mid-run
    # would restart the backend while a graph is executing.
    runtime_dir: Path = ROOT / ".rfdata"
    out_dir: Path = ROOT / ".rfdata" / "out"
    db_path: Path = ROOT / ".rfdata" / "rfactory.db"

    llm_provider: str = "lmstudio"

    # Qwen3 and friends emit a reasoning phase by default. It is invisible in the
    # response, uncapped, and routinely several times the length of the answer --
    # the difference between a one-minute call and a ten-minute one.
    disable_thinking: bool = True
    # Grammar-constrained output: the server is handed a JSON schema and the model
    # physically cannot emit anything else -- including a reasoning block. Set false
    # if your server rejects response_format; the code falls back automatically.
    structured_output: bool = True
    request_timeout: float = 180.0
    # Caps are a safety net, not a target. They must leave room for a reasoning phase
    # on the fallback path, where thinking tokens come out of the same budget.
    max_tokens_ingest: int = 1500
    max_tokens_tailor: int = 4000
    max_tokens_cover: int = 2000

    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_model: str = "qwen3-27b"
    # An OpenAI-compatible gateway (OmniRoute, FreeLLMAPI, LiteLLM). The gateway owns
    # routing, fallback and load balancing; this app just points at it and does not
    # reimplement any of that. Model names are whatever the gateway exposes, commonly
    # "provider/model".
    gateway_base_url: str = "http://127.0.0.1:20128/v1"
    gateway_model: str = ""
    gateway_api_key: str = ""

    cloud_base_url: str = ""
    cloud_model: str = ""
    cloud_api_key: str = ""

    latex_engine: str = "pdflatex"
    max_pages: int = 1
    max_fit_retries: int = 3
    max_verify_retries: int = 3


settings = Settings()
