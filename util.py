from typing import Any


def default_if_none(value: Any, default: Any):
    return default if value is None else value


def valid_comp(first: int, second: int) -> int:
    """
    Compares two values which can be either non-negative or -1.
    Any positive value is treated as smaller than -1.
    This function is a convenience function to simplify working with functions which return -1 on not found.

    :param first: The first value.
    :param second: The second value.
    :return: -1 if first is smaller than second, 0 if they are equal, 1 otherwise.
    """
    return 0 if first == second else (-1 if first != -1 and first < second or second == -1 else 1)


def valid_min(*elements: int) -> int:
    """
    Returns the smallest non-negative value or -1 if all are -1.
    This function is a convenience function to simplify working with functions which return -1 on not found.

    :param elements: The elements to be compared.
    :return: The she smallest non-negative value or -1 if all are -1.
    """
    if len(elements) == 1:
        return elements[0]

    first = elements[0]
    second = valid_min(*(elements[1:]))
    return first if valid_comp(first, second) < 0 else second
