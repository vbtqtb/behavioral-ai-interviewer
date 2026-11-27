"""Prompt formatting and concurrent LLM calls."""

import asyncio
import logging
import re
import time

log = logging.getLogger(__name__)


def chat_to_string(chat, only_topic=None, until_topic=None):
    """Convert messages from chat into one string."""
    topic_history = ""
    for message in chat:
        if only_topic and message["topic_idx"] != only_topic:
            continue
        if until_topic and message["topic_idx"] == until_topic:
            break
        if message["type"] == "question":
            topic_history += 'Interviewer: "{}"\n'.format(message["content"])
        if message["type"] == "answer":
            topic_history += 'Interviewee: "{}"\n'.format(message["content"])
    return topic_history.strip()


def transcript_text(chat, extra_message=None):
    """Human-readable transcript. `extra_message` covers replies that are not stored as a turn.

    The end-of-interview, off-topic, and flagged replies are returned to the
    browser but, as in the previous app, are not appended to the session list.
    They are still included here so the Qualtrics export contains them once.
    """
    lines = []
    for message in chat:
        content = message.get("content")
        if content is None or message.get("type") not in ("question", "answer"):
            continue
        role = "Interviewer" if message["type"] == "question" else "Interviewee"
        lines.append(f"{role}: {content}")
    shown = (extra_message or "").replace("---END---", "").strip()
    last = ""
    for message in reversed(chat):
        if message.get("type") in ("question", "answer") and message.get("content"):
            last = str(message["content"]).strip()
            break
    if shown and shown != last:
        lines.append(f"Interviewer: {shown}")
    return "\n".join(lines)


def fill_prompt_with_interview(template, topics, history, user_message=None):
    """Fill the prompt template with parameters from current interview."""
    state = history[-1]
    current_topic_idx = min(int(state["topic_idx"]), len(topics))
    next_topic_idx = min(current_topic_idx + 1, len(topics))
    current_topic_chat = chat_to_string(history, only_topic=current_topic_idx)
    prompt = template.format(
        topics="\n".join([topic["topic"] for topic in topics]),
        question=state["content"],
        answer=user_message,
        summary=state["summary"] or chat_to_string(history, until_topic=current_topic_idx),
        current_topic=topics[current_topic_idx - 1]["topic"],
        next_interview_topic=topics[next_topic_idx - 1]["topic"],
        current_topic_history=current_topic_chat,
    )
    log.debug("Prompt to the model:\n%s", prompt)
    assert not re.findall(r"\{[^{}]+\}", prompt)
    return prompt


async def execute_queries(provider, task_args):
    """
    Execute completion queries via the given provider.
    A single task is one call. Several tasks run concurrently with asyncio.gather.

    Args:
        provider: an LLMProvider (or a test double with the same async complete method)
        task_args: dict of {task_name: {messages, model, max_tokens, temperature}}
    Returns:
        dict of {task_name: response_text}
    """
    started = time.time()

    async def _one(task, kwargs):
        log.info("LLM call: task='%s' model='%s'", task, kwargs["model"])
        text = await provider.complete(
            messages=kwargs["messages"],
            model=kwargs["model"],
            max_tokens=kwargs["max_tokens"],
            temperature=kwargs["temperature"],
        )
        return task, text

    items = list(task_args.items())
    if len(items) == 1:
        task, text = await _one(items[0][0], items[0][1])
        suggestions = {task: text}
    else:
        pairs = await asyncio.gather(*[_one(task, kwargs) for task, kwargs in items])
        suggestions = dict(pairs)

    log.info("LLM query took %.2f seconds", time.time() - started)
    return suggestions
