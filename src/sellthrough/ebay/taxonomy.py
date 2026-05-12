"""Taxonomy API client for eBay category normalization.

Categories are an important bridge between messy keyword searches and stable
analytics. A query like "dewalt drill" may produce listings in several related
leaf categories; Taxonomy gives the project stable category IDs and names so
future snapshots can compare like with like over time.

The Taxonomy API returns tree-shaped data, while the CLI and database prefer
rows. This module is therefore both an API adapter and a tree-to-row normalizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sellthrough.config import Settings
from sellthrough.ebay.browse import DEFAULT_MARKETPLACE_ID
from sellthrough.ebay.client import EbayApiError, EbayClient, EbayRateLimitError


@dataclass(frozen=True)
class CategoryTree:
    """Metadata describing the default category tree for one marketplace."""

    marketplace_id: str
    category_tree_id: str
    category_tree_version: str | None
    raw_payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        *,
        marketplace_id: str,
        payload: dict[str, Any],
    ) -> "CategoryTree":
        return cls(
            marketplace_id=marketplace_id,
            category_tree_id=str(payload.get("categoryTreeId", "")),
            category_tree_version=payload.get("categoryTreeVersion"),
            raw_payload=payload,
        )


@dataclass(frozen=True)
class CategoryNode:
    """A flattened category node from an eBay category subtree.

    The Taxonomy API returns categories as nested trees. Flattening nodes with
    level and parent metadata makes CLI output readable and gives future DB
    storage a simple shape.
    """

    category_id: str
    category_name: str
    level: int
    parent_category_id: str | None
    leaf: bool


class TaxonomyClient:
    """High-level wrapper for eBay Taxonomy category lookups."""

    def __init__(self, ebay_client: EbayClient) -> None:
        self.ebay_client = ebay_client

    @classmethod
    def from_settings(cls, settings: Settings) -> "TaxonomyClient":
        return cls(EbayClient.from_settings(settings))

    def get_default_category_tree_id(
        self,
        *,
        marketplace_id: str = DEFAULT_MARKETPLACE_ID,
    ) -> CategoryTree:
        """Return the default category tree ID for a marketplace.

        eBay category IDs are marketplace-specific. Calling this first avoids
        hard-coding a tree ID that may only be valid for one marketplace.
        """

        payload = self._get_json(
            "/commerce/taxonomy/v1/get_default_category_tree_id",
            params={"marketplace_id": marketplace_id},
        )
        return CategoryTree.from_payload(marketplace_id=marketplace_id, payload=payload)

    def get_category_subtree(self, category_tree_id: str, category_id: str) -> tuple[CategoryNode, ...]:
        """Return a flattened category subtree rooted at `category_id`.

        Args:
            category_tree_id: Marketplace-specific category tree identifier.
            category_id: Root category to expand.

        Returns:
            Category nodes in preorder: parent first, then descendants.

        Raises:
            ValueError: If either identifier is blank.
            EbayApiError: If eBay rejects the request.
        """

        if not category_tree_id.strip():
            raise ValueError("Category tree ID cannot be blank.")
        if not category_id.strip():
            raise ValueError("Category ID cannot be blank.")

        payload = self._get_json(
            f"/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_category_subtree",
            params={"category_id": category_id},
        )
        root = payload.get("categorySubtreeNode") or {}
        return tuple(_flatten_category_tree(root))

    def get_category_suggestions(
        self,
        query: str,
        *,
        category_tree_id: str | None = None,
        marketplace_id: str = DEFAULT_MARKETPLACE_ID,
    ) -> tuple[CategoryNode, ...]:
        """Return category suggestions for a keyword query.

        This is useful during watchlist design: a human can start with a phrase
        such as "cordless drill" and inspect which eBay category IDs are likely
        candidates before pinning a watchlist entry to a category.
        """

        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Category suggestion query cannot be blank.")

        resolved_tree_id = category_tree_id
        if resolved_tree_id is None:
            # Let callers pass only a marketplace when they do not already know
            # the tree ID. This adds one API call but keeps the CLI ergonomic.
            resolved_tree_id = self.get_default_category_tree_id(
                marketplace_id=marketplace_id
            ).category_tree_id

        payload = self._get_json(
            f"/commerce/taxonomy/v1/category_tree/{resolved_tree_id}/get_category_suggestions",
            params={"q": cleaned_query},
        )

        suggestions = []
        for suggestion in payload.get("categorySuggestions") or ():
            # Each suggestion wraps category metadata in a nested `category`
            # object. We flatten it immediately so callers do not need to know
            # the response shape.
            category = suggestion.get("category") or {}
            category_id = str(category.get("categoryId", ""))
            leaf_node = suggestion.get("leafCategoryTreeNode")
            suggestions.append(
                CategoryNode(
                    category_id=category_id,
                    category_name=category.get("categoryName", ""),
                    level=0,
                    parent_category_id=None,
                    leaf=bool(leaf_node) or _suggestion_is_leaf(suggestion),
                )
            )
        return tuple(suggestions)

    def _get_json(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Issue an authenticated Taxonomy GET request and return JSON."""

        response = self.ebay_client.session.get(
            f"{self.ebay_client.settings.api_base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.ebay_client.bearer_token()}"},
            timeout=30,
        )
        payload = _safe_response_json(response)
        if not response.ok:
            if response.status_code == 429:
                raise EbayRateLimitError(
                    "Taxonomy request was rate-limited by eBay.",
                    retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
                    status_code=response.status_code,
                    payload=payload,
                )
            raise EbayApiError(
                f"Taxonomy request failed: {response.status_code}",
                status_code=response.status_code,
                payload=payload,
            )
        return payload


def _flatten_category_tree(
    node: dict[str, Any],
    *,
    level: int = 0,
    parent_category_id: str | None = None,
) -> list[CategoryNode]:
    """Flatten eBay's nested category tree into parent-aware rows.

    This is a recursive preorder traversal. Recursion is appropriate here
    because a category node naturally contains smaller category nodes. Each
    recursive call carries two pieces of context that eBay's child node does not
    need to repeat: its `level` for display indentation and its parent ID for
    future relational storage.
    """

    category = node.get("category") or {}
    category_id = str(category.get("categoryId", ""))
    children = node.get("childCategoryTreeNodes") or ()
    current = CategoryNode(
        category_id=category_id,
        category_name=category.get("categoryName", ""),
        level=level,
        parent_category_id=parent_category_id,
        leaf=not bool(children),
    )

    rows = [current]
    for child in children:
        # `extend` appends all descendant rows from the recursive call. That
        # preserves a flat list while still walking the original nested shape.
        rows.extend(
            _flatten_category_tree(
                child,
                level=level + 1,
                parent_category_id=category_id,
            )
        )
    return rows


def _suggestion_is_leaf(suggestion: dict[str, Any]) -> bool:
    """Infer leaf status from eBay suggestion payload variants.

    eBay's Taxonomy docs and live responses can expose leaf information in
    slightly different shapes. Keeping that interpretation here prevents CLI and
    storage code from learning API quirks independently.
    """

    category_tree_node = suggestion.get("categoryTreeNode") or {}
    return bool(category_tree_node.get("leafCategoryTreeNode"))


def _safe_response_json(response: Any) -> dict[str, Any]:
    """Return eBay JSON payloads and normalize empty/non-JSON bodies."""

    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_retry_after(value: str | None) -> int | None:
    """Parse numeric Retry-After seconds from an eBay response header."""

    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
