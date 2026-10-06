import uuid
from types import SimpleNamespace
from backend.services.analysis import _evaluate_hypothesis
import pytest

from backend.services.analysis import (
    _clamp,
    _retention_score,
    _latency_score,
    _recovery_metric_score,
    _latency_recovery_score,
    _calculate_failure_resistance,
    _calculate_recovery_score,
    _calculate_resilience_score,
    _determine_severity,
    _calculate_degradation,
    _determine_recovery,
    _calculate_recovery_time,
    _calculate_service_impact,
    _calculate_failure_impact,
    _generate_recommendations,
    _extract_result,
    analyze_experiment,
)


# ============================================================
# TEST DATA HELPERS
# ============================================================

def make_result(
    total_requests=100,
    successful_requests=100,
    failed_requests=0,
    success_rate=100.0,
    error_rate=0.0,
    average_latency_ms=100.0,
    p50_latency_ms=90.0,
    p95_latency_ms=150.0,
    p99_latency_ms=200.0,
    throughput=100.0,
    availability=100.0,
):
    return SimpleNamespace(
        total_requests=total_requests,
        successful_requests=successful_requests,
        failed_requests=failed_requests,
        success_rate=success_rate,
        error_rate=error_rate,
        average_latency_ms=average_latency_ms,
        p50_latency_ms=p50_latency_ms,
        p95_latency_ms=p95_latency_ms,
        p99_latency_ms=p99_latency_ms,
        throughput=throughput,
        availability=availability,
    )


def make_metrics(
    success_rate,
    latency,
    throughput,
    availability,
):
    return {
        "total_requests": 100,
        "successful_requests": int(success_rate),
        "failed_requests": 100 - int(success_rate),
        "success_rate": success_rate,
        "error_rate": 100 - success_rate,
        "average_latency_ms": latency,
        "p50_latency_ms": latency,
        "p95_latency_ms": latency,
        "p99_latency_ms": latency,
        "throughput": throughput,
        "availability": availability,
    }


# ============================================================
# BASIC SCORE FUNCTIONS
# ============================================================

def test_clamp():
    assert _clamp(50) == 50
    assert _clamp(-10) == 0
    assert _clamp(120) == 100


def test_retention_score():
    assert _retention_score(100, 100) == 100
    assert _retention_score(100, 80) == 80
    assert _retention_score(100, 50) == 50


def test_latency_score():
    assert _latency_score(100, 100) == 100
    assert _latency_score(100, 200) == 50


def test_recovery_metric_score():
    assert _recovery_metric_score(100, 100) == 100
    assert _recovery_metric_score(100, 80) == 80


def test_latency_recovery_score():
    # Within 5% of baseline = full recovery
    assert _latency_recovery_score(100, 105) == 100

    # Higher latency reduces score
    assert _latency_recovery_score(100, 200) < 100


# ============================================================
# FAILURE RESISTANCE
# ============================================================

def test_calculate_failure_resistance():

    baseline = make_metrics(
        success_rate=100,
        latency=100,
        throughput=100,
        availability=100,
    )

    failure = make_metrics(
        success_rate=80,
        latency=200,
        throughput=70,
        availability=80,
    )

    result = _calculate_failure_resistance(
        baseline,
        failure,
    )

    assert result["success_score"] == 80
    assert result["latency_score"] == 50
    assert result["throughput_score"] == 70

    assert result["failure_resistance_score"] == 67


# ============================================================
# RECOVERY SCORE
# ============================================================

def test_calculate_recovery_score():

    baseline = make_metrics(
        success_rate=100,
        latency=100,
        throughput=100,
        availability=100,
    )

    recovery = make_metrics(
        success_rate=100,
        latency=105,
        throughput=100,
        availability=100,
    )

    result = _calculate_recovery_score(
        baseline,
        recovery,
    )

    assert result["success_score"] == 100
    assert result["latency_score"] == 100
    assert result["throughput_score"] == 100
    assert result["recovery_score"] == 100


# ============================================================
# OVERALL SCORE / SEVERITY
# ============================================================

