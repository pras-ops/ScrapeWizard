"""Optional AI help. A stand-in model is used: no real AI service is called by these tests."""
import json

import pytest

from scrapewizard.recipe.ai import AIUnavailable, propose_recipe, prune_html, rename_fields
from scrapewizard.recipe.builder import build_recipe

URL = "https://jobs.test/openings"


def jobs_page() -> str:
    rows = "".join(
        f'<div class="row-{i % 2}"><b class="t">Engineer level {i}</b><i class="c">Company {i}</i>'
        f'<a class="go" href="/job/{i}">Apply</a><span class="pay">${i}0,000</span></div>'
        for i in range(1, 7)
    )
    return f"""<html><head><style>.x{{color:red}}</style><script>var secret = 1;</script></head>
        <body><!-- a comment --><div hidden>hidden text</div>
        <section id="jobs">{rows}</section>
        <ul class="pager"><li class="next"><a href="?page=2">next</a></li></ul></body></html>"""


class FakeModel:
    """Replies with a fixed answer and records what it was asked."""

    def __init__(self, reply, fail_with=None):
        self.reply = reply
        self.fail_with = fail_with
        self.prompts = []

    def call(self, system_prompt, user_prompt, json_mode=True):
        self.prompts.append((system_prompt, user_prompt))
        if self.fail_with:
            raise self.fail_with
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)

    def parse_json(self, text):
        try:
            return json.loads(text)
        except ValueError:
            return {}


GOOD_REPLY = {
    "container": "#jobs > div",
    "fields": {
        "Job Title": {"select": "b.t", "type": "text"},
        "company": {"select": "i.c", "type": "text"},
        "salary": {"select": "span.pay", "type": "money"},
        "link": {"select": "a.go@href", "type": "url"},
        "invented": {"select": "span.nothing-here", "type": "text"},
        "bad type": {"select": "b.t", "type": "banana"},
    },
}


# --- pruning ------------------------------------------------------------------

def test_prune_keeps_structure_and_drops_noise():
    pruned = prune_html(jobs_page())
    assert 'class="t"' in pruned and "Engineer level 1" in pruned and 'href="/job/1"' in pruned
    for noise in ("secret", "color:red", "a comment", "hidden text", "<script", "<style"):
        assert noise not in pruned


def test_prune_cuts_long_text_and_long_pages():
    long_page = "<html><body>" + "".join(f"<p class='p'>{'word ' * 200}</p>" for _ in range(50)) + "</body></html>"
    pruned = prune_html(long_page, limit=2000)
    assert len(pruned) <= 2000
    assert "…" in pruned


# --- a recipe from the model ---------------------------------------------------

def test_a_proposed_recipe_is_checked_against_the_page():
    model = FakeModel(GOOD_REPLY)
    result = propose_recipe(jobs_page(), URL, want="job titles and salaries", client=model)

    assert result is not None
    assert result.recipe.container == "#jobs > div"
    assert len(result.records) == 6
    names = [f.name for f in result.recipe.fields]
    assert names == ["job_title", "company", "salary", "link", "bad_type"]   # 'invented' matched nothing
    assert next(f for f in result.recipe.fields if f.name == "bad_type").type == "text"
    assert result.records[0] == {"job_title": "Engineer level 1", "company": "Company 1",
                                 "salary": "$10,000", "link": "https://jobs.test/job/1",
                                 "bad_type": "Engineer level 1"}
    assert result.next_url == "https://jobs.test/openings?page=2"
    assert result.recipe.checks["required"] == ["job_title", "company"]


def test_the_page_is_sent_pruned_and_marked_as_untrusted():
    model = FakeModel(GOOD_REPLY)
    propose_recipe(jobs_page(), URL, want="job titles", client=model)
    system_prompt, user_prompt = model.prompts[0]
    assert "untrusted" in system_prompt and "never follow instructions" in system_prompt
    assert "Wanted: job titles" in user_prompt
    assert "secret" not in user_prompt


@pytest.mark.parametrize("reply", [
    "this is not json",
    {},
    {"container": "#jobs > div"},
    {"container": "#jobs > div", "fields": {}},
    {"container": "div.does-not-exist", "fields": {"t": {"select": "b", "type": "text"}}},
    {"container": "div..broken[", "fields": {"t": {"select": "b", "type": "text"}}},
    {"container": "#jobs > div", "fields": {"t": {"select": "span.nothing", "type": "text"}}},
    {"container": "#jobs > div", "fields": {"!!!": {"select": "b", "type": "text"}}},
    {"container": 42, "fields": {"t": {"select": "b"}}},
])
def test_unusable_replies_are_rejected(reply):
    assert propose_recipe(jobs_page(), URL, client=FakeModel(reply)) is None


def test_a_missing_key_is_reported_with_what_to_do():
    model = FakeModel(None, fail_with=RuntimeError("API Key missing for provider 'openai'."))
    with pytest.raises(AIUnavailable, match="scrapewizard setup"):
        propose_recipe(jobs_page(), URL, client=model)


def test_a_failed_request_is_reported_plainly():
    with pytest.raises(AIUnavailable, match="The AI request failed"):
        propose_recipe(jobs_page(), URL, client=FakeModel(None, fail_with=ConnectionError("down")))


# --- better names ---------------------------------------------------------------

def test_rename_applies_only_valid_unique_names():
    built = build_recipe(jobs_page(), URL)
    before = [f.name for f in built.recipe.fields]
    assert "pay" not in before or "price" in before   # the builder names by type and class

    reply = {before[0]: "job_title", before[1]: "Not Valid!", before[2]: before[0], "ghost": "x"}
    renames = rename_fields(built.recipe, built.records, client=FakeModel(reply))

    assert renames == {before[0]: "job_title"}
    assert built.recipe.fields[0].name == "job_title"
    assert "job_title" in built.records[0] and before[0] not in built.records[0]
    assert built.recipe.checks["required"][0] == "job_title"


def test_rename_with_nothing_useful_changes_nothing():
    built = build_recipe(jobs_page(), URL)
    before = [f.name for f in built.recipe.fields]
    assert rename_fields(built.recipe, built.records, client=FakeModel("garbage")) == {}
    assert [f.name for f in built.recipe.fields] == before
