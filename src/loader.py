import yaml
import logging

logger = logging.getLogger(__name__)

def load_config(keys=None):
    config_path = "config/inference.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if keys is None:
            return config
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.warning(f"Key path {keys} not found in config")
                return None
        return value
    
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        return None
    