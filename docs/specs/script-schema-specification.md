# OmniUART Automation Script Specification

## 1. Scope & Purpose
The **OmniUART Script Specification** provides a declarative language in YAML or JSON for orchestrating automated sequences of UART commands, verifying device responses, and executing automated regression tests without writing custom test harnesses.

---

## 2. Script Structure

An OmniUART script comprises:
- `meta`: Name, description, author, and associated protocol definition reference.
- `configuration`: Overrides for serial port parameters, default step timeouts, and error handling policies (`abort` vs `continue`).
- `steps`: An ordered list of execution instructions (`send`, `expect`, `assert`, `delay_ms`, `log`, `loop`).

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
| `expect_response` | string | No | Name of expected response frame. |
| `timeout_ms` | integer | No | Step-specific timeout override. |
| `assertions` | list | No | Verification conditions checked against response fields. |

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

### 3.4 `repeat` / `loop` Step
Executes a sub-sequence multiple times or iterates across parameter values:
```yaml
- name: "Voltage Ramp"
  repeat: 5
  with_variable:
    name: "step_idx"
  steps:
    - command: "set_dac"
      params:
        channel: 0
        raw_value: "{{ step_idx * 1000 }}"
```

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
| `tolerance` | Floating point approx equality | `measured_v == 3.3 (within 0.05)` |

[[CAPTION:Table]] Supported assertion operators.

---

## 5. Execution Reporting & Exit Codes
The script execution engine generates structured test reports:
- **Console Summary**: Rich-rendered table displaying step names, execution duration, payload bytes, evaluated assertions, and pass/fail indicators.
- **Machine-Readable JSON**: Complete JSON artifact containing every transmitted/received frame with timestamps and assertion outcomes.
- **JUnit XML Report**: Standard CI test format compatible with GitHub Actions, Jenkins, and GitLab CI.

Process Exit Codes:
- `0`: All steps passed successfully.
- `1`: One or more assertions failed or timed out.
- `2`: Protocol or script schema validation error.
- `3`: Serial communication or transport error.
