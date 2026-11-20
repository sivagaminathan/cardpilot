"""PostgreSQL integration and period-math tests for T33 benefit endpoints (AC-11)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import close_engine, get_session_maker
from app.models import BenefitUsage
from app.seeds.loader import seed_all
from app.services.benefits import get_benefit_period_bounds


@pytest.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncGenerator[None, None]:
    """Dispose the shared asyncpg engine before each test's event loop closes."""
    yield
    await close_engine()


async def _ensure_seeded() -> None:
    await close_engine()
    session_factory = get_session_maker()
    async with session_factory() as session, session.begin():
        await seed_all(session)


@pytest.mark.parametrize(
    (
        "reset_period",
        "target_date",
        "opened_on",
        "expected_start",
        "expected_end",
        "expected_reset",
    ),
    [
        (
            "monthly",
            date(2026, 11, 15),
            None,
            date(2026, 11, 1),
            date(2026, 11, 30),
            date(2026, 12, 1),
        ),
        (
            "quarterly",
            date(2026, 11, 15),
            None,
            date(2026, 10, 1),
            date(2026, 12, 31),
            date(2027, 1, 1),
        ),
        (
            "semiannual",
            date(2026, 6, 30),
            None,
            date(2026, 1, 1),
            date(2026, 6, 30),
            date(2026, 7, 1),
        ),
        (
            "semiannual",
            date(2026, 7, 1),
            None,
            date(2026, 7, 1),
            date(2026, 12, 31),
            date(2027, 1, 1),
        ),
        (
            "calendar_year",
            date(2026, 5, 1),
            None,
            date(2026, 1, 1),
            date(2026, 12, 31),
            date(2027, 1, 1),
        ),
        (
            "card_year",
            date(2026, 7, 31),
            date(2025, 8, 1),
            date(2025, 8, 1),
            date(2026, 7, 31),
            date(2026, 8, 1),
        ),
        (
            "card_year",
            date(2026, 8, 1),
            date(2025, 8, 1),
            date(2026, 8, 1),
            date(2027, 7, 31),
            date(2027, 8, 1),
        ),
        # Leap-year opening (2024-02-29) clamps to Feb 28 in non-leap years, Feb 29 in leap years
        (
            "card_year",
            date(2026, 3, 1),
            date(2024, 2, 29),
            date(2026, 2, 28),
            date(2027, 2, 27),
            date(2027, 2, 28),
        ),
        (
            "card_year",
            date(2028, 2, 29),
            date(2024, 2, 29),
            date(2028, 2, 29),
            date(2029, 2, 27),
            date(2029, 2, 28),
        ),
    ],
)
def test_benefit_period_bounds_all_supported_periods(
    reset_period: str,
    target_date: date,
    opened_on: date | None,
    expected_start: date,
    expected_end: date,
    expected_reset: date,
) -> None:
    """All five reset_period types compute exact inclusive bounds and next reset dates."""
    bounds = get_benefit_period_bounds(reset_period, target_date, opened_on=opened_on)
    assert bounds.start_date == expected_start
    assert bounds.end_date == expected_end
    assert bounds.next_reset_date == expected_reset


def test_benefit_period_bounds_rejects_unsupported_period() -> None:
    """Unsupported reset_period values raise ValueError instead of silent fallback."""
    with pytest.raises(ValueError, match="Unsupported benefit reset_period"):
        get_benefit_period_bounds("weekly", date(2026, 11, 15))


