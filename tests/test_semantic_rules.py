"""Tests for the GL-S03 semantic lint rule."""

from genvm_linter.lint.safety import check_eq_strict_mismatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def codes(warnings):
    return [w.code for w in warnings]


# ---------------------------------------------------------------------------
# GL-S03: eq_principle_strict_eq nondeterminism mismatch
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

    def test_class_method_not_confused_with_module_function(self):
        src = """
def fetch_answer():
    return gl.exec_prompt("What is the answer?")

class MyContract(gl.Contract):
    def fetch_answer(self):
        return "deterministic"

gl.eq_principle.strict_eq(fetch_answer)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    def test_class_method_same_name_no_llm_module_fn_pure(self):
        src = """
def fetch_answer():
    return sum(range(10))

class MyContract(gl.Contract):
    def fetch_answer(self):
        return gl.exec_prompt("What is the answer?")

gl.eq_principle.strict_eq(fetch_answer)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)


# ---------------------------------------------------------------------------
# GL-S03: Full spec — conservative return-path detection, v0.1.3+ API, aliases
# ---------------------------------------------------------------------------


class TestGL_S03_FullSpec:
    # ------------------------------------------------------------------
    # SHOULD FLAG: v0.1.3+ API
    # ------------------------------------------------------------------

    def test_flags_v013_nondet_exec_prompt_lambda(self):
        src = """
gl.eq_principle.strict_eq(lambda: gl.nondet.exec_prompt("answer this"))
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "gl.nondet.exec_prompt (v0.1.3+) inside lambda must flag GL-S03"
        )

    def test_flags_v013_nondet_web_render_named_fn(self):
        src = """
def get_page():
    return gl.nondet.web.render("https://example.com")

gl.eq_principle.strict_eq(get_page)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "gl.nondet.web.render (v0.1.3+) in named function must flag GL-S03"
        )

    # ------------------------------------------------------------------
    # SHOULD FLAG: aliased import form
    # ------------------------------------------------------------------

    def test_flags_aliased_eq_principle_strict_eq(self):
        src = """
def fetch():
    return gl.exec_prompt("answer")

eq_principle.strict_eq(fetch)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "eq_principle.strict_eq aliased form must flag GL-S03"
        )

    def test_flags_aliased_exec_prompt_in_lambda(self):
        src = """
eq_principle_strict_eq(lambda: exec_prompt("What is the capital?"))
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "bare exec_prompt alias inside aliased strict_eq must flag GL-S03"
        )

    # ------------------------------------------------------------------
    # SHOULD FLAG: simple passthrough variable
    # ------------------------------------------------------------------

    def test_flags_simple_passthrough_variable(self):
        src = """
def fn():
    result = gl.exec_prompt("answer this")
    return result

gl.eq_principle.strict_eq(fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "var = nondet_call(); return var must flag GL-S03"
        )

    def test_flags_await_passthrough_variable(self):
        src = """
async def fn():
    result = await gl.exec_prompt("answer this")
    return result

gl.eq_principle.strict_eq(fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "var = await nondet_call(); return var must flag GL-S03"
        )

    # ------------------------------------------------------------------
    # SHOULD FLAG: one-level transitive call
    # ------------------------------------------------------------------

    def test_flags_one_level_transitive(self):
        src = """
def inner():
    return gl.exec_prompt("answer this")

def outer():
    return inner()

gl.eq_principle.strict_eq(outer)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "outer() returns inner() which returns raw nondet — one-level transitive must flag"
        )

    # ------------------------------------------------------------------
    # SHOULD NOT FLAG: processed / transformed output
    # ------------------------------------------------------------------

    def test_passes_bool_derived_from_webpage(self):
        src = """
def check():
    return 'keyword' in gl.get_webpage("https://example.com")

gl.eq_principle.strict_eq(check)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "bool derived from get_webpage is deterministic — must not flag"
        )

    def test_passes_comparison_from_exec_prompt(self):
        src = """
def classify():
    data = gl.exec_prompt("answer this")
    return data == "YES"

gl.eq_principle.strict_eq(classify)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "data == 'YES' is a comparison not raw nondet — must not flag"
        )

    def test_passes_json_processed_nondet(self):
        src = """
def process():
    data = gl.get_webpage("https://example.com")
    return json.loads(data)

gl.eq_principle.strict_eq(process)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "json.loads(data) transforms nondet output — must not flag"
        )

    def test_passes_reassigned_nondet_variable(self):
        src = """
def process():
    data = gl.exec_prompt("answer")
    data = data.strip()
    return data

gl.eq_principle.strict_eq(process)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "variable reassigned after nondet assign — not a pure passthrough, must not flag"
        )

    def test_passes_nondet_not_in_return_path(self):
        src = """
def fn():
    data = gl.exec_prompt("gather info")
    log(data)
    return 42

