import asyncio
from cli.ui import run_cli
from my_agents import analysis_agent


async def main():
    """Main conversation loop"""
    await run_cli(analysis_agent.agent)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 System shutdown by user")
    except Exception as e:
        print(f"\n❌ System error: {e}")
