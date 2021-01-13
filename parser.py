from __future__ import annotations

from typing import Any, Callable, List, Union

from util import valid_comp, valid_min
from variables import AllVariable, IndexVariable, RandomVariable, RangeVariable, SampleVariable, SizeVariable, \
    Variable, VariableDict, VariableSet, merge

# Default syntax specifiers
_default_listing_delimiter = ','
_default_range_delimiter = '~'
_default_level_opener = ':['
_default_level_closer = ']'
_default_level_delimiter = ','
_default_lazy_opener = ':'

# Default variable specifiers
_default_index_specifier = '#'
_default_random_specifier = '?'
_default_all_specifier = '*'


class ParseError(Exception):
    def __init__(self, position: int, message: str):
        super().__init__(f'At {position}: {message}')

        self.position = position
        self.message = message


def convert(value: str, level_type_converter: Callable, index_specifier=_default_index_specifier,
            random_specifier=_default_random_specifier,
            all_specifier=_default_all_specifier, overall_position: int = 0) -> Union[Variable, Any]:
    """
    Converts a value to either a variable or to the intended type using the given specifiers to determine special
    values or the given type converter respectively.

    :param value: The value to be converted.
    :param level_type_converter: The function which transforms the string values to their intended type.
    :param index_specifier: The string which prefixes an index. If repeated twice, then this denotes the size.
    :param random_specifier: The string which denotes "random" or prefixes a number which denotes the number of samples.
                             If it is repeated twice, then this denotes sampling without the original value.
    :param all_specifier: The string which denotes "all".
    :param overall_position: Tells the parser, where i currently is in the whole parsed string.
                             Typically this should not be set manually.
    :return: Either a variable or the type converted value.
    """
    if value.startswith(index_specifier):
        if value.startswith(index_specifier * 2):
            return SizeVariable()
        else:
            return IndexVariable(int(value[len(index_specifier):]))

    if value.startswith(random_specifier):
        exclude_original = value.startswith(random_specifier * 2)
        if value == random_specifier:
            return RandomVariable(exclude_original)
        else:
            return SampleVariable(int(value[len(random_specifier):]), exclude_original)

    if value == all_specifier:
        return AllVariable()

    try:
        return level_type_converter(value)
    except Exception:
        raise ParseError(overall_position, f'The value "{value}" cannot be converted to a variable or with the type '
                                            f'converter {level_type_converter}!')


def unravel(listing: str, level_type_converter: Callable, listing_delimiter: str = _default_listing_delimiter,
            range_delimiter: str = _default_range_delimiter, index_specifier: str = _default_index_specifier,
            random_specifier: str = _default_random_specifier,
            all_specifier: str = _default_all_specifier, overall_position: int = 0) -> VariableSet:
    """
    Returns a set of values, according to the given listing where the values are unraveled.
    Values are therefore unique and do not occur multiple times in the output.
    Supported are listings of ranges and single values.
    If ranges are used, the converter must transform the value to an object
    which can be used as start and end point in the builtin range function and which supports addition.

    :param listing: The listing which specifies the values to return.
    :param level_type_converter: The function which transforms the string values to their intended type.
    :param listing_delimiter: The string which delimits single ranges and values.
    :param range_delimiter: The string which delimits endpoints of ranges.
    :param index_specifier: The string which prefixes an index. If repeated twice, then this denotes the size.
    :param random_specifier: The string which denotes "random" or prefixes a number which denotes the number of samples.
                             If it is repeated twice, then this denotes sampling without the original value.
    :param all_specifier: The string which denotes "all".
    :param overall_position: Tells the parser, where i currently is in the whole parsed string.
                             Typically this should not be set manually.
    :return: A set of values, according to the given listing.
    """
    fixed_parts = set()
    variable_parts = set()

    def _convert(value, position):
        return convert(value, level_type_converter, index_specifier, random_specifier, all_specifier, position)

    if len(listing) > 0:
        for range_element in listing.split(listing_delimiter):
            if range_delimiter in range_element:
                first_tmp, last_tmp = range_element.split(range_delimiter)
                first = _convert(first_tmp, overall_position)
                last = _convert(last_tmp, overall_position + len(first_tmp) + len(range_delimiter))

                if isinstance(first, Variable) or isinstance(last, Variable):
                    variable_parts.add(RangeVariable(first, last))

                else:
                    for element in range(first, last + 1):
                        fixed_parts.add(element)
            else:
                element = _convert(range_element, overall_position)

                if isinstance(element, Variable):
                    variable_parts.add(element)
                else:
                    fixed_parts.add(element)

            overall_position += len(range_element) + len(listing_delimiter)

    return VariableSet(fixed_parts, variable_parts)


