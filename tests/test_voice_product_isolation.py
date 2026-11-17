import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.knowledge_search_service import search_knowledge


class FakeMappings:
    def all(self):
        return [
            {
                "chunk_id": uuid4(),
                "document_id": uuid4(),
                "content": "Product-scoped content",
                "similarity": 0.9,
                "document_title": "Scoped document",
                "document_file_name": "scoped.pdf",
            }
        ]


class FakeResult:
    def mappings(self):
        return FakeMappings()


class RecordingDatabaseSession:
    def __init__(self) -> None:
        self.statement = None
        self.parameters = None

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        return FakeResult()


class VoiceProductIsolationTests(unittest.TestCase):
    def test_rag_query_binds_authenticated_product_to_both_filters(self) -> None:
        db = RecordingDatabaseSession()
        authenticated_product_id = uuid4()

        with patch(
            "app.services.knowledge_search_service.generate_embedding",
            return_value=[0.0] * 768,
        ):
            results = search_knowledge(
                db=db,
                question="What are the fees?",
                product_id=authenticated_product_id,
                limit=5,
            )

        self.assertEqual(
            db.parameters["match_product_id"],
            authenticated_product_id,
        )
        sql = str(db.statement)
        self.assertIn("public.search_knowledge_chunks", sql)
        self.assertIn(
            "documents.product_id = :match_product_id",
            sql,
        )
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
