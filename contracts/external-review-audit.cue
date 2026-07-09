package externalreview

// JSON Schema is the source of truth.
// This file is a cue pilot mirror for packet shape checks.
#Packet: {
	schema: "bears-external-review-contract-packet.v1"
	packet_id: string
	issue: int
	review_state: "open" | "closed" | "superseded"
	surface: {
		path: string
		behavior_changing: bool
		governance_change: bool
		surface_type: "behavior" | "governance" | "docs" | "validator" | "schema" | "other"
	}
	json_schema_ref: string
	proof?: {
		path: string
		status: "pass" | "fail"
	}
	changelog?: {
		path: string
		status: "pass" | "fail"
	}
	decision?: {
		path: string
		status: "pass" | "fail"
	}
}
