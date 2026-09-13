import unittest

from signaldesk.engine import IncidentEngine

class IncidentEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.engine = IncidentEngine()

    def test_classifies_database_incident(self):
        result = self.engine.analyze("Postgres connection pool exhausted and database queries are timing out")
        self.assertEqual(result.category, "database")
        self.assertGreater(result.confidence, .3)

    def test_redacts_sensitive_values(self):
        result = self.engine.analyze("token=super-secret customer user@example.com connected from 10.1.2.3 and login failed")
        self.assertNotIn("super-secret", result.redacted_text)
        self.assertNotIn("user@example.com", result.redacted_text)
        self.assertNotIn("10.1.2.3", result.redacted_text)

    def test_retrieves_similar_resolved_incidents(self):
        result = self.engine.analyze("The canary release has elevated five hundred errors in production")
        self.assertEqual(result.category, "deployment")
        self.assertEqual(result.similar[0]["id"], "INC-4590")

    def test_rejects_empty_prompt(self):
        with self.assertRaises(ValueError): self.engine.analyze("short")

if __name__ == "__main__": unittest.main()

