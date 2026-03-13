import sys
import calculator

def test():
    assert calculator.add(2, 3) == 5, 'Add function is not working correctly'
    assert calculator.add(-2, 3) == 1, 'Add function is not working correctly with negative numbers'
    assert calculator.add(-2, -3) == -5, 'Add function is not working correctly with two negative numbers'

if __name__ == '__main__':
    test()
    sys.exit(0)
