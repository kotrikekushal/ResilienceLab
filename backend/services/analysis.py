def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(maximum, value),
    )


def _retention_score(
    baseline: float,
    current: float,
) -> float:
    """
    Measures how much of the baseline value was retained.

    Used for metrics where higher is better:
    - success rate
    - throughput
    """

    if baseline <= 0:
        return 100.0 if current >= 0 else 0.0

    return _clamp(
        (current / baseline) * 100
    )


def _latency_score(
    baseline: float,
    current: float,
) -> float:
    """
    Converts latency degradation into a 0-100 score.

    Lower latency is better.

    No degradation:
        100

    Increasing latency:
        score decreases continuously.
    """

    if baseline <= 0:
        return 100.0

    increase_ratio = max(
        0.0,
        (current - baseline) / baseline,
    )

    return _clamp(
        100 / (1 + increase_ratio)
    )


def _recovery_metric_score(
    baseline: float,
    recovery: float,
) -> float:
    """
    Measures how closely recovery returned to baseline
    for metrics where higher is better.
    """

    if baseline <= 0:
        return 100.0 if recovery >= 0 else 0.0

    return _clamp(
        (recovery / baseline) * 100
    )


def _latency_recovery_score(
    baseline: float,
    recovery: float,
) -> float:
    """
    Scores recovery latency.

    <= 5% above baseline = full recovery.

    Above that threshold the score decreases gradually.
    """

    if baseline <= 0:
        return 100.0

    latency_ratio = recovery / baseline

    if latency_ratio <= 1.05:
        return 100.0

    increase_ratio = latency_ratio - 1

    return _clamp(
        100 / (1 + increase_ratio)
    )


def _calculate_failure_resistance(
    baseline: dict,
    failure: dict,
) -> dict:
    """
    Calculates how well the system resisted the injected failure.

    Current weighting:

    Success rate      40%
    Latency           35%
    Throughput        25%

    Availability is intentionally not included separately because
    the current instrumentation derives availability from successful
    requests. Including it would double-count the same signal.
    """

    success_score = _retention_score(
        baseline["success_rate"],
        failure["success_rate"],
    )

    latency_score = _latency_score(
        baseline["average_latency_ms"],
        failure["average_latency_ms"],
    )

    throughput_score = _retention_score(
        baseline["throughput"],
        failure["throughput"],
    )

    failure_resistance = (
        success_score * 0.40
        + latency_score * 0.35
        + throughput_score * 0.25
    )

    return {
        "success_score": round(
            success_score,
            2,
        ),
        "latency_score": round(
            latency_score,
            2,
        ),
        "throughput_score": round(
            throughput_score,
            2,
        ),
        "failure_resistance_score": round(
            failure_resistance,
            2,
        ),
    }


def _calculate_recovery_score(
    baseline: dict,
    recovery: dict,
) -> dict:
    """
    Calculates how completely the system returned toward
    baseline behavior after the failure condition ended.

    Current weighting:

    Success rate      45%
    Latency           35%
    Throughput        20%
    """

    success_score = _recovery_metric_score(
        baseline["success_rate"],
        recovery["success_rate"],
    )

    latency_score = _latency_recovery_score(
        baseline["average_latency_ms"],
        recovery["average_latency_ms"],
    )

    throughput_score = _recovery_metric_score(
        baseline["throughput"],
        recovery["throughput"],
    )

    recovery_score = (
        success_score * 0.45
        + latency_score * 0.35
        + throughput_score * 0.20
    )

    return {
        "success_score": round(
            success_score,
            2,
        ),
        "latency_score": round(
            latency_score,
            2,
        ),
        "throughput_score": round(
            throughput_score,
            2,
        ),
        "recovery_score": round(
            recovery_score,
            2,
        ),
    }


def _calculate_resilience_score(
    failure_resistance_score: float,
    recovery_score: float,
) -> float:
    """
    Overall resilience score.

    Failure resistance = 70%
    Recovery           = 30%
    """

    return round(
        (
            failure_resistance_score * 0.70
            + recovery_score * 0.30
        ),
        2,
    )


def _determine_severity(
    resilience_score: float,
) -> str:
    """
    Overall experiment severity.
    """

    if resilience_score >= 90:
        return "low"

    if resilience_score >= 75:
        return "moderate"

    if resilience_score >= 50:
        return "high"

    return "critical"


