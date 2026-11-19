import json
import re

from app.core.config import settings
from app.schemas.chat import SourceCitation
from app.schemas.search import SearchResult


_WORD = re.compile(r"[\w'-]+", re.UNICODE)
_STOP_WORDS = {"the", "and", "for", "with", "from", "that", "this", "what", "when", "where", "which", "who", "how", "are", "was", "were", "does", "did", "about", "into", "your", "you"}


def rerank_results(question: str, results: list[SearchResult]) -> list[SearchResult]:
    terms = {term.lower() for term in _WORD.findall(question) if len(term) > 2 and term.lower() not in _STOP_WORDS}
    if not terms:
        return sorted(results, key=lambda item: item.similarity_score, reverse=True)

    def score(result: SearchResult) -> float:
        text_terms = {term.lower() for term in _WORD.findall(result.content)}
        lexical = len(terms & text_terms) / len(terms)
        return 0.8 * result.similarity_score + 0.2 * lexical

    return sorted(results, key=score, reverse=True)


def make_citations(results: list[SearchResult]) -> list[SourceCitation]:
    return [
        SourceCitation(
            document_id=result.document_id,
            document_name=result.document_name,
            chunk_id=result.chunk_id,
            page_number=result.page_number,
            source_text=result.content,
            similarity_score=result.similarity_score,
        )
        for result in results
    ]


def make_context_payload(citations: list[SourceCitation]) -> str:
    rows = [
        {
            "source_number": index,
            "document_name": citation.document_name,
            "page_number": citation.page_number,
            "text": citation.source_text,
        }
        for index, citation in enumerate(citations, start=1)
    ]
    return json.dumps(rows, ensure_ascii=False)


def relevant_citations(question: str, results: list[SearchResult]) -> list[SearchResult]:
    reranked = rerank_results(question, results)
    return [result for result in reranked if result.similarity_score >= settings.rag_min_similarity][:settings.chat_context_chunks]
