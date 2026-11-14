"""A pytest fixture for the route tests: each test starts with a clean route state.

The route layer keeps two things for the whole process: the keys that it must
remove from every text, and the stop request. A test that uses a short
placeholder key, or that asks the routes to stop, would otherwise change the
next test. Import ``fresh_route_state`` into a test module to use it.
"""
import pytest

from feedctrl import model_routes


@pytest.fixture(autouse=True)
def fresh_route_state():
    model_routes.forget_secrets()
    model_routes.reset_stop()
    yield
    model_routes.forget_secrets()
    model_routes.reset_stop()