@pytest.mark.asyncio
async def test_ac11_monthly_credit_boundaries_overuse_and_perk(
    async_client: AsyncClient,
) -> None:
    """AC-11: monthly credit partial/full/overuse, boundary inclusion, and perk status."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    try:
        # Before effective_from (2026-01-01), no benefits are active
        early = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2025-12-31"},
            )
        ).json()
        assert early == []

        benefits = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2026-11-15"},
            )
        ).json()
        dining_credit = next(b for b in benefits if b["name"] == "Monthly Dining Credit")
        perk = next(b for b in benefits if b["name"] == "Priority Boarding Perk")

        assert dining_credit["status"] == "unused"
        assert dining_credit["used_cents"] == 0
        assert dining_credit["remaining_cents"] == 1500
        assert dining_credit["next_reset_date"] == "2026-12-01"
        assert perk["used_cents"] is None
        assert perk["remaining_cents"] is None
        assert perk["over_used_cents"] is None
        assert perk["status"] == "unused"

        # Log usages outside period (2026-10-31 and 2026-12-01) and inside on boundaries
        for used_on, cents in [
            ("2026-10-31", 500),
            ("2026-12-01", 500),
            ("2026-11-01", 400),
            ("2026-11-30", 600),
        ]:
            res = await async_client.post(
                f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
                json={
                    "profile_card_id": dining_credit["profile_card_id"],
                    "amount_cents": cents,
                    "used_on": used_on,
                    "note": f"Usage {used_on}",
                },
            )
            assert res.status_code == 201

        after_partial = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2026-11-15"},
            )
        ).json()
        dc_partial = next(b for b in after_partial if b["name"] == "Monthly Dining Credit")
        assert dc_partial["used_cents"] == 1000
        assert dc_partial["remaining_cents"] == 500
        assert dc_partial["is_over_used"] is False
        assert dc_partial["status"] == "partially_used"
        assert dc_partial["usage_count"] == 2
        assert dc_partial["next_reset_date"] == "2026-12-01"

        # Log $5 more -> fully used ($15 / $15)
        full_res = await async_client.post(
            f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
            json={
                "profile_card_id": dining_credit["profile_card_id"],
                "amount_cents": 500,
                "used_on": "2026-11-15",
            },
        )
        assert full_res.status_code == 201
        dc_full = next(
            b
            for b in (
                await async_client.get(
                    "/api/v1/profiles/maya/benefits",
                    params={"as_of_date": "2026-11-15"},
                )
            ).json()
            if b["name"] == "Monthly Dining Credit"
        )
        assert dc_full["used_cents"] == 1500
        assert dc_full["remaining_cents"] == 0
        assert dc_full["is_over_used"] is False
        assert dc_full["status"] == "used"

        # Log $3 more -> over-used ($18 / $15), flagged accurately without inventing a rejection
        over_res = await async_client.post(
            f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
            json={
                "profile_card_id": dining_credit["profile_card_id"],
                "amount_cents": 300,
                "used_on": "2026-11-20",
            },
        )
        assert over_res.status_code == 201
        dc_over = next(
            b
            for b in (
                await async_client.get(
                    "/api/v1/profiles/maya/benefits",
                    params={"as_of_date": "2026-11-15"},
                )
            ).json()
            if b["name"] == "Monthly Dining Credit"
        )
        assert dc_over["used_cents"] == 1800
        assert dc_over["remaining_cents"] == 0
        assert dc_over["over_used_cents"] == 300
        assert dc_over["is_over_used"] is True
        assert dc_over["status"] == "over_used"

        # Log perk usage (null amount_cents) -> status becomes "used", monetary fields stay None
        perk_res = await async_client.post(
            f"/api/v1/profiles/maya/benefits/{perk['benefit_id']}/usages",
            json={
                "profile_card_id": perk["profile_card_id"],
                "used_on": "2026-11-15",
                "note": "Boarded Zone 1",
            },
        )
        assert perk_res.status_code == 201
        perk_after = next(
            b
            for b in (
                await async_client.get(
                    "/api/v1/profiles/maya/benefits",
                    params={"as_of_date": "2026-11-15"},
                )
            ).json()
            if b["name"] == "Priority Boarding Perk"
        )
        assert perk_after["used_cents"] is None
        assert perk_after["remaining_cents"] is None
        assert perk_after["usage_count"] == 1
        assert perk_after["status"] == "used"
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_card_isolation_quarterly_calendar_semiannual_and_delete(
    async_client: AsyncClient,
) -> None:
    """Separate cards/benefits stay isolated; quarterly/semiannual/calendar_year & DELETE work."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    await async_client.post("/api/v1/profiles/dev/reset")
    try:
        # Add a second Northwind Dining & Travel card to Maya to verify per-card isolation
        maya_cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        dining_card = next(
            c for c in maya_cards if c["card_product"]["name"] == "Northwind Dining & Travel"
        )
        second_card_res = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={
                "card_product_id": dining_card["card_product"]["id"],
                "nickname": "Dining Secondary",
                "opened_on": "2026-01-01",
            },
        )
        assert second_card_res.status_code == 201
        second_card_id = second_card_res.json()["id"]

        maya_benefits = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2026-08-15"},
            )
        ).json()
        dc_card1 = next(
            b
            for b in maya_benefits
            if b["name"] == "Monthly Dining Credit" and b["profile_card_id"] == dining_card["id"]
        )
        bag_allowance = next(
            b for b in maya_benefits if b["name"] == "Semiannual Checked Bag Allowance"
        )
        assert bag_allowance["period_start"] == "2026-07-01"
        assert bag_allowance["period_end"] == "2026-12-31"
        assert bag_allowance["next_reset_date"] == "2027-01-01"

        usage_res = await async_client.post(
            f"/api/v1/profiles/maya/benefits/{dc_card1['benefit_id']}/usages",
            json={
                "profile_card_id": dining_card["id"],
                "amount_cents": 1000,
                "used_on": "2026-08-10",
            },
        )
        assert usage_res.status_code == 201
        usage_id = usage_res.json()["id"]

        updated_maya = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2026-08-15"},
            )
        ).json()
        dc_card2 = next(
            b
            for b in updated_maya
            if b["name"] == "Monthly Dining Credit" and b["profile_card_id"] == second_card_id
        )
        assert dc_card2["used_cents"] == 0
        assert dc_card2["remaining_cents"] == 1500

        # Check Dev's quarterly and calendar_year benefits
        dev_benefits = (
            await async_client.get(
                "/api/v1/profiles/dev/benefits",
                params={"as_of_date": "2026-11-15"},
            )
        ).json()
        streaming = next(b for b in dev_benefits if b["name"] == "Quarterly Streaming Credit")
        annual_travel = next(
            b for b in dev_benefits if b["name"] == "Annual Travel Incidentals Credit"
        )
        assert streaming["period_start"] == "2026-10-01"
        assert streaming["period_end"] == "2026-12-31"
        assert annual_travel["period_start"] == "2026-01-01"
        assert annual_travel["period_end"] == "2026-12-31"

        # Cross-profile or mismatched-benefit DELETE returns 404
        assert (
            await async_client.delete(
                f"/api/v1/profiles/dev/benefits/{dc_card1['benefit_id']}/usages/{usage_id}"
            )
        ).status_code == 404
        assert (
            await async_client.delete(
                f"/api/v1/profiles/maya/benefits/{bag_allowance['benefit_id']}/usages/{usage_id}"
            )
        ).status_code == 404
        assert (
            await async_client.delete(
                f"/api/v1/profiles/maya/benefits/{dc_card1['benefit_id']}/usages/999999"
            )
        ).status_code == 404

        # Valid DELETE returns 204 and resets status
        del_res = await async_client.delete(
            f"/api/v1/profiles/maya/benefits/{dc_card1['benefit_id']}/usages/{usage_id}"
        )
        assert del_res.status_code == 204

        after_del = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2026-08-15"},
            )
        ).json()
        dc_after_del = next(
            b
            for b in after_del
            if b["name"] == "Monthly Dining Credit" and b["profile_card_id"] == dining_card["id"]
        )
        assert dc_after_del["used_cents"] == 0
        assert dc_after_del["remaining_cents"] == 1500
        assert dc_after_del["status"] == "unused"
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
        await async_client.post("/api/v1/profiles/dev/reset")


