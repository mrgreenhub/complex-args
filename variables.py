from abc import ABC, abstractmethod
from copy import deepcopy
import random
import sys
from typing import Any, Dict, Optional, Sequence, Set, Union

from util import default_if_none


class Variable(ABC):
    """
    An abstract base class for variables.
    A variable is an object, which contains information that can be fixed under a container,
    which specifies the value space.
    """

    @abstractmethod
    def evaluate(self, container: Sequence, original_value: Optional[Any] = None) -> Set:
        """
        Evaluates the fix value of the variable under the given container's value space.
        If the original value is given, enables sampling without overlapping with the original value.

        :param container: The container which specifies the value space.
        :param original_value: The original value.
        """
        pass


class ResolveError(Exception):
    def __init__(self, variable: Variable, container: Sequence, message: str):
        super().__init__(f'Variable {variable} cannot be resolved in {container} with: {message}')

        self.variable = variable
        self.container = container
        self.message = message


class VariableContainer(ABC):
    """
    An abstract base class for containers which can handle both fix and variable values.
    It must be evaluated recursively in order to be safe to use.
    """

    @abstractmethod
    def evaluate(self, container: Sequence) -> None:
        """
        Evaluates the keys of this container using the given container (which can e.g. also be a range).
        If there are further levels of VariableContainers, they must be evaluated explicitly as well.

        :param container: The container, on which the variable keys in this container are evaluated.
        """
        pass


class VariableDict(dict, VariableContainer):
    """
    A dictionary, which handles both fix and variable values.
    It must be evaluated recursively in order to be safe to use.
    """

    def __init__(self, fixed_parts: Dict = None, variable_parts: Dict[Variable, Any] = None) -> None:
        super().__init__()
        self.fixed_parts = default_if_none(fixed_parts, {})
        self.variable_parts = default_if_none(variable_parts, {})
        self.update(self.fixed_parts)
        self.update(self.variable_parts)

    def __getnewargs__(self):
        return self.fixed_parts, self.variable_parts

    def __new__(cls, *args, **kwargs):
        new_inst = super().__new__(cls)
        new_inst.__init__(*args, **kwargs)
        new_inst.extra = []
        return new_inst

    def evaluate(self, container: Sequence) -> None:
        self.clear()
        self.update(self.fixed_parts)

        if self.variable_parts is not None:
            for variable_part, value in self.variable_parts.items():
                for variable in variable_part.evaluate(container):
                    if variable not in self:
                        self[variable] = value
                    else:
                        self[variable] = merge(self[variable], value)


class VariableSet(set, VariableContainer):
    """
    A set which handles both fix and variable values.
    It must be evaluated recursively in order to be safe to use.
    """

    def __init__(self, fixed_parts: Set = None, variable_parts: Set[Variable] = None) -> None:
        super().__init__()
        self.fixed_parts = default_if_none(fixed_parts, set())
        self.variable_parts = default_if_none(variable_parts, set())
        self.update(self.fixed_parts)
        self.update(self.variable_parts)

    def __getnewargs__(self):
        return self.fixed_parts, self.variable_parts

    def __new__(cls, *args, **kwargs):
        new_inst = super().__new__(cls)
        new_inst.__init__(*args, **kwargs)
        new_inst.extra = []
        return new_inst

    # Honestly I don't know why I do have to do this but otherwise this always ends up as "VariableSet(<what i want>)"
    def __repr__(self):
        return f'{{{", ".join(str(x) for x in self)}}}'

    def evaluate(self, container: Sequence) -> None:
        self.clear()
        self.update(self.fixed_parts)

        if self.variable_parts is not None:
            for variable_part in self.variable_parts:
                self.update(variable_part.evaluate(container))


def merge(first: Union[VariableDict, VariableSet],
          second: Union[VariableDict, VariableSet]) -> Union[VariableDict, VariableSet]:
    """
    Deeply merges two dictionaries or two sets into new objects.
    Because of otherwise possible inconsistencies, the result is a merged deep copy when the containers are dicts.
    This function assumes, that a dictionary only contains either other dictionaries or only sets.
    It further assumes that the depth of each entry is equal.

    :param first: The first container.
    :param second: The second container.
    :return: A new container which is a deep merge of the given containers.
    """
    if type(first) != type(second):
        raise ValueError('first and second must be compatible')

    if isinstance(first, VariableSet):
        return VariableSet(first.fixed_parts.union(second.fixed_parts),
                           first.variable_parts.union(second.variable_parts))
    else:
        new_first = deepcopy(first)
        new_second = deepcopy(second)
        fixed_parts = new_first.fixed_parts
        variable_parts = new_first.variable_parts

        for element in new_second.fixed_parts:
            if element not in fixed_parts:
                fixed_parts[element] = new_second[element]
            else:
                fixed_parts[element] = merge(fixed_parts[element], new_second[element])

        for element in new_second.variable_parts:
            if element not in variable_parts:
                variable_parts[element] = new_second[element]
            else:
                variable_parts[element] = merge(variable_parts[element], new_second[element])

        return VariableDict(fixed_parts, variable_parts)


