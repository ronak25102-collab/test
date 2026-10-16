import importlib.util
from pathlib import Path


def test_regression_defaults_cover_banks_nbfc_and_insurance_and_write_failures(tmp_path):
    path = Path(__file__).parents[2] / 'scripts' / 'regression.py'
    spec = importlib.util.spec_from_file_location('regression_runner', path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    assert len(runner.DEFAULT_COMPANIES) >= 6
    assert {'BAJFINANCE', 'SBILIFE'} <= set(runner.DEFAULT_COMPANIES)
    target = tmp_path / 'regression.md'
    runner.write_report([{'symbol': 'EXAMPLE', 'seconds': 312, 'facts': 4, 'strength': 'Not established',
                          'outcome': 'partial', 'failures': ['Provider did not complete within the stage window']}], target)
    text = target.read_text(encoding='utf-8')
    assert 'exceeded' in text and 'Provider did not complete' in text
    assert 'Cache facts reused: 0' in text
