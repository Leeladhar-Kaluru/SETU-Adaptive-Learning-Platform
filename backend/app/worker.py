import os
import sys
import asyncio

# Ensure backend directory in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.pipeline_runner import (
    WORKER_ID,
    claim_next_document,
    claim_next_job,
    process_job,
    refresh_path_status,
    run_pipeline_loop as run_worker_loop,
)

if __name__ == "__main__":
    asyncio.run(run_worker_loop())
