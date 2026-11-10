"""Shared helper for the explicit state machines in this package.

Each lifecycle names its states in one ``Enum`` and its legal moves in one
transition table (``{state: {next_state, ...}}``). Every write goes through
``require_transition`` so an illegal move raises instead of leaving the object
in a state no reader expects.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, TypeVar

S = TypeVar("S", bound=Enum)


class IllegalTransition(RuntimeError):
    """A state change the machine's transition table does not allow."""

    def __init__(self, machine: str, current: Enum, target: Enum):
        super().__init__(f"{machine}: illegal transition {current.value} -> {target.value}")
        self.machine = machine
        self.current = current
        self.target = target


def require_transition(machine: str, table: Mapping[S, frozenset[S]], current: S, target: S) -> S:
    """Return ``target`` if ``current -> target`` is legal, else raise."""
    if target not in table[current]:
        raise IllegalTransition(machine, current, target)
    return target
