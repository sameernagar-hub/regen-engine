"""System benchmarks B1-B7: moved to engine/bench.py (v0.13) so the containers can run them. Same output.

    python scripts/bench_system.py [--save]
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.bench import main

if __name__ == "__main__":
    main()
