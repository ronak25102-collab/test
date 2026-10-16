from fastapi.testclient import TestClient
from signal_research.main import create_app
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


def test_health_and_replay_run(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}", data_dir=tmp_path, auto_start_worker=False)
    application = create_app(settings)
    with TestClient(application) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        company = client.get("/api/v1/companies?q=SYNTHBANK").json()["items"][0]
        response = client.post("/api/v1/runs", json={"company_id": company["id"], "as_of": "2026-10-08", "mode": "replay"})
        assert response.status_code == 202
        assert client.get(f"/api/v1/runs/{response.json()['run_id']}").status_code == 200
        history = client.get('/api/v1/runs/history?limit=1')
        assert history.status_code == 200
        assert history.json()['items'][0]['id'] == response.json()['run_id']
        assert history.json()['items'][0]['mode'] == 'replay'
        assert 'api_key' not in history.text
        assert client.get('/api/v1/runs/history?limit=0').status_code == 422


def test_report_evidence_and_exports(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'report.db'}", data_dir=tmp_path, auto_start_worker=False)
    application = create_app(settings)
    with TestClient(application) as client:
        company = client.get("/api/v1/companies?q=SYNTHBANK").json()["items"][0]
        run_id = client.post("/api/v1/runs", json={"company_id": company["id"], "as_of": "2026-10-08", "mode": "replay"}).json()["run_id"]
        application.state.store.lease_next("integration-worker")
        ResearchMachine(application.state.store, settings).process(run_id)
        report = client.get(f"/api/v1/runs/{run_id}/report")
        assert report.status_code == 200
        payload = report.json()
        claim_id = payload["claims"][0]["id"]
        assert client.get(f"/api/v1/claims/{claim_id}?run_id={run_id}").status_code == 200
        assert client.get(f"/api/v1/runs/{run_id}/exports/report.json").status_code == 200
        assert client.get(f"/api/v1/runs/{run_id}/exports/facts.csv").text.startswith("id,metric_key")
