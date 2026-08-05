from __future__ import annotations

from app.identity import canonical_key, normalize_name, parse_byline
from app.identity.resolver import add_alias, resolve_authors


def test_byline_prefix_and_titles_are_stripped():
    assert parse_byline("By Jane Smith, Senior Correspondent") == [("Jane Smith", "jane smith")]


def test_multiple_authors_split():
    names = [display for display, _ in parse_byline("By Jane Smith and Bob Lee")]
    assert names == ["Jane Smith", "Bob Lee"]


def test_honorifics_initials_and_case_fold_together():
    assert normalize_name("Dr. JANE Q. Smith") == "jane q smith"
    assert normalize_name("Smith, Jane") == "jane smith"
    assert canonical_key("Jane Smith") == "jane-smith"


def test_accents_are_folded():
    assert normalize_name("Zoë Bäcker") == "zoe backer"


def test_non_person_bylines_are_rejected():
    assert parse_byline("By Staff") == []
    assert parse_byline("Reuters") == []
    assert parse_byline("By Our Correspondent in Berlin") == []


def test_same_person_resolves_to_one_author_across_outlets(session):
    first = resolve_authors(session, "By Jane Smith", "economist.com")
    session.commit()
    second = resolve_authors(session, "by  jane   smith", "ft.com")
    assert [a.id for a in first] == [a.id for a in second]


def test_alias_table_merges_a_different_spelling(session):
    (author,) = resolve_authors(session, "By Jane Smith", "economist.com")
    session.commit()

    # Without an alias, an initialised byline is a different person.
    (other,) = resolve_authors(session, "By J. Smith", "economist.com")
    session.commit()
    assert other.id != author.id

    add_alias(session, author, normalize_name("J. Smith"), "economist.com")
    session.commit()

    (resolved,) = resolve_authors(session, "By J. Smith", "economist.com")
    assert resolved.id == author.id


def test_outlet_scoped_alias_beats_global_alias(session):
    (a,) = resolve_authors(session, "By Alice Anderson", "economist.com")
    (b,) = resolve_authors(session, "By Alan Anderson", "ft.com")
    session.commit()

    add_alias(session, a, "a anderson", None)
    add_alias(session, b, "a anderson", "ft.com")
    session.commit()

    assert resolve_authors(session, "By A. Anderson", "ft.com")[0].id == b.id
    assert resolve_authors(session, "By A. Anderson", "economist.com")[0].id == a.id