def test_calculate_resilience_score():

    result = _calculate_resilience_score(
        failure_resistance_score=70,
        recovery_score=100,
    )

    assert result == 79


def test_determine_severity():

    assert _determine_severity(95) == "low"
    assert _determine_severity(80) == "moderate"
    assert _determine_severity(60) == "high"
    assert _determine_severity(40) == "critical"


# ============================================================
# DEGRADATION
# ============================================================

def test_calculate_degradation():

    baseline = make_metrics(
        success_rate=100,
        latency=100,
        throughput=100,
        availability=100,
    )

    failure = make_metrics(
        success_rate=80,
        latency=200,
        throughput=70,
        availability=80,
    )

    result = _calculate_degradation(
        baseline,
        failure,
    )

    assert result["success_rate_drop_percentage_points"] == 20
    assert result["error_rate_increase_percentage_points"] == 20
    assert result["latency_increase_percentage"] == 100
    assert result["throughput_decrease_percentage"] == 30
    assert result["availability_drop_percentage_points"] == 20


# ============================================================
# RECOVERY DETECTION
# ============================================================

def test_determine_recovery_success():

    baseline = make_metrics(
        success_rate=100,
        latency=100,
        throughput=100,
        availability=100,
    )

    recovery = make_metrics(
        success_rate=100,
        latency=105,
        throughput=100,
        availability=100,
    )

    result = _determine_recovery(
        baseline,
        recovery,
    )

    assert result["recovered"] is True
    assert result["success_rate_recovered"] is True
    assert result["latency_recovered"] is True
    assert result["throughput_recovered"] is True


def test_determine_recovery_failure():

    baseline = make_metrics(
        success_rate=100,
        latency=100,
        throughput=100,
        availability=100,
    )

    recovery = make_metrics(
        success_rate=70,
        latency=300,
        throughput=50,
        availability=70,
    )

    result = _determine_recovery(
        baseline,
        recovery,
    )

    assert result["recovered"] is False
    assert result["success_rate_recovered"] is False
    assert result["latency_recovered"] is False
    assert result["throughput_recovered"] is False


# ============================================================
# RECOVERY TIME
# ============================================================

def test_calculate_recovery_time():

    failure_execution = {}
    recovery_execution = {}

    assert (
        _calculate_recovery_time(
            failure_execution,
            recovery_execution,
            measured_recovery_time=5.5,
        )
        == 5.5
    )

    assert (
        _calculate_recovery_time(
            failure_execution,
            recovery_execution,
            measured_recovery_time=None,
        )
        is None
    )

    assert (
        _calculate_recovery_time(
            failure_execution,
            recovery_execution,
            measured_recovery_time=-1,
        )
        is None
    )


# ============================================================
# SERVICE IMPACT
# ============================================================

def test_calculate_service_impact():

    service_id = str(uuid.uuid4())

    baseline_services = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "total_requests": 100,
            "successful_requests": 100,
            "average_latency_ms": 100,
        }
    ]

    failure_services = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "total_requests": 100,
            "successful_requests": 80,
            "average_latency_ms": 600,
        }
    ]

    recovery_services = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "total_requests": 100,
            "successful_requests": 100,
            "average_latency_ms": 105,
        }
    ]

    result = _calculate_service_impact(
        baseline_services,
        failure_services,
        recovery_services,
    )

    assert len(result) == 1

    service = result[0]

    assert service["service_id"] == service_id
    assert service["service_name"] == "Target Service"

    assert service["baseline_success_rate"] == 100
    assert service["failure_success_rate"] == 80
    assert service["recovery_success_rate"] == 100

    assert service["success_rate_drop_percentage_points"] == 20
    assert service["latency_increase_percentage"] == 500

    assert service["impact"] == "high"
    assert service["recovered"] is True


# ============================================================
# FAILURE IMPACT
# ============================================================

