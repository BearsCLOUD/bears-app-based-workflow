from __future__ import annotations
import unittest
from scripts import repo_onboarding

class RepoOnboardingTest(unittest.TestCase):
    def test_inventory_has_write_and_read_only(self):
        pkt=repo_onboarding.inventory()
        statuses={r['repo']:r['governance_status'] for r in pkt['repositories']}
        self.assertEqual('write_scoped', statuses['BearsCLOUD/bears-codex-workflow-plugin'])
        self.assertEqual('read_only', statuses['BearsCLOUD/bears-codex-workspace'])
    def test_validate(self):
        self.assertEqual([], repo_onboarding.validate_all())
    def test_doctor(self):
        self.assertEqual('pass', repo_onboarding.doctor()['status'])

if __name__ == '__main__': unittest.main()
