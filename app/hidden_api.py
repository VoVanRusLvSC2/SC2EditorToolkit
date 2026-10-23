"""Compatibility entry point for the modular SC2 Native Toolkit service."""
from sc2native.service import main
from sc2native.launcher import run
if __name__=="__main__":raise SystemExit(run(main))