def parse_tree(tree: str, level_type_converters: List[Callable],
               level_opener: str = _default_level_opener, lazy_opener: str = _default_lazy_opener,
               level_closer: str = _default_level_closer, level_delimiter: str = _default_level_delimiter,
               listing_delimiter: str = _default_listing_delimiter, range_delimiter: str = _default_range_delimiter,
               index_specifier: str = _default_index_specifier, random_specifier: str = _default_random_specifier,
               all_specifier: str = _default_all_specifier,
               overall_position: int = 0) -> Union[VariableDict, VariableSet]:
    """
    Parses a string which denotes a tree structured container in the way defined by the remaining arguments and returns
    a dictionary or set, which implements the tree, as denoted by the given string, where all values are unraveled.
    This function assumes, that the tree has equal depth and that on each level of the tree,
    all elements have the same type.
    It further assumes, that elements in the tree are compatible with the functionality provided by unravel().

    :param tree: The string which denotes the tree structured container.
    :param level_type_converters: The functions which transform the string values to their intended type.
    :param level_opener: The string which delimits two levels at the start of a deeper level.
    :param lazy_opener: The string which delimits two levels when closing brackets can be omitted.
    :param level_closer: The string which delimits two levels at the end of a deeper level.
    :param level_delimiter: The string which delimits two elements at the same level.
    :param listing_delimiter: The string which delimits single ranges and values.
    :param range_delimiter: The string which delimits endpoints of ranges.
    :param index_specifier: The string which prefixes an index. If repeated twice, then this denotes the size.
    :param random_specifier: The string which denotes "random" or prefixes a number which denotes the number of samples.
                             If it is repeated twice, then this denotes sampling without the original value.
    :param all_specifier: The string which denotes "all".
    :param overall_position: Tells the parser, where i currently is in the whole parsed string.
                             Typically this should not be set manually.
    :return: The dictionary or set, which implements the tree, as denoted by the given string.
    """
    # If a leave
    if len(level_type_converters) == 1:
        return unravel(tree, level_type_converters[0], listing_delimiter, range_delimiter, index_specifier,
                       random_specifier, all_specifier,  overall_position)

    result = VariableDict()

    def remove_trailing_lazy_openers(stack: List):
        while len(stack) > 0 and stack[-1] == lazy_opener:
            stack.pop()

    while True:
        next_roots: str
        tail: str

        first_opener = tree.find(level_opener)
        first_lazy_opener = tree.find(lazy_opener)
        first_opener_symbol = level_opener
        stack: List[str] = []

        # Convenience for lazy argument
        if valid_comp(first_lazy_opener, first_opener) < 0:
            next_roots, tail = tree.split(lazy_opener, 1)
            stack.append(lazy_opener)
            first_opener_symbol = lazy_opener
        elif first_opener > -1:
            next_roots, tail = tree.split(level_opener, 1)
            stack.append(level_opener)
        else:
            next_closer = valid_min(tree.find(level_closer), len(tree))
            raise ParseError(overall_position + next_closer,
                             f'At least one more level required or level opener ( "{level_opener}" ) '
                             f'or lazy opener ( "{lazy_opener}" ) missing!')

        # find corresponding level closer to the level opener
        current_position = 0
        done = False

        while True:
            next_opener = tail.find(level_opener, current_position)
            next_lazy_opener = tail.find(lazy_opener, current_position)
            next_closer = tail.find(level_closer, current_position)
            next_opener_symbol = level_opener
            terminal = False

            if valid_comp(next_lazy_opener, next_opener) < 0:
                next_opener = next_lazy_opener
                next_opener_symbol = lazy_opener

            if next_closer == -1:
                terminal = True

            if valid_comp(next_opener, next_closer) < 0:
                stack.append(next_opener_symbol)
                current_position = next_opener + len(next_opener_symbol)
            else:
                remove_trailing_lazy_openers(stack)

                if not terminal:
                    stack.pop()

                if terminal or next_closer + len(level_closer) == len(tail):
                    remove_trailing_lazy_openers(stack)
                    done = True

                    if len(stack) > 0:
                        raise ParseError(overall_position + len(tail),
                                          f'Expected one or more level closers ( "{level_closer}" )!')

                if len(stack) == 0:
                    if terminal:
                        current_position = len(tail)
                        done = True
                    else:
                        current_position = next_closer
                    break

                current_position = next_closer + len(level_closer)

        sub_trees = tail[:current_position]
        print(sub_trees)
        sub_trees_processed = parse_tree(sub_trees, level_type_converters[1:], level_opener, lazy_opener, level_closer,
                                         level_delimiter, listing_delimiter, range_delimiter, index_specifier,
                                         random_specifier, all_specifier,
                                         overall_position + len(next_roots) + len(first_opener_symbol))

        roots_unraveled = unravel(next_roots, level_type_converters[0], listing_delimiter, range_delimiter,
                                  index_specifier, random_specifier, all_specifier,  overall_position)

        result = merge(result, VariableDict(dict.fromkeys(roots_unraveled.fixed_parts, sub_trees_processed),
                                            dict.fromkeys(roots_unraveled.variable_parts, sub_trees_processed)))

        if done:
            break
        else:
            shift = current_position + len(level_closer) + len(level_delimiter)
            tree = tail[shift:]
            overall_position += first_lazy_opener + len(first_opener_symbol) + shift

    return result
