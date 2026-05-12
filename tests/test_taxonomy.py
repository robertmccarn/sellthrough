from __future__ import annotations

import unittest

from sellthrough.ebay.taxonomy import CategoryTree, TaxonomyClient


class CategoryTreeTests(unittest.TestCase):
    def test_from_payload_preserves_marketplace_context(self) -> None:
        tree = CategoryTree.from_payload(
            marketplace_id="EBAY_US",
            payload={"categoryTreeId": "0", "categoryTreeVersion": "134"},
        )

        self.assertEqual(tree.marketplace_id, "EBAY_US")
        self.assertEqual(tree.category_tree_id, "0")
        self.assertEqual(tree.category_tree_version, "134")


class TaxonomyClientFlattenTests(unittest.TestCase):
    def test_get_category_subtree_flattens_nested_nodes(self) -> None:
        class FakeResponse:
            ok = True
            status_code = 200
            headers = {}

            def json(self):
                return {
                    "categorySubtreeNode": {
                        "category": {"categoryId": "1", "categoryName": "Root"},
                        "childCategoryTreeNodes": [
                            {"category": {"categoryId": "2", "categoryName": "Child"}}
                        ],
                    }
                }

        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()

        class FakeEbayClient:
            session = FakeSession()

            class settings:
                api_base_url = "https://api.ebay.com"

            def bearer_token(self):
                return "token"

        client = TaxonomyClient(FakeEbayClient())
        nodes = client.get_category_subtree("0", "1")

        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].category_id, "1")
        self.assertFalse(nodes[0].leaf)
        self.assertEqual(nodes[1].parent_category_id, "1")
        self.assertTrue(nodes[1].leaf)

    def test_get_category_suggestions_reads_leaf_tree_node_shape(self) -> None:
        class FakeResponse:
            ok = True
            status_code = 200
            headers = {}

            def json(self):
                return {
                    "categorySuggestions": [
                        {
                            "category": {
                                "categoryId": "184655",
                                "categoryName": "Cordless Drills",
                            },
                            "categoryTreeNode": {"leafCategoryTreeNode": True},
                        }
                    ]
                }

        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()

        class FakeEbayClient:
            session = FakeSession()

            class settings:
                api_base_url = "https://api.ebay.com"

            def bearer_token(self):
                return "token"

        client = TaxonomyClient(FakeEbayClient())
        suggestions = client.get_category_suggestions("cordless drill", category_tree_id="0")

        self.assertEqual(suggestions[0].category_id, "184655")
        self.assertTrue(suggestions[0].leaf)


if __name__ == "__main__":
    unittest.main()
