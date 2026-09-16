"""Explicit operator command: create the private container and append an origin-specific CORS rule."""

import argparse
from urllib.parse import urlparse

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import CorsRule

from cognitive_os.core.config import Settings
from cognitive_os.infrastructure.storage.azure_recordings import recording_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True, help="Exact frontend origin, e.g. http://localhost:5173")
    origin = parser.parse_args().origin
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or "*" in origin:
        parser.error("Supply an exact HTTP(S) origin without path or wildcard")
    with recording_store(Settings()) as store:
        try:
            store.service.create_container(store.container)
        except ResourceExistsError:
            pass
        store.ensure_private()
        cors = list(store.service.get_service_properties()["cors"])
        if not any(origin in rule.allowed_origins and "PUT" in rule.allowed_methods for rule in cors):
            if len(cors) >= 5:
                parser.error("Review existing Azure CORS rules; none were removed")
            cors.append(CorsRule(allowed_origins=[origin], allowed_methods=["PUT", "GET", "HEAD", "OPTIONS"],
                                 allowed_headers=["content-type", "x-ms-*", "range", "if-match"],
                                 exposed_headers=["etag", "content-range", "content-length", "x-ms-request-id"],
                                 max_age_in_seconds=600))
            store.service.set_service_properties(cors=cors)
    print("Private container verified; CORS configured. No videos were uploaded.")


if __name__ == "__main__":
    main()
