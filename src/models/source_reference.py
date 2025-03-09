"""
Source Reference Model

This module contains the SourceReference class which is used to track and manage
references to external sources used in the research process.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Set


@dataclass(frozen=True)
class SourceReference:
    """
    A class to represent a reference to an external source.

    This immutable dataclass stores information about external sources used in research,
    including URL, title, access time, and reference number.
    """

    url: str
    title: str
    accessed_at: str
    reference_number: Optional[int] = None

    def to_dict(self) -> Dict:
        """
        Convert the reference to a dictionary format.

        Returns:
            Dict: Dictionary representation of the reference
        """
        return {
            "url": self.url,
            "title": self.title,
            "accessed_at": self.accessed_at,
            "reference_number": self.reference_number,
        }

    @staticmethod
    def from_dict(data: Dict) -> "SourceReference":
        """
        Create a SourceReference instance from a dictionary.

        Args:
            data: Dictionary containing reference data

        Returns:
            SourceReference: New instance created from dictionary data
        """
        return SourceReference(
            url=data["url"],
            title=data["title"],
            accessed_at=data["accessed_at"],
            reference_number=data.get("reference_number"),
        )

    def get_citation_mark(self) -> str:
        """
        Get the citation mark for in-text references.

        Returns:
            str: Citation mark in the format [※N] or empty string if no reference number
        """
        return (
            f"[※{self.reference_number}]" if self.reference_number is not None else ""
        )


class SourceReferenceManager:
    """
    A class to manage source references.

    This class maintains a collection of SourceReference objects,
    assigns reference numbers, and provides methods for accessing and
    formatting references.
    """

    def __init__(self):
        """Initialize the source reference manager with an empty collection."""
        self.references: List[SourceReference] = []
        self._next_reference_number = 1
        self._url_set: Set[str] = set()  # Track URLs to avoid duplicates

    def add_reference(self, reference: SourceReference) -> str:
        """
        Add a new reference to the collection and return its citation mark.

        If the URL already exists in the collection, returns the existing citation mark.

        Args:
            reference: The SourceReference instance to add

        Returns:
            str: The citation mark for the reference
        """
        # Check if URL already exists
        if reference.url in self._url_set:
            # Find existing reference with same URL
            for existing_ref in self.references:
                if existing_ref.url == reference.url:
                    return existing_ref.get_citation_mark()

        # Add URL to tracking set
        self._url_set.add(reference.url)

        # Create a new instance with the reference number since the original is immutable
        new_reference = SourceReference(
            url=reference.url,
            title=reference.title,
            accessed_at=reference.accessed_at,
            reference_number=self._next_reference_number,
        )
        self.references.append(new_reference)
        self._next_reference_number += 1
        return new_reference.get_citation_mark()

    def get_all_references(self) -> List[SourceReference]:
        """
        Get all stored references sorted by reference number.

        Returns:
            List[SourceReference]: Sorted list of all references
        """
        return sorted(self.references, key=lambda x: x.reference_number or 0)

    def get_reference_by_number(self, number: int) -> Optional[SourceReference]:
        """
        Get a reference by its reference number.

        Args:
            number: The reference number to look for

        Returns:
            Optional[SourceReference]: The reference if found, None otherwise
        """
        for ref in self.references:
            if ref.reference_number == number:
                return ref
        return None

    def to_markdown(self) -> str:
        """
        Convert all references to markdown format with reference numbers.

        Returns:
            str: Markdown formatted reference list or empty string if no references
        """
        if not self.references:
            return ""

        markdown = "\n## Appendix: References\n\n"
        for ref in self.get_all_references():
            markdown += f"※{ref.reference_number}. [{ref.title}]({ref.url}) (Accessed: {ref.accessed_at})\n"
        return markdown
