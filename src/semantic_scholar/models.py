"""Pydantic models for Semantic Scholar API responses."""

from pydantic import BaseModel, Field


class Author(BaseModel):
    """Author information."""

    author_id: str | None = Field(None, alias="authorId")
    name: str | None = None


class OpenAccessPdf(BaseModel):
    """Open access PDF information."""

    url: str
    status: str | None = None


class PaperSearchResult(BaseModel):
    """Paper metadata returned from search endpoint."""

    paper_id: str = Field(..., alias="paperId")
    title: str | None = None
    abstract: str | None = None
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    citation_count: int | None = Field(None, alias="citationCount")
    fields_of_study: list[str] | None = Field(None, alias="fieldsOfStudy")
    publication_types: list[str] | None = Field(None, alias="publicationTypes")

    model_config = {"populate_by_name": True}


class PaperDetails(PaperSearchResult):
    """Full paper details including open access PDF URL and full text."""

    open_access_pdf: OpenAccessPdf | None = Field(None, alias="openAccessPdf")
    venue: str | None = None
    url: str | None = None
    external_ids: dict[str, str | int] | None = Field(None, alias="externalIds")
    full_text: str | None = None


class SearchFilters(BaseModel):
    """Filters for paper search."""

    year: str | None = None  # e.g., "2020-2024" or "2020-" or "-2024"
    fields_of_study: list[str] | None = None
    min_citation_count: int | None = None
    publication_types: list[str] | None = None
    open_access_only: bool = False

    def to_query_params(self) -> dict[str, str]:
        """Convert filters to API query parameters."""
        params: dict[str, str] = {}

        if self.year:
            params["year"] = self.year

        if self.fields_of_study:
            params["fieldsOfStudy"] = ",".join(self.fields_of_study)

        if self.min_citation_count is not None:
            params["minCitationCount"] = str(self.min_citation_count)

        if self.publication_types:
            params["publicationTypes"] = ",".join(self.publication_types)

        if self.open_access_only:
            params["openAccessPdf"] = ""

        return params


class SearchResponse(BaseModel):
    """Response from the paper search endpoint."""

    total: int = 0
    offset: int = 0
    next: int | None = None
    data: list[PaperSearchResult] = Field(default_factory=list)