def _calculate_degradation(
    baseline: dict,
    failure: dict,
) -> dict:
    """
    Calculates measurable degradation between baseline
    and failure executions.
    """

    success_rate_drop = (
        baseline["success_rate"]
        - failure["success_rate"]
    )

    error_rate_increase = (
        failure["error_rate"]
        - baseline["error_rate"]
    )

    latency_increase_percentage = (
        (
            (
                failure["average_latency_ms"]
                - baseline["average_latency_ms"]
            )
            / baseline["average_latency_ms"]
        )
        * 100
        if baseline["average_latency_ms"] > 0
        else 0.0
    )

    throughput_decrease_percentage = (
        (
            (
                baseline["throughput"]
                - failure["throughput"]
            )
            / baseline["throughput"]
        )
        * 100
        if baseline["throughput"] > 0
        else 0.0
    )

    availability_drop = (
        baseline["availability"]
        - failure["availability"]
    )

    return {
        "success_rate_drop_percentage_points": round(
            max(
                0.0,
                success_rate_drop,
            ),
            2,
        ),
        "error_rate_increase_percentage_points": round(
            max(
                0.0,
                error_rate_increase,
            ),
            2,
        ),
        "latency_increase_percentage": round(
            max(
                0.0,
                latency_increase_percentage,
            ),
            2,
        ),
        "throughput_decrease_percentage": round(
            max(
                0.0,
                throughput_decrease_percentage,
            ),
            2,
        ),
        "availability_drop_percentage_points": round(
            max(
                0.0,
                availability_drop,
            ),
            2,
        ),
    }


def _determine_recovery(
    baseline: dict,
    recovery: dict,
) -> dict:
    """
    Determines whether recovery returned the system
    sufficiently close to baseline.

    Thresholds:

    Success rate  >= 95% of baseline
    Latency       <= 125% of baseline OR baseline + 5 ms
    Throughput    >= 95% of baseline

    The absolute latency floor prevents small normal measurement
    fluctuations from being incorrectly classified as non-recovery.
    """

    success_recovered = (
        recovery["success_rate"]
        >= baseline["success_rate"] * 0.95
    )

    baseline_latency_ms = baseline["average_latency_ms"]
    latency_limit_ms = max(
        baseline_latency_ms * 1.25,
        baseline_latency_ms + 5.0,
    )

    latency_recovered = (
        recovery["average_latency_ms"]
        <= latency_limit_ms
    )

    throughput_recovered = (
        recovery["throughput"]
        >= baseline["throughput"] * 0.95
    )

    recovered = (
        success_recovered
        and latency_recovered
        and throughput_recovered
    )

    return {
        "recovered": recovered,
        "success_rate_recovered": success_recovered,
        "latency_recovered": latency_recovered,
        "throughput_recovered": throughput_recovered,
    }


def _calculate_recovery_time(
    failure_execution: dict,
    recovery_execution: dict,
    measured_recovery_time: float | None = None,
) -> float | None:
    """
    Returns the true recovery time measured by the execution engine.

    The execution engine performs active health probing after the
    failure condition ends and passes the measured recovery time
    into the analysis layer.

    Execution timestamps are intentionally not used as a substitute
    for true recovery time.
    """

    if measured_recovery_time is None:
        return None

    if measured_recovery_time < 0:
        return None

    return float(measured_recovery_time)


