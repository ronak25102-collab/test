import subprocess
from pathlib import Path

import pytest
from signal_research.extraction.ocr import LowNumericConfidence, ocr_page
from signal_research.retrieval.metadata import source_publication


@pytest.mark.parametrize("confidence", [99, 80])
def test_packaged_renderer_preserves_ocr_rows_and_withholds_uncertain_numbers(tmp_path, monkeypatch, confidence):
    monkeypatch.setattr("shutil.which", lambda name: None if name == "pdftoppm" else "tesseract")
    commands = []
    tsv = ("level\tblock_num\tpar_num\tline_num\tconf\ttext\n"
           "5\t1\t1\t1\t99\tDeposits\n"
           f"5\t1\t1\t1\t{confidence}\t100000\n"
           "5\t1\t1\t2\t99\tAdvances\n"
           "5\t1\t1\t2\t99\t80000\n")
    def run(command, **kwargs):
        commands.append(command)
        assert 0 < kwargs["timeout"] <= 10
        return subprocess.CompletedProcess(command, 0, stdout=tsv.encode())
    monkeypatch.setattr(subprocess, "run", run)
    if confidence == 80:
        with pytest.raises(LowNumericConfidence, match="numeric confidence") as failure:
            ocr_page(Path("scan.pdf"), 0, tmp_path, 10)
        assert failure.value.identity_text == 'Deposits\nAdvances'
        assert not any(c.isdigit() for c in failure.value.identity_text)
    else:
        assert ocr_page(Path("scan.pdf"), 0, tmp_path, 10) == "Deposits 100000\nAdvances 80000"
    assert "signal_research.extraction.render_worker" in commands[0]


def test_rating_action_cover_date_is_eligible_but_balance_date_is_not():
    rating = "June 23, 2026\nHDFC Bank Limited: Ratings reaffirmed\nDeposits at March 31, 2026"
    assert source_publication(b"%PDF", rating).date().isoformat() == "2026-06-23"
    assert source_publication(b"%PDF", "March 31, 2026\nHDFC Bank standalone balance sheet") is None
