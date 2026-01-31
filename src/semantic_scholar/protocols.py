"""Protocol definitions for paper search APIs."""

from typing import Protocol, runtime_checkable

from .models import PaperSearchResult, PaperDetails, SearchFilters


@runtime_checkable
class PaperSearchProvider(Protocol):
    """Protocol for paper search providers.

    Implement this protocol to add support for new paper search APIs.
    """

    async def search_papers(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 100,
    ) -> list[PaperSearchResult]:
        """
        Search for papers matching query and filters.

        Args:
            query: Search query string
            filters: Optional search filters (year, fields of study, etc.)
            limit: Maximum number of results to return

        Returns:
            List of PaperSearchResult objects
        """
        ...

    async def fetch_papers(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """
        Fetch full paper details including open access PDF URLs.

        Args:
            paper_ids: List of paper IDs (format depends on provider)

        Returns:
            List of PaperDetails objects with openAccessPdf field
        """
        ...


@runtime_checkable
class PDFExtractor(Protocol):
    """Protocol for PDF text extraction."""

    async def extract_text(self, pdf_url: str) -> str:
        """
        Download PDF and extract text content.

        Args:
            pdf_url: URL of the PDF to download

        Returns:
            Extracted text content from the PDF
        """
        ...
