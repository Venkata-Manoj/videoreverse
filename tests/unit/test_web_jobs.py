from web.jobs import Job, JobStore


def test_job_store_tracks_artifact_paths() -> None:
    store = JobStore()
    job = Job(id="job1")

    store._push(job, "step", {"files": {"json": "output.json"}})

    assert job.files["json"] == "output.json"
