from unittest.mock import patch

import main


def test_run_job_returns_zero_and_logs_summary(capsys):
    result = {
        "articles_fetched": 10,
        "summaries_extracted": 3,
        "earnings": [],
        "delivery_succeeded": 1,
        "critical_errors": [],
    }

    with patch("main.TechPulseCrew") as crew_cls:
        crew_cls.return_value.run.return_value = result
        exit_code = main.run_job()

    assert exit_code == 0
    assert "Pipeline completed. Fetched: 10, Processed: 3, Delivered: 1" in capsys.readouterr().out


def test_run_job_returns_one_when_pipeline_reports_critical_errors(capsys):
    result = {
        "articles_fetched": 0,
        "summaries_extracted": 0,
        "earnings": [],
        "delivery_succeeded": 0,
        "critical_errors": ["ingestion:rss"],
    }

    with patch("main.TechPulseCrew") as crew_cls:
        crew_cls.return_value.run.return_value = result
        exit_code = main.run_job()

    assert exit_code == 1
    assert "Pipeline completed with critical errors: ['ingestion:rss']" in capsys.readouterr().out


def test_run_job_returns_one_on_critical_exception(capsys):
    with patch("main.TechPulseCrew") as crew_cls:
        crew_cls.return_value.run.side_effect = RuntimeError("boom")
        exit_code = main.run_job()

    assert exit_code == 1
    assert "Pipeline failed with a critical unhandled exception" in capsys.readouterr().out