def _calculate_service_impact(
    baseline_services: list[dict],
    failure_services: list[dict],
    recovery_services: list[dict],
) -> list[dict]:
    """
    Calculates service-level degradation and recovery.

    Impact classification considers both:

    - request success degradation
    - latency degradation

    Latency is also considered in absolute terms so that a tiny
    baseline does not automatically make a few hundred milliseconds
    appear catastrophic.
    """

    baseline_map = {
        service["service_id"]: service
        for service in baseline_services
    }

    failure_map = {
        service["service_id"]: service
        for service in failure_services
    }

    recovery_map = {
        service["service_id"]: service
        for service in recovery_services
    }

    service_results = []

    for service_id, baseline in baseline_map.items():

        failure = failure_map.get(
            service_id,
            baseline,
        )

        recovery = recovery_map.get(
            service_id,
            baseline,
        )

        baseline_total = baseline[
            "total_requests"
        ]

        failure_total = failure[
            "total_requests"
        ]

        recovery_total = recovery[
            "total_requests"
        ]

        baseline_success_rate = (
            (
                baseline[
                    "successful_requests"
                ]
                / baseline_total
            )
            * 100
            if baseline_total > 0
            else 0.0
        )

        failure_success_rate = (
            (
                failure[
                    "successful_requests"
                ]
                / failure_total
            )
            * 100
            if failure_total > 0
            else 0.0
        )

        recovery_success_rate = (
            (
                recovery[
                    "successful_requests"
                ]
                / recovery_total
            )
            * 100
            if recovery_total > 0
            else 0.0
        )

        success_rate_drop = max(
            0.0,
            baseline_success_rate
            - failure_success_rate,
        )

        baseline_latency = baseline[
            "average_latency_ms"
        ]

        failure_latency = failure[
            "average_latency_ms"
        ]

        recovery_latency = recovery[
            "average_latency_ms"
        ]

        latency_increase = (
            (
                (
                    failure_latency
                    - baseline_latency
                )
                / baseline_latency
            )
            * 100
            if baseline_latency > 0
            else 0.0
        )

        latency_increase = max(
            0.0,
            latency_increase,
        )

        # --------------------------------------------------------
        # SERVICE IMPACT CLASSIFICATION
        # --------------------------------------------------------
        #
        # Success degradation is the strongest signal.
        #
        # Latency degradation is evaluated using both relative
        # increase and absolute failure latency.
        #
        # This prevents a tiny baseline from making a modest
        # absolute latency automatically appear catastrophic.
        # --------------------------------------------------------

        if (
            success_rate_drop > 30
            or (
                latency_increase > 500
                and failure_latency >= 1000
            )
        ):
            impact = "critical"

        elif (
            success_rate_drop > 15
            or latency_increase > 200
            or failure_latency >= 500
        ):
            impact = "high"

        elif (
            success_rate_drop > 5
            or latency_increase > 50
            or failure_latency >= 100
        ):
            impact = "moderate"

        else:
            impact = "low"

        recovery_latency_limit = max(
            baseline_latency * 1.25,
            baseline_latency + 5.0,
        )

        recovered = (
            recovery_success_rate
            >= baseline_success_rate * 0.95
            and recovery_latency
            <= recovery_latency_limit
        )

        service_results.append(
            {
                "service_id": service_id,

                "service_name": baseline[
                    "service_name"
                ],

                "baseline_success_rate": round(
                    baseline_success_rate,
                    2,
                ),

                "failure_success_rate": round(
                    failure_success_rate,
                    2,
                ),

                "recovery_success_rate": round(
                    recovery_success_rate,
                    2,
                ),

                "baseline_latency_ms": round(
                    baseline_latency,
                    2,
                ),

                "failure_latency_ms": round(
                    failure_latency,
                    2,
                ),

                "recovery_latency_ms": round(
                    recovery_latency,
                    2,
                ),

                "success_rate_drop_percentage_points": round(
                    success_rate_drop,
                    2,
                ),

                "latency_increase_percentage": round(
                    latency_increase,
                    2,
                ),

                "recovered": recovered,

                "impact": impact,
            }
        )

    return service_results


def _calculate_failure_impact(
    failures: list[dict],
    service_impacts: list[dict],
) -> list[dict]:
    """
    Associates each configured failure with the measured
    impact on its target service.
    """

    service_map = {
        service["service_id"]: service
        for service in service_impacts
    }

    results = []

    for failure in failures:

        service_id = failure.get(
            "service_id"
        )

        service = service_map.get(
            service_id
        )

        results.append(
            {
                "failure_id": failure.get(
                    "id"
                ),

                "service_id": service_id,

                "failure_type": failure.get(
                    "failure_type"
                ),

                "duration_seconds": failure.get(
                    "duration_seconds"
                ),

                "parameters": failure.get(
                    "parameters"
                ),

                "impact": (
                    service["impact"]
                    if service
                    else "unknown"
                ),
            }
        )

    return results


