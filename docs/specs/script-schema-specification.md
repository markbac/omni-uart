# OmniUART Automation Script Specification

## 1. Scope & Purpose
The **OmniUART Script Specification** provides a declarative language in YAML or JSON for orchestrating automated sequences of UART commands, verifying device responses, and executing automated regression tests without writing custom test harnesses.

---

## 2. Script Structure

An OmniUART script comprises:
- `meta`: Name, description, author, and associated protocol definition reference.
- `configuration`: Overrides for serial port parameters, default step timeouts, and error handling policies (`abort` vs `continue`).
- `variables` *(optional)*: Initial variables available as `${name}` in step parameters, assertion values and log messages.
- `steps`: An ordered list of execution instructions (a `command` with optional `assertions`, `delay_ms`, `log`).

```yaml
version: "1.0.0"
meta:
  name: "Actuator Calibration & Thermal Suite"
  protocol: "protocols/smart_actuator.yaml"
  description: "Initializes actuator, runs thermal sweep, and asserts sensor readings"

config:
  abort_on_error: true
  default_timeout_ms: 1000

steps:
  - name: "Ping Device"
    command: "ping"
    params: {}
    expect_response: "ping_reply"

  - name: "Set Target Temperature"
    command: "set_temperature"
    params:
      channel: 1
      target_temp: 45.0
    expect_response: "set_temperature_reply"
    assertions:
      - field: "status"
        op: "=="
        value: 0
      - field: "current_temp"
        op: "<="
        value: 50.0

  - name: "Dwell Time"
    delay_ms: 500

  - name: "Log Status"
    log: "Thermal sweep step completed successfully."
```
[[CAPTION:Figure]] Example automated test script definition.

---

## 3. Step Types & Actions

### 3.1 `command` Step
Dispatches an outbound message defined in the protocol schema:
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | No | Descriptive label for the test step. |
| `command` | string | Yes | Protocol command name matching the protocol definition. |
| `params` | object | No | Key-value mapping of parameter values. |
| `expect_response` | string | No | Label for the expected response. Declares that the step requires a response; the command must define a `response` in the protocol, otherwise the script is invalid. |
| `timeout_ms` | integer | No | Step-specific response timeout override. |
| `assertions` | list | No | Verification conditions checked against the decoded response fields. |
| `save` | object | No | Maps variable names to response fields, e.g. `{previous: value}`. |

The response timeout is the step's `timeout_ms`, else `config.default_timeout_ms` when the script sets it, else the command's own `response.timeout_ms`. A `delay_ms` or `log` on a command step runs before the command is sent.

[[CAPTION:Table]] Command step properties.

### 3.2 `delay_ms` Step
Introduces a deterministic pause in milliseconds before executing subsequent steps:
```yaml
- name: "Settle Capacitor"
  delay_ms: 250
```

### 3.3 `log` Step
Outputs user-defined messages or variable values to console and test reports:
```yaml
- name: "Milestone Log"
  log: "Phase 1 calibration completed."
```

### 3.4 Variables
Variables come from the script's `variables` map, from values passed by the caller, and from `save` on earlier steps. `${name}` is replaced in step `params`, assertion `value` and `log` text. A value that is exactly one reference keeps the variable's type (`value: "${previous}"` stays an integer); inside longer text it is converted to a string. Referencing an undefined variable is a script error.

```yaml
variables:
  target: 42
steps:
  - command: "set_temperature"
    params: { target_temp: "${target}" }
  - command: "get_readings"
    save: { measured: "temperature" }
    assertions:
      - { field: "temperature", op: "tolerance", value: "${target}", tolerance: 2.0 }
  - log: "measured ${measured}"
```

> **Note:** `repeat` / `loop` steps are not implemented. A step that has none of `command`, `delay_ms` or `log` is reported as an error rather than being skipped, so an unsupported construct can never make a script pass.

---

## 4. Assertion Operators

Assertions validate field values returned in the device's response payload:

| Operator | Meaning | Example |
| :--- | :--- | :--- |
| `==` | Exact equality | `status == 0` |
| `!=` | Inequality | `error_code != 255` |
| `<` | Less than | `temperature < 85.0` |
| `<=` | Less than or equal | `pressure <= 1013.25` |
| `>` | Greater than | `voltage > 3.0` |
| `>=` | Greater than or equal | `rssi >= -80` |
| `in` | Value is member of set | `state in [1, 2, 4]` |
| `tolerance` | Floating point approx equality; requires the assertion's `tolerance` value (`==` with `tolerance` set behaves the same) | `measured_v == 3.3 (within 0.05)` |

[[CAPTION:Table]] Supported assertion operators.

The kit-format names `equals`, `notEquals`, `lessThan`, `lessThanOrEqual`, `greaterThan` and `greaterThanOrEqual` (and `eq`, `ne`, `lt`, `le`, `gt`, `ge`) are accepted as aliases. An unknown operator is a script error. A field that is missing from the response, or values that cannot be compared, fail the assertion.

---

## 5. Execution Reporting & Exit Codes
The engine (`omniuart.core.runner.ScriptRunner`, driven by `omni-uart run`) executes steps in order against a real or simulated device and reports each step as `passed`, `failed` (the device did not behave as required: timeout, invalid response or failed assertion), `error` (the script or link is broken) or `skipped` (an earlier step failed and `abort_on_error` is `true`). With `abort_on_error: false` execution continues after a failure.

- **Console Summary**: One line per step with duration and failure reason, then a result line.
- **Machine-Readable JSON** (`--report file.json`): Every step with its request and response bytes, decoded fields and assertion outcomes.
- **Session Recording** (`--record file.jsonl`): Every transmitted and received frame, replayable with `omni-uart replay`.

> **Note:** JUnit XML output is not implemented yet.

Process Exit Codes:
- `0`: All steps passed.
- `1`: A step failed (assertion, timeout or invalid response), or steps were skipped.
- `2`: Invalid script or input: unknown variable or operator, invalid parameters, unsupported step, protocol not found, or no transport selected.
- `3`: Serial communication or transport error.
