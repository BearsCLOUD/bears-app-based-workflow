from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from scripts import context_budget, skill_surface

class ContextBudgetTest(unittest.TestCase):
    def test_current_surfaces_scan(self):
        result=context_budget.scan()
        self.assertGreater(result['surface_count'], 0)
    def test_oversized_fixture_needs_split_decision(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d)/'big.md'; p.write_text('# Big\n' + ('text\n'*9000))
            surface=context_budget.surface(p)
            decision=skill_surface.split_decision(p)
            self.assertEqual('split_required', surface['split_policy'])
            self.assertEqual('split', decision['decision'])
    def test_mixed_authority_fixture_splits(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d)/'mixed.md'; p.write_text('## Scope\nA\n## Workflow gates\nB\n## Validation\nC\n## Runtime\nD\n')
            decision=skill_surface.split_decision(p)
            self.assertEqual('mixed_authority', decision['reason_code'])
    def test_section_selection_is_bounded(self):
        pkt=context_budget.select_sections(Path('docs/reference/context-budget-governance.md'), max_tokens=80)
        self.assertLessEqual(pkt['estimated_tokens'], 80)
    def test_doctor(self):
        self.assertEqual([], context_budget.validate_all())

if __name__ == '__main__': unittest.main()
