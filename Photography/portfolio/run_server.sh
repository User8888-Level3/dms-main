#!/bin/bash
# Launch-config shim: run the portfolio server from its own directory so
# `python -m portfolio_app.server` resolves (launch.json has no cwd field).
cd "$(dirname "$0")"
exec ../.venv/bin/python -m portfolio_app.server
