from tg_time_logger.economy import calculate_fun_economy


def test_milestone_boundary_599() -> None:
    snap = calculate_fun_economy(599, 0)
    assert snap.base_fun_minutes == 199
    assert snap.bonus_blocks == 0
    assert snap.bonus_fun_minutes == 0
    assert snap.earned_fun_minutes == 199


def test_milestone_boundary_600() -> None:
    snap = calculate_fun_economy(600, 0)
    assert snap.base_fun_minutes == 200
    assert snap.bonus_blocks == 1
    assert snap.bonus_fun_minutes == 180
    assert snap.earned_fun_minutes == 380


def test_milestone_boundary_1200_with_spend() -> None:
    snap = calculate_fun_economy(1200, 100)
    assert snap.base_fun_minutes == 400
    assert snap.bonus_blocks == 2
    assert snap.bonus_fun_minutes == 360
    assert snap.earned_fun_minutes == 760
    assert snap.fun_left_minutes == 660