def test_calculate_failure_impact():

    service_id = str(uuid.uuid4())
    failure_id = str(uuid.uuid4())

    service_impacts = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "impact": "high",
        }
    ]

    failures = [
        {
            "id": failure_id,
            "service_id": service_id,
            "failure_type": "cpu_stress",
            "duration_seconds": 30,
            "parameters": {
                "cpu_percent": 90
            },
        }
    ]

    result = _calculate_failure_impact(
        failures,
        service_impacts,
    )

    assert len(result) == 1

    failure = result[0]

    assert failure["failure_id"] == failure_id
    assert failure["service_id"] == service_id
    assert failure["failure_type"] == "cpu_stress"
    assert failure["duration_seconds"] == 30
    assert failure["impact"] == "high"


# ============================================================
# RECOMMENDATIONS
# ============================================================

def test_generate_recommendations():

    degradation = {
        "success_rate_drop_percentage_points": 20,
        "error_rate_increase_percentage_points": 20,
        "latency_increase_percentage": 100,
        "throughput_decrease_percentage": 30,
        "availability_drop_percentage_points": 20,
    }

    recovery = {
        "recovered": False,
    }

    service_impacts = [
        {
            "impact": "high"
        }
    ]

    result = _generate_recommendations(
        degradation,
        recovery,
        service_impacts,
    )

    assert len(result) == 6

    assert any(
        "fault handling" in recommendation
        for recommendation in result
    )

    assert any(
        "latency bottlenecks" in recommendation
        for recommendation in result
    )

    assert any(
        "concurrency handling" in recommendation
        for recommendation in result
    )

    assert any(
        "redundancy" in recommendation
        for recommendation in result
    )

    assert any(
        "recovery mechanisms" in recommendation
        for recommendation in result
    )

    assert any(
        "highly affected services" in recommendation
        for recommendation in result
    )


# ============================================================
# EXTRACT RESULT
# ============================================================

def test_extract_result():

    result = make_result(
        total_requests=100,
        successful_requests=90,
        failed_requests=10,
        success_rate=90,
        error_rate=10,
        average_latency_ms=120,
        p50_latency_ms=100,
        p95_latency_ms=180,
        p99_latency_ms=250,
        throughput=80,
        availability=90,
    )

    extracted = _extract_result(result)

    assert extracted == {
        "total_requests": 100,
        "successful_requests": 90,
        "failed_requests": 10,
        "success_rate": 90,
        "error_rate": 10,
        "average_latency_ms": 120,
        "p50_latency_ms": 100,
        "p95_latency_ms": 180,
        "p99_latency_ms": 250,
        "throughput": 80,
        "availability": 90,
    }


# ============================================================
# COMPLETE ANALYSIS
# ============================================================

def test_analyze_experiment():

    experiment_id = str(uuid.uuid4())
    service_id = str(uuid.uuid4())
    failure_id = str(uuid.uuid4())

    baseline_result = make_result(
        success_rate=100,
        error_rate=0,
        average_latency_ms=100,
        throughput=100,
        availability=100,
    )

    failure_result = make_result(
        success_rate=80,
        error_rate=20,
        average_latency_ms=200,
        throughput=70,
        availability=80,
    )

    recovery_result = make_result(
        success_rate=100,
        error_rate=0,
        average_latency_ms=105,
        throughput=100,
        availability=100,
    )

    baseline_services = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "total_requests": 100,
            "successful_requests": 100,
            "average_latency_ms": 100,
        }
    ]

    failure_services = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "total_requests": 100,
            "successful_requests": 80,
            "average_latency_ms": 600,
        }
    ]

    recovery_services = [
        {
            "service_id": service_id,
            "service_name": "Target Service",
            "total_requests": 100,
            "successful_requests": 100,
            "average_latency_ms": 105,
        }
    ]

    experiment_result = {
        "experiment_id": experiment_id,
        "executions": [
            {
                "run_type": "baseline",
                "result": baseline_result,
                "services": baseline_services,
            },
            {
                "run_type": "failure",
                "result": failure_result,
                "services": failure_services,
            },
            {
                "run_type": "recovery",
                "result": recovery_result,
                "services": recovery_services,
            },
        ],
    }

    failures = [
        {
            "id": failure_id,
            "service_id": service_id,
            "failure_type": "cpu_stress",
            "duration_seconds": 30,
            "parameters": {
                "cpu_percent": 90
            },
        }
    ]

    result = analyze_experiment(
        experiment_result,
        failures=failures,
        recovery_time_seconds=5.5,
    )

    assert result["experiment_id"] == experiment_id

    assert result["overall"]["resilience_score"] == 76.9
    assert result["overall"]["severity"] == "moderate"

    assert (
        result["overall"]["failure_resistance_score"]
        == 67
    )

    assert (
        result["overall"]["recovery_score"]
        == 100
    )

    assert (
        result["degradation"]
        ["success_rate_drop_percentage_points"]
        == 20
    )

    assert (
        result["degradation"]
        ["latency_increase_percentage"]
        == 100
    )

    assert (
        result["degradation"]
        ["throughput_decrease_percentage"]
        == 30
    )

    assert (
        result["recovery"]["recovered"]
        is True
    )

    assert (
        result["recovery"]
        ["recovery_time_seconds"]
        == 5.5
    )

    assert (
        result["recovery"]
        ["recovery_time_measured"]
        is True
    )

    assert len(result["services"]) == 1
    assert result["services"][0]["impact"] == "high"

    assert len(result["failures"]) == 1
    assert result["failures"][0]["impact"] == "high"

    assert len(result["recommendations"]) > 0


