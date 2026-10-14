import sys

if "--callback-only" in sys.argv:
    from grokbot_discord.callback_main import main
else:
    from grokbot_discord.bot import main

if __name__ == "__main__":
    main()
