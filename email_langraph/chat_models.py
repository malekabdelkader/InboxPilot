from langchain_openai import ChatOpenAI


def get_model_for_task(task: str) -> ChatOpenAI:
    del task  # reserved for future per-task routing
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)
