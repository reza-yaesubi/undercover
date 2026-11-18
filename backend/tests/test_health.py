def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_operations_have_unique_ids_and_documentation(client):
    schema = client.get("/openapi.json").json()
    operations = [
        operation for path in schema["paths"].values() for operation in path.values()
    ]
    identifiers = [operation["operationId"] for operation in operations]
    assert len(identifiers) == len(set(identifiers))
    assert set(identifiers) == {
        "health",
        "list_claims",
        "get_claim",
        "get_policy_wording",
        "get_agent_instructions",
        "list_handlers",
        "record_decision",
        "sign_off_claim",
        "pay_claim",
        "start_claim_run",
        "get_claim_activity",
        "record_claim_activity",
    }
    assert all(operation["description"] for operation in operations)
    for operation in operations:
        assert all(
            parameter["required"] for parameter in operation.get("parameters", [])
        )


def test_openapi_mutation_bodies_have_no_optional_fields(client):
    schema = client.get("/openapi.json").json()
    for suffix in ["decision", "sign-off", "pay", "activity"]:
        operation = schema["paths"][f"/api/claims/{{claim_id}}/{suffix}"]["post"]
        body = operation["requestBody"]
        assert body["required"]
        reference = body["content"]["application/json"]["schema"]["$ref"]
        model = schema["components"]["schemas"][reference.rsplit("/", 1)[1]]
        assert set(model["required"]) == set(model["properties"])
    assert "requestBody" not in schema["paths"]["/api/claims/{claim_id}/run"]["post"]
