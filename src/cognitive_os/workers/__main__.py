import argparse
import time
from uuid import UUID

from sqlalchemy import create_engine

from cognitive_os.core.config import Settings
from cognitive_os.infrastructure.ai.openai_drafts import OpenAIDraftProvider
from cognitive_os.infrastructure.ai.openai_visual import OpenAIVisualProvider
from cognitive_os.workers.consolidation import run_once
from cognitive_os.workers.visual import run_visual_once
from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
from cognitive_os.workers.recording_index import run_index_once


def main():
    parser = argparse.ArgumentParser(description="Process captured text into reviewable drafts")
    parser.add_argument("--once", action="store_true", help="Process at most one available job")
    parser.add_argument("--organization-id", type=UUID, help="Restrict processing to one organization")
    parser.add_argument("--kind", choices=["consolidate", "analyze_recording", "index_recording"], default="consolidate")
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url:
        parser.error("Configure COGNITIVE_DATABASE_URL locally")
    try:
        provider = {"analyze_recording": OpenAIVisualProvider, "index_recording": OpenAIEmbeddingProvider,
                    "consolidate": OpenAIDraftProvider}[args.kind](settings)
        if args.kind == "analyze_recording" and not settings.azure_storage_connection_string:
            provider.close()
            parser.error("Configure AZURE_STORAGE_CONNECTION_STRING locally")
    except ValueError as exc:
        parser.error(str(exc))
    engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                           hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        while True:
            if args.kind == "index_recording":
                worked = run_index_once(engine, provider, args.organization_id)
            elif args.kind == "analyze_recording":
                worked = run_visual_once(engine, provider, settings, args.organization_id)
            else:
                worked = run_once(engine, provider, settings.worker_lease_seconds, args.organization_id)
            if args.once:
                break
            if not worked:
                time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()
        provider.close()


if __name__ == "__main__":
    main()
