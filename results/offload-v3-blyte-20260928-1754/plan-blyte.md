# Implementation Plan: State-Scoped Data Ownership and Lifecycle

## Overview

Currently, states in `python-statemachine` lack built-in scoped data ownership, requiring manual variable management on the machine or model without lifecycle management (initialization, cleanup, history snapshotting/restoring) or hierarchical scoping.

This plan introduces state-scoped data ownership:
- Declarative `data` on `State`, `State.Compound`, `State.Parallel`, and SCXML.
- `DataVar` specification with type enforcement and factories.
- Scoped lifecycle: fresh initialization on state entry, persistence across `on_enter` and `on_exit` callbacks, cleanup on state exit, reset on normal re-entry.
- History recall restoring data snapshots (deep for full descendants, shallow for direct children).
- Hierarchical scoping (merging ancestor data into child callbacks with child shadowing parent, parallel regions isolated) and `state_data` injection.
- Methods `get_state_data(state)`, `set_state_data(state, key, value)`, property `state_data_values`, change tracking with `get_data_changes()` returning `DataChangeInfo` records cleared at macrostep boundaries.
- Full serialization/pickle support, SCXML parsing of literals, and diagram annotation.

---

## 1. Git Workflow

Before starting implementation:
```bash
git checkout -b feature/state-data main
```
When complete, add all modified and new files and commit:
```bash
git add -A
git commit -m "feat: implement state-scoped data ownership, lifecycle, and scoping"
```

---

## 2. Files to Create and Modify

### 2.1. NEW FILE: `statemachine/data.py`
Create `statemachine/data.py` containing:

1. **`_MISSING` sentinel**:
   ```python
   _MISSING = object()
   ```

2. **`DataChangeInfo` dataclass**:
   ```python
   from dataclasses import dataclass
   from typing import Any

   @dataclass(frozen=True)
   class DataChangeInfo:
       state_id: str
       key: str
       old_value: Any
       new_value: Any
   ```

3. **`_check_type(value: Any, expected_type: Any) -> bool` helper**:
   - Handles `type` (e.g. `int`, `str`), `tuple` of types (e.g. `(int, float)`).
   - Handles `typing.Union`, `typing.Optional`, and Python 3.10+ `types.UnionType` (`int | str`) via `typing.get_origin` and `typing.get_args`.
   - Rejects boolean `True`/`False` when `expected_type is int` (since `bool` is a subclass of `int` in Python, but semantically distinct).
   - Returns `True` if `value` matches `expected_type`, `False` otherwise.

4. **`DataVar` class**:
   ```python
   from typing import Any, Callable, Optional, Tuple, Type
   from .exceptions import InvalidDefinition

   class DataVar:
       def __init__(
           self,
           default: Any = _MISSING,
           *,
           factory: Optional[Callable[[], Any]] = None,
           default_factory: Optional[Callable[[], Any]] = None,
           type: Optional[Any] = None,
       ):
           actual_factory = factory if factory is not None else default_factory
           if default is not _MISSING and actual_factory is not None:
               raise InvalidDefinition("DataVar rejects simultaneous default and factory.")
           if actual_factory is not None and not callable(actual_factory):
               raise InvalidDefinition("DataVar factory must be callable.")

           self.default = None if default is _MISSING else default
           self._has_default = default is not _MISSING
           self.factory = actual_factory
           self.type = type

           if self._has_default and self.type is not None and self.default is not None:
               if not _check_type(self.default, self.type):
                   raise InvalidDefinition(
                       f"Default value {self.default!r} does not match DataVar type constraint {self.type}."
                   )

       def create_initial_value(self) -> Any:
           if self.factory is not None:
               val = self.factory()
           elif self._has_default:
               import copy
               val = copy.deepcopy(self.default)
           else:
               val = None

           if self.type is not None and val is not None:
               if not _check_type(val, self.type):
                   raise InvalidDefinition(
                       f"Initial value {val!r} does not match DataVar type constraint {self.type}."
                   )
           return val
   ```

5. **`ScopedData` dict wrapper**:
   Inherits from `dict`. Pre-populated with the merged ancestor + current state data.
   Overriding `__setitem__(self, key: str, value: Any)`:
   - Identifies which state in the scope chain declared `key` (checking `self._state` first, then ancestors in order). If not found, defaults to `self._state`.
   - Calls `self._machine.set_state_data(target_state, key, value)` (which performs active state, declared key, and DataVar type validation, and logs `DataChangeInfo`).
   - Updates `super().__setitem__(key, value)`.

---

