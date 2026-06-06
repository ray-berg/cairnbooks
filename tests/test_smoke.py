"""Trivial smoke test — verifies the cairnbooks package imports and has a version."""

from cairnbooks import __version__


def test_package_importable() -> None:
    """The cairnbooks package must be importable without errors."""
    import cairnbooks  # noqa: F401


def test_version_defined() -> None:
    """A __version__ string must be defined."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_smoke() -> None:
    """Trivial always-passing canary."""
    assert True