# ============================================================
# VALIDATION / ERROR CASES
# ============================================================

def test_analyze_experiment_requires_three_executions():

    experiment_result = {
        "experiment_id": str(uuid.uuid4()),
        "executions": [],
    }

    with pytest.raises(ValueError) as exc_info:
        analyze_experiment(experiment_result)

    assert (
        str(exc_info.value)
        == "Analysis requires baseline, failure, and recovery executions."
    )


def test_analyze_experiment_requires_all_execution_types():

    experiment_result = {
        "experiment_id": str(uuid.uuid4()),
        "executions": [
            {
                "run_type": "baseline",
                "result": make_result(),
                "services": [],
            },
            {
                "run_type": "failure",
                "result": make_result(),
                "services": [],
            },
            {
                "run_type": "something_else",
                "result": make_result(),
                "services": [],
            },
        ],
    }

    with pytest.raises(ValueError) as exc_info:
        analyze_experiment(experiment_result)

    assert "Missing execution types" in str(
        exc_info.value
    )

def test_hypothesis_not_defined():
    result = _evaluate_hypothesis(
        None,
        {
            "success_rate": 97.0,
            "p95_latency_ms": 1500.0,
            "availability": 98.0,
        },
    )

    assert result["defined"] is False
    assert result["passed"] is None
    assert result["checks"] == []


def test_hypothesis_passes():
    result = _evaluate_hypothesis(
        {
            "min_success_rate": 95,
            "max_p95_latency_ms": 2000,
            "min_availability": 95,
        },
        {
            "success_rate": 97.0,
            "p95_latency_ms": 1500.0,
            "availability": 98.0,
        },
    )

    assert result["defined"] is True
    assert result["passed"] is True
    assert len(result["checks"]) == 3
    assert all(check["passed"] for check in result["checks"])


def test_hypothesis_fails():
    result = _evaluate_hypothesis(
        {
            "min_success_rate": 95,
            "max_p95_latency_ms": 2000,
        },
        {
            "success_rate": 90.0,
            "p95_latency_ms": 1500.0,
            "availability": 98.0,
        },
    )

    assert result["defined"] is True
    assert result["passed"] is False
    assert result["checks"][0]["passed"] is False
    assert result["checks"][1]["passed"] is True


def test_hypothesis_partial_criteria():
    result = _evaluate_hypothesis(
        {
            "min_success_rate": 95,
        },
        {
            "success_rate": 97.0,
            "p95_latency_ms": 3000.0,
            "availability": 90.0,
        },
    )

    assert result["defined"] is True
    assert result["passed"] is True
    assert len(result["checks"]) == 1