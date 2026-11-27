"""LLM agents: probe within a topic, transition, summarise, and moderate."""

import logging

from interviewer.auxiliary import chat_to_string, execute_queries, fill_prompt_with_interview
from interviewer.config import model_for
from interviewer.dag_agent import DAGAgent

log = logging.getLogger(__name__)


class LLMAgent:
    """Class to manage LLM-based agents via one provider."""

    def __init__(self, provider):
        self.provider = provider
        self.parameters = {}

    def load_parameters(self, parameters):
        """Load interview guidelines for prompt construction."""
        self.parameters = parameters

    def _model(self, task):
        """Model for a task: LLM_MODEL, then the task's model, then the provider default."""
        return model_for(
            self.parameters.get(task) or {},
            self.provider.provider_name,
            getattr(self.provider, "model_override", None),
        )

    def construct_query(self, tasks, history, user_message=None):
        """
        Build completion requests for the given tasks.
        Defaults: 300 max_tokens, temperature 0.
        """
        return {
            task: {
                "messages": [
                    {
                        "role": "user",
                        "content": fill_prompt_with_interview(
                            self.parameters[task]["prompt"],
                            self.parameters["interview_plan"],
                            history,
                            user_message=user_message,
                        ),
                    }
                ],
                "model": self._model(task),
                "max_tokens": self.parameters[task].get("max_tokens", 300),
                "temperature": self.parameters[task].get("temperature", 0),
            }
            for task in tasks
        }

    async def transcribe(self, audio):
        """Transcribe base64-encoded audio."""
        return await self.provider.transcribe(audio)

    async def review_answer(self, message, history):
        """Moderate answers: are they on topic?"""
        response = await execute_queries(
            self.provider,
            self.construct_query(["moderator"], history, message),
        )
        return "yes" in response["moderator"].lower()

    async def review_question(self, next_question):
        """Moderate questions via the provider moderation endpoint."""
        return await self.provider.moderate_text(next_question)

    async def probe_within_topic(self, history):
        """Return the next within-topic probing question."""
        response = await execute_queries(
            self.provider,
            self.construct_query(["probe"], history),
        )
        return response["probe"]

    async def transition_topic(self, history):
        """
        Generate a topic transition question and, when configured, a summary.
        The two calls run concurrently. Returns (transition_question, summary_text).
        """
        summarize = self.parameters.get("summarize")
        tasks = ["summary", "transition"] if summarize else ["transition"]
        response = await execute_queries(
            self.provider,
            self.construct_query(tasks, history),
        )
        return response["transition"], response.get("summary", "")

    async def extract_dag(self, topic, topic_idx, history):
        """
        Extract a causal DAG from the completed topic's interview history.

        Args:
            topic: description of the topic just completed
            topic_idx: 1-based topic index used to filter history
            history: full interview history
        Returns:
            dict with 'nodes' and 'edges', or {} if dag is not configured
        """
        if not self.parameters.get("dag"):
            return {}
        dag_params = self.parameters["dag"]
        model = model_for(dag_params, self.provider.provider_name, getattr(self.provider, "model_override", None))
        history_text = chat_to_string(history, only_topic=topic_idx)
        dag = await DAGAgent(self.provider).extract_dag(
            topic=topic,
            history_text=history_text,
            model=model,
            max_tokens=dag_params.get("max_tokens", 1000),
        )
        log.info("DAG agent returned %s nodes", len(dag.get("nodes", [])))
        return dag