def _generate_recommendations(
    degradation: dict,
    recovery: dict,
    service_impacts: list[dict],
) -> list[str]:
    """
    Generates recommendations based on measured degradation
    and recovery behavior.
    """

    recommendations = []

    # ------------------------------------------------------------
    # AVAILABILITY / SUCCESS
    # ------------------------------------------------------------

    if (
        degradation[
            "success_rate_drop_percentage_points"
        ] > 10
    ):
        recommendations.append(
            "Improve fault handling, fallback "
            "mechanisms, graceful degradation, "
            "and error isolation."
        )

    # ------------------------------------------------------------
    # LATENCY
    # ------------------------------------------------------------

    if (
        degradation[
            "latency_increase_percentage"
        ] > 50
    ):
        recommendations.append(
            "Investigate latency bottlenecks, "
            "dependency delays, timeout handling, "
            "queueing, and resource contention."
        )

    # ------------------------------------------------------------
    # THROUGHPUT
    # ------------------------------------------------------------

    if (
        degradation[
            "throughput_decrease_percentage"
        ] > 20
    ):
        recommendations.append(
            "Improve concurrency handling, "
            "capacity planning, backpressure, "
            "and resource utilization."
        )

    # ------------------------------------------------------------
    # AVAILABILITY
    # ------------------------------------------------------------

    if (
        degradation[
            "availability_drop_percentage_points"
        ] > 10
    ):
        recommendations.append(
            "Strengthen redundancy, failover, "
            "health checks, and service isolation."
        )

    # ------------------------------------------------------------
    # RECOVERY
    # ------------------------------------------------------------

    if not recovery["recovered"]:
        recommendations.append(
            "Improve recovery mechanisms because "
            "the system did not return within the "
            "defined recovery thresholds."
        )

    # ------------------------------------------------------------
    # SERVICE IMPACT
    # ------------------------------------------------------------

    critical_services = [
        service
        for service in service_impacts
        if service["impact"] == "critical"
    ]

    high_services = [
        service
        for service in service_impacts
        if service["impact"] == "high"
    ]

    if critical_services:
        recommendations.append(
            "Prioritize critically affected services "
            "and strengthen their fault isolation, "
            "dependency resilience, and recovery paths."
        )

    elif high_services:
        recommendations.append(
            "Prioritize highly affected services "
            "and investigate their latency, "
            "dependency behavior, and fault handling."
        )

    # ------------------------------------------------------------
    # NO MAJOR ISSUES
    # ------------------------------------------------------------

    if not recommendations:
        recommendations.append(
            "The system maintained strong performance "
            "and recovered within the defined resilience "
            "thresholds under the tested failure condition."
        )

    return recommendations


def _extract_result(result) -> dict:
    """
    Converts a ResultDB object into the normalized dictionary
    used by the analysis engine.
    """

    return {
        "total_requests": result.total_requests,
        "successful_requests": result.successful_requests,
        "failed_requests": result.failed_requests,
        "success_rate": result.success_rate,
        "error_rate": result.error_rate,
        "average_latency_ms": result.average_latency_ms,
        "p50_latency_ms": result.p50_latency_ms,
        "p95_latency_ms": result.p95_latency_ms,
        "p99_latency_ms": result.p99_latency_ms,
        "throughput": result.throughput,
        "availability": result.availability,
    }


