python_sources(
    name="pants_scripts",
    sources=["scripts/*.py"],
)

python_tests(
    name="pants_tests",
    sources=["tests/test_*.py"],
)

files(
    name="pants_catalog_files",
    sources=["assets/catalog/*.json"],
)

files(
    name="pants_schema_files",
    sources=["assets/schemas/*.json"],
)

files(
    name="pants_graph_files",
    sources=[
        "pants.toml",
        "docs/reference/pants-test-graph.md",
        "assets/catalog/pants-test-graph.v1.json",
        "assets/schemas/pants-test-graph.v1.schema.json",
    ],
)

files(
    name="ci_and_pr_pipeline_files",
    sources=[".github/workflows/*.yml"],
)

files(
    name="external_review_audit_files",
    sources=[
        "docs/audits/external-review-2026-06-25/*",
        "assets/catalog/external-review-audit.v1.json",
        "assets/schemas/external-review-audit.v1.schema.json",
    ],
)

files(
    name="file_context_index_files",
    sources=["assets/file-context/index.v1.json"],
)

files(
    name="external_review_contract_files",
    sources=[
        "contracts/external-review-audit.cue",
        "docs/reference/external-review-contract.md",
        "tests/fixtures/external_review_contract/**/*.json",
    ],
)

files(
    name="dagger_delivery_files",
    sources=[
        "dagger.json",
        "docs/reference/dagger-delivery-pipeline.md",
    ],
)

files(
    name="temporal_evaluation_files",
    sources=["docs/research/temporal-evaluation.md"],
)

files(
    name="doctor_component_coverage_files",
    sources=[
        "assets/catalog/doctor-component-coverage.v1.json",
        "assets/schemas/doctor-component-coverage.v1.schema.json",
        "assets/schemas/doctor-component-gap.v1.schema.json",
        "docs/reference/doctor-component-coverage.md",
        "tests/fixtures/doctor_component_coverage/**/*.json",
    ],
)
