import unittest

from scripts import authority_map


class AuthorityMapTests(unittest.TestCase):
    def test_authority_map_validate_passes(self) -> None:
        self.assertEqual(authority_map.validate_all(), [])

    def test_all_required_topics_are_present(self) -> None:
        packet = authority_map.load(authority_map.CATALOG)
        topics = {item["topic"] for item in packet["topics"]}
        self.assertTrue(authority_map.REQUIRED_TOPICS.issubset(topics))

    def test_deprecated_surface_cannot_be_canonical(self) -> None:
        errors = authority_map.validate_map(authority_map.BAD / "deprecated-is-canonical.json", require_all_topics=False)
        self.assertIn("deprecated surface is active authority", "\n".join(errors))

    def test_good_fixture_passes_without_full_topic_set(self) -> None:
        errors = authority_map.validate_map(authority_map.GOOD / "minimal.json", require_all_topics=False)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