def analyze_experiment(
    experiment_result: dict,
    failures: list[dict] | None = None,
    recovery_time_seconds: float | None = None,
) -> dict:
    """
    Performs the complete resilience analysis.

    Required executions:

    1. baseline
    2. failure
    3. recovery

    The analysis compares:

        baseline → failure
        baseline → recovery

    and produces:

        - overall resilience score
        - failure resistance score
        - recovery score
        - degradation metrics
        - recovery status
        - service-level impact
        - failure-level impact
        - recommendations
    """

    executions = experiment_result.get(
        "executions",
        [],
    )

    if len(executions) < 3:
        raise ValueError(
            "Analysis requires baseline, "
            "failure, and recovery executions."
        )

    execution_map = {
        execution["run_type"]: execution
        for execution in executions
    }

    required_types = {
        "baseline",
        "failure",
        "recovery",
    }

    missing_types = (
        required_types
        - set(execution_map.keys())
    )

    if missing_types:
        raise ValueError(
            "Missing execution types: "
            + ", ".join(
                sorted(missing_types)
            )
        )

    baseline_execution = execution_map[
        "baseline"
    ]

    failure_execution = execution_map[
        "failure"
    ]

    recovery_execution = execution_map[
        "recovery"
    ]

    # ------------------------------------------------------------
    # EXTRACT RESULTS
    # ------------------------------------------------------------

    baseline = _extract_result(
        baseline_execution["result"]
    )

    failure = _extract_result(
        failure_execution["result"]
    )

    recovery = _extract_result(
        recovery_execution["result"]
    )

    # ------------------------------------------------------------
    # DEGRADATION
    # ------------------------------------------------------------

    degradation = _calculate_degradation(
        baseline,
        failure,
    )

    # ------------------------------------------------------------
    # FAILURE RESISTANCE
    # ------------------------------------------------------------

    failure_scores = _calculate_failure_resistance(
        baseline,
        failure,
    )

    # ------------------------------------------------------------
    # RECOVERY SCORE
    # ------------------------------------------------------------

    recovery_scores = _calculate_recovery_score(
        baseline,
        recovery,
    )

    # ------------------------------------------------------------
    # OVERALL RESILIENCE
    # ------------------------------------------------------------

    resilience_score = _calculate_resilience_score(
        failure_scores[
            "failure_resistance_score"
        ],
        recovery_scores[
            "recovery_score"
        ],
    )

    severity = _determine_severity(
        resilience_score
    )

    # ------------------------------------------------------------
    # RECOVERY STATUS
    # ------------------------------------------------------------

    recovery_status = _determine_recovery(
        baseline,
        recovery,
    )

    # ------------------------------------------------------------
    # TRUE RECOVERY TIME
    # ------------------------------------------------------------
    #
    # Not available with current instrumentation.
    # Do not report execution gap as MTTR.
    # ------------------------------------------------------------

    recovery_time = _calculate_recovery_time(
        failure_execution,
        recovery_execution,
        measured_recovery_time=recovery_time_seconds,
    )

    # ------------------------------------------------------------
    # SERVICE IMPACT
    # ------------------------------------------------------------

    service_impacts = _calculate_service_impact(
        baseline_execution.get(
            "services",
            [],
        ),
        failure_execution.get(
            "services",
            [],
        ),
        recovery_execution.get(
            "services",
            [],
        ),
    )

    # ------------------------------------------------------------
    # FAILURE IMPACT
    # ------------------------------------------------------------

    failure_impacts = _calculate_failure_impact(
        failures or [],
        service_impacts,
    )

    # ------------------------------------------------------------
    # RECOMMENDATIONS
    # ------------------------------------------------------------

    recommendations = _generate_recommendations(
        degradation,
        recovery_status,
        service_impacts,
    )

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------

    if severity == "low":

        summary = (
            "The system demonstrated strong resilience "
            "under the tested failure conditions with "
            "limited performance degradation and successful "
            "recovery."
        )

    elif severity == "moderate":

        summary = (
            "The system remained generally resilient but "
            "experienced measurable degradation under "
            "failure conditions."
        )

    elif severity == "high":

        summary = (
            "The system experienced significant performance "
            "degradation under failure conditions and "
            "requires resilience improvements."
        )

    else:

        summary = (
            "The system experienced severe resilience "
            "degradation and requires immediate attention."
        )

    # ------------------------------------------------------------
    # FINAL ANALYSIS RESULT
    # ------------------------------------------------------------

    return {
        "experiment_id": experiment_result[
            "experiment_id"
        ],

        "overall": {
            "resilience_score": resilience_score,

            "severity": severity,

            "summary": summary,

            "failure_resistance_score": (
                failure_scores[
                    "failure_resistance_score"
                ]
            ),

            "recovery_score": (
                recovery_scores[
                    "recovery_score"
                ]
            ),
        },

        "baseline": baseline,

        "failure": failure,

        "degradation": degradation,

        "recovery": {
            **recovery,

            "recovery_time_seconds": (
                round(
                    recovery_time,
                    3,
                )
                if recovery_time is not None
                else None
            ),

            "recovery_time_measured": (
                recovery_time is not None
            ),

            **recovery_status,
        },

        "score_breakdown": {
            "failure_resistance": failure_scores,
            "recovery": recovery_scores,
        },

        "services": service_impacts,

        "failures": failure_impacts,

        "recommendations": recommendations,
    }