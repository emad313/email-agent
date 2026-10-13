"""Command-line entry point for the local email agent."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
import time

from agent import EmailAgent
from config import Config, load_config
from gmail_client import GmailClient
from ollama_client import OllamaClient
from storage import Storage


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    if not logger.handlers:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def build_agent(config: Config) -> EmailAgent:
    logger = logging.getLogger(__name__)
    gmail = GmailClient.from_oauth()
    ollama = OllamaClient(config.ollama)
    storage = Storage(config.agent.database_path)
    return EmailAgent(config, gmail, ollama, storage, logger)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Gmail/Ollama email agent")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true", help="Process one polling cycle")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--test-gmail", action="store_true")
    parser.add_argument("--test-ollama", action="store_true")
    parser.add_argument("--status", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        logger = configure_logging(config.agent.log_path)
        if args.check_config:
            logger.info("Configuration is valid.")
            return 0
        if args.status:
            print(Storage(config.agent.database_path).get_status_counts())
            return 0
        if args.test_ollama:
            OllamaClient(config.ollama).check_available()
            logger.info("Ollama model available.")
            return 0
        if args.test_gmail:
            GmailClient.from_oauth()
            logger.info("Gmail authentication successful.")
            return 0
        agent = build_agent(config)
        if not agent.ollama.check_available():
            raise RuntimeError(f"Ollama model is not installed: {config.ollama.model}")
        logger.info("Agent started.")
        if args.once:
            logger.info("Checking inbox.")
            agent.run_cycle()
            return 0
        while True:
            try:
                logger.info("Checking inbox.")
                count = agent.run_cycle()
                logger.info("Polling cycle complete (%d messages).", count)
            except Exception:
                logger.exception("Recoverable polling error; retrying.")
            time.sleep(config.agent.poll_interval_seconds)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Agent stopped.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
