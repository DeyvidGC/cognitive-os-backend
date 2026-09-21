"""Blends the video-fragment vector search (recording_knowledge) with the
published-procedure full-text search (procedures) into one ranked list, so
the frontend can run a single query against both indexes instead of two.
"""

from cognitive_os.application.procedures import search_knowledge
from cognitive_os.application.recording_knowledge import search_vectors

SNIPPET_LENGTH = 280


def _video_hit(row):
    return {"type": "video", "score": row["score"], "snippet": row["content"][:SNIPPET_LENGTH],
            "timestamp_ms": row["timestamp_ms"], "recording_id": row["recording_id"],
            "session_id": row["session_id"]}


def _procedure_hit(row):
    # ts_rank is an unbounded, open-ended score; squash it into 0..1 so it
    # sits on roughly the same scale as the video search's cosine score for
    # a single blended, sorted list. A heuristic, not an exact normalization.
    rank = row["rank"]
    return {"type": "procedure", "score": rank / (rank + 1) if rank else 0.0,
            "snippet": row["content"][:SNIPPET_LENGTH], "procedure_id": row["procedure_id"],
            "version_id": row["version_id"], "step_id": row["step_id"]}


def unified_search(db, organization_id, model_name, vector, query_text, limit):
    video_hits = [_video_hit(row) for row in search_vectors(db, organization_id, model_name, vector, limit)]
    procedure_hits = [_procedure_hit(row) for row in search_knowledge(db, organization_id, query_text, limit)]
    results = sorted(video_hits + procedure_hits, key=lambda item: item["score"], reverse=True)
    return results[:limit]
