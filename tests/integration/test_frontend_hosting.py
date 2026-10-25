from fastapi.testclient import TestClient
from signal_research.main import create_app


def test_combined_hosting_serves_frontend_and_preserves_api_routes(tmp_path, settings):
    frontend = tmp_path / "frontend"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text('<html><div id="root">Beyond</div></html>')
    (assets / "app.js").write_text('console.log("Beyond")')
    settings.frontend_dist_dir = frontend

    with TestClient(create_app(settings)) as client:
        for path in ("/", "/?view=report&run=saved-run&section=figures"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert 'id="root"' in response.text

        assert client.get("/assets/app.js").text == 'console.log("Beyond")'
        assert client.get("/api/v1/health/live").json()["status"] == "ok"
        assert client.get("/api/v1/companies?q=SYNTHBANK").json()["items"]
        assert client.get("/api/v1/not-a-route").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404


def test_api_can_run_without_a_frontend_build(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/v1/health/live").status_code == 200
