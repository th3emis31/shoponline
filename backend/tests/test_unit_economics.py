import pytest

from app.services.unit_economics import calculate


def test_desk_mat_matches_blueprint():
    r = calculate(price=3200, landed_cost=600, shipping=400, packaging=100)
    assert r.net_revenue == 2667
    assert r.payment_fee == 68
    assert r.returns_allowance == 55
    assert r.contribution_pre_ads == 1444
    assert round(r.break_even_roas, 2) == 2.22
    assert calculate(3200, 600, 400, 100, cac=1000).contribution_post_ads == 444
    assert calculate(3200, 600, 400, 100, cac=2000).contribution_post_ads == -556


def test_bundle_matches_blueprint():
    r = calculate(price=7500, landed_cost=1700, shipping=650, packaging=200)
    assert r.net_revenue == 6250
    assert r.returns_allowance == 95
    assert abs(r.contribution_pre_ads - 3472) <= 1
    assert round(r.break_even_roas, 2) == 2.16


def test_loss_making_product_has_no_break_even():
    assert calculate(price=100, landed_cost=500, shipping=0, packaging=0).break_even_roas is None


@pytest.mark.parametrize("kwargs", [
    dict(price=-1, landed_cost=0, shipping=0, packaging=0),
    dict(price=100, landed_cost=1.5, shipping=0, packaging=0),
    dict(price=100, landed_cost=0, shipping=0, packaging=0, return_rate=2),
])
def test_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        calculate(**kwargs)
