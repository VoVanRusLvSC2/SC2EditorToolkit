"""MCP stdio entry point. The windowed EXE restores inherited pipe handles."""
from sc2native.mcp import main
from sc2native.launcher import run
if __name__=='__main__':raise SystemExit(run(main))
