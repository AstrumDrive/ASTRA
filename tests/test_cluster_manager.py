import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from remote.astra_cluster_manager import ClusterStore, rpc, run_job


class ClusterStoreFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {
                "ASTRA_CLUSTER_CPU_SLOTS": "8",
                "ASTRA_CLUSTER_CPU_RESERVE": "1",
                "ASTRA_CLUSTER_GPU_SLOTS": "1",
                "ASTRA_CLUSTER_MEMORY_TOTAL_MB": "32768",
                "ASTRA_CLUSTER_MEMORY_RESERVE_MB": "4096",
            },
            clear=False,
        )
        self.environment.start()
        self.store = ClusterStore(self.root)

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def submit(self, client_id="nelson", code="print('VERDICT: PASS')", **extra):
        request = {
            "action": "submit",
            "client_id": client_id,
            "project": "shared-test",
            "code": code,
            "timeout_seconds": 30,
            **extra,
        }
        return rpc(self.store, request)


class ClusterManagerTests(ClusterStoreFixture):
    def test_submit_persists_attribution_resources_and_isolated_input(self):
        with patch.dict(
            os.environ,
            {"SSH_CONNECTION": "100.64.0.7 43210 100.64.0.8 22"},
            clear=False,
        ):
            job = self.submit(
                client_id="Gabriel Abellan",
                code="# ASTRA_ENGINE: sage\nprint('VERDICT: PASS')",
            )
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["client_id"], "gabriel-abellan")
        self.assertEqual(job["project"], "shared-test")
        self.assertEqual(job["engine"], "sage")
        self.assertEqual(job["cpu_slots"], 4)
        self.assertEqual(job["source_ip"], "100.64.0.7")
        request_path = Path(job["artifact_dir"]) / "request.json"
        persisted = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["job_id"], job["job_id"])
        self.assertEqual(persisted["client_id"], "gabriel-abellan")

    def test_native_idempotency_replays_same_job_after_store_restart(self):
        first = self.submit(idempotency_key="campaign-a-task-1-attempt-1")
        restarted = ClusterStore(self.root)
        replay = rpc(
            restarted,
            {
                "action": "submit",
                "client_id": "nelson",
                "project": "shared-test",
                "code": "print('VERDICT: PASS')",
                "timeout_seconds": 30,
                "idempotency_key": "campaign-a-task-1-attempt-1",
            },
        )
        self.assertEqual(replay["job_id"], first["job_id"])
        self.assertTrue(replay["idempotent_replay"])
        with restarted.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        self.assertEqual(count, 1)

    def test_native_idempotency_rejects_changed_request(self):
        first = self.submit(idempotency_key="immutable-request")
        conflict = self.submit(
            code="print('different')", idempotency_key="immutable-request"
        )
        self.assertIn("different request", conflict["error"])
        with self.store.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(self.store.status(first["job_id"])["status"], "queued")

    def test_callers_without_idempotency_key_remain_non_deduplicated(self):
        first = self.submit()
        second = self.submit()
        self.assertNotEqual(first["job_id"], second["job_id"])

    def test_scheduler_rotates_between_clients(self):
        first_nelson = self.submit("nelson")
        self.submit("nelson")
        gabriel = self.submit("gabriel")
        first = self.store.reserve_next()
        self.assertEqual(first["job_id"], first_nelson["job_id"])
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status='succeeded', finished_ts=? WHERE job_id=?",
                (first["started_ts"] + 1, first["job_id"]),
            )
        second = self.store.reserve_next()
        self.assertEqual(second["job_id"], gabriel["job_id"])

    def test_queued_job_can_be_cancelled(self):
        submitted = self.submit("gabriel")
        cancelled = rpc(
            self.store,
            {
                "action": "cancel",
                "job_id": submitted["job_id"],
                "client_id": "nelson",
            },
        )
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["cancel_requested"])

    def test_gpu_slot_blocks_another_gpu_job_but_not_cpu_work(self):
        first_gpu = self.submit(
            "nelson",
            code="import torch\nprint(torch.cuda.is_available())",
        )
        self.submit(
            "gabriel",
            code="import cupy\nprint(cupy.cuda.runtime.getDeviceCount())",
        )
        cpu_job = self.submit("gabriel", code="print(2 + 2)")
        reserved_gpu = self.store.reserve_next()
        self.assertEqual(reserved_gpu["job_id"], first_gpu["job_id"])
        self.assertEqual(reserved_gpu["gpu_slots"], 1)
        reserved_cpu = self.store.reserve_next()
        self.assertEqual(reserved_cpu["job_id"], cpu_job["job_id"])
        self.assertEqual(reserved_cpu["gpu_slots"], 0)

    def test_memory_reservation_blocks_oversubscription_but_not_smaller_work(self):
        first_large = self.submit("nelson", memory_mb=24000)
        second_large = self.submit("gabriel", memory_mb=8000)
        small = self.submit("gabriel", memory_mb=2048)

        reserved_large = self.store.reserve_next()
        self.assertEqual(reserved_large["job_id"], first_large["job_id"])
        reserved_small = self.store.reserve_next()
        self.assertEqual(reserved_small["job_id"], small["job_id"])
        self.assertEqual(self.store.status(second_large["job_id"])["status"], "queued")

        capacity = self.store.capacity()
        self.assertEqual(capacity["memory_slots_mb"], 28672)
        self.assertEqual(capacity["used_memory_mb"], 26048)
        self.assertEqual(capacity["available_memory_mb"], 2624)

    def test_submit_rejects_memory_request_above_allocatable_capacity(self):
        rejected = self.submit("nelson", memory_mb=28673)
        self.assertIn("exceeds allocatable ASTRUM memory", rejected["error"])

    def test_runner_writes_terminal_result_and_verdict(self):
        submitted = self.submit("nelson")
        reserved = self.store.reserve_next()
        self.assertEqual(reserved["job_id"], submitted["job_id"])
        worker = Path(__file__).resolve().parents[1] / "remote" / "astra_remote_worker.py"
        with patch.dict(
            os.environ,
            {
                "ASTRA_CLUSTER_WORKER": str(worker),
                "ASTRA_CLUSTER_PYTHON": os.sys.executable,
            },
            clear=False,
        ):
            exit_code = run_job(self.store, submitted["job_id"])
        self.assertEqual(exit_code, 0)
        status = self.store.status(submitted["job_id"])
        self.assertEqual(status["status"], "succeeded")
        self.assertEqual(status["verdict"], "PASS")
        self.assertEqual(status["result"]["cluster_job_id"], submitted["job_id"])
        self.assertEqual(status["result"]["client_id"], "nelson")

    def test_successful_lean_typecheck_is_a_pass_verdict(self):
        submitted = self.submit(
            "nelson",
            code="# ASTRA_ENGINE: lean\nexample : True := by trivial",
        )
        self.store.reserve_next()
        fake_worker = self.root / "fake_lean_worker.py"
        fake_worker.write_text(
            "import json, sys\n"
            "json.load(sys.stdin)\n"
            "print(json.dumps({'stdout':'','stderr':'','exit_code':0,'engine':'lean4'}))\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {
                "ASTRA_CLUSTER_WORKER": str(fake_worker),
                "ASTRA_CLUSTER_PYTHON": os.sys.executable,
            },
            clear=False,
        ):
            self.assertEqual(run_job(self.store, submitted["job_id"]), 0)
        status = self.store.status(submitted["job_id"])
        self.assertEqual(status["verdict"], "PASS")


