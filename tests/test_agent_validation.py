import pytest

from agent import validate_task
from ollama_client import OllamaClient, OllamaError


def base(action="reply"):
    return {
        "action": action, "reply": "ok", "research_query": "",
        "file_name": "report", "file_format": "md", "file_content": "# hi",
        "computer_action": "list_workspace", "summary": "test",
    }


def test_unknown_task_rejected():
    with pytest.raises(ValueError, match="Unknown"):
        validate_task(base("unknown"))


def test_unsafe_file_name_rejected():
    data = base("create_file")
    data["file_name"] = "../secret"
    with pytest.raises(ValueError, match="Unsafe"):
        validate_task(data)


def test_invalid_model_shape_rejected():
    with pytest.raises(ValueError, match="Unsupported file format"):
        data = base("create_file")
        data["file_format"] = "exe"
        validate_task(data)


def test_computer_action_allowlist():
    data = base("computer")
    data["computer_action"] = "delete_files"
    with pytest.raises(ValueError, match="Unsupported"):
        validate_task(data)


def test_invalid_model_json_rejected():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "not-json"}

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    client = OllamaClient(
        type("Config", (), {
            "endpoint": "http://localhost", "model": "test",
            "timeout_seconds": 1, "context_length": 10, "max_output_tokens": 10,
        })(),
        Session(),
    )
    with pytest.raises(OllamaError, match="invalid task JSON"):
        client.generate_json("prompt")
