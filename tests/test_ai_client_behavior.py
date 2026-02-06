# -*- coding: utf-8 -*-
"""
Behavior tests for ai_client configuration and menu flow.
"""

import builtins

import ai_client
import ai_config


class _FakeService:
    def __init__(self, name, api_type="openai", base_url="https://x", api_key="sk-test", model="m1", timeout=30):
        self.name = name
        self.api_type = api_type
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout


class _FakeAIConfig:
    def __init__(self):
        self.services = [_FakeService("openai")]
        self.reload_calls = 0
        self.active_service = self.services[0]

    def reload(self):
        self.reload_calls += 1

    def list_valid_services(self):
        return list(self.services)

    def get_active_service(self):
        return self.active_service

    def get_setting(self, key, default=None):
        settings = {
            "max_retries": 2,
            "allow_service_switch": True,
        }
        return settings.get(key, default)

    def set_active_service(self, service_id):
        for service in self.services:
            if service.name == service_id:
                self.active_service = service
                return True
        return False


def test_config_manager_load_config_clears_stale_services_and_reloads(monkeypatch):
    fake = _FakeAIConfig()
    monkeypatch.setattr(ai_config, "get_ai_config", lambda *args, **kwargs: fake)
    monkeypatch.setattr(ai_client.ConfigManager, "_services_displayed", True)

    manager = ai_client.ConfigManager()
    assert "openai" in manager.configs

    # Simulate service set changed in environment.
    fake.services = [_FakeService("gemini", api_type="gemini")]
    fake.active_service = fake.services[0]
    manager.load_config()

    assert "openai" not in manager.configs
    assert "gemini" in manager.configs
    assert manager.default_service == "gemini"
    assert fake.reload_calls >= 2


def test_ai_client_run_option_5_shows_performance_and_option_6_exits(monkeypatch):
    class _FakeConfigManager:
        def __init__(self):
            pass

    monkeypatch.setattr(ai_client, "ConfigManager", _FakeConfigManager)
    client = ai_client.AIClient()

    calls = {"perf": 0}
    monkeypatch.setattr(client, "print_performance_report", lambda: calls.__setitem__("perf", calls["perf"] + 1))

    inputs = iter(["5", "6"])
    monkeypatch.setattr(builtins, "input", lambda _="": next(inputs))

    client.run()

    assert calls["perf"] == 1
