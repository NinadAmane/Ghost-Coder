# Define a function to add two numbers
def add(a, b):
    """
    This function adds two numbers.

    Args:
        a (int): The first number.
        b (int): The second number.

    Returns:
        int: The sum of a and b.
    """
    return a + b

# Define a function to subtract two numbers
def subtract(a, b):
    """
    This function subtracts two numbers.

    Args:
        a (int): The first number.
        b (int): The second number.

    Returns:
        int: The difference of a and b.
    """
    return a - b

# Define a function to multiply two numbers
def multiply(a, b):
    """
    This function multiplies two numbers.

    Args:
        a (int): The first number.
        b (int): The second number.

    Returns:
        int: The product of a and b.
    """
    return a * b

# Define a function to divide two numbers
def divide(a, b):
    """
    This function divides two numbers.

    Args:
        a (int): The first number.
        b (int): The second number.

    Returns:
        float: The quotient of a and b.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b