### 2.2. MODIFY: `statemachine/__init__.py`
- Import and export `DataVar` and `DataChangeInfo`:
  ```python
  from .data import DataChangeInfo
  from .data import DataVar
  ```
- Add `"DataVar"` and `"DataChangeInfo"` to `__all__`.

---

### 2.3. MODIFY: `statemachine/state.py`
1. **Update `State.__init__`**:
   - Accept `data: Optional[Dict[str, Any]] = None`.
   - Validation:
     ```python
     if data is not None:
         if not isinstance(data, dict):
             raise InvalidDefinition(_("'data' must be a dict."))
         for key, val in data.items():
             if not isinstance(key, str):
                 raise InvalidDefinition(_("State data keys must be strings."))
             if isinstance(val, DataVar) and val._has_default and val.type is not None and val.default is not None:
                 if not _check_type(val.default, val.type):
                     raise InvalidDefinition(
                         _("Default value does not match DataVar type constraint.")
                     )
         self.data = dict(data)
     else:
         self.data = {}
     ```
   - Crucial: `self.data` on `State` holds only declared templates/defaults. It is NEVER mutated at runtime. Active values are stored per `StateMachine` instance.

2. **Update `InstanceState`**:
   - Add property `data`:
     ```python
     @property
     def data(self):
         machine = self._machine()
         if machine is not None:
             return machine.get_state_data(self._state)
         return None
     ```

3. **`NestedStateFactory`**:
   - `NestedStateFactory` already passes `**inherited_kwargs` to `State(...)`. When `class MyCompound(State.Compound, data={...}):` is declared, `kwargs` has `data`, which automatically passes into `State.__init__(data=...)`. No extra changes required here.

---

### 2.4. MODIFY: `statemachine/event.py`
- Add `"state_data"` to `_event_data_kwargs`:
  ```python
  _event_data_kwargs = {
      "event_data",
      "machine",
      "event",
      "model",
      "transition",
      "state",
      "source",
      "target",
      "state_data",
  }
  ```

---

### 2.5. MODIFY: `statemachine/event_data.py`
- In `EventData`:
  - Add property `state_data`:
    ```python
    @property
    def state_data(self) -> Dict[str, Any]:
        return self.machine._get_scoped_data(self.state)
    ```
  - In `extended_kwargs`:
    ```python
    kwargs["state_data"] = self.state_data
    ```

---

### 2.6. MODIFY: `statemachine/statemachine.py`
1. **Initialize StateMachine Instance Data Attributes in `__init__`**:
   ```python
   self._active_state_data: Dict[str, Dict[str, Any]] = {}
   self.history_data: Dict[str, Dict[str, Dict[str, Any]]] = {}
   self._data_changes: List[DataChangeInfo] = []
   self._pending_history_restores: Dict[str, Dict[str, Any]] = {}
   ```