gl.eq_principle.strict_eq(fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "nondet call present but not in return path — must not flag"
        )

    def test_passes_sorted_nondet_output(self):
        src = """
def stable_result():
    raw = gl.get_webpage("https://example.com")
    return sorted(raw.split())

gl.eq_principle.strict_eq(stable_result)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "sorted output of nondet is a transformation — must not flag"
        )

    # ------------------------------------------------------------------
    # SHOULD NOT FLAG: third-party exec_prompt
    # ------------------------------------------------------------------

    def test_third_party_exec_prompt_not_flagged(self):
        src = """
gl.eq_principle.strict_eq(lambda: some_lib.llm.exec_prompt("What is 2+2?"))
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "third-party .exec_prompt must not be matched by GL-S03"
        )

    def test_sdk_exec_prompt_still_flagged(self):
        src = """
gl.eq_principle.strict_eq(lambda: gl.exec_prompt("What is 2+2?"))
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws)

    # ------------------------------------------------------------------
    # EDGE CASES
    # ------------------------------------------------------------------

    def test_edge_empty_none_lambda(self):
        src = """
gl.eq_principle.strict_eq(lambda: None)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_edge_strict_eq_no_nondet_at_all(self):
        src = """
def pure():
    x = 1 + 1
    return x

gl.eq_principle.strict_eq(pure)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws)

    def test_edge_nondet_in_nested_func_not_flagged(self):
        src = """
def outer():
    def inner():
        return gl.exec_prompt("answer")
    return 42

gl.eq_principle.strict_eq(outer)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "nondet only inside a nested function — outer returns constant, must not flag"
        )

    def test_passes_augmented_assignment_breaks_nondet_chain(self):
        src = """
def fn():
    result = gl.exec_prompt("summarise this")
    result += " post-processed"
    return result

gl.eq_principle_strict_eq(fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "AugAssign after nondet call should break the chain "
            "and not flag as raw nondet output"
        )

    # ------------------------------------------------------------------
    # CHANGE 1: decorator form
    # ------------------------------------------------------------------

    def test_flags_decorator_form_gl_eq_principle_strict_eq(self):
        src = """
@gl.eq_principle.strict_eq
def fn():
    return gl.exec_prompt("What is the answer?")
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "@gl.eq_principle.strict_eq decorator on fn returning raw exec_prompt must flag GL-S03"
        )

    def test_flags_decorator_form_bare_strict_eq(self):
        src = """
@eq_principle_strict_eq
def fn():
    return gl.exec_prompt("What is the answer?")
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "@eq_principle_strict_eq decorator on fn returning raw exec_prompt must flag GL-S03"
        )

    def test_passes_decorator_form_bool_return(self):
        src = """
@gl.eq_principle.strict_eq
def fn():
    return "keyword" in gl.get_webpage("https://example.com")
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "@gl.eq_principle.strict_eq on fn returning bool from get_webpage must not flag"
        )

    # ------------------------------------------------------------------
    # CHANGE 2: self.method resolution
    # ------------------------------------------------------------------

    def test_flags_self_method_raw_nondet(self):
        src = """
class MyContract(gl.Contract):
    def run(self):
        gl.eq_principle_strict_eq(self.fetch)

    def fetch(self):
        return gl.exec_prompt("answer this")
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "self.fetch returning raw exec_prompt passed to strict_eq must flag GL-S03"
        )

    def test_passes_self_method_bool_return(self):
        src = """
class MyContract(gl.Contract):
    def run(self):
        gl.eq_principle_strict_eq(self.fetch)

    def fetch(self):
        return "keyword" in gl.get_webpage("https://example.com")
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "self.fetch returning bool derived from nondet must not flag"
        )

    def test_passes_self_method_not_found_in_class(self):
        src = """
class MyContract(gl.Contract):
    def run(self):
        gl.eq_principle_strict_eq(self.external)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "self.external not defined in class body — conservative, must not flag"
        )

    # ------------------------------------------------------------------
    # CHANGE 3 / CHANGE 4: alias and nondet source list coverage
    # ------------------------------------------------------------------

    def test_passes_third_party_exec_prompt_not_flagged_alias(self):
        src = """
def fn():
    return my_llm.exec_prompt("What is the answer?")

gl.eq_principle.strict_eq(fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert not any(w.code == "GL-S03" for w in ws), (
            "my_llm.exec_prompt is a third-party call — must not match GL-S03 nondet list"
        )

    def test_flags_get_webpage_v010_raw_return(self):
        src = """
def fn():
    return gl.get_webpage("https://example.com")

gl.eq_principle_strict_eq(fn)
"""
        ws = check_eq_strict_mismatch(src)
        assert any(w.code == "GL-S03" for w in ws), (
            "gl.get_webpage (v0.1.0 API) raw return must flag GL-S03"
        )

    def test_message_contains_call_name_and_line(self):
        src = """
gl.eq_principle.strict_eq(lambda: gl.exec_prompt("test"))
"""
        ws = check_eq_strict_mismatch(src)
        assert ws
        msg = ws[0].msg
        assert "gl.exec_prompt" in msg
        assert "eq_principle_prompt_comparative" in msg
        assert "eq_principle_prompt_non_comparative" in msg
