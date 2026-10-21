"""Example only: worker-side function, not a synchronous LINE webhook handler."""
from rag.service import answer_drug_question


def generate_drug_reply(user_message: str) -> str:
    """Run in a separate worker, not in the LINE webhook request lifecycle."""
    return answer_drug_question(user_message)["answer"]