2. **Helper Methods on `StateMachine`**:
   - **`_resolve_state(self, state: "State | InstanceState | str") -> State`**:
     Resolves an input state (State, InstanceState, state ID string, or state value string) to a `State` instance. Searches `self.states_map` (by value and by `id`). Raises `InvalidDefinition` if unknown.
   - **`_init_state_data(self, state: State) -> None`**:
     Initializes fresh defaults for `state` in `self._active_state_data[state.id]`:
     - If spec is `DataVar`: `spec.create_initial_value()`.
     - Else if `callable(spec)`: `spec()`.
     - Else: `copy.deepcopy(spec)`.
   - **`_get_scoped_data(self, state: Optional[State]) -> ScopedData`**:
     Computes merged hierarchical scope:
     ```python
     if state is None:
         return ScopedData({}, self, None)
     scoped: Dict[str, Any] = {}
     for ancestor in reversed(list(state.ancestors())):
         if ancestor.id in self._active_state_data:
             scoped.update(self._active_state_data[ancestor.id])
     if state.id in self._active_state_data:
         scoped.update(self._active_state_data[state.id])
     return ScopedData(scoped, self, state)
     ```
     *Note on Parallel Regions*: Because parallel regions are siblings (not in each other's `ancestors()`), they naturally isolate scopes while both inheriting from parent parallel state ancestors.
   - **`_clear_data_changes(self) -> None`**:
     `self._data_changes.clear()`

3. **Public API Methods on `StateMachine`**:
   - **`get_state_data(self, state: "State | InstanceState | str") -> Optional[Dict[str, Any]]`**:
     Resolves `state`. If the state is currently active (`s.id in self._active_state_data`), returns the active data dict `self._active_state_data[s.id]`. Otherwise returns `None`.
   - **`state_data_values` property**:
     ```python
     @property
     def state_data_values(self) -> Dict[str, Dict[str, Any]]:
         return {
             state_id: copy.deepcopy(data)
             for state_id, data in self._active_state_data.items()
         }
     ```
   - **`set_state_data(self, state: "State | InstanceState | str", key: str, value: Any) -> None`**:
     1. Resolve `state` to `s: State`.
     2. Validate active: `if s.id not in self._active_state_data: raise InvalidDefinition(...)`.
     3. Validate declared key: `if not s.data or key not in s.data: raise InvalidDefinition(...)`.
     4. Validate DataVar type constraint: if `isinstance(s.data[key], DataVar)` and `s.data[key].type is not None`: if not `_check_type(value, s.data[key].type)`: `raise InvalidDefinition(...)`.
     5. Retrieve `old_value = self._active_state_data[s.id].get(key)`.
     6. Set `self._active_state_data[s.id][key] = value`.
     7. Append `DataChangeInfo(state_id=s.id, key=key, old_value=old_value, new_value=value)` to `self._data_changes`.
   - **`get_data_changes(self) -> List[DataChangeInfo]`**:
     `return list(self._data_changes)`

4. **Serialization (`__getstate__` and `__setstate__`)**:
   - `self._active_state_data`, `self.history_data`, and `self._data_changes` are in `self.__dict__` and contain only primitives, dicts, and `DataChangeInfo`. They survive `pickle.dumps` and `pickle.loads` naturally.
   - In `__setstate__`, `self.__dict__.update(state)` restores them. Since `self.sm.current_state_value is not None` when deserialized from a running machine, `_engine.start()` will not re-activate the initial state, preserving the unpickled data.

---

### 2.7. MODIFY: `statemachine/engines/base.py`, `sync.py`, and `async_.py`

1. **Macrostep Boundary Change Tracking**:
   - In `SyncEngine.processing_loop` and `AsyncEngine.processing_loop`:
     When `self._macrostep_count += 1` occurs, call `self.sm._clear_data_changes()`.
   - In `SyncEngine.activate_initial_state` and `AsyncEngine.activate_initial_state`:
     Call `self.sm._clear_data_changes()` at the start of initial activation.

2. **History Snapshotting in `_prepare_exit_states` (`BaseEngine`)**:
   ```python
   for info in ordered_states:
       state = info.state
       for history in state.history:
           if history.type.is_deep:
               history_value = [s for s in self.sm.configuration if s.is_descendant(state)]
           else:  # shallow history
               history_value = [s for s in self.sm.configuration if s.parent == state]

           self.sm.history_values[history.id] = history_value
           # Snapshot data for these history states:
           self.sm.history_data[history.id] = {
               s.id: copy.deepcopy(self.sm._active_state_data[s.id])
               for s in history_value
               if s.id in self.sm._active_state_data
           }
   ```

3. **History Recall in `add_descendant_states_to_enter` (`BaseEngine`)**:
   When `state and state.is_history` and `state.id in self.sm.history_values`:
   ```python
   if state.id in self.sm.history_data:
       self.sm._pending_history_restores.update(
           copy.deepcopy(self.sm.history_data[state.id])
       )
   ```

4. **Lifecycle in `_enter_states` (`BaseEngine` and `AsyncEngine`)**:
   For each `info` in `ordered_states`:
   - `target = info.state`
   - **Initialize Data**:
     ```python
     if target.id in self.sm._pending_history_restores:
         restored = self.sm._pending_history_restores.pop(target.id)
         self.sm._active_state_data[target.id] = copy.deepcopy(restored)
     else:
         self.sm._init_state_data(target)
     ```
   - **Add to Configuration**: `self._add_state_to_configuration(target)`
   - **Prepare Callbacks**:
     `args, kwargs = self._get_args_kwargs(transition, trigger_data, target=target)`
     Ensure `kwargs["state"] = target` and `kwargs["state_data"] = self.sm._get_scoped_data(target)`.
   - **Execute `target.enter` Callback**: Data persists and is fully accessible inside `on_enter`.

5. **Lifecycle in `_exit_states` (`BaseEngine` and `AsyncEngine`)**:
   For each `info` in `ordered_states`:
   - `args, kwargs = self._get_args_kwargs(info.transition, trigger_data)`
   - `kwargs = kwargs.copy()`
   - `kwargs["state"] = info.state`
   - `kwargs["state_data"] = self.sm._get_scoped_data(info.state)`
   - **Execute `info.state.exit` Callback**: Data persists and is fully accessible inside `on_exit`.
   - **Remove from Configuration**: `self._remove_state_from_configuration(info.state)`
   - **Remove Data**:
     ```python
     if info.state is not None and info.state.id in self.sm._active_state_data:
         del self.sm._active_state_data[info.state.id]
     ```

6. **Available Transitions Check**:
   In `SyncEngine.select_transitions` and `AsyncEngine.select_transitions` where conditions are evaluated:
   Pass `extended_kwargs["state_data"] = sm._get_scoped_data(state)`.

---

### 2.8. MODIFY: SCXML Integration (`statemachine/io/scxml/`)
1. **`statemachine/io/scxml/schema.py`**:
   Add `data: Dict[str, Any] = field(default_factory=dict)` to `State`.
2. **`statemachine/io/scxml/parser.py`**:
   In `parse_state`:
   Parse `<datamodel><data id="..." expr="..."/></datamodel>` and `<data id="..." expr="..."/>` children of `state_elem`.
   Parse `expr` as a Python literal via `ast.literal_eval`:
   ```python
   for dm_elem in state_elem.findall("datamodel"):
       for data_elem in dm_elem.findall("data"):
           data_id = data_elem.get("id")
           expr = data_elem.get("expr")
           if data_id:
               if expr is not None:
                   try:
                       val = ast.literal_eval(expr)
                   except (ValueError, SyntaxError):
                       val = expr
               else:
                   val = None
               state.data[data_id] = val
   ```
   In `_find_own_datamodel_elements(root)`:
   Ensure `<datamodel>` elements nested inside `<state>`, `<parallel>`, or `<final>` elements are skipped so they remain state-scoped rather than root-scoped.
3. **`statemachine/io/scxml/processor.py`**:
   In `_process_state(state)`:
   If `state.data`: `state_dict["data"] = state.data`.
4. **`statemachine/io/__init__.py`**:
   In `BaseStateKwargs` and `StateDefinition`:
   Add `data: Optional[Dict[str, Any]] = None`.

---

### 2.9. MODIFY: Diagram Annotation (`statemachine/contrib/diagram/`)
1. **`statemachine/contrib/diagram/model.py`**:
   Add `DATA = "data"` to `ActionType`.
2. **`statemachine/contrib/diagram/extract.py`**:
   In `_extract_state_actions(state: "State", getter) -> List[DiagramAction]`:
   If `getattr(state, "data", None)`:
   For `key, val` in `state.data.items()`:
   Format the variable representation (e.g. `key = 0`, `key: int`, or `key = factory()`):
   ```python
   if isinstance(val, DataVar):
       if val.factory is not None:
           fname = getattr(val.factory, "__name__", str(val.factory))
           body = f"{key} = {fname}()"
       elif val._has_default:
           body = f"{key} = {val.default!r}"
       elif val.type is not None:
           tname = getattr(val.type, "__name__", str(val.type))
           body = f"{key}: {tname}"
       else:
           body = f"{key}"
   elif callable(val):
       fname = getattr(val, "__name__", str(val))
       body = f"{key} = {fname}()"
   else:
       body = f"{key} = {val!r}"
   actions.append(DiagramAction(type=ActionType.DATA, body=body))
   ```
3. **`statemachine/contrib/diagram/renderers/mermaid.py` and `renderers/dot.py`**:
   In `_format_action(self, action: DiagramAction) -> str`:
   ```python
   if action.type == ActionType.DATA:
       return f"data / {action.body}"
   ```
   Both Dot (HTML table / compound label) and Mermaid (`{state.id} : {action}`) will now display `data / {body}`.
   In `mermaid.py` `_render_compound_state`:
   Ensure actions on compound states are rendered inside the compound block.

---

## 3. Edge Cases to Handle

1. **Declaration Validations**:
   - `data` is not a `dict` (e.g. `data=["a"]`): raises `InvalidDefinition`.
   - `data` has non-string key (e.g. `{1: "value"}`): raises `InvalidDefinition`.
   - `DataVar(default=..., factory=...)` has both: raises `InvalidDefinition`.
   - `DataVar(factory="not_callable")`: raises `InvalidDefinition`.
   - `DataVar(default="abc", type=int)` default violates type: raises `InvalidDefinition`.
2. **Runtime State Data Mutation (`set_state_data`)**:
   - Setting data on inactive state: raises `InvalidDefinition`.
   - Setting undeclared key: raises `InvalidDefinition`.
   - Setting value that violates DataVar type (e.g. setting `str` where `int` is expected, or setting `bool` where `int` is expected): raises `InvalidDefinition`.
   - Setting data when state is referenced by `State`, `InstanceState`, or `str` (id or value): all supported.
3. **Scoping**:
   - **Ancestry merging**: Child callback receives merged ancestors + child data. Child shadows parent keys.
   - **Parallel isolation**: Active state in Region 1 receives data from Region 1 and Parallel Parent, but CANNOT see data declared in Region 2.
   - **Transition callbacks**: `before`, `validators`, and `cond` receive source state scope; `after` receives target state scope.
4. **Lifecycle & Clean Re-entry**:
   - Re-entering a state without history resets data to a fresh copy of defaults (or re-invokes factory callables). No residue from prior activation.
   - Mutating a plain default (like an in-place list append) during an entry must not mutate the declaration or subsequent entries.
5. **History Recall**:
   - **Deep history**: Snapshots all descendant states in configuration when exiting; restores snapshots on recall.
   - **Shallow history**: Snapshots direct children only. If a direct child is compound, it restores the direct child's snapshot, but nested grandchildren re-initialize with fresh defaults.
6. **Pickling / Deepcopying**:
   - Running machine unpickled maintains `get_state_data()`, `state_data_values`, `_data_changes`, and `history_data`.
7. **Change Tracking Boundary**:
   - `get_data_changes()` returns changes from the current macrostep.
   - When the next event is popped from the external queue (or during initial activation), `_data_changes` is cleared.

---

## 4. Tests to Add

Create a comprehensive test suite in `tests/test_state_data.py`:

1. **`TestStateDataDeclaration`**:
   - Valid dictionary with primitive types, factories, and `DataVar`.
   - Non-dict `data` raises `InvalidDefinition`.
   - Non-string keys raise `InvalidDefinition`.
   - `DataVar` with both default and factory raises `InvalidDefinition`.
   - `DataVar` with invalid factory raises `InvalidDefinition`.
   - `DataVar` with mismatching default and type raises `InvalidDefinition`.
   - Compound state with `data` via metaclass keyword (`class Compound(State.Compound, data={...})`).
   - Parallel state with `data` via metaclass keyword (`class Parallel(State.Parallel, data={...})`).

2. **`TestStateDataLifecycle`**:
   - Initial state data initializes on startup.
   - Plain callables and `DataVar(factory=...)` called per entry.
   - Data persists and is accessible in `on_enter` and `on_exit`.
   - On exit, data is removed (`get_state_data` returns `None`).
   - Re-entering without history resets data to defaults.
   - Stored per instance: two SM instances have independent state data; mutating one does not mutate the other.

3. **`TestStateDataScoping`**:
   - Hierarchical: Child `on_enter` sees merged ancestor data.
   - Shadowing: Child key overrides parent key.
   - Parallel: Parallel region 1 cannot see parallel region 2 data.
   - Callback injection: `state_data` parameter receives dictionary in `on_enter`, `on_exit`, `before`, `on`, `after`, and condition checks.
   - `event_data.state_data` property matches callback injection.

4. **`TestGetSetStateDataAndChanges`**:
   - `get_state_data(state)` returns active dict or None.
   - `state_data_values` returns deepcopy snapshot mapping `state_id -> dict`.
   - `set_state_data` with valid key and type updates data and logs `DataChangeInfo`.
   - `set_state_data` on inactive state raises `InvalidDefinition`.
   - `set_state_data` with undeclared key raises `InvalidDefinition`.
   - `set_state_data` violating `DataVar(type=...)` raises `InvalidDefinition`.
   - `get_data_changes()` returns `DataChangeInfo(state_id, key, old_value, new_value)`.
   - Macrostep boundary: changes accumulate across microsteps within a macrostep, and clear when the next external event is processed.

5. **`TestHistoryRecallData`**:
   - Deep history recall: Nested descendants restore modified data snapshots.
   - Shallow history recall: Direct child restores snapshot; grandchild enters fresh default.
   - Clean entry without history restores defaults.

6. **`TestPickleAndDeepcopy`**:
   - Machine with active data, modified values, and history snapshots survives `pickle.dumps` / `pickle.loads` and `copy.deepcopy`.

7. **`TestSCXMLDataParsing`**:
   - SCXML with `<state id="s1"><datamodel><data id="n" expr="42"/><data id="s" expr="'foo'"/></datamodel></state>`.
   - Verifies parsed Python literals (`42` as int, `'foo'` as str).

8. **`TestDiagramDataAnnotation`**:
   - Graphviz DOT output contains `data / ...` annotations for states with data.
   - Mermaid output contains `data / ...` lines for states with data.

---

## 5. Verification Shell Command

Run the following command from the repository root to verify the entire test suite and all new functionality:

```bash
pytest
```

To run specifically with concurrency and fast feedback:
```bash
pytest -n 4
```