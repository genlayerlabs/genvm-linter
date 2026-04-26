"""Tests for GL-S01, GL-S02, GL-S03 semantic lint rules."""

from genvm_linter.lint.safety import (
    check_eq_strict_mismatch,
    check_vague_prompts,
    check_weak_eq_criteria,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def codes(warnings):
    return [w.code for w in warnings]


# ---------------------------------------------------------------------------
# GL-S01: Vague prompt language
# ---------------------------------------------------------------------------


class TestGL_S01_VaguePromptLanguage:
    def test_flags_vague_ambiguity_marker(self):
        src = """
result = gl.exec_prompt("Is this a fair assessment of the candidate?")
"""
        ws = check_vague_prompts(src)
        assert any(w.code == "GL-S01" for w in ws), "expected GL-S01 for vague 'fair'"

    def test_flags_multiple_ambiguity_markers(self):
        src = """
r = exec_prompt("Evaluate whether the answer is good and appropriate for this context")
"""
        ws = check_vague_prompts(src)
        assert any(w.code == "GL-S01" for w in ws)

    def test_passes_prompt_with_explicit_criteria(self):
        src = """
result = gl.exec_prompt("Return YES if the score > 90, NO if the score <= 90")
"""
        ws = check_vague_prompts(src)
        assert not any(w.code == "GL-S01" for w in ws), "criteria present — should not flag"

    def test_passes_prompt_with_threshold(self):
        src = """
result = gl.exec_prompt("If the price difference is > 5%, return NO, otherwise return YES")
"""
        ws = check_vague_prompts(src)
        assert not any(w.code == "GL-S01" for w in ws)

    def test_edge_variable_prompt_not_flagged(self):
        # Non-literal first arg — cannot inspect at lint time
        src = """
prompt = build_prompt(user_input)
result = gl.exec_prompt(prompt)
"""
        ws = check_vague_prompts(src)
        assert not any(w.code == "GL-S01" for w in ws)

    def test_edge_no_args_not_flagged(self):
        src = """
result = exec_prompt()
"""
        ws = check_vague_prompts(src)
        assert not any(w.code == "GL-S01" for w in ws)

    def test_flags_response_format_missing_in_conditional(self):
        src = """
def check(self):
    result = gl.exec_prompt("Summarise this article")
    if result:
        return True
    return False
"""
        ws = check_vague_prompts(src)
        assert any(w.code == "GL-S01" for w in ws), (
            "result used in if without structured response_format"
        )

    def test_passes_structured_response_format_in_conditional(self):
        src = """
def check(self):
    result = gl.exec_prompt("Is this correct?", response_format=bool)
    if result:
        return True
    return False
"""
        ws = check_vague_prompts(src)
        # response_format is not 'text' and not absent — no GL-S01 from that sub-rule
        assert not any(
            w.code == "GL-S01" and "response_format" in w.msg for w in ws
        )

    def test_passes_response_format_string_yesno_when_no_conditional(self):
        # response_format=text but not used in an if — response_format sub-rule stays quiet
        src = """
def fn(self):
    result = gl.exec_prompt("Describe this image", response_format="text")
    return result
"""
        ws = check_vague_prompts(src)
        assert not any(
            w.code == "GL-S01" and "response_format" in w.msg for w in ws
        )

    def test_fstring_prompt_with_ambiguity_flagged(self):
        src = """
topic = "salary"
r = gl.exec_prompt(f"Is this a suitable {topic} for a senior role?")
"""
        ws = check_vague_prompts(src)
        assert any(w.code == "GL-S01" for w in ws)

    def test_fstring_prompt_with_criteria_not_flagged(self):
        src = """
limit = 100
r = gl.exec_prompt(f"Return YES/NO if the value > {limit}")
"""
        ws = check_vague_prompts(src)
        assert not any(w.code == "GL-S01" for w in ws)


# ---------------------------------------------------------------------------
# GL-S02: Weak eq_principle criteria
# ---------------------------------------------------------------------------


class TestGL_S02_WeakEqCriteria:
    def test_flags_single_word_principle_high(self):
        src = """
gl.eq_principle.prompt_comparative(leader_fn, principle="same")
"""
        ws = check_weak_eq_criteria(src)
        assert any(w.code == "GL-S02" for w in ws)
        assert any("HIGH" in w.msg for w in ws if w.code == "GL-S02")

    def test_flags_short_principle_high(self):
        # 4 words — below 10-word threshold → HIGH
        src = """
eq_principle_prompt_comparative(fn, principle="equivalent output match")
"""
        ws = check_weak_eq_criteria(src)
        assert any(w.code == "GL-S02" for w in ws)
        assert any("HIGH" in w.msg for w in ws if w.code == "GL-S02")

    def test_flags_no_bounds_medium(self):
        # ≥10 words but no numeric, conditional, or category signals → MEDIUM
        src = """
gl.eq_principle.prompt_comparative(
    fn,
    principle="The output should be reasonable and appropriate for the context provided here",
)
"""
        ws = check_weak_eq_criteria(src)
        assert any(w.code == "GL-S02" for w in ws)
        assert any("MEDIUM" in w.msg for w in ws if w.code == "GL-S02")

    def test_passes_strong_criteria_with_numeric(self):
        src = """
gl.eq_principle.prompt_comparative(
    fn,
    principle="Return YES if prices differ by less than 5%, NO otherwise",
)
"""
        ws = check_weak_eq_criteria(src)
        assert not any(w.code == "GL-S02" for w in ws)

    def test_passes_strong_criteria_with_categories(self):
        src = """
gl.eq_principle.prompt_comparative(
    fn,
    principle="Answer must be one of: approved, rejected, or pending review",
)
"""
        ws = check_weak_eq_criteria(src)
        assert not any(w.code == "GL-S02" for w in ws)

    def test_edge_variable_principle_not_flagged(self):
        # principle is a variable — can't inspect at lint time
        src = """
gl.eq_principle.prompt_comparative(fn, principle=my_principle)
"""
        ws = check_weak_eq_criteria(src)
        assert not any(w.code == "GL-S02" for w in ws)

    def test_flags_non_comparative_weak_criteria(self):
        src = """
gl.eq_principle.prompt_non_comparative(
    fn,
    task="classify text",
    criteria="similar",
)
"""
        ws = check_weak_eq_criteria(src)
        assert any(w.code == "GL-S02" for w in ws)

    def test_passes_non_comparative_strong_criteria(self):
        src = """
eq_principle_prompt_non_comparative(
    fn,
    task="classify sentiment",
    criteria="Must return YES if sentiment score >= 0.7, NO if < 0.7",
)
"""
        ws = check_weak_eq_criteria(src)
        assert not any(w.code == "GL-S02" for w in ws)

    def test_edge_no_principle_kwarg_not_flagged(self):
        # kwarg missing entirely — we can't check it
        src = """
gl.eq_principle.prompt_comparative(fn)
"""
        ws = check_weak_eq_criteria(src)
        assert not any(w.code == "GL-S02" for w in ws)

    def test_message_contains_snippet(self):
        src = """
eq_principle_prompt_comparative(fn, principle="same")
"""
        ws = check_weak_eq_criteria(src)
        assert ws
        assert "same" in ws[0].msg


# ---------------------------------------------------------------------------
# GL-S03: eq_principle_strict_eq type mismatch
# ---------------------------------------------------------------------------


class TestGL_S03_EqPrincipleTypeMismatch:
    def test_flags_lambda_with_exec_prompt(self):
        src = """
gl.eq_principle.strict_eq(lambda: gl.exec_prompt("What is the capital of France?"))
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    def test_flags_lambda_with_get_webpage(self):
        src = """
gl.eq_principle.strict_eq(lambda: gl.get_webpage("https://example.com"))
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    def test_flags_bare_eq_principle_strict_eq_with_exec_prompt(self):
        src = """
eq_principle_strict_eq(lambda: exec_prompt("Summarise this text"))
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    def test_passes_deterministic_lambda(self):
        src = """
gl.eq_principle.strict_eq(lambda: compute_hash(data))
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_passes_literal_lambda(self):
        src = """
eq_principle_strict_eq(lambda: 42)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_flags_named_function_with_exec_prompt(self):
        src = """
def fetch_answer():
    return gl.exec_prompt("Answer this question")

gl.eq_principle.strict_eq(fetch_answer)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    def test_flags_named_function_with_get_webpage(self):
        src = """
def get_content():
    return get_webpage("https://example.com")

eq_principle_strict_eq(get_content)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    def test_passes_named_function_no_llm(self):
        src = """
def pure_compute():
    return sum(range(100))

gl.eq_principle.strict_eq(pure_compute)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_edge_no_args_not_flagged(self):
        src = """
gl.eq_principle.strict_eq()
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_edge_unknown_function_ref_not_flagged(self):
        # Reference to a function defined elsewhere — can't inspect
        src = """
gl.eq_principle.strict_eq(external_fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_message_template(self):
        src = """
gl.eq_principle.strict_eq(lambda: gl.exec_prompt("test"))
"""
        ws = check_eq_strict_mismatch(src)
        assert ws
        msg = ws[0].msg
        assert "eq_principle_strict_eq" in msg
        assert "eq_principle_prompt_comparative" in msg
        assert "eq_principle_prompt_non_comparative" in msg
