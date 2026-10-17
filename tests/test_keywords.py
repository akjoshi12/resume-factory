from rfactory.config import settings
from rfactory.models.master import MasterResume
from rfactory.scoring.claims import absent_tools, mentions, tool_violations
from rfactory.scoring.coverage import keywords, score


def test_plurals_and_compounds_meet_their_resume_forms():
    wanted = "ELT/ETL transformations, Git-based workflows, data validations"
    have = "ELT and ETL transformation, Git, data validation, workflow"
    assert score("", have, focus=[wanted]).score == 1.0


def test_soft_words_do_not_count():
    assert not keywords("exceptional comfort with similar related equivalent practical skills")


def test_lowercase_tool_the_candidate_never_used_is_caught():
    master = MasterResume.load(settings.master_resume)
    absent = absent_tools(["dbt", "Airflow", "Snowflake", "Git"], master.claimable_text())
    assert absent == ["dbt", "Airflow"]
    assert tool_violations("objective", "Skilled in dbt and Python.", absent)
    assert not mentions("GitHub webhooks", "Git")


def test_plural_and_vendor_prefix_count_as_mentions():
    assert mentions("government CSVs", "CSV")
    assert mentions("Databricks pipelines", "Azure Databricks")
    assert not mentions("Databricks pipelines", "Azure Synapse")
    assert not mentions("cloud migration, SQL", "Google Cloud")
    assert not mentions("cloud migration, SQL", "Azure SQL")


def test_a_rewrite_that_drops_a_tool_or_number_is_flagged():
    from rfactory.scoring.claims import dropped_keywords

    source = "Built a Jenkins CI pipeline across a ~15,400-line codebase."
    assert dropped_keywords("b", source, "Built a CI pipeline across a codebase.", {"jenkins"})
    kept = "Built CI pipeline in Jenkins for a ~15,400-line codebase."
    assert not dropped_keywords("b", source, kept, {"jenkins"})


def test_cover_paste_and_stock_phrases_are_flagged():
    from rfactory.graph.nodes.cover import _style_problems

    bullet = (
        "Built and maintained Azure Data Factory and Databricks pipelines for large "
        "enterprise clients across coatings, consumer goods, and apparel."
    )
    pasted = "At TekLink I " + bullet.lower()
    assert _style_problems("p", pasted, [bullet])
    assert _style_problems("p", "This aligns directly with the posting.", [bullet])
    assert not _style_problems("p", "At TekLink I ran daily pipelines moving 200GB.", [bullet])


def test_domain_words_borrowed_from_the_posting_are_flagged():
    from rfactory.graph.nodes.tailor import _borrowed_terms

    source = "Built ETL data pipelines and Power BI dashboards with reconciliation logic."
    assert _borrowed_terms("objective", "Supports financial reporting.", source)
    assert not _borrowed_terms("objective", "Gathered business requirements for ETL.", source)


def test_cover_bridge_sentences_and_tool_stacks_are_flagged():
    from rfactory.graph.nodes.cover import _role_named, _style_problems

    bridge = ("This experience directly supports your need for scalable pipelines.",
              "This hands-on work with CI/CD answers your requirement for maintaining jobs.",
              "That project prepares me for your focus on data quality.")
    for sentence in bridge:
        assert _style_problems("p", sentence, []), sentence
    assert not _style_problems("p", "I would welcome the chance to discuss your team's needs.", [])

    skills = {"Whisper", "Pyannote", "FastAPI", "MySQL", "Elasticsearch", "React", "Databricks"}
    stack = ("I built a pipeline with Whisper and Pyannote, served through FastAPI with "
             "MySQL, Elasticsearch, and a React front end.")
    assert _style_problems("p", stack, [], skills)
    assert not _style_problems("p", "At TekLink I moved 200GB a day in Databricks.", [], skills)

    assert _role_named("Zurich's Data Engineer role", "Data Engineer, Data Management (Hybrid)")
    assert not _role_named("I am a strong candidate for this role.", "Data Engineer")


def test_letter_only_notes_posting_terms_the_candidate_claims():
    from rfactory.scoring.claims import verify_letter

    describe = "Zurich Canada's Data Management team builds the data foundations."
    _, notes = verify_letter("p1", "Built pipelines in Databricks.", describe, set(),
                             {"management", "zurich", "canada"})
    assert not notes
    claim = "I bring years of Data Management work."
    _, notes = verify_letter("p1", "Built pipelines in Databricks.", claim, set(), {"management"})
    assert notes
