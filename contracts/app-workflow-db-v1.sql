PRAGMA user_version = 2;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE waves (
    wave_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('DIRECT', 'DELEGATED')),
    owner_session_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    current_phase TEXT,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE TABLE phases (
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    phase TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    status TEXT NOT NULL,
    process_record_ref TEXT,
    reopened_by TEXT,
    revision INTEGER NOT NULL,
    PRIMARY KEY (wave_id, phase),
    UNIQUE (wave_id, ordinal)
);

CREATE TABLE process_records (
    record_ref TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    phase TEXT NOT NULL,
    outcome TEXT NOT NULL,
    owner_session_ref TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    output_digest TEXT NOT NULL,
    artifact_refs_json TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    supersedes_ref TEXT REFERENCES process_records(record_ref),
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    created_revision INTEGER NOT NULL
);

CREATE UNIQUE INDEX process_one_active
ON process_records(wave_id, phase) WHERE active = 1;

CREATE TABLE entities (
    entity_ref TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
    replacement_ref TEXT,
    properties_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE TABLE observations (
    observation_ref TEXT PRIMARY KEY,
    entity_ref TEXT NOT NULL REFERENCES entities(entity_ref),
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
    replacement_ref TEXT,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE TABLE relations (
    relation_ref TEXT PRIMARY KEY,
    from_entity_ref TEXT NOT NULL REFERENCES entities(entity_ref),
    to_entity_ref TEXT NOT NULL REFERENCES entities(entity_ref),
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'depends_on', 'constrains', 'defines', 'decomposes_to',
        'implemented_by', 'evidenced_by', 'replaces', 'remediates'
    )),
    status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
    replacement_ref TEXT,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE TABLE provenance (
    provenance_ref TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    object_ref TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    created_revision INTEGER NOT NULL,
    UNIQUE (object_type, object_ref, source_ref)
);

CREATE TABLE tasks (
    task_ref TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    title TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    status TEXT NOT NULL,
    record_status TEXT NOT NULL CHECK (record_status IN ('active', 'retired')),
    replacement_ref TEXT,
    owner_session_ref TEXT NOT NULL,
    worker_ref TEXT,
    change_digest TEXT,
    change_refs_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE UNIQUE INDEX tasks_active_sequence ON tasks (wave_id, sequence) WHERE record_status = 'active';

CREATE TABLE dependencies (
    task_ref TEXT NOT NULL REFERENCES tasks(task_ref),
    depends_on_ref TEXT NOT NULL REFERENCES tasks(task_ref),
    created_revision INTEGER NOT NULL,
    PRIMARY KEY (task_ref, depends_on_ref),
    CHECK (task_ref <> depends_on_ref)
);

CREATE TABLE reviews (
    review_ref TEXT PRIMARY KEY,
    task_ref TEXT NOT NULL REFERENCES tasks(task_ref),
    reviewer_ref TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('approved', 'changes_requested')),
    change_digest TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL
);

CREATE TABLE findings (
    finding_ref TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    review_ref TEXT REFERENCES reviews(review_ref),
    analysis_ref TEXT,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    route TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'resolved')),
    source_refs_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE TABLE corrections (
    correction_ref TEXT PRIMARY KEY,
    finding_ref TEXT NOT NULL REFERENCES findings(finding_ref),
    task_ref TEXT NOT NULL REFERENCES tasks(task_ref),
    status TEXT NOT NULL CHECK (status IN ('open', 'resolved')),
    evidence_refs_json TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL
);

CREATE TABLE analyses (
    analysis_ref TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    status TEXT NOT NULL CHECK (status IN ('findings', 'ready')),
    route TEXT,
    source_refs_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL
);

CREATE TABLE snapshot_files (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    captured_revision INTEGER NOT NULL
);

CREATE TABLE audit_attestations (
    audit_ref TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    revision INTEGER NOT NULL,
    logical_digest TEXT NOT NULL,
    snapshot_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'stale')),
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX audit_one_active
ON audit_attestations(wave_id) WHERE status = 'active';

CREATE TABLE request_log (
    request_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    revision INTEGER NOT NULL,
    logical_digest TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX provenance_object ON provenance(object_type, object_ref);
CREATE INDEX relations_from ON relations(from_entity_ref, relation_type, status);
CREATE INDEX relations_to ON relations(to_entity_ref, relation_type, status);
CREATE INDEX findings_wave_status ON findings(wave_id, status);
CREATE INDEX tasks_wave_status ON tasks(wave_id, record_status, sequence);
