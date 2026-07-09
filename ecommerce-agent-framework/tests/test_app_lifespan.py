import asyncio

import app.main as main_module


class FakeChatManager:
    def __init__(self):
        self.initialized_with = None
        self.started = False
        self.stopped = False

    async def initialize(self, configs):
        self.initialized_with = configs
        return True

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class FakeEngine:
    def __init__(self):
        self.initialized = False

    def initialize(self):
        self.initialized = True


class FakeStorageManager:
    def __init__(self):
        self.stats_requested = False

    def get_stats(self):
        self.stats_requested = True
        return {"session_storage": {"status": "connected"}}


def test_lifespan_initializes_and_stops_services(monkeypatch):
    chat_manager = FakeChatManager()
    engine = FakeEngine()
    storage_manager = FakeStorageManager()
    configs = {"pinduoduo": {"listen_mode": "web"}}

    monkeypatch.setattr(main_module, "chat_manager", chat_manager)
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module, "storage_manager", storage_manager)
    monkeypatch.setattr(main_module, "_build_platform_configs", lambda: configs)

    async def exercise_lifespan():
        async with main_module.lifespan(main_module.app):
            assert chat_manager.initialized_with == configs
            assert chat_manager.started is True
            assert engine.initialized is True
            assert storage_manager.stats_requested is True
            assert chat_manager.stopped is False

    asyncio.run(exercise_lifespan())

    assert chat_manager.stopped is True


def test_lifespan_skips_platform_start_without_config(monkeypatch):
    chat_manager = FakeChatManager()

    monkeypatch.setattr(main_module, "chat_manager", chat_manager)
    monkeypatch.setattr(main_module, "engine", FakeEngine())
    monkeypatch.setattr(main_module, "storage_manager", FakeStorageManager())
    monkeypatch.setattr(main_module, "_build_platform_configs", lambda: {})

    async def exercise_lifespan():
        async with main_module.lifespan(main_module.app):
            assert chat_manager.initialized_with is None
            assert chat_manager.started is False

    asyncio.run(exercise_lifespan())

    assert chat_manager.stopped is True
