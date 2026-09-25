"""Unit coverage for the unverified-claim receipt on gated session turns (gh #4296).

A recall phrased as an affirmative statement or a run of keywords asserts its content
instead of asking about it. Gating such a turn returned an acknowledgement that restated
-- and could harden -- the assertion, and that text is stored verbatim as the QA answer and
replayed into later turns as retrieval guidance, so an unverified claim became a durable
fact. These tests pin the receipt substitution, and just as importantly the neighbouring
cases that must keep the model acknowledgement.
"""

from cognee.infrastructure.session.feedback_models import SessionTurnAnalysis
from cognee.infrastructure.session.session_turn import (
    UNVERIFIED_CLAIM_RECEIPT,
    acknowledgement_for_turn,
    is_unverified_claim_message,
    should_answer_turn,
)

# Verbatim recall phrasings from gh #4296, reproduced there on 3/3 attempts.
KEYWORD_QUERY = "PR 67157 slash-command part watch 44063 Desktop delivered"
AFFIRMATIVE_QUERY = (
    "cognee-poc_postgres volume migrated to CephFS 3 replicas validated in production"
)
VM_KEYWORD_QUERY = "VM 110 detail 6 vCPU 24 GB 250 GB CephRBD snapshot off"
PROSE_CLAIM_QUERY = "volume migrated to CephFS replicas validated in production"

# The model hardened "added to the watch list" into "merged", a word present neither in
# the query nor in any ingested document (gh #4296).
HARDENED_ACKNOWLEDGEMENT = "Noted: PR 67157 merged, PR 44063 added to the watch list."


def test_gated_keyword_query_returns_a_receipt_not_the_assertion():
    assert is_unverified_claim_message(KEYWORD_QUERY) is True
    assert (
        acknowledgement_for_turn(HARDENED_ACKNOWLEDGEMENT, user_message=KEYWORD_QUERY)
        == UNVERIFIED_CLAIM_RECEIPT
    )


def test_gated_affirmative_query_returns_a_receipt():
    assert is_unverified_claim_message(AFFIRMATIVE_QUERY) is True
    assert (
        acknowledgement_for_turn("Duly noted.", user_message=AFFIRMATIVE_QUERY)
        == UNVERIFIED_CLAIM_RECEIPT
    )


def test_gated_vm_keyword_query_returns_a_receipt():
    assert is_unverified_claim_message(VM_KEYWORD_QUERY) is True


def test_prose_claim_without_identifiers_is_still_a_claim():
    assert is_unverified_claim_message(PROSE_CLAIM_QUERY) is True


def test_receipt_does_not_repeat_the_hardened_claim():
    """The point of the fix: no word the corpus never contained reaches the caller."""

    receipt = acknowledgement_for_turn(
        HARDENED_ACKNOWLEDGEMENT, user_message=KEYWORD_QUERY
    )

    assert "merged" not in receipt.lower()
    assert receipt == UNVERIFIED_CLAIM_RECEIPT


def test_gated_claim_turn_is_still_gated_and_still_recorded():
    """The receipt replaces the wording only; gating and the QA write are unchanged."""
    analysis = SessionTurnAnalysis(response_to_user=HARDENED_ACKNOWLEDGEMENT)

    assert should_answer_turn(analysis, has_previous_qa=True) is False
    receipt = acknowledgement_for_turn(
        analysis.response_to_user, user_message=KEYWORD_QUERY
    )

    assert receipt
    assert receipt == UNVERIFIED_CLAIM_RECEIPT


def test_question_is_not_a_claim_and_keeps_the_model_acknowledgement():
    message = "Is the CephFS migration done?"

    assert is_unverified_claim_message(message) is False
    assert acknowledgement_for_turn("Checking now.", user_message=message) == "Checking now."


def test_unpunctuated_question_is_not_a_claim():
    assert is_unverified_claim_message("what is the state of PR 67157") is False


def test_request_is_not_a_claim():
    assert is_unverified_claim_message("I need the runbook for VM 110") is False


def test_correction_is_not_a_claim():
    message = "No, that is wrong, it was ext4 all along"

    assert is_unverified_claim_message(message) is False
    assert acknowledgement_for_turn("Corrected.", user_message=message) == "Corrected."


def test_recordation_instruction_is_not_a_claim():
    """An explicit instruction to remember something keeps its acknowledgement."""
    message = "remember that the deploy is on Friday"

    assert is_unverified_claim_message(message) is False
    assert acknowledgement_for_turn("Will remember.", user_message=message) == "Will remember."


def test_positive_feedback_is_not_a_claim():
    assert is_unverified_claim_message("Glad it helped!") is False
    assert is_unverified_claim_message("That worked") is False


def test_empty_and_punctuation_only_messages_are_not_claims():
    assert is_unverified_claim_message(None) is False
    assert is_unverified_claim_message("") is False
    assert is_unverified_claim_message("   ") is False
    assert is_unverified_claim_message("...") is False


def test_no_message_supplied_keeps_the_model_acknowledgement():
    """The conservative default: callers that pass no message are unaffected."""
    assert acknowledgement_for_turn(HARDENED_ACKNOWLEDGEMENT) == HARDENED_ACKNOWLEDGEMENT
    assert acknowledgement_for_turn(None) == "Got it."