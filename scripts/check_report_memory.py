"""Exercise real report publication and concurrent downloads against a local server.

Run on Linux under a cgroup/container memory limit (512 MiB, swap disabled).
Uses a temporary SQLite database; never connects to the deployment database.
"""
import argparse
import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


def serve(database, port):
    import uvicorn
    from signal_research.main import create_app
    from signal_research.settings import Settings

    settings = Settings(_env_file=None, database_url=f"sqlite:///{database}",
                        data_dir=Path(database).parent, auto_start_worker=True,
                        pipeline_mode="precomputed", replay_duration_seconds=.25,
                        clerk_publishable_key="", auth_required=False, frontend_dist_dir=None)
    uvicorn.run(create_app(settings), host="127.0.0.1", port=port, log_level="warning")


def check():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}/api/v1"
    peak = [0]
    stop = threading.Event()

    def request(path, payload=None, expected=200, decode=False):
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(base + path, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            response = urllib.request.urlopen(req, timeout=180)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (path, response.status, response.read(1000))
            if decode:
                return json.load(response)
            size = 0
            while chunk := response.read(64 * 1024):
                size += len(chunk)
            return size

    # Modern Linux runners mount /tmp as tmpfs. A growing SQLite database there
    # consumes unreclaimable RAM, unlike Render's external Postgres database.
    # Keep this isolated test database on the workspace's disk filesystem.
    scratch = Path.cwd() / ".review-cache"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="beyond-memory-", dir=scratch) as directory:
        database = str(Path(directory) / "isolated.db")
        with open(Path(directory) / "server.log", "w+") as log:
            process = subprocess.Popen([sys.executable, __file__, "--serve", database,
                                        "--port", str(port)], stdout=log, stderr=log,
                                       env={**os.environ, "MALLOC_ARENA_MAX": "2"})

            def sample():
                while not stop.wait(.01):
                    try:
                        status = Path(f"/proc/{process.pid}/status").read_text()
                        rss = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
                        peak[0] = max(peak[0], int(rss.split()[1]) * 1024)
                    except (OSError, StopIteration):
                        pass

            sampler = threading.Thread(target=sample, daemon=True)
            sampler.start()
            try:
                deadline = time.monotonic() + 90
                while True:
                    assert process.poll() is None, "Server exited during startup"
                    try:
                        request("/health/live")
                        break
                    except OSError:
                        assert time.monotonic() < deadline, "Startup timed out"
                        time.sleep(.1)
                companies = [request("/companies/resolve", {"query": symbol}, decode=True)["resolved"]
                             for symbol in ("KOTAKBANK", "HDFCBANK", "ICICIBANK", "AXISBANK")]
                print("Server ready; starting concurrent publications", flush=True)

                def create(company):
                    return request("/runs", {"company_id": company["id"], "as_of": "2026-10-24"},
                                   expected=202, decode=True)["run_id"]

                with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
                    runs = list(pool.map(create, companies))
                    for round_number in range(2):
                        deadline = time.monotonic() + 180
                        while True:
                            states = [request(f"/runs/{run_id}", decode=True)["status"] for run_id in runs]
                            assert not set(states) & {"failed", "cancelled"}, states
                            if set(states) == {"completed"}:
                                break
                            assert time.monotonic() < deadline, states
                            assert process.poll() is None, "Server died during publication"
                            time.sleep(.1)
                        jobs = []
                        print(f"Batch {round_number + 1} published; starting downloads; "
                              f"peak RSS {peak[0] / 1024 ** 2:.1f} MiB", flush=True)
                        # Repeated reports, ZIPs and evidence requests compete with
                        # publication of the next batch of four investigations.
                        for run_id in runs:
                            for suffix in ("report", "exports/report.json", "exports/report.html", "exports/evidence.zip"):
                                jobs.append(pool.submit(request, f"/runs/{run_id}/{suffix}"))
                            jobs.append(pool.submit(request, f"/documents/{uuid4()}/passages?run_id={run_id}", expected=404))
                        if round_number == 0:
                            next_runs = [pool.submit(create, company) for company in companies]
                        for job in jobs:
                            assert job.result() > 0
                        if round_number == 0:
                            runs = [job.result() for job in next_runs]
                    assert request("/health/ready", decode=True)["database"] == "ok"
                print(json.dumps({"completed_runs": 8, "concurrent_clients": 16,
                                  "server_peak_rss_mib": round(peak[0] / 1024 ** 2, 1)}), flush=True)
                cgroup = Path("/proc/self/cgroup")
                if cgroup.is_file() and cgroup.read_text().startswith("0::"):
                    root = Path("/sys/fs/cgroup") / cgroup.read_text().strip().split("::", 1)[1].lstrip("/")
                    if (root / "memory.max").is_file():
                        limit = (root / "memory.max").read_text().strip()
                        print(json.dumps({"cgroup_memory_limit_bytes": limit,
                                          "cgroup_memory_peak_bytes": int((root / "memory.peak").read_text()),
                                          "memory_events": (root / "memory.events").read_text().splitlines()}))
                        assert limit != "max" and int(limit) <= 512 * 1024 ** 2, "Run under a 512 MiB cgroup limit"
                        assert "oom_kill 0" in (root / "memory.events").read_text().splitlines()
                assert peak[0] < 450 * 1024 ** 2, "Insufficient headroom under the 512 MiB host limit"
            except BaseException:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                stop.set()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                sampler.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.port)
    else:
        check()
