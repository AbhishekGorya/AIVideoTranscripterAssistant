import os

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda


def get_llm():
    return ChatMistralAI(
        model="mistral-small-latest",
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        temperature=0.2,
    )


def build_chain(system_prompt: str):
    llm = get_llm()
    return (
        RunnablePassthrough()
        | RunnableLambda(lambda x: {"text": x})  # [1]
        | ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{text}"),
            ]
        )
        | llm
        | StrOutputParser()
    )


def extract_action_items(transcript: str) -> str:
    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all action items. For each provide:\n"
        "- Task description\n"
        "- Owner (who is responsible)\n"
        "- Deadline (if mentioned, else write 'Not specified')\n\n"
        "Format as a numbered list. If none found say 'No action items found.'"
    )
    return chain.invoke(transcript)


def extract_key_decisions(transcript: str) -> str:
    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all key decisions made. Format as a numbered list. "
        "If none found say 'No key decisions found.'"
    )
    return chain.invoke(transcript)


def extract_questions(transcript: str) -> str:
    chain = build_chain(
        "From the meeting transcript, extract all unresolved questions "
        "or topics needing follow-up. Format as a numbered list. "
        "If none found say 'No open questions found.'"
    )
    return chain.invoke(transcript)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
# [1] RunnableLambda(lambda x: {"text": x}) wraps the raw transcript string
#     into a dict, because ChatPromptTemplate expects a dict of variables
#     (here it needs a "text" key to fill the {text} placeholder in the
#     "human" message). RunnablePassthrough() at the start just forwards
#     whatever is passed to chain.invoke(...) unchanged into that lambda.
#
# Workflow overview:
#   This module builds three independent LangChain (LCEL) pipelines —
#   action items, key decisions, and open questions — all sharing the same
#   chain "shape" via build_chain(): passthrough -> wrap into dict ->
#   prompt -> LLM -> string output. Only the system prompt differs between
#   them. Each extractor function is a thin wrapper that supplies its own
#   prompt and invokes the chain on a given meeting transcript.