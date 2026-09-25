"""Unit coverage for the unverified-guidance contract on the served session-context block.

Session guidance is derived from what a user asserted earlier in the session; nothing in
the pipeline verifies it against the corpus. Served without that framing, the answering
model treats an entry as an established fact, cites it as a source it never retrieved, and
declares a correct ingested document outdated (gh #4296). The block therefore carries the
precedence and provenance rules that keep stored guidance from overruling retrieval.

These tests pin the rendered text (deterministic, no LLM) and the turn-analysis prompt
contract that stops an affirmative/keyword message from being stored as a durable fact.
"""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from cognee.infrastructure.session.session_context_builder import (
    UNVERIFIED_GUIDANCE_NOTICE,
    build_active_context_block,
    render_preference_block,
)
from cognee.infrastructure.session.session_context_models import (
    SessionContextEntry,
    normalize_content,
)


def _entry(section, content, **kwargs):
    return SessionContextEntry(
        id=kwargs.pop("id", str(uuid4())),
        section=section,
        content=content,
        normalized_content=normalize_content(content),
        created_at=kwargs.pop("created_at", datetime.now(timezone.utc).isoformat()),
        **kwargs,
    )


class FakeSessionManager:
    """In-memory stand-in for SessionManager's context read surface."""

    def __init__(self, entries=None):
        self.store = [
            e.model_dump() if isinstance(e, SessionContextEntry) else e for e in (entries or [])
        ]

    async def get_session_context_entries(self, user_id, session_id):
        return list(self.store)

    async def create_session_context_entry(self, user_id, session_id, entry_dump):
        self.store.append(entry_dump)

    async def update_session_context_entry(self, user_id, session_id, entry_id, merge):
        for row in self.store:
            if row.get("id") == entry_id:
                row.update(merge)
                return True
        return False


# --------------------------------------------------------------- served-block contract


@pytest.mark.asyncio
async def test_block_marks_guidance_as_unverified_user_statements():
    sm = FakeSessionManager([_entry("lessons_learned", "Volume migrated to CephFS", id="l1")])

    block, _served = await build_active_context_block(
        session_manager=sm, user_id="u", session_id="s", query="volume"
    )

    assert UNVERIFIED_GUIDANCE_NOTICE in block
    assert "unverified statements the user made earlier in this session" in block
    assert "not facts retrieved from your documents" in block


@pytest.mark.asyncio
async def test_block_makes_retrieved_content_authoritative_on_conflict():
    """A stored entry must not be able to overrule the document it contradicts (gh #4296)."""
    sm = FakeSessionManager([_entry("lessons_learned", "stop-first removed", id="l1")])

    block, _served = await build_active_context_block(
        session_manager=sm, user_id="u", session_id="s", query="stop-first"
    )

    assert "Treat retrieved content as authoritative" in block
    assert "follow the document" in block


@pytest.mark.asyncio
async def test_block_forbids_citing_guidance_as_a_source():
    """Guidance is not retrieval output, so it must never be cited as provenance."""
    sm = FakeSessionManager([_entry("lessons_learned", "PR was merged", id="l1")])

    block, _served = await build_active_context_block(
        session_manager=sm, user_id="u", session_id="s", query="pr"
    )

    assert "Do not cite a guidance item as a source" in block


@pytest.mark.asyncio
async def test_block_forbids_declaring_a_document_outdated_from_guidance_alone():
    """The reported failure: a correct ingested note declared obsolete by session text."""
    sm = FakeSessionManager([_entry("lessons_learned", "Volume migrated to CephFS", id="l1")])

    block, _served = await build_active_context_block(
        session_manager=sm, user_id="u", session_id="s", query="volume"
    )

    assert "do not describe a document as outdated" in block
    assert "on the basis of guidance alone" in block


@pytest.mark.asyncio
async def test_notice_precedes_the_entries_it_governs():
    """The provenance rule has to be read before the entries it constrains."""
    sm = FakeSessionManager([_entry("goals", "Ship the MVP", id="g1")])

    block, _served = await build_active_context_block(
        session_manager=sm, user_id="u", session_id="s", query="anything"
    )

    assert block.index(UNVERIFIED_GUIDANCE_NOTICE) < block.index("Ship the MVP")


@pytest.mark.asyncio
async def test_agent_profile_block_carries_the_same_notice():
    sm = FakeSessionManager(
        [
            _entry(
                "environment_facts",
                "Postgres runs on port 5433",
                id="a1",
                context_profile="agent",
            )
        ]
    )

    block, _served = await build_active_context_block(
        session_manager=sm,
        user_id="u",
        session_id="s",
        query="postgres",
        context_profile="agent",
    )

    assert UNVERIFIED_GUIDANCE_NOTICE in block


def test_preference_only_block_carries_the_same_notice():
    """Preference lines share the one guidance block, so they inherit the same rules."""
    block = render_preference_block(["Keep answers concise."])

    assert UNVERIFIED_GUIDANCE_NOTICE in block
    assert block.startswith("## Active session guidance")


@pytest.mark.asyncio
async def test_existing_ordering_and_titles_are_unchanged():
    """The notice is additive: section headings, ordering, and ids are untouched."""
    entries = [
        _entry("preferences", "Prefer 2 bullets.", id="p-old", created_at="2026-06-10T10:14:22"),
        _entry("preferences", "Prefer 4 bullets.", id="p-new", created_at="2026-06-10T10:19:08"),
    ]
    sm = FakeSessionManager(entries)

    block, served = await build_active_context_block(
        session_manager=sm, user_id="u", session_id="s", query="bullet points"
    )

    assert "## Active session guidance" in block
    assert "### Preferences" in block
    assert "When guidance conflicts, prefer the later item." in block
    assert block.index("[10:14:22] Prefer 2 bullets.") < block.index(
        "[10:19:08] Prefer 4 bullets."
    )
    assert set(served) == {"p-old", "p-new"}


# ------------------------------------------------------- turn-analysis prompt contract


def _turn_analysis_prompt() -> str:
    return (
        Path(__file__).parents[4]
        / "infrastructure"
        / "llm"
        / "prompts"
        / "feedback_detection_system.txt"
    ).read_text()


def test_prompt_forbids_acknowledgement_asserting_the_callers_claims():
    """A gated turn may acknowledge receipt, not ratify the claim as established."""
    prompt = _turn_analysis_prompt()

    assert "must not assert the sender's" in prompt
    assert "claims as established fact" in prompt


def test_prompt_treats_affirmative_keyword_messages_as_not_evidence():
    """The core of gh #4296: a keyword string is a claim, not a durable fact."""
    prompt = _turn_analysis_prompt()

    assert "is not evidence on its own" in prompt
    assert "Do not store a claim the user only stated as a durable fact" in prompt


def test_prompt_keeps_its_existing_signal_sections():
    """The new rules are additive; the analyzer's signal contract is unchanged."""
    prompt = _turn_analysis_prompt()

    assert "## 1. Query to answer" in prompt
    assert "## 2. Candidate session-context updates" in prompt
    assert "## 3. Served context ratings" in prompt