class PerUserAccessTests(ClusterStoreFixture):
    """Identity, ownership, quotas and MPI threads (docs/ASTRUM_ACCESO_POR_USUARIO.md)."""

    def as_user(self, client_id):
        return patch.dict(os.environ, {"ASTRA_AUTHENTICATED_CLIENT": client_id}, clear=False)

    def write_quotas(self, config):
        (self.root / "quotas.json").write_text(json.dumps(config), encoding="utf-8")

    def events(self, job_id):
        with self.store.connect() as connection:
            return [
                (row["event"], row["detail"])
                for row in connection.execute(
                    "SELECT event, detail FROM events WHERE job_id=? ORDER BY id", (job_id,)
                ).fetchall()
            ]

    def run_with_env_probe(self, job_id):
        probe = self.root / "env_probe_worker.py"
        probe.write_text(
            "import json, os, sys\n"
            "json.load(sys.stdin)\n"
            "names = ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')\n"
            "out = ' '.join(f'{n}={os.environ.get(n)}' for n in names)\n"
            "print(json.dumps({'stdout': out, 'stderr': '', 'exit_code': 0}))\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"ASTRA_CLUSTER_WORKER": str(probe), "ASTRA_CLUSTER_PYTHON": os.sys.executable},
            clear=False,
        ):
            self.assertEqual(run_job(self.store, job_id), 0)
        return self.store.status(job_id)["result"]["stdout"]

    def test_authenticated_identity_replaces_declared_client(self):
        with self.as_user("ivaylo"):
            job = self.submit(client_id="nelson")
        self.assertEqual(job["client_id"], "ivaylo")
        self.assertIn(("submitted", "auth=ssh-user"), self.events(job["job_id"]))
        persisted = json.loads((Path(job["artifact_dir"]) / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["client_id"], "ivaylo")

    def test_service_account_path_keeps_declared_client(self):
        job = self.submit(client_id="nelson")
        self.assertEqual(job["client_id"], "nelson")
        self.assertIn(("submitted", ""), self.events(job["job_id"]))

    def test_caller_cannot_inject_private_fields(self):
        job = self.submit(client_id="nelson", _auth="ssh-user", _source_ip="203.0.113.9")
        self.assertEqual(job["source_ip"], "")
        self.assertIn(("submitted", ""), self.events(job["job_id"]))

    def test_authenticated_user_cannot_cancel_a_foreign_job(self):
        foreign = self.submit(client_id="gabriel")
        with self.as_user("ivaylo"):
            refused = rpc(self.store, {"action": "cancel", "job_id": foreign["job_id"], "client_id": "gabriel"})
        self.assertIn("belongs to gabriel", refused["error"])
        self.assertEqual(self.store.status(foreign["job_id"])["status"], "queued")
        self.assertNotIn("cancel_requested", [event for event, _ in self.events(foreign["job_id"])])

    def test_authenticated_user_can_cancel_own_job(self):
        with self.as_user("ivaylo"):
            own = self.submit()
            cancelled = rpc(self.store, {"action": "cancel", "job_id": own["job_id"]})
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIn(("cancel_requested", "ivaylo auth=ssh-user"), self.events(own["job_id"]))

    def test_authenticated_administrator_can_cancel_any_job(self):
        foreign = self.submit(client_id="gabriel")
        with self.as_user("nelson"):
            cancelled = rpc(self.store, {"action": "cancel", "job_id": foreign["job_id"]})
        self.assertEqual(cancelled["status"], "cancelled")

    def test_administrators_come_from_environment(self):
        foreign = self.submit(client_id="gabriel")
        with self.as_user("nelson"), patch.dict(os.environ, {"ASTRA_CLUSTER_ADMINS": "someone-else"}):
            refused = rpc(self.store, {"action": "cancel", "job_id": foreign["job_id"]})
        self.assertIn("belongs to gabriel", refused["error"])

    def test_max_queued_quota_rejects_extra_jobs_but_not_other_clients(self):
        self.write_quotas({"default": {"max_queued": 2}})
        self.submit("ivaylo")
        self.submit("ivaylo")
        refused = self.submit("ivaylo")
        self.assertIn("max_queued quota 2", refused["error"])
        self.assertEqual(self.submit("gabriel")["status"], "queued")

    def test_idempotent_replay_is_not_blocked_by_max_queued(self):
        self.write_quotas({"default": {"max_queued": 1}})
        first = self.submit("ivaylo", idempotency_key="k1")
        replay = self.submit("ivaylo", idempotency_key="k1")
        self.assertEqual(replay["job_id"], first["job_id"])
        self.assertTrue(replay["idempotent_replay"])

    def test_running_cpu_quota_holds_a_client_back_but_not_others(self):
        # The node has 8 slots, so only the quota keeps the second 4-slot job waiting.
        self.write_quotas({"default": {"max_running_cpu_slots": 4}})
        first = self.submit("ivaylo", cpu_slots=4)
        self.submit("ivaylo", cpu_slots=4)
        self.assertEqual(self.store.reserve_next()["job_id"], first["job_id"])
        self.assertIsNone(self.store.reserve_next())
        other = self.submit("gabriel", cpu_slots=2)
        self.assertEqual(self.store.reserve_next()["job_id"], other["job_id"])
        running = self.store.capacity()["per_client_running"]
        self.assertEqual(running["ivaylo"]["cpu_slots"], 4)
        self.assertEqual(running["gabriel"]["cpu_slots"], 2)

    def test_running_gpu_quota_holds_back_second_gpu_job_of_same_client(self):
        with patch.dict(os.environ, {"ASTRA_CLUSTER_GPU_SLOTS": "2"}, clear=False):
            self.write_quotas({"default": {"max_running_gpu_slots": 1}})
            first = self.submit("ivaylo", gpu_slots=1)
            self.submit("ivaylo", gpu_slots=1)
            self.assertEqual(self.store.reserve_next()["job_id"], first["job_id"])
            self.assertIsNone(self.store.reserve_next())

    def test_submit_rejects_request_above_client_quota(self):
        self.write_quotas({"default": {"max_running_cpu_slots": 4}})
        refused = self.submit("ivaylo", cpu_slots=6)
        self.assertIn("max_running_cpu_slots quota of client ivaylo (4)", refused["error"])

    def test_client_override_takes_precedence_over_default(self):
        self.write_quotas(
            {"default": {"max_running_cpu_slots": 4}, "clients": {"nelson": {"max_running_cpu_slots": 8}}}
        )
        self.assertEqual(self.submit("nelson", cpu_slots=8)["status"], "queued")
        self.assertIn("error", self.submit("ivaylo", cpu_slots=8))

    def test_malformed_quota_file_disables_quotas_and_is_reported(self):
        (self.root / "quotas.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.submit("ivaylo", cpu_slots=8)["status"], "queued")
        self.assertIn("JSONDecodeError", self.store.capacity()["quotas_error"])

    def test_no_quota_file_means_no_quotas(self):
        for _ in range(3):
            self.assertEqual(self.submit("ivaylo", cpu_slots=8)["status"], "queued")
        self.assertEqual(self.store.capacity()["quotas"], {})

    def test_threads_per_process_sets_one_thread_per_mpi_rank(self):
        job = self.submit("ivaylo", cpu_slots=4, threads_per_process=1)
        self.store.reserve_next()
        stdout = self.run_with_env_probe(job["job_id"])
        self.assertEqual(stdout.split(), ["OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1"])

    def test_threads_default_remains_one_per_reserved_slot(self):
        job = self.submit("ivaylo", cpu_slots=4)
        self.store.reserve_next()
        self.assertIn("MKL_NUM_THREADS=4", self.run_with_env_probe(job["job_id"]))

    def test_threads_per_process_is_clamped_and_absent_when_unset(self):
        clamped = self.submit("ivaylo", cpu_slots=2, threads_per_process=99)
        persisted = json.loads((Path(clamped["artifact_dir"]) / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["threads_per_process"], 2)
        plain = self.submit("ivaylo", cpu_slots=2)
        persisted = json.loads((Path(plain["artifact_dir"]) / "request.json").read_text(encoding="utf-8"))
        self.assertNotIn("threads_per_process", persisted)

    def test_info_reports_host_identity_and_engines(self):
        fake = patch(
            "remote.astra_cluster_manager.subprocess.run",
            return_value=__import__("subprocess").CompletedProcess([], 0, "  [OK ] oracle\n  [OK ] sci\n", ""),
        )
        with fake, self.as_user("gabriel"):
            info = rpc(self.store, {"action": "info"})
        self.assertEqual(info["client_id"], "gabriel")
        self.assertTrue(info["authenticated"])
        self.assertEqual(info["engines"], ["  [OK ] oracle", "  [OK ] sci"])
        self.assertTrue(info["host"])


if __name__ == "__main__":
    unittest.main()