@pytest.mark.asyncio
async def test_benefit_usage_validation_and_sensitive_digit_guard(
    async_client: AsyncClient,
) -> None:
    """Validate ownership, product match, amount/date rules, and SafeFreeText guard."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    await async_client.post("/api/v1/profiles/dev/reset")
    try:
        maya_benefits = (
            await async_client.get(
                "/api/v1/profiles/maya/benefits",
                params={"as_of_date": "2026-11-15"},
            )
        ).json()
        dev_cards = (await async_client.get("/api/v1/profiles/dev/cards")).json()
        dining_credit = next(b for b in maya_benefits if b["name"] == "Monthly Dining Credit")
        perk = next(b for b in maya_benefits if b["name"] == "Priority Boarding Perk")

        # Cross-profile card -> 404
        assert (
            await async_client.post(
                f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
                json={
                    "profile_card_id": dev_cards[0]["id"],
                    "amount_cents": 500,
                    "used_on": "2026-11-15",
                },
            )
        ).status_code == 404

        # Benefit/product mismatch -> 422
        assert (
            await async_client.post(
                f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
                json={
                    "profile_card_id": perk["profile_card_id"],
                    "amount_cents": 500,
                    "used_on": "2026-11-15",
                },
            )
        ).status_code == 422

        # Missing credit amount, non-null perk amount, non-positive amount, out-of-range date
        for bad_bid, bad_body in [
            (
                dining_credit["benefit_id"],
                {"profile_card_id": dining_credit["profile_card_id"], "used_on": "2026-11-15"},
            ),
            (
                dining_credit["benefit_id"],
                {
                    "profile_card_id": dining_credit["profile_card_id"],
                    "amount_cents": 0,
                    "used_on": "2026-11-15",
                },
            ),
            (
                dining_credit["benefit_id"],
                {
                    "profile_card_id": dining_credit["profile_card_id"],
                    "amount_cents": 500,
                    "used_on": "2025-12-31",
                },
            ),
            (
                perk["benefit_id"],
                {
                    "profile_card_id": perk["profile_card_id"],
                    "amount_cents": 500,
                    "used_on": "2026-11-15",
                },
            ),
        ]:
            res = await async_client.post(
                f"/api/v1/profiles/maya/benefits/{bad_bid}/usages",
                json=bad_body,
            )
            assert res.status_code == 422
            assert res.headers["content-type"].startswith("application/problem+json")

        # Sensitive 13-19 digit sequence in note -> 422, no echo, zero rows persisted
        session_factory = get_session_maker()
        async with session_factory() as session:
            before_count = await session.scalar(select(func.count(BenefitUsage.id)))

        secret_note = "Card 4111 1111 1111 1111"
        sec_res = await async_client.post(
            f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
            json={
                "profile_card_id": dining_credit["profile_card_id"],
                "amount_cents": 500,
                "used_on": "2026-11-15",
                "note": secret_note,
            },
        )
        assert sec_res.status_code == 422
        assert sec_res.headers["content-type"].startswith("application/problem+json")
        assert secret_note not in sec_res.text

        async with session_factory() as session:
            after_count = await session.scalar(select(func.count(BenefitUsage.id)))
            assert after_count == before_count

        # 12-digit and 20-digit boundaries allowed
        for safe_note in ("Ref 1234 5678 9012", "Track 1234 5678-9012 3456-7890"):
            ok_res = await async_client.post(
                f"/api/v1/profiles/maya/benefits/{dining_credit['benefit_id']}/usages",
                json={
                    "profile_card_id": dining_credit["profile_card_id"],
                    "amount_cents": 200,
                    "used_on": "2026-11-15",
                    "note": safe_note,
                },
            )
            assert ok_res.status_code == 201
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
        await async_client.post("/api/v1/profiles/dev/reset")
