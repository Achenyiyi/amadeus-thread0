from pathlib import Path


def test_phase2_repo_fixture_smoke():
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / "AGENTS.md").exists()
    assert (repo_root / "docker" / "sandbox_phase2" / "Dockerfile").exists()
    assert (repo_root / "tests" / "test_sandbox_phase2_repo_fixture.py").exists()
