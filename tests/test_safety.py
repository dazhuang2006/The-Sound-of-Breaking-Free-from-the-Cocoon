"""医疗安全规则测试：规则层必须能独立于 LLM 兜底。"""

from __future__ import annotations

from app.services.safety import (
    CAUTION_BANNER,
    DISCLAIMER,
    assess_input,
    ensure_disclaimer,
    review_output,
)


def test_emergency_detected():
    verdict = assess_input("孩子刚才抽搐了，现在叫不醒")
    assert verdict.level == "emergency"
    assert verdict.blocked is True
    assert "120" in verdict.message


def test_diagnosis_redirect():
    verdict = assess_input("我孩子是不是自闭症？")
    assert verdict.level == "redirect"
    assert "diagnosis" in verdict.categories
    assert "诊断" in verdict.message


def test_medication_redirect():
    verdict = assess_input("可以给孩子吃利他林吗，剂量多少")
    assert verdict.level == "redirect"
    assert "medication" in verdict.categories
    assert "用药" in verdict.message


def test_unverified_therapy_redirect():
    verdict = assess_input("听说干细胞治疗对自闭症有效，要不要试试")
    assert verdict.level == "redirect"
    assert "unverified_therapy" in verdict.categories


def test_self_injury_is_caution_not_block():
    verdict = assess_input("孩子最近总打自己的头，我该怎么办")
    assert verdict.level == "caution"
    assert verdict.blocked is False
    assert verdict.needs_caution is True
    assert "self_injury_behavior" in verdict.categories


def test_normal_question_passes():
    verdict = assess_input("孩子晚上不肯睡觉，有什么居家办法")
    assert verdict.level == "normal"
    assert verdict.blocked is False


def test_output_review_removes_dosage_and_guarantee():
    text = (
        "孩子就是自闭症。建议服用利他林 10mg，保证三个月恢复正常。"
        "你可以先固定睡前流程，观察一周。"
    )
    review = review_output(text)
    assert review.passed is False
    assert review.sanitized is True
    assert "10mg" not in review.text
    assert "保证" not in review.text
    assert DISCLAIMER in review.text
    assert "睡前流程" in review.text


def test_output_review_keeps_safe_content():
    review = review_output("可以先记录一周的睡眠时间，再和医生讨论。")
    assert review.passed is True
    assert review.text.endswith(DISCLAIMER)


def test_disclaimer_is_idempotent():
    once = ensure_disclaimer("建议保持固定作息。")
    twice = ensure_disclaimer(once)
    assert once == twice


def test_empty_output_falls_back_to_safe_text():
    review = review_output("")
    assert review.violations
    assert "抱歉" in review.text


def test_caution_banner_constant():
    assert "自伤" in CAUTION_BANNER
