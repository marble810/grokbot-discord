# grokbot-discord

Python Discord gateway for talking to Grok Bots from a private server. One Discord bot, many Grok Bots. Built so you can chat from a phone anywhere Discord works.

Licensed under the [MIT License](LICENSE).

Grok Bot has no Discord inbound plugin. A long-running process holds the Gateway, hears an address (a Discord `@mention`, a mapped role, or a leading bot name), replies **Got it.** immediately, POSTs a webhook ping to wake the target Grok Bot, then posts the real reply when that bot calls back.

```
Discord  --gateway-->  Python process  --POST webhook-->  Grok Bot
     ^                         |
     |                         |  POST /reply
     +------ channel post -----+
```

The webhook returns **200** (any 2xx is accepted) when the Grok Bot *wakes*, not when it finishes. Replies are async. The pickup ack is not.

Wake requests are `POST` JSON with `Authorization: Bearer <key>` (the routine's `crsr_…` key), per [Grok Bot routines](https://cursor.com/help/grok-bot/routines.md).

## 1. Discord application

1. Open [Discord Developer Portal](https://discord.com/developers/applications) → New Application.
2. Bot → Add Bot. Enable **Message Content Intent**.
3. Reset Token and copy it. That is `DISCORD_BOT_TOKEN`. Never commit it.
4. OAuth2 → URL Generator. Scopes: `bot`. Permissions: View Channels, Send Messages, Read Message History.
5. Open the URL, invite the bot into a **private** server and the channel you will use.
6. Discord Settings → Advanced → Developer Mode. Right-click the server, channel, and your user → Copy ID. Those are the allowlists.

## 2. One webhook routine per Grok Bot

On each Grok Bot:

1. Create a routine with trigger type `webhook`.
2. Use [prompts/webhook-routine.md](prompts/webhook-routine.md) as the prompt.
3. Open the routine panel. Copy the webhook URL (`https://api2.cursor.sh/automations/webhook/<id>`).
4. Copy the webhook **key** (`crsr_…`). Do not paste it into chat or git.

The Discord bridge already replies **Got it.** The webhook routine should send the real answer, not another pickup ack.

## 3. Local config

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
cp bots.example.yaml bots.yaml
chmod +x watch.sh ensure-up.sh
```

Fill `.env`:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ALLOWLIST`, `DISCORD_CHANNEL_ALLOWLIST`, `DISCORD_AUTHOR_ALLOWLIST` (comma-separated snowflakes)
- `CALLBACK_SECRET` (a long random string the Grok Bots use when they POST replies)
- `GROK_BOT_<NAME>_WEBHOOK_URL` and `GROK_BOT_<NAME>_WEBHOOK_KEY` (the `crsr_…` key; legacy `_WEBHOOK_SECRET` also read) for each bot in `bots.yaml`
- `CALLBACK_PUBLIC_URL` **or** `CALLBACK_PUBLIC_URL_FILE` (tunnel script writes the latter; re-read on every wake)

Empty allowlists refuse to start. Empty bots list refuses to start. Missing webhook URL/key refuses to start unless `DRY_RUN=true`.

`bots.yaml` maps names, aliases, and optional Discord role IDs to those env vars. Keys stay in env.

## 4. Run

```bash
.venv/bin/pytest
.venv/bin/python -m grokbot_discord
```

Logs `online as YourBot#1234` when the Gateway is up. The process also listens on `CALLBACK_BIND:CALLBACK_PORT` (default `127.0.0.1:8787`) for `/health` and `/reply`.

Foreground is fine for a first test. For a crash loop, start the watchdog instead:

```bash
./ensure-up.sh
```

Confirm `bridge.log` contains `online as`. `watch.sh` restarts the gateway if it exits.

Dry-run first, no Grok Bot keys required:

```bash
DRY_RUN=true .venv/bin/python -m grokbot_discord
```

Addressed messages are logged as would-POST. Nothing leaves the machine.

## 5. Talk to a bot

In the allowlisted channel, any one of these wakes a Grok Bot. You do not need both a Discord `@` and the bot name.

- `loops ping` or `@loops ping` — first token is a name or alias from `bots.yaml` (leading `@` is optional text, not a Discord mention)
- `@bridge loops ping` — Discord `@mention` of this bot, then the Grok Bot name
- mention a Discord role mapped in `bots.yaml`
- `@bridge ping` — uses `DEFAULT_BOT` / `default:` in yaml if set

The channel gets an instant **Got it.** then the real reply when the Grok Bot calls back.

An unknown name does not fire a webhook. The channel gets `unknown bot. configured: …`.

## 6. Where this runs

The bridge and the Grok Bots run on the **same box**, so the callback stays local: wakes carry `reply_url=http://127.0.0.1:8787/reply` by default and each routine POSTs its answer there. No tunnel is needed; the bridge only needs outbound HTTPS to Discord and the webhook endpoints.

```bash
./scripts/supervise.sh --callback-only   # /health + /reply only, no Discord token needed
./scripts/supervise.sh                   # full gateway (needs token, allowlists, webhook secrets)
```

Override the URL with `CALLBACK_PUBLIC_URL` (static) or `CALLBACK_PUBLIC_URL_FILE` (re-read on every wake) only if a bot runs elsewhere. `--tunnel` optionally starts a Cloudflare quick tunnel that writes `.public_url`; it needs outbound port 7844 and does not work on sandboxed boxes.

Do not put the webhook key or `CALLBACK_SECRET` in the browser or in git. `REPLY_TIMEOUT_S` (default 900) releases in-flight slots and posts a timeout notice if the bot never calls back.

## Discord bridge watchdog

A scheduled Grok Bot routine named **discord bridge watchdog** is already saved on the live bot. That prompt was not previously in this repo.

This tree now has the keep-alive from [discord-grok-bot-kit](https://github.com/larry-fuqua/discord-grok-bot-kit), adapted here:

- `watch.sh` — restart loop if the gateway process dies
- `ensure-up.sh` — start `watch.sh` if it is not running
- [prompts/keep-alive-routine.md](prompts/keep-alive-routine.md) — in-repo copy of the watchdog prompt, so the live routine can be recreated if it drifts

Point the existing **discord bridge watchdog** routine at `./ensure-up.sh` in this directory. Stay quiet if the listener is already up. Only message the owner if it could not be started.

Optional cron if you do not want to rely on the Grok Bot schedule:

```
@reboot /path/to/grokbot-discord/ensure-up.sh
15 8,12,16,20 * * * /path/to/grokbot-discord/ensure-up.sh
```

## Routing and filters

A message is dropped when:

- the author is this Discord bot
- guild, channel, or author is not allowlisted (allowlisted *bots* are accepted; there is no blanket `author.bot` drop)
- `REQUIRE_MENTION=true` and the message is not addressed: no Discord `@mention` of this bot, no mapped role mention, and the first token is not a configured bot name/alias
- `message_id` was already handled
- the channel already has `IN_FLIGHT_PER_CHANNEL` wakes waiting on a reply (default 2)

## Layout

- `src/grokbot_discord/` — Gateway, filters, routing, webhook client, reply callback
- `prompts/webhook-routine.md` — paste into each Grok Bot webhook routine
- `prompts/keep-alive-routine.md` — in-repo copy of the **discord bridge watchdog** scheduled routine
- `watch.sh`, `ensure-up.sh` — crash loop and start-if-missing
- `.github/workflows/ci.yml` — `ruff` + `pytest` on PRs
