import unittest
from pathlib import Path
import re

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.contracts import RackSpatialNode
from app.main import create_app
from app.core.ao02_state_and_graph import ResourceType


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings(_env_file=None, openai_api_key="private-test-secret")))

    def test_bootstrap_has_reference_geometry_and_no_credentials(self):
        response = self.client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["racks"]), 12)
        self.assertEqual(len({r["rackId"] for r in data["racks"]}), 12)
        self.assertEqual(len(data["coolingUnits"]), 2)
        self.assertFalse(data["telemetryAvailable"])
        self.assertNotIn("private-test-secret", response.text)
        self.assertNotIn("tenant", response.text.lower())

    def test_health_and_read_only_boundary(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        self.assertEqual(self.client.post("/api/bootstrap", json={}).status_code, 405)
        self.assertEqual(self.client.get("/api/incidents").status_code, 401)

    def test_frontend_resource_contract_matches_backend(self):
        source = (Path(__file__).resolve().parents[2] / "frontend/src/types/ao02.ts").read_text()
        declaration = source.split("as const", 1)[0]
        self.assertEqual(re.findall(r"'([A-Z_]+)'", declaration), [item.value for item in ResourceType])

    def test_cors_rejects_unlisted_origins(self):
        response = self.client.options("/api/bootstrap", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_contract_aliases_and_validation(self):
        rack = dict(rackId="R-01", gridPosition={"row": 0, "col": 0},
                    status="HEALTHY", powerLoadKw=4, maxPowerKw=10)
        value = RackSpatialNode.model_validate(rack)
        self.assertEqual(value.model_dump(by_alias=True)["rackId"], "R-01")
        with self.assertRaises(ValidationError):
            RackSpatialNode.model_validate({**rack, "powerLoadKw": -1})
        with self.assertRaises(ValidationError):
            RackSpatialNode.model_validate({**rack, "status": "UNKNOWN"})


if __name__ == "__main__":
    unittest.main()
