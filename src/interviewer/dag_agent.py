"""Extract a causal DAG from one completed interview topic."""

import logging

log = logging.getLogger(__name__)

DAG_SYSTEM_PROMPT = """You are an expert in cognitive mapping and causal reasoning for qualitative research.
Extract a causal Directed Acyclic Graph (DAG) from the interview transcript provided, representing the interviewee's mental model about the given topic.

Rules:
- Extract only concepts and relationships explicitly expressed by the interviewee (not the interviewer)
- Each node should be a concise concept (2-5 words)
- Edges represent causal or associative relationships between concepts
- Maximum 10 nodes and 12 edges
- The graph must be acyclic (no cycles)
- Edge labels should briefly describe the relationship (e.g., "leads to", "increases", "causes", "results in")

Return ONLY valid JSON in this exact format, no other text:
{
  "nodes": [
    {"id": "1", "label": "concept name"}
  ],
  "edges": [
    {"source": "1", "target": "2", "label": "relationship type"}
  ]
}"""


class DAGAgent:
    """
    Agent that extracts a causal DAG from an interview transcript,
    capturing the interviewee's mental model about a given topic.
    """

    def __init__(self, provider):
        self.provider = provider

    async def extract_dag(self, topic, history_text, model="gpt-4o", max_tokens=1000):
        """
        Extract a DAG from the interview transcript for a given topic.

        Args:
            topic: description of the interview topic
            history_text: formatted transcript (Interviewer/Interviewee turns)
            model: model name for the active provider
            max_tokens: maximum tokens for the response

        Returns:
            dict with 'nodes' and 'edges' lists, or empty lists on failure
        """
        messages = [
            {"role": "system", "content": DAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"Topic: {topic}\n\nInterview transcript:\n{history_text}"},
        ]
        try:
            dag = await self.provider.complete_json(messages, model, max_tokens, temperature=0)
            if not isinstance(dag, dict):
                return {"nodes": [], "edges": []}
            dag.setdefault("nodes", [])
            dag.setdefault("edges", [])
            log.info(
                "DAG extracted: %s nodes, %s edges",
                len(dag.get("nodes", [])),
                len(dag.get("edges", [])),
            )
            return dag
        except Exception as exc:
            log.error("DAG extraction failed: %s", exc)
            return {"nodes": [], "edges": []}
