
from core.execution.execution_engine import ExecutionEngine
from domain.enums import Decision, ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionResult
from domain.risk import RiskDecision


class FakeBroker:
    def __init__(self):
        self.called = False

    def submit_order(self, order):
        self.called = True
        return ExecutionResult(success=True, status=ExecutionStatus.SUBMITTED)


def make_decision(**kwargs):
    base = dict(
        instrument_id="BTC",
        trade_instrument_id="BTCUSDT",
        allowed=True,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=None,
        quantity=1.0,
    )
    base.update(kwargs)
    return RiskDecision(**base)


def test_allowed_false_rejected():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(make_decision(allowed=False))

    assert result.status == ExecutionStatus.REJECTED
    assert not broker.called


def test_missing_quantity():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(make_decision(quantity=None))

    assert result.reason == "missing_quantity"
    assert not broker.called


def test_invalid_quantity():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(make_decision(quantity=0))

    assert result.reason == "invalid_quantity"
    assert not broker.called


def test_open_long_contract_invalid():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(
        make_decision(side=Side.SELL)
    )

    assert result.reason == "invalid_open_long_contract"
    assert not broker.called


def test_open_short_contract_invalid():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(
        make_decision(
            decision=Decision.OPEN_SHORT,
            side=Side.BUY,
            position_side=PositionSide.SHORT,
        )
    )

    assert result.reason == "invalid_open_short_contract"
    assert not broker.called


def test_close_side_none_invalid():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(
        make_decision(
            decision=Decision.CLOSE,
            side=Side.NONE,
        )
    )

    assert result.reason == "invalid_close_side"
    assert not broker.called


def test_hold_not_executable():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(
        make_decision(decision=Decision.HOLD)
    )

    assert result.reason == "hold_not_executable"
    assert not broker.called


def test_no_position_side_fallback():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(
        make_decision(position_side=None)
    )

    assert result.reason == "missing_position_side"
    assert not broker.called


def test_valid_calls_broker():
    broker = FakeBroker()
    engine = ExecutionEngine(broker)

    _, result = engine.execute(make_decision())

    assert broker.called
    assert result.status == ExecutionStatus.SUBMITTED