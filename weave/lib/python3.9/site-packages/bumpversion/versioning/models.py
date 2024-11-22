"""Models for managing versioning of software projects."""

from __future__ import annotations

from collections import defaultdict, deque
from itertools import chain
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, model_validator

from bumpversion.exceptions import InvalidVersionPartError
from bumpversion.utils import key_val_string
from bumpversion.versioning.functions import CalVerFunction, NumericFunction, PartFunction, ValuesFunction


class VersionComponent:
    """
    Represent part of a version number.

    Determines the PartFunction that rules how the part behaves when increased or reset
    based on the configuration given.
    """

    def __init__(
        self,
        values: Optional[list] = None,
        optional_value: Optional[str] = None,
        first_value: Union[str, int, None] = None,
        independent: bool = False,
        always_increment: bool = False,
        calver_format: Optional[str] = None,
        source: Optional[str] = None,
        value: Union[str, int, None] = None,
    ):
        self._value = str(value) if value is not None else None
        self.func: Optional[PartFunction] = None
        self.always_increment = always_increment
        self.independent = True if always_increment else independent
        self.source = source
        self.calver_format = calver_format
        if values:
            str_values = [str(v) for v in values]
            str_optional_value = str(optional_value) if optional_value is not None else None
            str_first_value = str(first_value) if first_value is not None else None
            self.func = ValuesFunction(str_values, str_optional_value, str_first_value)
        elif calver_format:
            self.func = CalVerFunction(calver_format)
            self._value = self._value or self.func.first_value
        else:
            self.func = NumericFunction(optional_value, first_value or "0")

    @property
    def value(self) -> str:
        """Return the value of the part."""
        return self._value or self.func.optional_value

    def copy(self) -> "VersionComponent":
        """Return a copy of the part."""
        return VersionComponent(
            values=getattr(self.func, "_values", None),
            optional_value=self.func.optional_value,
            first_value=self.func.first_value,
            independent=self.independent,
            always_increment=self.always_increment,
            calver_format=self.calver_format,
            source=self.source,
            value=self._value,
        )

    def bump(self) -> "VersionComponent":
        """Return a part with bumped value."""
        new_component = self.copy()
        new_component._value = self.func.bump(self.value)
        return new_component

    def null(self) -> "VersionComponent":
        """Return a part with first value."""
        new_component = self.copy()
        new_component._value = self.func.first_value
        return new_component

    @property
    def is_optional(self) -> bool:
        """Is the part optional?"""
        return self.value == self.func.optional_value

    @property
    def is_independent(self) -> bool:
        """Is the part independent of the other parts?"""
        return self.independent

    def __format__(self, format_spec: str) -> str:
        try:
            val = int(self.value)
        except ValueError:
            return self.value
        else:
            return int.__format__(val, format_spec)

    def __repr__(self) -> str:
        return f"<bumpversion.VersionPart:{self.func.__class__.__name__}:{self.value}>"

    def __eq__(self, other: Any) -> bool:
        return self.value == other.value if isinstance(other, VersionComponent) else False


class VersionComponentSpec(BaseModel):
    """
    Configuration of a version component.

    This is used to read in the configuration from the bumpversion config file.
    """

    values: Optional[list] = None
    """The possible values for the component. If it and `calver_format` is None, the component is numeric."""

    optional_value: Optional[str] = None  # Optional.
    """The value that is optional to include in the version.

    - Defaults to first value in values or 0 in the case of numeric.
    - Empty string means nothing is optional.
    - CalVer components ignore this."""

    first_value: Union[str, int, None] = None
    """The first value to increment from."""

    independent: bool = False
    """Is the component independent of the other components?"""

    always_increment: bool = False
    """Should the component always increment, even if it is not necessary?"""

    calver_format: Optional[str] = None
    """The format string for a CalVer component."""

    # source: Optional[str] = None  # Name of environment variable or context variable to use as the source for value
    depends_on: Optional[str] = None
    """The name of the component this component depends on."""

    @model_validator(mode="before")
    @classmethod
    def set_always_increment_with_calver(cls, data: Any) -> Any:
        """Set always_increment to True if calver_format is present."""
        if isinstance(data, dict) and data.get("calver_format"):
            data["always_increment"] = True
        return data

    def create_component(self, value: Union[str, int, None] = None) -> VersionComponent:
        """Generate a version component from the configuration."""
        return VersionComponent(
            values=self.values,
            optional_value=self.optional_value,
            first_value=self.first_value,
            independent=self.independent,
            always_increment=self.always_increment,
            calver_format=self.calver_format,
            # source=self.source,
            value=value,
        )


