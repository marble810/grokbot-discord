from grokbot_discord.routing import Router
from tests.conftest import make_msg


def route(bots, content, mentions=frozenset({"99"}), roles=frozenset(), default="loops"):
    msg = make_msg(content=content, mention_user_ids=mentions, mention_role_ids=roles)
    return Router(bots, default).route(msg, "99")


def test_alias_after_mention(bots):
    hit = route(bots, "<@99> loop ping")
    assert (hit.bot.name, hit.text) == ("loops", "ping")


def test_bare_and_at_name(bots):
    assert route(bots, "loops ping", mentions=frozenset()).text == "ping"
    assert route(bots, "@XO status", mentions=frozenset()).bot.name == "xo"


def test_role_mention(bots):
    hit = route(bots, "<@&role-xo> status", frozenset(), frozenset({"role-xo"}))
    assert (hit.bot.name, hit.text) == ("xo", "status")


def test_multi_role_is_none(bots):
    assert route(bots, "hey", roles=frozenset({"role-loops", "role-xo"})) is None


def test_default_only_when_mentioned(bots):
    assert route(bots, "<@99> what?").bot.name == "loops"
    assert route(bots, "please ping loops", mentions=frozenset()) is None
    assert route(bots, "<@99> no-such ping", default="") is None
