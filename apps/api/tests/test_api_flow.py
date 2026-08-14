from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_safe_plan_flow_is_idempotent_and_paused():
    payload = {
        "customer_id": "demo",
        "name": "KubeGame Pro | Search | MVP",
        "final_url": "https://example.com/oferta",
        "daily_budget": {"amount": "25.00", "currency": "BRL"},
        "period": {"start": "2026-08-14", "end": "2026-08-31"},
        "geo_targets": ["Brasil"],
        "language_targets": ["pt-BR"],
        "conversion_goal_ids": ["purchase"],
        "campaign_negatives": ["grátis", "pirata"],
        "ad_groups": [{
            "name": "CKA",
            "keywords": ["curso cka"],
            "headlines": ["Curso CKA", "Prepare-se para CKA", "Pacote completo"],
            "descriptions": ["Treinamento prático.", "Conheça o pacote."],
        }],
    }
    created = client.post("/v1/plans", json=payload)
    assert created.status_code == 201
    plan_id = created.json()["id"]

    validation = client.post(f"/v1/plans/{plan_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["allowed"] is True

    approval = client.post(
        f"/v1/plans/{plan_id}/approve", json={"approved_by": "QA Owner"}
    )
    assert approval.status_code == 200

    headers = {"Idempotency-Key": f"test-{plan_id}"}
    first = client.post(f"/v1/plans/{plan_id}/execute", headers=headers)
    second = client.post(f"/v1/plans/{plan_id}/execute", headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["status"] == "CREATED_PAUSED"
    assert second.json()["external_spend"] == "0.00"
