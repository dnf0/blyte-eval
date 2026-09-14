from lab.engine.runner import AblationRunner
from lab.engine.adapters.superstate_relay import SuperstateRelayAdapter
from lab.engine.adapters.superstate_daemon import SuperstateDaemonAdapter
from lab.engine.adapters.superstate import SuperstateAdapter


def test_runner_resolves_relay_and_daemon_arms():
    runner = AblationRunner()
    
    relay_adapter = runner._get_adapter("superstate_relay")
    assert isinstance(relay_adapter, SuperstateRelayAdapter)

    daemon_adapter = runner._get_adapter("superstate_daemon")
    assert isinstance(daemon_adapter, SuperstateDaemonAdapter)

    solo_adapter = runner._get_adapter("superstate_solo")
    assert isinstance(solo_adapter, SuperstateAdapter)
