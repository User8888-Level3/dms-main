"""Parse CLIENT.md frontmatter into a structured buyer config dict."""

from pathlib import Path
import yaml


REQUIRED_FIELDS = ("client_name", "client_role")
VALID_ROLES = ("buyer", "seller")
LIST_FIELDS_DEFAULT_EMPTY = ("preferred_areas", "must_haves", "nice_to_haves", "deal_breakers")


class BuyerConfigError(Exception):
    """Raised when CLIENT.md frontmatter is missing, malformed, or invalid."""


def load_buyer_config(client_md_path):
    path = Path(client_md_path)
    if not path.is_file():
        raise BuyerConfigError(f"CLIENT.md not found at {path}")

    text = path.read_text()
    if not text.endswith("\n"):
        text += "\n"
    if not text.startswith("---\n"):
        raise BuyerConfigError(f"No frontmatter found in {path}. Expected YAML between --- markers.")

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise BuyerConfigError(f"No frontmatter found in {path}. Expected YAML between --- markers.")

    yaml_text = parts[1]
    try:
        config = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise BuyerConfigError(f"Malformed YAML in {path}: {e}") from e

    if not isinstance(config, dict):
        raise BuyerConfigError(f"Frontmatter must be a YAML dict in {path}.")

    for field in REQUIRED_FIELDS:
        if field not in config:
            raise BuyerConfigError(f"Missing required field '{field}' in {path}.")

    if config["client_role"] not in VALID_ROLES:
        raise BuyerConfigError(
            f"Invalid client_role '{config['client_role']}' in {path}. Must be one of: {VALID_ROLES}"
        )

    for field in LIST_FIELDS_DEFAULT_EMPTY:
        config.setdefault(field, [])

    return config
