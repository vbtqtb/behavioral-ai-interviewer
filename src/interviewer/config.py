"""Load interview TOML files and resolve which model an agent should call.

A broken file raises ConfigError while the worker is starting. Cloudflare then
keeps the previously deployed version, which is what we want: a bad edit should
not replace a working interview.
"""

import tomllib
from pathlib import Path

from interviewer.errors import ClientError

INTERVIEWS_DIR = Path(__file__).resolve().parent.parent / "interviews"

# Used when an agent block has no `model` and LLM_MODEL is unset.
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash-lite",
    "claude": "claude-haiku-5-5",
}

_REQUIRED_MESSAGES = (
    "first_question",
    "termination_message",
    "flagged_message",
    "off_topic_message",
    "end_of_interview_message",
)


class ConfigError(Exception):
    """Invalid interview configuration. The message names the file and field."""


def model_for(agent_params, provider_name, override=None):
    """Pick a model: LLM_MODEL, then the agent's own model, then the provider default."""
    if override:
        return override
    if agent_params and agent_params.get("model"):
        return agent_params["model"]
    try:
        return DEFAULT_MODELS[provider_name]
    except KeyError:
        raise ClientError(
            f"Unknown LLM provider '{provider_name}'. Use openai, gemini, or claude.",
            status=500,
        ) from None


def _fail(filename, field, message):
    raise ConfigError(f"{filename}: field '{field}': {message}")


def _require_text(filename, field, value):
    if not isinstance(value, str) or not value.strip():
        _fail(filename, field, "expected a non-empty string")
    return value


def _optional_text(filename, field, value):
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(filename, field, "expected a string")
    return value


def _require_bool(filename, field, value, default):
    if value is None:
        return default
    if not isinstance(value, bool):
        _fail(filename, field, "expected true or false")
    return value


def _require_positive_int(filename, field, value):
    # bool is a subclass of int; reject it so `length = true` is not accepted.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(filename, field, "expected a positive integer")
    return value


def _validate_agent(filename, name, block, require_prompt):
    if block is None:
        if require_prompt:
            _fail(filename, name, "required for this interview, but the table is missing")
        return None
    if not isinstance(block, dict):
        _fail(filename, name, "expected a table")
    out = dict(block)
    if require_prompt or "prompt" in out:
        _require_text(filename, f"{name}.prompt", out.get("prompt"))
    if "model" in out:
        _require_text(filename, f"{name}.model", out.get("model"))
    if "max_tokens" in out:
        _require_positive_int(filename, f"{name}.max_tokens", out.get("max_tokens"))
    if "temperature" in out:
        temp = out.get("temperature")
        if isinstance(temp, bool) or not isinstance(temp, (int, float)):
            _fail(filename, f"{name}.temperature", "expected a number")
        out["temperature"] = float(temp)
    return out


def validate_interview(filename, data):
    """Return a normalised config or raise ConfigError naming `filename` and the field."""
    if not isinstance(data, dict):
        _fail(filename, "(root)", "expected a TOML table")
    cfg = dict(data)

    for key in ("_name", "_description"):
        if key in cfg:
            _optional_text(filename, key, cfg.get(key))

    for key in _REQUIRED_MESSAGES:
        cfg[key] = _require_text(filename, key, cfg.get(key))

    plan = cfg.get("interview_plan")
    if not isinstance(plan, list) or not plan:
        _fail(filename, "interview_plan", "expected a non-empty list of {topic, length} tables")
    normalised_plan = []
    for index, item in enumerate(plan):
        if not isinstance(item, dict):
            _fail(filename, f"interview_plan[{index}]", "expected a table with topic and length")
        topic = _require_text(filename, f"interview_plan[{index}].topic", item.get("topic"))
        length = _require_positive_int(filename, f"interview_plan[{index}].length", item.get("length"))
        normalised_plan.append({"topic": topic, "length": length})
    cfg["interview_plan"] = normalised_plan

    closing = cfg.get("closing_questions", [])
    if not isinstance(closing, list) or not all(isinstance(item, str) and item.strip() for item in closing):
        _fail(filename, "closing_questions", "expected a list of non-empty strings (an empty list is allowed)")
    cfg["closing_questions"] = list(closing)

    # Documented defaults. The shipped interviews set every flag explicitly.
    cfg["summarize"] = _require_bool(filename, "summarize", cfg.get("summarize"), True)
    cfg["moderate_answers"] = _require_bool(filename, "moderate_answers", cfg.get("moderate_answers"), True)
    cfg["moderate_questions"] = _require_bool(filename, "moderate_questions", cfg.get("moderate_questions"), True)
    if "max_flags_allowed" in cfg and cfg["max_flags_allowed"] is not None:
        cfg["max_flags_allowed"] = _require_positive_int(filename, "max_flags_allowed", cfg["max_flags_allowed"])
    else:
        cfg["max_flags_allowed"] = 3

    cfg["probe"] = _validate_agent(filename, "probe", cfg.get("probe"), require_prompt=True)
    cfg["transition"] = _validate_agent(
        filename,
        "transition",
        cfg.get("transition"),
        require_prompt=len(normalised_plan) > 1,
    )
    cfg["summary"] = _validate_agent(filename, "summary", cfg.get("summary"), require_prompt=cfg["summarize"])
    cfg["moderator"] = _validate_agent(
        filename,
        "moderator",
        cfg.get("moderator"),
        require_prompt=cfg["moderate_answers"],
    )
    if "dag" in cfg:
        cfg["dag"] = _validate_agent(filename, "dag", cfg.get("dag"), require_prompt=False)
    return cfg


def load_interviews(directory=None):
    """Read every interview TOML. Files whose name starts with '_' are templates and are skipped."""
    directory = Path(directory) if directory else INTERVIEWS_DIR
    if not directory.is_dir():
        raise ConfigError(f"Interview directory not found: {directory}")
    found = {}
    for path in sorted(directory.glob("*.toml")):
        if path.name.startswith("_"):
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path.name}: invalid TOML: {exc}") from exc
        found[path.stem] = validate_interview(path.name, data)
    if not found:
        raise ConfigError(f"No interview TOML files in {directory}")
    return found


INTERVIEWS = load_interviews()
