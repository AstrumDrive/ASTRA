# Optional remote oracle

ASTRA can keep its interface and orchestration local while executing validation
scripts on a Linux worker reachable through SSH.

Copy `.env.example` to `.env` and configure:

```dotenv
ASTRA_ORACLE_MODE=remote
ASTRA_REMOTE_HOST=user@compute-host.example
ASTRA_REMOTE_PYTHON=~/astra-worker/venv/bin/python
ASTRA_REMOTE_WORKER=~/astra-worker/astra_remote_worker.py
ASTRA_REMOTE_WORKDIR=~/astra-worker/workspace
ASTRA_REMOTE_CONNECT_TIMEOUT=15
ASTRA_REMOTE_SSH_OPTIONS=-i C:\path\to\ssh_key
```

Deploy the worker with `remote/deploy_worker.ps1`, then run
`remote/check_remote_oracle.ps1`. Keep hostnames, private addresses, identity
files, and credentials in local configuration rather than committing them.

The scripts in this directory can install the Python stack, optional GPU
packages, and external CAS tools. Review them before running on shared systems.
