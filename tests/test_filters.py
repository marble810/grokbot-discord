from grokbot_discord.filters import Dedupe, Policy
from tests.conftest import make_msg

POLICY = Policy(frozenset({"g1"}), frozenset({"10"}), frozenset({"u1", "other-bot"}))


def drop(msg, addressed=True):
    return POLICY.drop_reason(msg, self_user_id="99", addressed=addressed)


def test_drop_reasons():
    assert drop(make_msg()) is None
    assert drop(make_msg(author_id="99")) == "bot"
    assert drop(make_msg(guild_id="nope")) == "guild"
    assert drop(make_msg(channel_id="nope")) == "channel"
    assert drop(make_msg(author_id="stranger")) == "author"
    assert drop(make_msg(), addressed=False) == "mention"


def test_bot_authors_always_dropped_even_if_allowlisted():
    assert drop(make_msg(author_id="other-bot", author_is_bot=True)) == "bot"


def test_dedupe():
    d = Dedupe(cap=2)
    assert not d.already_seen("a")
    assert d.already_seen("a")
