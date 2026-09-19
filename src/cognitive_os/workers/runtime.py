"""Opt-in local workers owned by the API lifespan; PostgreSQL leases remain authoritative."""

import logging
import multiprocessing
import time

from sqlalchemy import create_engine

log = logging.getLogger(__name__)


def worker_loop(settings, kind, stop):
    try:
        from cognitive_os.infrastructure.ai.openai_drafts import OpenAIDraftProvider
        from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
        from cognitive_os.infrastructure.ai.openai_curator import OpenAIKnowledgeCurator
        from cognitive_os.infrastructure.ai.openai_policy import OpenAIPolicyProvider
        from cognitive_os.infrastructure.ai.openai_visual import OpenAIVisualProvider
        from cognitive_os.workers.consolidation import run_once
        from cognitive_os.workers.policy_index import run_policy_index_once
        from cognitive_os.workers.recording_index import run_index_once
        from cognitive_os.workers.visual import run_visual_once
    except KeyboardInterrupt:
        # Ctrl+C can land mid-import (e.g. inside the azure-core import chain)
        # before the loop's own try/except below is even reached.
        log.info("Worker %s stopping on interrupt", kind)
        return

    provider = None
    curator = None
    policy_provider = None
    engine = None
    try:
        provider = {"consolidate": OpenAIDraftProvider, "analyze_recording": OpenAIVisualProvider,
                    "index_recording": OpenAIEmbeddingProvider,
                    "index_policy": OpenAIEmbeddingProvider}[kind](settings)
        if kind == "index_recording":
            curator = OpenAIKnowledgeCurator(settings)
        if kind == "index_policy":
            policy_provider = OpenAIPolicyProvider(settings)
        engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                               hide_parameters=True, connect_args={"connect_timeout": 5})
        while not stop.is_set():
            try:
                if kind == "analyze_recording":
                    worked = run_visual_once(engine, provider, settings)
                elif kind == "index_recording":
                    worked = run_index_once(engine, provider, None, curator, settings.knowledge_supersede_similarity)
                elif kind == "index_policy":
                    worked = run_policy_index_once(engine, provider, policy_provider, settings)
                else:
                    worked = run_once(engine, provider, settings.worker_lease_seconds)
                if not worked:
                    stop.wait(2)
            except Exception:
                # Never emit SDK exception text, signed URLs or database credentials.
                log.warning("Worker %s temporarily unavailable; retrying in 5 seconds", kind)
                stop.wait(5)
    except KeyboardInterrupt:
        # Ctrl+C reaches every process in the console group, so each worker raises
        # here while waiting and multiprocessing prints a traceback per process.
        # LocalWorkers.close is already stopping us, so shut down quietly instead.
        log.info("Worker %s stopping on interrupt", kind)
    finally:
        if provider is not None:
            provider.close()
        if curator is not None:
            curator.close()
        if policy_provider is not None:
            policy_provider.close()
        if engine is not None:
            engine.dispose()


class LocalWorkers:
    def __init__(self, settings):
        self.settings = settings
        self.processes = {}
        self.stop_event = multiprocessing.get_context("spawn").Event()

    def start(self):
        if not self.settings.database_url or not self.settings.openai_api_key:
            log.warning("Local workers not started: database or OpenAI configuration missing")
            return
        context = multiprocessing.get_context("spawn")
        for kind in ("consolidate", "analyze_recording", "index_recording", "index_policy"):
            if kind in ("analyze_recording", "index_policy") and not self.settings.azure_storage_connection_string:
                continue
            process = context.Process(target=worker_loop, args=(self.settings, kind, self.stop_event),
                                      name=f"cognitive-{kind}", daemon=True)
            process.start()
            self.processes[kind] = process

    def status(self):
        return {kind: process.is_alive() for kind, process in self.processes.items()}

    def close(self):
        self.stop_event.set()
        deadline = time.monotonic() + 5
        for process in self.processes.values():
            process.join(timeout=max(0, deadline - time.monotonic()))
        for process in self.processes.values():
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
        # Interrupted work is recovered after its persisted lease expires.
