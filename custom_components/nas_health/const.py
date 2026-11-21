"""Constants for the NAS Health integration."""

from datetime import timedelta

DOMAIN = "nas_health"
CONF_VERIFY_SSL = "verify_ssl"
CONF_INSTALL_TOKEN = "install_token"
JOB_POLL_SECONDS = 5
JOB_MAX_SECONDS = 80 * 60
DEFAULT_NAME = "NAS"
SCAN_INTERVAL = timedelta(seconds=60)
EVENT_STATE_CHANGED = "nas_health_state_changed"

PROBLEM_COLORS = ("red", "yellow")
COLORS = ["green", "yellow", "red", "cyan"]