class VersionSpec:
    """The specification of a version's components and their relationships."""

    def __init__(self, components: Dict[str, VersionComponentSpec], order: Optional[List[str]] = None):
        if not components:
            raise ValueError("A VersionSpec must have at least one component.")
        if not order:
            order = list(components.keys())
        if len(set(order) - set(components.keys())) > 0:
            raise ValueError("The order of components refers to items that are not in your components.")

        self.component_configs = components
        self.order = order
        self.dependency_map = defaultdict(list)
        previous_component = self.order[0]
        self.always_increment = [name for name, config in self.component_configs.items() if config.always_increment]
        for component in self.order[1:]:
            if self.component_configs[component].independent:
                continue
            elif self.component_configs[component].depends_on:
                self.dependency_map[self.component_configs[component].depends_on].append(component)
            else:
                self.dependency_map[previous_component].append(component)
            previous_component = component

    def create_version(self, values: Dict[str, str]) -> "Version":
        """Generate a version from the given values."""
        components = {
            key: comp_config.create_component(value=values.get(key))
            for key, comp_config in self.component_configs.items()
        }
        return Version(version_spec=self, components=components)

    def get_dependents(self, component_name: str) -> List[str]:
        """Return the parts that depend on the given part."""
        stack = deque(self.dependency_map.get(component_name, []), maxlen=len(self.order))
        visited = []

        while stack:
            e = stack.pop()
            if e not in visited:
                visited.append(e)
                stack.extendleft(self.dependency_map[e])

        return visited


class Version:
    """The specification of a version and its parts."""

    def __init__(
        self, version_spec: VersionSpec, components: Dict[str, VersionComponent], original: Optional[str] = None
    ):
        self.version_spec = version_spec
        self.components = components
        self.original = original

    def values(self) -> Dict[str, VersionComponent]:
        """Return the values of the parts."""
        return dict(self.components.items())

    def __getitem__(self, key: str) -> VersionComponent:
        return self.components[key]

    def __len__(self) -> int:
        return len(self.components)

    def __iter__(self):
        return iter(self.components)

    def __repr__(self):
        return f"<bumpversion.Version:{key_val_string(self.components)}>"

    def __eq__(self, other: Any) -> bool:
        return (
            all(value == other.components[key] for key, value in self.components.items())
            if isinstance(other, Version)
            else False
        )

    def required_components(self) -> List[str]:
        """Return the names of the parts that are required."""
        return [key for key, value in self.components.items() if value.value != value.func.optional_value]

    def bump(self, component_name: str) -> "Version":
        """Increase the value of the specified component, reset its dependents, and return a new Version."""
        if component_name not in self.components:
            raise InvalidVersionPartError(f"No part named {component_name!r}")

        new_values = dict(self.components.items())
        always_incr_values, components_to_reset = self._always_increment()
        new_values.update(always_incr_values)

        if component_name not in components_to_reset:
            new_values[component_name] = self.components[component_name].bump()
            components_to_reset |= set(self.version_spec.get_dependents(component_name))

        for component in components_to_reset:
            if not self.components[component].is_independent:
                new_values[component] = self.components[component].null()

        return Version(self.version_spec, new_values, self.original)

    def _always_incr_dependencies(self) -> dict:
        """Return the components that always increment and depend on the given component."""
        return {name: self.version_spec.get_dependents(name) for name in self.version_spec.always_increment}

    def _increment_always_incr(self) -> dict:
        """Increase the values of the components that always increment."""
        components = self.version_spec.always_increment
        return {name: self.components[name].bump() for name in components}

    def _always_increment(self) -> Tuple[dict, set]:
        """Return the components that always increment and their dependents."""
        values = self._increment_always_incr()
        dependents = self._always_incr_dependencies()
        for component_name, value in values.items():
            if value == self.components[component_name]:
                dependents.pop(component_name, None)
        unique_dependents = set(chain.from_iterable(dependents.values()))
        return values, unique_dependents
