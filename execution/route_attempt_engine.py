# ==============================
# execution/route_attempt_engine.py
# RailOne Route Attempt Engine
# ==============================

from datetime import datetime

from ledger.db import SessionLocal

from execution.route_attempt_models import (
    RouteAttempt
)


def create_attempt(

    utt_id,
    rtt_id,
    continuity_uid,
    attempt_number,
    route
):

    session = SessionLocal()

    try:

        attempt = RouteAttempt(

            utt_id=utt_id,

            rtt_id=rtt_id,

            continuity_uid=
                continuity_uid,

            attempt_number=
                attempt_number,

            route=route
        )

        session.add(attempt)

        session.commit()

        return attempt

    finally:

        session.close()


def start_attempt(rtt_id):

    session = SessionLocal()

    try:

        attempt = (

            session.query(
                RouteAttempt
            )

            .filter_by(
                rtt_id=rtt_id
            )

            .first()
        )

        if attempt:

            attempt.status = (
                "IN_PROGRESS"
            )

            session.commit()

        return attempt

    finally:

        session.close()


def fail_attempt(

    rtt_id,
    reason,
    provider_response=None
):

    session = SessionLocal()

    try:

        attempt = (

            session.query(
                RouteAttempt
            )

            .filter_by(
                rtt_id=rtt_id
            )

            .first()
        )

        if attempt:

            attempt.status = "FAILED"

            attempt.failure_reason = (
                reason
            )

            attempt.provider_response = (
                provider_response
            )

            attempt.completed_at = (
                datetime.utcnow()
            )

            session.commit()

        return attempt

    finally:

        session.close()


def settle_attempt(

    rtt_id,
    provider,
    provider_reference,
    latency_ms,
    provider_response=None
):

    session = SessionLocal()

    try:

        attempt = (

            session.query(
                RouteAttempt
            )

            .filter_by(
                rtt_id=rtt_id
            )

            .first()
        )

        if attempt:

            attempt.status = (
                "SETTLED"
            )

            attempt.provider = (
                provider
            )

            attempt.provider_reference = (
                provider_reference
            )

            attempt.latency_ms = (
                latency_ms
            )

            attempt.provider_response = (
                provider_response
            )

            attempt.completed_at = (
                datetime.utcnow()
            )

            session.commit()

        return attempt

    finally:

        session.close()