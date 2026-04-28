"""URIP Hybrid-SaaS On-Premise Agent — Phase 4.

This package ships inside a Docker container that runs on the customer's
network.  See agent/README.md for install + run instructions.

Components
----------
- agent_main.py         — entrypoint; starts scheduler + heartbeat loop
- reporter.py           — encrypted reporter (HMAC signed POST to cloud)
- local_db.py           — local Postgres helper (raw findings stay here)
- heartbeat.py          — periodic agent health check-in
- drilldown_responder.py — long-poll handler for cloud-initiated raw fetches
"""

__version__ = "0.1.0"
AGENT_VERSION = __version__