class LeaveVariable(Variable, ABC):
    """
    An abstract base class for leave variables, i.e. variables, which are always evaluated to single values,
    i.e. to a set with only one element.
    """
    pass


class IndexVariable(LeaveVariable):
    """
    A variable which represents an index.
    """

    def __init__(self, index: int) -> None:
        """
        Initializes the variable with the given index.

        :param index: The index.
        """
        self._index = index

    def __repr__(self):
        return f'INDEX({self._index})'

    def evaluate(self, container, original_value=None) -> Set:
        return {container[self._index]}


class SizeVariable(LeaveVariable):
    """
    A variable which represents the size of a container.
    """

    def __repr__(self):
        return 'SIZE'

    def evaluate(self, container, original_value=None) -> Set:
        return {len(container)}


class ConstantVariable(LeaveVariable):
    """
    A pseudo-variable which represent a constant value as a variable.
    Hence evaluating this variable will always return its internal value.
    """

    def __init__(self, value: Any) -> None:
        """
        Initializes the constant with the given value.

        :param value: The constant value.
        """
        self._value = value

    def __repr__(self):
        return f'CONST({self._value})'

    def evaluate(self, container, original_value=None) -> Set:
        return {self._value}


class AllVariable(Variable):
    """
    A variable which represents all elements.
    """

    def __repr__(self):
        return 'ALL'

    def evaluate(self, container, original_value=None) -> Set:
        return set(container)


class RangeVariable(Variable):
    """
    A variable which represents a range with partly or completely variable limits.
    """

    def __init__(self, first: Union[LeaveVariable, int], last: Union[LeaveVariable, int]) -> None:
        """
        Initializes the variable with the two limits, both of which are included in the range.
        Both limits can be either a leave variable or a fix index.

        :param first: The lower limit of the range.
        :param last: The upper limit of the range.
        """
        self._first = first
        self._last = last

    def __repr__(self):
        return f'RANGE({self._first}, {self._last})'

    def evaluate(self, container, original_value=None) -> Set:
        first = self._first
        last = self._last

        try:
            first = first.evaluate(container).pop()
        except AttributeError:
            pass

        try:
            last = last.evaluate(container).pop()
        except AttributeError:
            pass

        return set(range(first, last + 1))


class SampleVariable(Variable):
    """
    A variable which represents a sample of given size.
    """

    def __init__(self, n: int, exclude_original: bool):
        """
        Initializes the variable with the sample size.

        :param n: The sample size.
        :param exclude_original: Exclude original value from sampling.
        """
        self._n = n
        self._exclude_original = exclude_original
        self._id = random.randint(0, sys.maxsize)

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self._id == other._id

    def __hash__(self):
        return hash(hash(self._id) + hash(self.__class__))

    def __repr__(self):
        return f'SAMPLE({self._n})'

    def evaluate(self, container, original_value=None) -> Set:
        if not self._exclude_original:
            if self._n > (lc := len(container)):
                raise ResolveError(self, container, f'Cannot draw {self._n} values from {lc} values!')

            return set(random.sample(container, self._n))
        else:
            if original_value is None:
                raise ResolveError(self, container, f'Sampling without overlapping is not supported here!')

            if self._n + 1 > (lc := len(container)):
                raise ResolveError(self, container,
                                   f'Cannot draw {self._n} values from {lc} values without overlapping!')

            result = set(random.sample(container, self._n + 1))

            if original_value in result:
                result.remove(original_value)
            else:
                result.pop()

            return result


class RandomVariable(LeaveVariable, SampleVariable):
    """
    A special case of the sample variable, where only one value is sampled.
    """

    def __init__(self, exclude_original: bool):
        """
        Initializes the variable.

        :param exclude_original: Exclude original value from sampling.
        """
        super().__init__(1, exclude_original)

    def __repr__(self):
        return f'RANDOM'
