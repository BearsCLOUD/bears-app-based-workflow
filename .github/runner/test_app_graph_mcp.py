"""Exercise MCP lifecycle, strict schemas, notifications, and wire budgets."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "scripts/app_graph_mcp.py"


def run(lines: list[object], *, maintainer: bool = False) -> list[dict]:
    payload = b"".join((item if isinstance(item, bytes) else json.dumps(item).encode()) + b"\n" for item in lines)
    command = ["python3", str(SERVER), *(["--maintainer"] if maintainer else [])]
    result = subprocess.run(command, cwd=ROOT, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
    return [json.loads(line) for line in result.stdout.splitlines()]


class AppGraphMcpTests(unittest.TestCase):
    def initialized(self, *calls: dict, maintainer: bool = False) -> list[dict]:
        return run([
            {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1"}}},
            {"jsonrpc":"2.0","method":"notifications/initialized"},
            *calls,
        ], maintainer=maintainer)

    def test_malformed_and_unsupported_protocol_do_not_crash(self) -> None:
        replies = run([b"{", {"jsonrpc":"2.0","id":2,"method":"initialize","params":{"protocolVersion":"1900-01-01"}}, {"jsonrpc":"2.0","id":3,"method":"ping"}])
        self.assertEqual([-32700, -32602, -32002], [item["error"]["code"] for item in replies])

    def test_notifications_have_no_response_and_server_continues(self) -> None:
        replies = self.initialized(
            {"jsonrpc":"2.0","method":"notifications/cancelled","params":{}},
            {"jsonrpc":"2.0","id":2,"method":"ping"},
        )
        self.assertEqual([1, 2], [item["id"] for item in replies])

    def test_strict_tool_schema_and_server_separation(self) -> None:
        replies = self.initialized(
            {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"graph_compile","arguments":{"app_root":str(ROOT)}}},
            {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"graph_trace","arguments":{"app_root":str(ROOT),"raw_toml":"x"}}},
        )
        self.assertEqual([-32602, -32602], [item["error"]["code"] for item in replies[1:]])
        tools = self.initialized({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}, maintainer=True)[1]["result"]["tools"]
        self.assertEqual({"graph_compile", "process_record_event"}, {item["name"] for item in tools})
        self.assertTrue(all(item["inputSchema"]["additionalProperties"] is False for item in tools))

    def test_every_wire_response_is_bounded(self) -> None:
        replies = self.initialized({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
        self.assertTrue(all(len(json.dumps(item, separators=(",", ":")).encode()) <= 16 * 1024 for item in replies))

    def test_tools_list_accepts_request_metadata_but_not_a_cursor(self) -> None:
        replies = self.initialized(
            {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"_meta":{"progressToken":"startup"}}},
            {"jsonrpc":"2.0","id":3,"method":"tools/list","params":{"cursor":"unexpected"}},
        )
        self.assertIn("tools", replies[1]["result"])
        self.assertEqual(-32602, replies[2]["error"]["code"])


if __name__ == "__main__": unittest.main()
