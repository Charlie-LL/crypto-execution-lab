# tests/test_smoke_imports.py

def test_imports_smoke():
    # 只做“能安装+能导入”的冒烟，不做行为正确性
    import engine.state
    import engine.decision

    import execution.order_state
    import execution.order_engine
    import execution.metrics_engine
    import execution.policy

    import observer.config
    import observer.paths
    import observer.regime
    import observer.stream

    import risk.risk_guard
    import permission.permission
    import health.health


def test_entrypoint_module_smoke():
    # 确保 observer.run 作为模块可被导入（不要在 import 时自动跑 main loop）
    import observer.run
    assert hasattr(observer.run, "__file__")
