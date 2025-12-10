"""CLI wrapper to run the agent orchestrator against the MCP server."""
from .orchestrator import Orchestrator
import sys


def main(argv):
    if len(argv) < 2:
        print("Usage: python -m agents.run_orchestrator <sample.pdf> [--mcp http://host:port]")
        return 2
    pdf = argv[1]
    # Optional: allow --mcp override
    if "--mcp" in argv:
        i = argv.index("--mcp")
        try:
            from agents import orchestrator
            orchestrator.MCP_URL = argv[i+1]
        except Exception:
            pass
    orch = Orchestrator()
    rpt = orch.run_pipeline(pdf)
    print(rpt)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
