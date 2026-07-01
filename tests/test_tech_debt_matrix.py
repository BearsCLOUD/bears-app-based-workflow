import json
import unittest

from scripts import tech_debt_matrix


class TechDebtMatrixTest(unittest.TestCase):
    def test_catalog_validates(self):
        catalog = tech_debt_matrix.load_json(tech_debt_matrix.CATALOG_PATH)
        self.assertEqual([], tech_debt_matrix.validate_catalog(catalog))

    def test_rejects_missing_state_refs(self):
        catalog = tech_debt_matrix.load_json(tech_debt_matrix.CATALOG_PATH)
        catalog = json.loads(json.dumps(catalog))
        catalog['items'][0]['state_refs'].pop('merge_authority_state')
        errors = tech_debt_matrix.validate_catalog(catalog)
        self.assertIn('tech-debt-matrix.items[0].state_refs.merge_authority_state is required', errors)

    def test_rejects_duplicate_ids(self):
        catalog = tech_debt_matrix.load_json(tech_debt_matrix.CATALOG_PATH)
        catalog = json.loads(json.dumps(catalog))
        catalog['items'][1]['id'] = catalog['items'][0]['id']
        errors = tech_debt_matrix.validate_catalog(catalog)
        self.assertIn('tech-debt-matrix.items[1].id must be unique', errors)


if __name__ == '__main__':
    unittest.main()
