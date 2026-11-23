from app import calculate_stock

def test_stock_calculation():
    assert calculate_stock(100, 20) == 80

def test_zero_sales():
    assert calculate_stock(50, 0) == 50
