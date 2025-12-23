"""Citations package.

Filesystem-first citation registry and validation helpers.
"""

from .crossref import (
    CrossrefClient,
    CrossrefClientConfig,
    CrossrefError,
    CrossrefNotFoundError,
    normalize_doi,
    resolve_crossref_doi_and_upsert,
    resolve_crossref_doi_to_record,
)

from .bibliography import (
    BibliographyPaths,
    bibliography_paths,
    build_bibliography,
    citation_record_to_bibtex,
    dedupe_citation_records_by_doi,
    mint_stable_citation_key,
)

__all__ = [
    "CrossrefClient",
    "CrossrefClientConfig",
    "CrossrefError",
    "CrossrefNotFoundError",
    "normalize_doi",
    "resolve_crossref_doi_and_upsert",
    "resolve_crossref_doi_to_record",

    "BibliographyPaths",
    "bibliography_paths",
    "build_bibliography",
    "citation_record_to_bibtex",
    "dedupe_citation_records_by_doi",
    "mint_stable_citation_key",
]
