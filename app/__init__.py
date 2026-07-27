"""User interfaces for the local RAG assistant (CLI and Streamlit).

Interfaces stay thin on purpose: they collect a question, call
:class:`foundry_rag.RagPipeline`, and render the result. All logic lives in the
library so that swapping the interface never touches the pipeline.
"""
