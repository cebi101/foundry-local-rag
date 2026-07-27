"""Prompt construction for grounded question answering.

The system prompt is the single highest-leverage file in a RAG project. Five
rules do the heavy lifting here:

1. use only the supplied context
2. say "I don't know" rather than guess
3. cite the source of every claim
4. stay short
5. answer in the user's language

Small local models drift without all five. Keep this list tight -- a long rule
list eats the context window and dilutes the model's attention.
"""

from __future__ import annotations

from typing import Sequence

from .retrieval import SearchHit

SYSTEM_PROMPT = """Sen, yalnızca sana verilen belge alıntılarına dayanarak cevap veren bir yardımcısın.

KURALLAR:
1. Sadece "BAĞLAM" bölümünde verilen metni kullan. Kendi genel bilgini kullanma.
2. Cevap bağlamda yoksa, tam olarak şunu söyle: "Bu bilgi elimdeki belgelerde yok."
   Tahmin yürütme, uydurma.
3. Her iddianın sonunda kaynağı köşeli parantez içinde belirt. Örnek: [01-rag-nedir.md]
4. Kısa ve net yaz. Gereksiz giriş cümlesi kurma, doğrudan cevaba geç.
5. Cevabını {language} dilinde ver.
"""

NO_CONTEXT_ANSWER = "Bu bilgi elimdeki belgelerde yok."


def build_system_prompt(language: str = "Türkçe") -> str:
    """Fill the language placeholder in the system prompt."""
    return SYSTEM_PROMPT.format(language=language)


def format_context(hits: Sequence[SearchHit]) -> str:
    """Render retrieved chunks as a numbered, source-labelled block.

    Each passage is labelled with its source file so the model can cite it, and
    passages are separated clearly so they do not bleed into one another.
    """
    blocks = []
    for i, hit in enumerate(hits, start=1):
        header = f"[{i}] Kaynak: {hit.record.source}"
        if hit.record.heading:
            header += f" | Bölüm: {hit.record.heading}"
        blocks.append(f"{header}\n{hit.record.content}")
    return "\n\n---\n\n".join(blocks)


def build_user_prompt(question: str, hits: Sequence[SearchHit]) -> str:
    """Assemble the user turn: context first, then the question.

    Context before question is deliberate -- the model reads the material, then
    learns what it is being asked to do with it.
    """
    return (
        "BAĞLAM:\n"
        f"{format_context(hits)}\n\n"
        "---\n\n"
        f"SORU: {question.strip()}\n\n"
        "Yukarıdaki bağlamı kullanarak soruyu cevapla ve kaynakları belirt."
    )


def build_messages(
    question: str,
    hits: Sequence[SearchHit],
    language: str = "Türkçe",
) -> list[dict[str, str]]:
    """Full chat message list ready for a chat-completions call."""
    return [
        {"role": "system", "content": build_system_prompt(language)},
        {"role": "user", "content": build_user_prompt(question, hits)},
    ]
