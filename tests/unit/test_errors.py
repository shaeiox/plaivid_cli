from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import ErrorKind


def test_app_error_has_stable_category_and_safe_message() -> None:
    error = AppError(ErrorKind.PROCESS, "local command timed out", code="PROCESS_TIMEOUT")
    assert error.kind is ErrorKind.PROCESS
    assert error.code == "PROCESS_TIMEOUT"
    assert str(error) == "local command timed out"
    assert error.retryable is False
