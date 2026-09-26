# Hardware Protocol Specification: AT Command Set for a GSM/Cellular Modem (Hayes + 3GPP TS 27.007 subset)

**Version**: `V.250 / TS 27.007`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `none`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/at-commands-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/at-commands-uart-interface.html)

## Description
Plain text command/response lines. No length field, no CRC, and no escaping -- a delimiter-framed protocol with only an end marker, CRLF, for almost every message. One command (SendSmsBody) is the exception: its body is terminated by Ctrl-Z instead, via endDelimiterOverride -- see its own description.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `AttentionCheck` (Command ID: `AT`) - The base 'is anybody there' command every AT command set supports.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetEchoOff` (Command ID: `ATE0`) - ATE0 -- stop the modem echoing back everything it receives. Most scripted/automated use wants this; interactive terminal use usually wants echo on (ATE1) so what you type is visible.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetEchoOn` (Command ID: `ATE1`) - ATE1 -- the modem's power-on default on most hardware.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `Reset` (Command ID: `ATZ`) - ATZ -- reset to the profile stored in non-volatile memory (not necessarily factory defaults -- see FactoryDefaults for that).

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `FactoryDefaults` (Command ID: `AT&F`) - AT&F -- restore factory default configuration.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `Identify` (Command ID: `ATI`) - ATI -- a free-form multi-line identification string, format entirely vendor-specific.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetBaudRate` (Command ID: `AT+IPR?`) - AT+IPR? (section 3.2).

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetBaudRate` (Command ID: `AT+IPR=`) - AT+IPR=<rate> -- one of the module's own real supported rates (2400-460800). Wired up to this whole interface's own baudRateNegotiation (see the top-level property): the module acks at the OLD rate, then the host must reconfigure its own UART to match.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `rate` | `bytes` | - | - | - |

#### `SetVerboseErrors` (Command ID: `AT+CMEE=2`) - AT+CMEE=2 (section 10.2) -- without this, most of the CmeError responses modeled throughout this whole file wouldn't actually be returned at all; the module would send plain ERROR instead. Worth sending early in any real integration's init sequence, right after SetEchoOff.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetBatteryVoltage` (Command ID: `AT+CBC`) - AT+CBC (section 10.1) -- for a battery-powered deployment, worth polling before/after any high-current radio activity.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `ResetModule` (Command ID: `AT+QRST=1`) - AT+QRST=1 (section 10.4) -- immediate reset, without a clean network detach first.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetClock` (Command ID: `AT+CCLK?`) - AT+CCLK? (section 12.1).

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetClock` (Command ID: `AT+CCLK=`) - AT+CCLK=<time>, format \"YY/MM/DD,hh:mm:ss+zz\" (quarter-hours from GMT, not whole hours -- +08 means +2 hours, per the manual's own worked example).

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `time` | `bytes` | - | - | - |

### Category: IDENTIFICATION

#### `Identify` (Command ID: `ATI`) - ATI -- a free-form multi-line identification string, format entirely vendor-specific.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetManufacturer` (Command ID: `AT+CGMI`) - AT+CGMI.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetModel` (Command ID: `AT+CGMM`) - AT+CGMM.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetSerialNumber` (Command ID: `AT+CGSN`) - AT+CGSN -- returns the modem's IMEI.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetFirmwareRevision` (Command ID: `AT+CGMR`) - AT+CGMR -- from the BC660K-GL manual (section 2.4). Worth flagging: its response line is literally 'Revision: <revision>', not a '+CGMR:' prefix the way almost every other query response here works -- a genuine, sourced exception to the pattern, not a modeling choice.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetSerialNumberLegacy` (Command ID: `AT+GSN`) - AT+GSN -- the older Hayes-style serial number query. Response is the raw IMEI digit string with no prefix, unlike GetSerialNumber's AT+CGSN which modern modules also usually support; both often return the same value.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

### Category: SIM-NETWORK

#### `GetPinStatus` (Command ID: `AT+CPIN?`) - AT+CPIN? -- whether the SIM needs a PIN/PUK entered before it can be used.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetNetworkRegistration` (Command ID: `AT+CREG?`) - AT+CREG? -- whether, and how, the modem is registered on the network.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SignalQuery` (Command ID: `AT+CSQ`) - AT+CSQ

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetExtendedSignalQuality` (Command ID: `AT+CESQ`) - AT+CESQ -- supersedes CSQ with metrics meaningful for UMTS/LTE (RSCP, EcNo, RSRQ, RSRP), not just GSM RSSI/BER.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetOperator` (Command ID: `AT+COPS?`) - AT+COPS? -- the currently selected network operator and how it was selected.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetOperatorAutomatic` (Command ID: `AT+COPS=0`) - AT+COPS=0 -- automatic network/operator selection. Each COPS mode is its own command here, the same way SetEchoOff/SetEchoOn are separate rather than one parameterized command: the trailing parameters COPS actually accepts genuinely differ by mode (0 and 2 take none at all; 1 and 4 require an operator; 3 takes only a format), and this schema has no way to make a message's own required fields conditional on another field's value within the same message.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetOperatorManual` (Command ID: `AT+COPS=1,`) - AT+COPS=1,<format>,<oper> -- manually select a specific operator. The real command also accepts an optional trailing <AcT> (radio access technology); left out of this modeled version for simplicity rather than made a genuinely optional positional field, which this delimiter-based field model handles awkwardly.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `format` | `bytes` | - | - | - |
| `oper` | `bytes` | - | - | - |

#### `SetOperatorDeregister` (Command ID: `AT+COPS=2`) - AT+COPS=2 -- deregister from the network and remain deregistered until told otherwise.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetOperatorFormatOnly` (Command ID: `AT+COPS=3,`) - AT+COPS=3,<format> -- sets how OperatorResult's oper field will be formatted on future queries, without changing registration at all.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `format` | `bytes` | - | - | - |

#### `SetOperatorManualAutomatic` (Command ID: `AT+COPS=4,`) - AT+COPS=4,<format>,<oper> -- try the given operator manually; fall back to automatic selection if that specific one can't be reached. Same AcT simplification as SetOperatorManual.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `format` | `bytes` | - | - | - |
| `oper` | `bytes` | - | - | - |

#### `EnterPin` (Command ID: `AT+CPIN=`) - AT+CPIN=<pin> -- from the Quectel BC660K-GL manual (AT+CPIN, section 8.6): entering a plain SIM PIN. See EnterPukWithNewPin for the other shape this same command takes.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `pin` | `bytes` | - | - | - |

#### `EnterPukWithNewPin` (Command ID: `AT+CPIN=`) - AT+CPIN=<puk>,<newpin> -- when the SIM demands PUK (not plain PIN), a second argument -- the new PIN to set -- is required. Genuinely COPS-like: same command name, argument COUNT (not a leading mode digit this time) selects which shape applies, and this schema has no way to make newpin conditionally required on pin actually being a PUK rather than a PIN -- an engine, or a human, has to know which case applies from GetPinStatus's own +CPIN: SIM PUK result first.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `puk` | `bytes` | - | - | - |
| `newpin` | `bytes` | - | - | - |

#### `UnlockFacility` (Command ID: `0x00`) - AT+CLCK=<fac>,0[,<passwd>] -- from the manual's AT+CLCK (section 8.5). fac is quoted, e.g. \"SC\" for the SIM facility.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `fac` | `bytes` | - | - | - |
| `mode` | `bytes` | - | - | - |

#### `LockFacility` (Command ID: `0x01`) - AT+CLCK=<fac>,1[,<passwd>].

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `fac` | `bytes` | - | - | - |
| `mode` | `bytes` | - | - | - |

#### `QueryFacilityLock` (Command ID: `0x02`) - AT+CLCK=<fac>,2 -- the third CLCK shape: mode=2 needs no password, and gets a genuinely different response format (FacilityLockResult lines, not a bare OK) from mode=0/1 -- but that's not actually ambiguous for this schema's dispatch algorithm, since FacilityLockResult has its own +CLCK: prefix distinguishing it from Ok. Worth including precisely because it's a case where a mode-dependent response DOESN'T need special handling, unlike G460's write-variant ambiguity.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `fac` | `bytes` | - | - | - |
| `mode` | `bytes` | - | - | - |

#### `SetPsmDisabled` (Command ID: `AT+CPSMS=2`) - AT+CPSMS=2 -- from the manual's AT+CPSMS (section 9.4): mode=2 is a 'special form' that takes no further parameters at all and resets everything to defaults, unlike mode=0/1 below.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetPsmParameters` (Command ID: `,,,`) - AT+CPSMS=<mode>,,,<TAU>,<activeTime> -- mode 0 (disable) or 1 (enable) plus the requested timer values. Two literal empty positions (the manual's own ',,,' -- unused parameters this module doesn't support) sit between mode and TAU; modeled as a literal separator field rather than tidied away, since that's genuinely how the command is written on the wire. mode is restricted to {0,1} via a named enum type specifically so this can't overlap with SetPsmDisabled's mode=2 -- with a plain unrestricted uint here, an engine could wrongly treat 'AT+CPSMS=2' as this command's prefix plus mode=2 rather than SetPsmDisabled's own single constValue, a genuine ambiguity risk this fixes rather than leaves.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `mode` | `enum` | - | - | `{'0': 'Disable', '1': 'Enable'}` |
| `separator` | `bytes` | - | - | - |
| `tau` | `bytes` | - | - | - |
| `activeTime` | `bytes` | - | - | - |

#### `QcfgGetDataInactTimer` (Command ID: `AT+QCFG=\"DataInactTimer\"`) - AT+QCFG=\"DataInactTimer\" -- Quectel's AT+QCFG (section 11.1) is itself a text-based sub-command dispatcher: its first argument, a quoted function name, selects an entirely different parameter set for everything after it -- the same COPS-like pattern, but keyed on a string rather than a mode digit. Modeled as separate commands per function, the same way COPS's modes are. Omitting the value here means query.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `QcfgSetDataInactTimer` (Command ID: `AT+QCFG=\"DataInactTimer\",`) - AT+QCFG=\"DataInactTimer\",<value> -- supplying the value switches this from a query to a set.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `value` | `bytes` | - | - | - |

#### `QcfgGpioInitialize` (Command ID: `AT+QCFG=\"GPIO\",1,`) - AT+QCFG=\"GPIO\",1,<pin>,<dir>,<pullsel>,<level> -- a SECOND, nested level of the same COPS-like pattern: within the 'GPIO' function specifically, a further <mode> digit (1/2/3) selects yet another shape. mode=1 (initialize) requires every parameter; contrast QcfgGpioQuery and QcfgGpioConfigure below, which need fewer. This is genuinely a two-level dispatch (function name, then mode within it), and it validates fine with nothing beyond the ordinary field/constValue/role mechanism already used for COPS -- no new schema capability was needed for this, just more layers of the same one.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `pin` | `bytes` | - | - | - |
| `dir` | `bytes` | - | - | - |
| `pullsel` | `bytes` | - | - | - |
| `level` | `bytes` | - | - | - |

#### `QcfgGpioQuery` (Command ID: `AT+QCFG=\"GPIO\",2,`) - AT+QCFG=\"GPIO\"[,2[,<pin>]] -- mode=2 (the default if omitted entirely) with pin optional: omit it for every GPIO's status, or give one for just that pin. Modeled here as the explicit mode=2,pin form; the bare AT+QCFG=\"GPIO\" (mode and pin both omitted) is QcfgGetDataInactTimer's sibling case and isn't separately modeled to keep this set from growing unboundedly -- the pattern is established by the two variants that are here.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `pin` | `bytes` | - | - | - |

#### `QcfgGpioConfigure` (Command ID: `AT+QCFG=\"GPIO\",3,`) - AT+QCFG=\"GPIO\",3,<pin>,<level> -- mode=3: set one GPIO's output level. Per the manual, 'only and must set value of a specified GPIO' -- pin and level only, no dir/pullsel, a third distinct trailing shape for the same function name.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `pin` | `bytes` | - | - | - |
| `level` | `bytes` | - | - | - |

#### `GetIccidQuectel` (Command ID: `AT+QCCID`) - AT+QCCID -- correction: an earlier version of this file modeled a generic, vendor-unspecified 'AT+CCID' for this. The Quectel BC660K-GL manual's actual command (section 8.11) is AT+QCCID, an execution command with no arguments at all; response is +QCCID:, not +CCID:. Kept alongside the generic GetIccid/IccidResult below rather than replacing them, since other vendors do genuinely use the generic form -- but where you have the real target module's manual, as here, prefer the sourced command over the generic guess.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetEdrxDisabled` (Command ID: `AT+CEDRXS=3`) - AT+CEDRXS=3 (section 9.1) -- the exact same COPS/CPSMS-like pattern again: a bare mode value that takes no further parameters and resets everything, distinct from mode 0/1/2 below which all need AcT_type and a requested value.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SetEdrxParameters` (Command ID: `AT+CEDRXS=`) - AT+CEDRXS=<mode>,<AcT_type>,<requested_eDRX_value> -- mode restricted to {0,1,2} via a named enum type for the same reason SetPsmParameters restricts its own mode: so this can't overlap with SetEdrxDisabled's mode=3.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `mode` | `enum` | - | - | `{'0': 'Disable', '1': 'Enable', '2': 'EnableWithUrc'}` |
| `actType` | `bytes` | - | - | - |
| `requestedEdrxValue` | `bytes` | - | - | - |

#### `GetOperatorNames` (Command ID: `AT+COPN`) - AT+COPN -- dumps the modem's whole built-in numeric-to-alphanumeric operator name table. The device sends one OperatorNameResult line per known operator, then OK -- a burst of many same-shaped response frames, not one. No special modeling needed for that: each line dispatches independently like any other response, there just happen to be a lot of them in a row.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetPreferredListSelection` (Command ID: `AT+CPLS?`) - AT+CPLS? -- which preferred-PLMN list is currently active: 0=SIM/USIM (user-controlled), 1=operator-controlled, 2=HPLMN selector.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetPreferredOperatorList` (Command ID: `AT+CPOL?`) - AT+CPOL? -- entries stored in the list GetPreferredListSelection points at. Like GetOperatorNames, typically returns several PreferredOperatorResult lines, one per stored entry, before OK.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetImsi` (Command ID: `AT+CIMI`) - AT+CIMI -- the SIM's IMSI. Response is the raw digit string with no +CIMI: prefix at all, unlike most other query responses here -- see ImsiResult.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetIccid` (Command ID: `AT+CCID`) - Reads the SIM's ICCID. Genuinely non-standardized across vendors (AT+CCID, AT+ICCID, AT+QCCID and others all exist) -- AT+CCID modeled here as one common form, not a universal one.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetGprsRegistration` (Command ID: `AT+CGREG?`) - AT+CGREG? -- packet-switched (GPRS/UMTS) registration status, analogous to GetNetworkRegistration's AT+CREG? for circuit-switched.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `GetEpsRegistration` (Command ID: `AT+CEREG?`) - AT+CEREG? -- LTE/EPS registration status, the AT+CREG?/AT+CGREG? equivalent for 4G.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

### Category: DATA-CONNECTION

#### `SetPdpContextActivation` (Command ID: `AT+CGACT=`) - AT+CGACT=<state>,<cid> (section 5.1) -- brings the data connection actually up (or down). DefinePdpContext only defines the context's parameters; nothing flows until this activates it.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `state` | `bytes` | - | - | - |
| `cid` | `bytes` | - | - | - |

#### `GetPdpAddress` (Command ID: `AT+CGPADDR`) - AT+CGPADDR (section 4.4, bare execution form) -- the IP address actually assigned to the device once its PDP context is active.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SendControlPlaneData` (Command ID: `AT+CSODCP=`) - AT+CSODCP=<cid>,<cpdataLength>,<cpdata> (section 7.4) -- the actual point of this NB-IoT module for many real products: small non-IP data sent via the control plane (NIDD), avoiding the overhead of a full IP stack. This, not a PPP-style data-mode switch, is the primary data path this specific hardware is built for. Simplified from the manual's full AT+CSODCP=<cid>,<cpdataLength>,<cpdata>[,<RAI>[,<type_of_user_data>]] by omitting the two trailing optional parameters, the same simplification already used for SetOperatorManual.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `cid` | `bytes` | - | - | - |
| `cpdataLength` | `bytes` | - | - | - |
| `cpdata` | `bytes` | - | - | - |

#### `SetControlPlaneDataReporting` (Command ID: `AT+CRTDCP=`) - AT+CRTDCP=<reporting> (section 7.3) -- enables the +CRTDCP: URC (ControlPlaneDataReceived) for downlink data arriving the same way SendControlPlaneData sends it uplink.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `reporting` | `bytes` | - | - | - |

#### `SetGprsAttach` (Command ID: `AT+CGATT=1`) - AT+CGATT=1 -- attach to the GPRS/packet-data service, a precondition for DefinePdpContext.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `DefinePdpContext` (Command ID: `\"IP\"`) - AT+CGDCONT=<cid>,<pdpType>,<apn> -- the first genuinely parameterized command here, showing delimiter-separated arguments rather than a single constValue line.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `cid` | `bytes` | - | - | - |
| `pdpType` | `bytes` | - | - | - |
| `apn` | `bytes` | - | - | - |

#### `Dial` (Command ID: `ATD`) - ATD<number> -- for a circuit-switched or legacy dial-up data call.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `phoneNumber` | `bytes` | - | - | - |

#### `HangUp` (Command ID: `ATH`) - ATH.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `EnterDataMode` (Command ID: `AT+CGDATA=\"PPP\",1`) - AT+CGDATA=\"PPP\",1 -- switches this same link from AT command mode into raw PPP. See relatedInterfaces.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

### Category: SMS

#### `SmsTextMode` (Command ID: `AT+CMGF=1`) - AT+CMGF=1 -- text mode rather than PDU mode, a precondition for SendSmsHeader as modeled here.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `SendSmsHeader` (Command ID: `\"`) - AT+CMGS=\"<number>\" -- the modem replies with a bare '> ' prompt (not modeled as its own response here -- it's a 2-character prompt, not a CRLF-terminated line, and this schema's message model assumes the latter), then waits for SendSmsBody.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `prefix` | `bytes` | - | - | - |
| `phoneNumber` | `bytes` | - | - | - |
| `suffix` | `bytes` | - | - | - |

#### `SendSmsBody` (Command ID: `0x3D`) - The actual message text, sent only after SendSmsHeader's '> ' prompt. Terminated by Ctrl-Z (0x1A), NOT this interface's usual CRLF -- endDelimiterOverride exists specifically for this case. (Esc instead of Ctrl-Z cancels the send instead; not separately modeled here.)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `messageText` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: AT Command Set for a GSM/Cellular Modem (Hayes + 3GPP TS 27.007 subset)
  version: V.250 / TS 27.007
  description: 'Plain text command/response lines. No length field, no CRC, and no
    escaping -- a delimiter-framed protocol with only an end marker, CRLF, for almost
    every message. One command (SendSmsBody) is the exception: its body is terminated
    by Ctrl-Z instead, via endDelimiterOverride -- see its own description.'
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/9600
    protocol: serial
    description: Physical UART Transport (9600 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 9600
        dataBits: 8
        parity: none
        stopBits: 1.0
        framingType: delimited
        integrity: none
channels:
  omniuart/cmd/AttentionCheck:
    publish:
      summary: 'Send command AttentionCheck (ID: AT)'
      description: The base 'is anybody there' command every AT command set supports.
      message:
        name: AttentionCheck_Message
        title: AttentionCheck Command
        payload:
          $ref: '#/components/schemas/AttentionCheck_Request'
  omniuart/cmd/SetEchoOff:
    publish:
      summary: 'Send command SetEchoOff (ID: ATE0)'
      description: ATE0 -- stop the modem echoing back everything it receives. Most
        scripted/automated use wants this; interactive terminal use usually wants
        echo on (ATE1) so what you type is visible.
      message:
        name: SetEchoOff_Message
        title: SetEchoOff Command
        payload:
          $ref: '#/components/schemas/SetEchoOff_Request'
  omniuart/cmd/SetEchoOn:
    publish:
      summary: 'Send command SetEchoOn (ID: ATE1)'
      description: ATE1 -- the modem's power-on default on most hardware.
      message:
        name: SetEchoOn_Message
        title: SetEchoOn Command
        payload:
          $ref: '#/components/schemas/SetEchoOn_Request'
  omniuart/cmd/Reset:
    publish:
      summary: 'Send command Reset (ID: ATZ)'
      description: ATZ -- reset to the profile stored in non-volatile memory (not
        necessarily factory defaults -- see FactoryDefaults for that).
      message:
        name: Reset_Message
        title: Reset Command
        payload:
          $ref: '#/components/schemas/Reset_Request'
  omniuart/cmd/FactoryDefaults:
    publish:
      summary: 'Send command FactoryDefaults (ID: AT&F)'
      description: AT&F -- restore factory default configuration.
      message:
        name: FactoryDefaults_Message
        title: FactoryDefaults Command
        payload:
          $ref: '#/components/schemas/FactoryDefaults_Request'
  omniuart/cmd/Identify:
    publish:
      summary: 'Send command Identify (ID: ATI)'
      description: ATI -- a free-form multi-line identification string, format entirely
        vendor-specific.
      message:
        name: Identify_Message
        title: Identify Command
        payload:
          $ref: '#/components/schemas/Identify_Request'
  omniuart/cmd/GetManufacturer:
    publish:
      summary: 'Send command GetManufacturer (ID: AT+CGMI)'
      description: AT+CGMI.
      message:
        name: GetManufacturer_Message
        title: GetManufacturer Command
        payload:
          $ref: '#/components/schemas/GetManufacturer_Request'
  omniuart/cmd/GetModel:
    publish:
      summary: 'Send command GetModel (ID: AT+CGMM)'
      description: AT+CGMM.
      message:
        name: GetModel_Message
        title: GetModel Command
        payload:
          $ref: '#/components/schemas/GetModel_Request'
  omniuart/cmd/GetSerialNumber:
    publish:
      summary: 'Send command GetSerialNumber (ID: AT+CGSN)'
      description: AT+CGSN -- returns the modem's IMEI.
      message:
        name: GetSerialNumber_Message
        title: GetSerialNumber Command
        payload:
          $ref: '#/components/schemas/GetSerialNumber_Request'
  omniuart/cmd/GetPinStatus:
    publish:
      summary: 'Send command GetPinStatus (ID: AT+CPIN?)'
      description: AT+CPIN? -- whether the SIM needs a PIN/PUK entered before it can
        be used.
      message:
        name: GetPinStatus_Message
        title: GetPinStatus Command
        payload:
          $ref: '#/components/schemas/GetPinStatus_Request'
  omniuart/cmd/GetNetworkRegistration:
    publish:
      summary: 'Send command GetNetworkRegistration (ID: AT+CREG?)'
      description: AT+CREG? -- whether, and how, the modem is registered on the network.
      message:
        name: GetNetworkRegistration_Message
        title: GetNetworkRegistration Command
        payload:
          $ref: '#/components/schemas/GetNetworkRegistration_Request'
  omniuart/cmd/SignalQuery:
    publish:
      summary: 'Send command SignalQuery (ID: AT+CSQ)'
      description: AT+CSQ
      message:
        name: SignalQuery_Message
        title: SignalQuery Command
        payload:
          $ref: '#/components/schemas/SignalQuery_Request'
  omniuart/cmd/GetExtendedSignalQuality:
    publish:
      summary: 'Send command GetExtendedSignalQuality (ID: AT+CESQ)'
      description: AT+CESQ -- supersedes CSQ with metrics meaningful for UMTS/LTE
        (RSCP, EcNo, RSRQ, RSRP), not just GSM RSSI/BER.
      message:
        name: GetExtendedSignalQuality_Message
        title: GetExtendedSignalQuality Command
        payload:
          $ref: '#/components/schemas/GetExtendedSignalQuality_Request'
  omniuart/cmd/GetOperator:
    publish:
      summary: 'Send command GetOperator (ID: AT+COPS?)'
      description: AT+COPS? -- the currently selected network operator and how it
        was selected.
      message:
        name: GetOperator_Message
        title: GetOperator Command
        payload:
          $ref: '#/components/schemas/GetOperator_Request'
  omniuart/cmd/SetOperatorAutomatic:
    publish:
      summary: 'Send command SetOperatorAutomatic (ID: AT+COPS=0)'
      description: 'AT+COPS=0 -- automatic network/operator selection. Each COPS mode
        is its own command here, the same way SetEchoOff/SetEchoOn are separate rather
        than one parameterized command: the trailing parameters COPS actually accepts
        genuinely differ by mode (0 and 2 take none at all; 1 and 4 require an operator;
        3 takes only a format), and this schema has no way to make a message''s own
        required fields conditional on another field''s value within the same message.'
      message:
        name: SetOperatorAutomatic_Message
        title: SetOperatorAutomatic Command
        payload:
          $ref: '#/components/schemas/SetOperatorAutomatic_Request'
  omniuart/cmd/SetOperatorManual:
    publish:
      summary: 'Send command SetOperatorManual (ID: AT+COPS=1,)'
      description: AT+COPS=1,<format>,<oper> -- manually select a specific operator.
        The real command also accepts an optional trailing <AcT> (radio access technology);
        left out of this modeled version for simplicity rather than made a genuinely
        optional positional field, which this delimiter-based field model handles
        awkwardly.
      message:
        name: SetOperatorManual_Message
        title: SetOperatorManual Command
        payload:
          $ref: '#/components/schemas/SetOperatorManual_Request'
  omniuart/cmd/SetOperatorDeregister:
    publish:
      summary: 'Send command SetOperatorDeregister (ID: AT+COPS=2)'
      description: AT+COPS=2 -- deregister from the network and remain deregistered
        until told otherwise.
      message:
        name: SetOperatorDeregister_Message
        title: SetOperatorDeregister Command
        payload:
          $ref: '#/components/schemas/SetOperatorDeregister_Request'
  omniuart/cmd/SetOperatorFormatOnly:
    publish:
      summary: 'Send command SetOperatorFormatOnly (ID: AT+COPS=3,)'
      description: AT+COPS=3,<format> -- sets how OperatorResult's oper field will
        be formatted on future queries, without changing registration at all.
      message:
        name: SetOperatorFormatOnly_Message
        title: SetOperatorFormatOnly Command
        payload:
          $ref: '#/components/schemas/SetOperatorFormatOnly_Request'
  omniuart/cmd/SetOperatorManualAutomatic:
    publish:
      summary: 'Send command SetOperatorManualAutomatic (ID: AT+COPS=4,)'
      description: AT+COPS=4,<format>,<oper> -- try the given operator manually; fall
        back to automatic selection if that specific one can't be reached. Same AcT
        simplification as SetOperatorManual.
      message:
        name: SetOperatorManualAutomatic_Message
        title: SetOperatorManualAutomatic Command
        payload:
          $ref: '#/components/schemas/SetOperatorManualAutomatic_Request'
  omniuart/cmd/EnterPin:
    publish:
      summary: 'Send command EnterPin (ID: AT+CPIN=)'
      description: 'AT+CPIN=<pin> -- from the Quectel BC660K-GL manual (AT+CPIN, section
        8.6): entering a plain SIM PIN. See EnterPukWithNewPin for the other shape
        this same command takes.'
      message:
        name: EnterPin_Message
        title: EnterPin Command
        payload:
          $ref: '#/components/schemas/EnterPin_Request'
  omniuart/cmd/EnterPukWithNewPin:
    publish:
      summary: 'Send command EnterPukWithNewPin (ID: AT+CPIN=)'
      description: 'AT+CPIN=<puk>,<newpin> -- when the SIM demands PUK (not plain
        PIN), a second argument -- the new PIN to set -- is required. Genuinely COPS-like:
        same command name, argument COUNT (not a leading mode digit this time) selects
        which shape applies, and this schema has no way to make newpin conditionally
        required on pin actually being a PUK rather than a PIN -- an engine, or a
        human, has to know which case applies from GetPinStatus''s own +CPIN: SIM
        PUK result first.'
      message:
        name: EnterPukWithNewPin_Message
        title: EnterPukWithNewPin Command
        payload:
          $ref: '#/components/schemas/EnterPukWithNewPin_Request'
  omniuart/cmd/UnlockFacility:
    publish:
      summary: 'Send command UnlockFacility (ID: 0x00)'
      description: AT+CLCK=<fac>,0[,<passwd>] -- from the manual's AT+CLCK (section
        8.5). fac is quoted, e.g. \"SC\" for the SIM facility.
      message:
        name: UnlockFacility_Message
        title: UnlockFacility Command
        payload:
          $ref: '#/components/schemas/UnlockFacility_Request'
  omniuart/cmd/LockFacility:
    publish:
      summary: 'Send command LockFacility (ID: 0x01)'
      description: AT+CLCK=<fac>,1[,<passwd>].
      message:
        name: LockFacility_Message
        title: LockFacility Command
        payload:
          $ref: '#/components/schemas/LockFacility_Request'
  omniuart/cmd/QueryFacilityLock:
    publish:
      summary: 'Send command QueryFacilityLock (ID: 0x02)'
      description: 'AT+CLCK=<fac>,2 -- the third CLCK shape: mode=2 needs no password,
        and gets a genuinely different response format (FacilityLockResult lines,
        not a bare OK) from mode=0/1 -- but that''s not actually ambiguous for this
        schema''s dispatch algorithm, since FacilityLockResult has its own +CLCK:
        prefix distinguishing it from Ok. Worth including precisely because it''s
        a case where a mode-dependent response DOESN''T need special handling, unlike
        G460''s write-variant ambiguity.'
      message:
        name: QueryFacilityLock_Message
        title: QueryFacilityLock Command
        payload:
          $ref: '#/components/schemas/QueryFacilityLock_Request'
  omniuart/cmd/SetPsmDisabled:
    publish:
      summary: 'Send command SetPsmDisabled (ID: AT+CPSMS=2)'
      description: 'AT+CPSMS=2 -- from the manual''s AT+CPSMS (section 9.4): mode=2
        is a ''special form'' that takes no further parameters at all and resets everything
        to defaults, unlike mode=0/1 below.'
      message:
        name: SetPsmDisabled_Message
        title: SetPsmDisabled Command
        payload:
          $ref: '#/components/schemas/SetPsmDisabled_Request'
  omniuart/cmd/SetPsmParameters:
    publish:
      summary: 'Send command SetPsmParameters (ID: ,,,)'
      description: AT+CPSMS=<mode>,,,<TAU>,<activeTime> -- mode 0 (disable) or 1 (enable)
        plus the requested timer values. Two literal empty positions (the manual's
        own ',,,' -- unused parameters this module doesn't support) sit between mode
        and TAU; modeled as a literal separator field rather than tidied away, since
        that's genuinely how the command is written on the wire. mode is restricted
        to {0,1} via a named enum type specifically so this can't overlap with SetPsmDisabled's
        mode=2 -- with a plain unrestricted uint here, an engine could wrongly treat
        'AT+CPSMS=2' as this command's prefix plus mode=2 rather than SetPsmDisabled's
        own single constValue, a genuine ambiguity risk this fixes rather than leaves.
      message:
        name: SetPsmParameters_Message
        title: SetPsmParameters Command
        payload:
          $ref: '#/components/schemas/SetPsmParameters_Request'
  omniuart/cmd/QcfgGetDataInactTimer:
    publish:
      summary: 'Send command QcfgGetDataInactTimer (ID: AT+QCFG=\"DataInactTimer\")'
      description: 'AT+QCFG=\"DataInactTimer\" -- Quectel''s AT+QCFG (section 11.1)
        is itself a text-based sub-command dispatcher: its first argument, a quoted
        function name, selects an entirely different parameter set for everything
        after it -- the same COPS-like pattern, but keyed on a string rather than
        a mode digit. Modeled as separate commands per function, the same way COPS''s
        modes are. Omitting the value here means query.'
      message:
        name: QcfgGetDataInactTimer_Message
        title: QcfgGetDataInactTimer Command
        payload:
          $ref: '#/components/schemas/QcfgGetDataInactTimer_Request'
  omniuart/cmd/QcfgSetDataInactTimer:
    publish:
      summary: 'Send command QcfgSetDataInactTimer (ID: AT+QCFG=\"DataInactTimer\",)'
      description: AT+QCFG=\"DataInactTimer\",<value> -- supplying the value switches
        this from a query to a set.
      message:
        name: QcfgSetDataInactTimer_Message
        title: QcfgSetDataInactTimer Command
        payload:
          $ref: '#/components/schemas/QcfgSetDataInactTimer_Request'
  omniuart/cmd/QcfgGpioInitialize:
    publish:
      summary: 'Send command QcfgGpioInitialize (ID: AT+QCFG=\"GPIO\",1,)'
      description: 'AT+QCFG=\"GPIO\",1,<pin>,<dir>,<pullsel>,<level> -- a SECOND,
        nested level of the same COPS-like pattern: within the ''GPIO'' function specifically,
        a further <mode> digit (1/2/3) selects yet another shape. mode=1 (initialize)
        requires every parameter; contrast QcfgGpioQuery and QcfgGpioConfigure below,
        which need fewer. This is genuinely a two-level dispatch (function name, then
        mode within it), and it validates fine with nothing beyond the ordinary field/constValue/role
        mechanism already used for COPS -- no new schema capability was needed for
        this, just more layers of the same one.'
      message:
        name: QcfgGpioInitialize_Message
        title: QcfgGpioInitialize Command
        payload:
          $ref: '#/components/schemas/QcfgGpioInitialize_Request'
  omniuart/cmd/QcfgGpioQuery:
    publish:
      summary: 'Send command QcfgGpioQuery (ID: AT+QCFG=\"GPIO\",2,)'
      description: 'AT+QCFG=\"GPIO\"[,2[,<pin>]] -- mode=2 (the default if omitted
        entirely) with pin optional: omit it for every GPIO''s status, or give one
        for just that pin. Modeled here as the explicit mode=2,pin form; the bare
        AT+QCFG=\"GPIO\" (mode and pin both omitted) is QcfgGetDataInactTimer''s sibling
        case and isn''t separately modeled to keep this set from growing unboundedly
        -- the pattern is established by the two variants that are here.'
      message:
        name: QcfgGpioQuery_Message
        title: QcfgGpioQuery Command
        payload:
          $ref: '#/components/schemas/QcfgGpioQuery_Request'
  omniuart/cmd/QcfgGpioConfigure:
    publish:
      summary: 'Send command QcfgGpioConfigure (ID: AT+QCFG=\"GPIO\",3,)'
      description: 'AT+QCFG=\"GPIO\",3,<pin>,<level> -- mode=3: set one GPIO''s output
        level. Per the manual, ''only and must set value of a specified GPIO'' --
        pin and level only, no dir/pullsel, a third distinct trailing shape for the
        same function name.'
      message:
        name: QcfgGpioConfigure_Message
        title: QcfgGpioConfigure Command
        payload:
          $ref: '#/components/schemas/QcfgGpioConfigure_Request'
  omniuart/cmd/GetIccidQuectel:
    publish:
      summary: 'Send command GetIccidQuectel (ID: AT+QCCID)'
      description: 'AT+QCCID -- correction: an earlier version of this file modeled
        a generic, vendor-unspecified ''AT+CCID'' for this. The Quectel BC660K-GL
        manual''s actual command (section 8.11) is AT+QCCID, an execution command
        with no arguments at all; response is +QCCID:, not +CCID:. Kept alongside
        the generic GetIccid/IccidResult below rather than replacing them, since other
        vendors do genuinely use the generic form -- but where you have the real target
        module''s manual, as here, prefer the sourced command over the generic guess.'
      message:
        name: GetIccidQuectel_Message
        title: GetIccidQuectel Command
        payload:
          $ref: '#/components/schemas/GetIccidQuectel_Request'
  omniuart/cmd/GetFirmwareRevision:
    publish:
      summary: 'Send command GetFirmwareRevision (ID: AT+CGMR)'
      description: 'AT+CGMR -- from the BC660K-GL manual (section 2.4). Worth flagging:
        its response line is literally ''Revision: <revision>'', not a ''+CGMR:''
        prefix the way almost every other query response here works -- a genuine,
        sourced exception to the pattern, not a modeling choice.'
      message:
        name: GetFirmwareRevision_Message
        title: GetFirmwareRevision Command
        payload:
          $ref: '#/components/schemas/GetFirmwareRevision_Request'
  omniuart/cmd/GetBaudRate:
    publish:
      summary: 'Send command GetBaudRate (ID: AT+IPR?)'
      description: AT+IPR? (section 3.2).
      message:
        name: GetBaudRate_Message
        title: GetBaudRate Command
        payload:
          $ref: '#/components/schemas/GetBaudRate_Request'
  omniuart/cmd/SetBaudRate:
    publish:
      summary: 'Send command SetBaudRate (ID: AT+IPR=)'
      description: 'AT+IPR=<rate> -- one of the module''s own real supported rates
        (2400-460800). Wired up to this whole interface''s own baudRateNegotiation
        (see the top-level property): the module acks at the OLD rate, then the host
        must reconfigure its own UART to match.'
      message:
        name: SetBaudRate_Message
        title: SetBaudRate Command
        payload:
          $ref: '#/components/schemas/SetBaudRate_Request'
  omniuart/cmd/SetVerboseErrors:
    publish:
      summary: 'Send command SetVerboseErrors (ID: AT+CMEE=2)'
      description: AT+CMEE=2 (section 10.2) -- without this, most of the CmeError
        responses modeled throughout this whole file wouldn't actually be returned
        at all; the module would send plain ERROR instead. Worth sending early in
        any real integration's init sequence, right after SetEchoOff.
      message:
        name: SetVerboseErrors_Message
        title: SetVerboseErrors Command
        payload:
          $ref: '#/components/schemas/SetVerboseErrors_Request'
  omniuart/cmd/SetPdpContextActivation:
    publish:
      summary: 'Send command SetPdpContextActivation (ID: AT+CGACT=)'
      description: AT+CGACT=<state>,<cid> (section 5.1) -- brings the data connection
        actually up (or down). DefinePdpContext only defines the context's parameters;
        nothing flows until this activates it.
      message:
        name: SetPdpContextActivation_Message
        title: SetPdpContextActivation Command
        payload:
          $ref: '#/components/schemas/SetPdpContextActivation_Request'
  omniuart/cmd/GetPdpAddress:
    publish:
      summary: 'Send command GetPdpAddress (ID: AT+CGPADDR)'
      description: AT+CGPADDR (section 4.4, bare execution form) -- the IP address
        actually assigned to the device once its PDP context is active.
      message:
        name: GetPdpAddress_Message
        title: GetPdpAddress Command
        payload:
          $ref: '#/components/schemas/GetPdpAddress_Request'
  omniuart/cmd/SendControlPlaneData:
    publish:
      summary: 'Send command SendControlPlaneData (ID: AT+CSODCP=)'
      description: 'AT+CSODCP=<cid>,<cpdataLength>,<cpdata> (section 7.4) -- the actual
        point of this NB-IoT module for many real products: small non-IP data sent
        via the control plane (NIDD), avoiding the overhead of a full IP stack. This,
        not a PPP-style data-mode switch, is the primary data path this specific hardware
        is built for. Simplified from the manual''s full AT+CSODCP=<cid>,<cpdataLength>,<cpdata>[,<RAI>[,<type_of_user_data>]]
        by omitting the two trailing optional parameters, the same simplification
        already used for SetOperatorManual.'
      message:
        name: SendControlPlaneData_Message
        title: SendControlPlaneData Command
        payload:
          $ref: '#/components/schemas/SendControlPlaneData_Request'
  omniuart/cmd/SetControlPlaneDataReporting:
    publish:
      summary: 'Send command SetControlPlaneDataReporting (ID: AT+CRTDCP=)'
      description: 'AT+CRTDCP=<reporting> (section 7.3) -- enables the +CRTDCP: URC
        (ControlPlaneDataReceived) for downlink data arriving the same way SendControlPlaneData
        sends it uplink.'
      message:
        name: SetControlPlaneDataReporting_Message
        title: SetControlPlaneDataReporting Command
        payload:
          $ref: '#/components/schemas/SetControlPlaneDataReporting_Request'
  omniuart/cmd/GetBatteryVoltage:
    publish:
      summary: 'Send command GetBatteryVoltage (ID: AT+CBC)'
      description: AT+CBC (section 10.1) -- for a battery-powered deployment, worth
        polling before/after any high-current radio activity.
      message:
        name: GetBatteryVoltage_Message
        title: GetBatteryVoltage Command
        payload:
          $ref: '#/components/schemas/GetBatteryVoltage_Request'
  omniuart/cmd/ResetModule:
    publish:
      summary: 'Send command ResetModule (ID: AT+QRST=1)'
      description: AT+QRST=1 (section 10.4) -- immediate reset, without a clean network
        detach first.
      message:
        name: ResetModule_Message
        title: ResetModule Command
        payload:
          $ref: '#/components/schemas/ResetModule_Request'
  omniuart/cmd/GetClock:
    publish:
      summary: 'Send command GetClock (ID: AT+CCLK?)'
      description: AT+CCLK? (section 12.1).
      message:
        name: GetClock_Message
        title: GetClock Command
        payload:
          $ref: '#/components/schemas/GetClock_Request'
  omniuart/cmd/SetClock:
    publish:
      summary: 'Send command SetClock (ID: AT+CCLK=)'
      description: AT+CCLK=<time>, format \"YY/MM/DD,hh:mm:ss+zz\" (quarter-hours
        from GMT, not whole hours -- +08 means +2 hours, per the manual's own worked
        example).
      message:
        name: SetClock_Message
        title: SetClock Command
        payload:
          $ref: '#/components/schemas/SetClock_Request'
  omniuart/cmd/SetEdrxDisabled:
    publish:
      summary: 'Send command SetEdrxDisabled (ID: AT+CEDRXS=3)'
      description: 'AT+CEDRXS=3 (section 9.1) -- the exact same COPS/CPSMS-like pattern
        again: a bare mode value that takes no further parameters and resets everything,
        distinct from mode 0/1/2 below which all need AcT_type and a requested value.'
      message:
        name: SetEdrxDisabled_Message
        title: SetEdrxDisabled Command
        payload:
          $ref: '#/components/schemas/SetEdrxDisabled_Request'
  omniuart/cmd/SetEdrxParameters:
    publish:
      summary: 'Send command SetEdrxParameters (ID: AT+CEDRXS=)'
      description: 'AT+CEDRXS=<mode>,<AcT_type>,<requested_eDRX_value> -- mode restricted
        to {0,1,2} via a named enum type for the same reason SetPsmParameters restricts
        its own mode: so this can''t overlap with SetEdrxDisabled''s mode=3.'
      message:
        name: SetEdrxParameters_Message
        title: SetEdrxParameters Command
        payload:
          $ref: '#/components/schemas/SetEdrxParameters_Request'
  omniuart/cmd/GetOperatorNames:
    publish:
      summary: 'Send command GetOperatorNames (ID: AT+COPN)'
      description: 'AT+COPN -- dumps the modem''s whole built-in numeric-to-alphanumeric
        operator name table. The device sends one OperatorNameResult line per known
        operator, then OK -- a burst of many same-shaped response frames, not one.
        No special modeling needed for that: each line dispatches independently like
        any other response, there just happen to be a lot of them in a row.'
      message:
        name: GetOperatorNames_Message
        title: GetOperatorNames Command
        payload:
          $ref: '#/components/schemas/GetOperatorNames_Request'
  omniuart/cmd/GetPreferredListSelection:
    publish:
      summary: 'Send command GetPreferredListSelection (ID: AT+CPLS?)'
      description: 'AT+CPLS? -- which preferred-PLMN list is currently active: 0=SIM/USIM
        (user-controlled), 1=operator-controlled, 2=HPLMN selector.'
      message:
        name: GetPreferredListSelection_Message
        title: GetPreferredListSelection Command
        payload:
          $ref: '#/components/schemas/GetPreferredListSelection_Request'
  omniuart/cmd/GetPreferredOperatorList:
    publish:
      summary: 'Send command GetPreferredOperatorList (ID: AT+CPOL?)'
      description: AT+CPOL? -- entries stored in the list GetPreferredListSelection
        points at. Like GetOperatorNames, typically returns several PreferredOperatorResult
        lines, one per stored entry, before OK.
      message:
        name: GetPreferredOperatorList_Message
        title: GetPreferredOperatorList Command
        payload:
          $ref: '#/components/schemas/GetPreferredOperatorList_Request'
  omniuart/cmd/GetImsi:
    publish:
      summary: 'Send command GetImsi (ID: AT+CIMI)'
      description: 'AT+CIMI -- the SIM''s IMSI. Response is the raw digit string with
        no +CIMI: prefix at all, unlike most other query responses here -- see ImsiResult.'
      message:
        name: GetImsi_Message
        title: GetImsi Command
        payload:
          $ref: '#/components/schemas/GetImsi_Request'
  omniuart/cmd/GetIccid:
    publish:
      summary: 'Send command GetIccid (ID: AT+CCID)'
      description: Reads the SIM's ICCID. Genuinely non-standardized across vendors
        (AT+CCID, AT+ICCID, AT+QCCID and others all exist) -- AT+CCID modeled here
        as one common form, not a universal one.
      message:
        name: GetIccid_Message
        title: GetIccid Command
        payload:
          $ref: '#/components/schemas/GetIccid_Request'
  omniuart/cmd/GetSerialNumberLegacy:
    publish:
      summary: 'Send command GetSerialNumberLegacy (ID: AT+GSN)'
      description: AT+GSN -- the older Hayes-style serial number query. Response is
        the raw IMEI digit string with no prefix, unlike GetSerialNumber's AT+CGSN
        which modern modules also usually support; both often return the same value.
      message:
        name: GetSerialNumberLegacy_Message
        title: GetSerialNumberLegacy Command
        payload:
          $ref: '#/components/schemas/GetSerialNumberLegacy_Request'
  omniuart/cmd/GetGprsRegistration:
    publish:
      summary: 'Send command GetGprsRegistration (ID: AT+CGREG?)'
      description: AT+CGREG? -- packet-switched (GPRS/UMTS) registration status, analogous
        to GetNetworkRegistration's AT+CREG? for circuit-switched.
      message:
        name: GetGprsRegistration_Message
        title: GetGprsRegistration Command
        payload:
          $ref: '#/components/schemas/GetGprsRegistration_Request'
  omniuart/cmd/GetEpsRegistration:
    publish:
      summary: 'Send command GetEpsRegistration (ID: AT+CEREG?)'
      description: AT+CEREG? -- LTE/EPS registration status, the AT+CREG?/AT+CGREG?
        equivalent for 4G.
      message:
        name: GetEpsRegistration_Message
        title: GetEpsRegistration Command
        payload:
          $ref: '#/components/schemas/GetEpsRegistration_Request'
  omniuart/cmd/SetGprsAttach:
    publish:
      summary: 'Send command SetGprsAttach (ID: AT+CGATT=1)'
      description: AT+CGATT=1 -- attach to the GPRS/packet-data service, a precondition
        for DefinePdpContext.
      message:
        name: SetGprsAttach_Message
        title: SetGprsAttach Command
        payload:
          $ref: '#/components/schemas/SetGprsAttach_Request'
  omniuart/cmd/DefinePdpContext:
    publish:
      summary: 'Send command DefinePdpContext (ID: \"IP\")'
      description: AT+CGDCONT=<cid>,<pdpType>,<apn> -- the first genuinely parameterized
        command here, showing delimiter-separated arguments rather than a single constValue
        line.
      message:
        name: DefinePdpContext_Message
        title: DefinePdpContext Command
        payload:
          $ref: '#/components/schemas/DefinePdpContext_Request'
  omniuart/cmd/Dial:
    publish:
      summary: 'Send command Dial (ID: ATD)'
      description: ATD<number> -- for a circuit-switched or legacy dial-up data call.
      message:
        name: Dial_Message
        title: Dial Command
        payload:
          $ref: '#/components/schemas/Dial_Request'
  omniuart/cmd/HangUp:
    publish:
      summary: 'Send command HangUp (ID: ATH)'
      description: ATH.
      message:
        name: HangUp_Message
        title: HangUp Command
        payload:
          $ref: '#/components/schemas/HangUp_Request'
  omniuart/cmd/EnterDataMode:
    publish:
      summary: 'Send command EnterDataMode (ID: AT+CGDATA=\"PPP\",1)'
      description: AT+CGDATA=\"PPP\",1 -- switches this same link from AT command
        mode into raw PPP. See relatedInterfaces.
      message:
        name: EnterDataMode_Message
        title: EnterDataMode Command
        payload:
          $ref: '#/components/schemas/EnterDataMode_Request'
  omniuart/cmd/SmsTextMode:
    publish:
      summary: 'Send command SmsTextMode (ID: AT+CMGF=1)'
      description: AT+CMGF=1 -- text mode rather than PDU mode, a precondition for
        SendSmsHeader as modeled here.
      message:
        name: SmsTextMode_Message
        title: SmsTextMode Command
        payload:
          $ref: '#/components/schemas/SmsTextMode_Request'
  omniuart/cmd/SendSmsHeader:
    publish:
      summary: 'Send command SendSmsHeader (ID: \")'
      description: AT+CMGS=\"<number>\" -- the modem replies with a bare '> ' prompt
        (not modeled as its own response here -- it's a 2-character prompt, not a
        CRLF-terminated line, and this schema's message model assumes the latter),
        then waits for SendSmsBody.
      message:
        name: SendSmsHeader_Message
        title: SendSmsHeader Command
        payload:
          $ref: '#/components/schemas/SendSmsHeader_Request'
  omniuart/cmd/SendSmsBody:
    publish:
      summary: 'Send command SendSmsBody (ID: 0x3D)'
      description: The actual message text, sent only after SendSmsHeader's '> ' prompt.
        Terminated by Ctrl-Z (0x1A), NOT this interface's usual CRLF -- endDelimiterOverride
        exists specifically for this case. (Esc instead of Ctrl-Z cancels the send
        instead; not separately modeled here.)
      message:
        name: SendSmsBody_Message
        title: SendSmsBody Command
        payload:
          $ref: '#/components/schemas/SendSmsBody_Request'
components:
  messages: {}
  schemas:
    AttentionCheck_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT
          description: Opcode ID for AttentionCheck
        text:
          type: integer
      description: The base 'is anybody there' command every AT command set supports.
    SetEchoOff_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ATE0
          description: Opcode ID for SetEchoOff
        text:
          type: integer
      description: ATE0 -- stop the modem echoing back everything it receives. Most
        scripted/automated use wants this; interactive terminal use usually wants
        echo on (ATE1) so what you type is visible.
    SetEchoOn_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ATE1
          description: Opcode ID for SetEchoOn
        text:
          type: integer
      description: ATE1 -- the modem's power-on default on most hardware.
    Reset_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ATZ
          description: Opcode ID for Reset
        text:
          type: integer
      description: ATZ -- reset to the profile stored in non-volatile memory (not
        necessarily factory defaults -- see FactoryDefaults for that).
    FactoryDefaults_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT&F
          description: Opcode ID for FactoryDefaults
        text:
          type: integer
      description: AT&F -- restore factory default configuration.
    Identify_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ATI
          description: Opcode ID for Identify
        text:
          type: integer
      description: ATI -- a free-form multi-line identification string, format entirely
        vendor-specific.
    GetManufacturer_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGMI
          description: Opcode ID for GetManufacturer
        text:
          type: integer
      description: AT+CGMI.
    GetModel_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGMM
          description: Opcode ID for GetModel
        text:
          type: integer
      description: AT+CGMM.
    GetSerialNumber_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGSN
          description: Opcode ID for GetSerialNumber
        text:
          type: integer
      description: AT+CGSN -- returns the modem's IMEI.
    GetPinStatus_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CPIN?
          description: Opcode ID for GetPinStatus
        text:
          type: integer
      description: AT+CPIN? -- whether the SIM needs a PIN/PUK entered before it can
        be used.
    GetNetworkRegistration_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CREG?
          description: Opcode ID for GetNetworkRegistration
        text:
          type: integer
      description: AT+CREG? -- whether, and how, the modem is registered on the network.
    SignalQuery_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CSQ
          description: Opcode ID for SignalQuery
        text:
          type: integer
      description: AT+CSQ
    GetExtendedSignalQuality_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CESQ
          description: Opcode ID for GetExtendedSignalQuality
        text:
          type: integer
      description: AT+CESQ -- supersedes CSQ with metrics meaningful for UMTS/LTE
        (RSCP, EcNo, RSRQ, RSRP), not just GSM RSSI/BER.
    GetOperator_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPS?
          description: Opcode ID for GetOperator
        text:
          type: integer
      description: AT+COPS? -- the currently selected network operator and how it
        was selected.
    SetOperatorAutomatic_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPS=0
          description: Opcode ID for SetOperatorAutomatic
        text:
          type: integer
      description: 'AT+COPS=0 -- automatic network/operator selection. Each COPS mode
        is its own command here, the same way SetEchoOff/SetEchoOn are separate rather
        than one parameterized command: the trailing parameters COPS actually accepts
        genuinely differ by mode (0 and 2 take none at all; 1 and 4 require an operator;
        3 takes only a format), and this schema has no way to make a message''s own
        required fields conditional on another field''s value within the same message.'
    SetOperatorManual_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPS=1,
          description: Opcode ID for SetOperatorManual
        prefix:
          type: integer
        format:
          type: integer
        oper:
          type: integer
      description: AT+COPS=1,<format>,<oper> -- manually select a specific operator.
        The real command also accepts an optional trailing <AcT> (radio access technology);
        left out of this modeled version for simplicity rather than made a genuinely
        optional positional field, which this delimiter-based field model handles
        awkwardly.
    SetOperatorDeregister_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPS=2
          description: Opcode ID for SetOperatorDeregister
        text:
          type: integer
      description: AT+COPS=2 -- deregister from the network and remain deregistered
        until told otherwise.
    SetOperatorFormatOnly_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPS=3,
          description: Opcode ID for SetOperatorFormatOnly
        prefix:
          type: integer
        format:
          type: integer
      description: AT+COPS=3,<format> -- sets how OperatorResult's oper field will
        be formatted on future queries, without changing registration at all.
    SetOperatorManualAutomatic_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPS=4,
          description: Opcode ID for SetOperatorManualAutomatic
        prefix:
          type: integer
        format:
          type: integer
        oper:
          type: integer
      description: AT+COPS=4,<format>,<oper> -- try the given operator manually; fall
        back to automatic selection if that specific one can't be reached. Same AcT
        simplification as SetOperatorManual.
    EnterPin_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CPIN=
          description: Opcode ID for EnterPin
        prefix:
          type: integer
        pin:
          type: integer
      description: 'AT+CPIN=<pin> -- from the Quectel BC660K-GL manual (AT+CPIN, section
        8.6): entering a plain SIM PIN. See EnterPukWithNewPin for the other shape
        this same command takes.'
    EnterPukWithNewPin_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CPIN=
          description: Opcode ID for EnterPukWithNewPin
        prefix:
          type: integer
        puk:
          type: integer
        newpin:
          type: integer
      description: 'AT+CPIN=<puk>,<newpin> -- when the SIM demands PUK (not plain
        PIN), a second argument -- the new PIN to set -- is required. Genuinely COPS-like:
        same command name, argument COUNT (not a leading mode digit this time) selects
        which shape applies, and this schema has no way to make newpin conditionally
        required on pin actually being a PUK rather than a PIN -- an engine, or a
        human, has to know which case applies from GetPinStatus''s own +CPIN: SIM
        PUK result first.'
    UnlockFacility_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for UnlockFacility
        prefix:
          type: integer
        fac:
          type: integer
        mode:
          type: integer
      description: AT+CLCK=<fac>,0[,<passwd>] -- from the manual's AT+CLCK (section
        8.5). fac is quoted, e.g. \"SC\" for the SIM facility.
    LockFacility_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for LockFacility
        prefix:
          type: integer
        fac:
          type: integer
        mode:
          type: integer
      description: AT+CLCK=<fac>,1[,<passwd>].
    QueryFacilityLock_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 2
          description: Opcode ID for QueryFacilityLock
        prefix:
          type: integer
        fac:
          type: integer
        mode:
          type: integer
      description: 'AT+CLCK=<fac>,2 -- the third CLCK shape: mode=2 needs no password,
        and gets a genuinely different response format (FacilityLockResult lines,
        not a bare OK) from mode=0/1 -- but that''s not actually ambiguous for this
        schema''s dispatch algorithm, since FacilityLockResult has its own +CLCK:
        prefix distinguishing it from Ok. Worth including precisely because it''s
        a case where a mode-dependent response DOESN''T need special handling, unlike
        G460''s write-variant ambiguity.'
    SetPsmDisabled_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CPSMS=2
          description: Opcode ID for SetPsmDisabled
        text:
          type: integer
      description: 'AT+CPSMS=2 -- from the manual''s AT+CPSMS (section 9.4): mode=2
        is a ''special form'' that takes no further parameters at all and resets everything
        to defaults, unlike mode=0/1 below.'
    SetPsmParameters_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ',,,'
          description: Opcode ID for SetPsmParameters
        prefix:
          type: integer
        mode:
          type: integer
        separator:
          type: integer
        tau:
          type: integer
        activeTime:
          type: integer
      description: AT+CPSMS=<mode>,,,<TAU>,<activeTime> -- mode 0 (disable) or 1 (enable)
        plus the requested timer values. Two literal empty positions (the manual's
        own ',,,' -- unused parameters this module doesn't support) sit between mode
        and TAU; modeled as a literal separator field rather than tidied away, since
        that's genuinely how the command is written on the wire. mode is restricted
        to {0,1} via a named enum type specifically so this can't overlap with SetPsmDisabled's
        mode=2 -- with a plain unrestricted uint here, an engine could wrongly treat
        'AT+CPSMS=2' as this command's prefix plus mode=2 rather than SetPsmDisabled's
        own single constValue, a genuine ambiguity risk this fixes rather than leaves.
    QcfgGetDataInactTimer_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QCFG=\"DataInactTimer\"
          description: Opcode ID for QcfgGetDataInactTimer
        text:
          type: integer
      description: 'AT+QCFG=\"DataInactTimer\" -- Quectel''s AT+QCFG (section 11.1)
        is itself a text-based sub-command dispatcher: its first argument, a quoted
        function name, selects an entirely different parameter set for everything
        after it -- the same COPS-like pattern, but keyed on a string rather than
        a mode digit. Modeled as separate commands per function, the same way COPS''s
        modes are. Omitting the value here means query.'
    QcfgSetDataInactTimer_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QCFG=\"DataInactTimer\",
          description: Opcode ID for QcfgSetDataInactTimer
        prefix:
          type: integer
        value:
          type: integer
      description: AT+QCFG=\"DataInactTimer\",<value> -- supplying the value switches
        this from a query to a set.
    QcfgGpioInitialize_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QCFG=\"GPIO\",1,
          description: Opcode ID for QcfgGpioInitialize
        prefix:
          type: integer
        pin:
          type: integer
        dir:
          type: integer
        pullsel:
          type: integer
        level:
          type: integer
      description: 'AT+QCFG=\"GPIO\",1,<pin>,<dir>,<pullsel>,<level> -- a SECOND,
        nested level of the same COPS-like pattern: within the ''GPIO'' function specifically,
        a further <mode> digit (1/2/3) selects yet another shape. mode=1 (initialize)
        requires every parameter; contrast QcfgGpioQuery and QcfgGpioConfigure below,
        which need fewer. This is genuinely a two-level dispatch (function name, then
        mode within it), and it validates fine with nothing beyond the ordinary field/constValue/role
        mechanism already used for COPS -- no new schema capability was needed for
        this, just more layers of the same one.'
    QcfgGpioQuery_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QCFG=\"GPIO\",2,
          description: Opcode ID for QcfgGpioQuery
        prefix:
          type: integer
        pin:
          type: integer
      description: 'AT+QCFG=\"GPIO\"[,2[,<pin>]] -- mode=2 (the default if omitted
        entirely) with pin optional: omit it for every GPIO''s status, or give one
        for just that pin. Modeled here as the explicit mode=2,pin form; the bare
        AT+QCFG=\"GPIO\" (mode and pin both omitted) is QcfgGetDataInactTimer''s sibling
        case and isn''t separately modeled to keep this set from growing unboundedly
        -- the pattern is established by the two variants that are here.'
    QcfgGpioConfigure_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QCFG=\"GPIO\",3,
          description: Opcode ID for QcfgGpioConfigure
        prefix:
          type: integer
        pin:
          type: integer
        level:
          type: integer
      description: 'AT+QCFG=\"GPIO\",3,<pin>,<level> -- mode=3: set one GPIO''s output
        level. Per the manual, ''only and must set value of a specified GPIO'' --
        pin and level only, no dir/pullsel, a third distinct trailing shape for the
        same function name.'
    GetIccidQuectel_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QCCID
          description: Opcode ID for GetIccidQuectel
        text:
          type: integer
      description: 'AT+QCCID -- correction: an earlier version of this file modeled
        a generic, vendor-unspecified ''AT+CCID'' for this. The Quectel BC660K-GL
        manual''s actual command (section 8.11) is AT+QCCID, an execution command
        with no arguments at all; response is +QCCID:, not +CCID:. Kept alongside
        the generic GetIccid/IccidResult below rather than replacing them, since other
        vendors do genuinely use the generic form -- but where you have the real target
        module''s manual, as here, prefer the sourced command over the generic guess.'
    GetFirmwareRevision_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGMR
          description: Opcode ID for GetFirmwareRevision
        text:
          type: integer
      description: 'AT+CGMR -- from the BC660K-GL manual (section 2.4). Worth flagging:
        its response line is literally ''Revision: <revision>'', not a ''+CGMR:''
        prefix the way almost every other query response here works -- a genuine,
        sourced exception to the pattern, not a modeling choice.'
    GetBaudRate_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+IPR?
          description: Opcode ID for GetBaudRate
        text:
          type: integer
      description: AT+IPR? (section 3.2).
    SetBaudRate_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+IPR=
          description: Opcode ID for SetBaudRate
        prefix:
          type: integer
        rate:
          type: integer
      description: 'AT+IPR=<rate> -- one of the module''s own real supported rates
        (2400-460800). Wired up to this whole interface''s own baudRateNegotiation
        (see the top-level property): the module acks at the OLD rate, then the host
        must reconfigure its own UART to match.'
    SetVerboseErrors_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CMEE=2
          description: Opcode ID for SetVerboseErrors
        text:
          type: integer
      description: AT+CMEE=2 (section 10.2) -- without this, most of the CmeError
        responses modeled throughout this whole file wouldn't actually be returned
        at all; the module would send plain ERROR instead. Worth sending early in
        any real integration's init sequence, right after SetEchoOff.
    SetPdpContextActivation_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGACT=
          description: Opcode ID for SetPdpContextActivation
        prefix:
          type: integer
        state:
          type: integer
        cid:
          type: integer
      description: AT+CGACT=<state>,<cid> (section 5.1) -- brings the data connection
        actually up (or down). DefinePdpContext only defines the context's parameters;
        nothing flows until this activates it.
    GetPdpAddress_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGPADDR
          description: Opcode ID for GetPdpAddress
        text:
          type: integer
      description: AT+CGPADDR (section 4.4, bare execution form) -- the IP address
        actually assigned to the device once its PDP context is active.
    SendControlPlaneData_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CSODCP=
          description: Opcode ID for SendControlPlaneData
        prefix:
          type: integer
        cid:
          type: integer
        cpdataLength:
          type: integer
        cpdata:
          type: integer
      description: 'AT+CSODCP=<cid>,<cpdataLength>,<cpdata> (section 7.4) -- the actual
        point of this NB-IoT module for many real products: small non-IP data sent
        via the control plane (NIDD), avoiding the overhead of a full IP stack. This,
        not a PPP-style data-mode switch, is the primary data path this specific hardware
        is built for. Simplified from the manual''s full AT+CSODCP=<cid>,<cpdataLength>,<cpdata>[,<RAI>[,<type_of_user_data>]]
        by omitting the two trailing optional parameters, the same simplification
        already used for SetOperatorManual.'
    SetControlPlaneDataReporting_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CRTDCP=
          description: Opcode ID for SetControlPlaneDataReporting
        prefix:
          type: integer
        reporting:
          type: integer
      description: 'AT+CRTDCP=<reporting> (section 7.3) -- enables the +CRTDCP: URC
        (ControlPlaneDataReceived) for downlink data arriving the same way SendControlPlaneData
        sends it uplink.'
    GetBatteryVoltage_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CBC
          description: Opcode ID for GetBatteryVoltage
        text:
          type: integer
      description: AT+CBC (section 10.1) -- for a battery-powered deployment, worth
        polling before/after any high-current radio activity.
    ResetModule_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+QRST=1
          description: Opcode ID for ResetModule
        text:
          type: integer
      description: AT+QRST=1 (section 10.4) -- immediate reset, without a clean network
        detach first.
    GetClock_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CCLK?
          description: Opcode ID for GetClock
        text:
          type: integer
      description: AT+CCLK? (section 12.1).
    SetClock_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CCLK=
          description: Opcode ID for SetClock
        prefix:
          type: integer
        time:
          type: integer
      description: AT+CCLK=<time>, format \"YY/MM/DD,hh:mm:ss+zz\" (quarter-hours
        from GMT, not whole hours -- +08 means +2 hours, per the manual's own worked
        example).
    SetEdrxDisabled_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CEDRXS=3
          description: Opcode ID for SetEdrxDisabled
        text:
          type: integer
      description: 'AT+CEDRXS=3 (section 9.1) -- the exact same COPS/CPSMS-like pattern
        again: a bare mode value that takes no further parameters and resets everything,
        distinct from mode 0/1/2 below which all need AcT_type and a requested value.'
    SetEdrxParameters_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CEDRXS=
          description: Opcode ID for SetEdrxParameters
        prefix:
          type: integer
        mode:
          type: integer
        actType:
          type: integer
        requestedEdrxValue:
          type: integer
      description: 'AT+CEDRXS=<mode>,<AcT_type>,<requested_eDRX_value> -- mode restricted
        to {0,1,2} via a named enum type for the same reason SetPsmParameters restricts
        its own mode: so this can''t overlap with SetEdrxDisabled''s mode=3.'
    GetOperatorNames_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+COPN
          description: Opcode ID for GetOperatorNames
        text:
          type: integer
      description: 'AT+COPN -- dumps the modem''s whole built-in numeric-to-alphanumeric
        operator name table. The device sends one OperatorNameResult line per known
        operator, then OK -- a burst of many same-shaped response frames, not one.
        No special modeling needed for that: each line dispatches independently like
        any other response, there just happen to be a lot of them in a row.'
    GetPreferredListSelection_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CPLS?
          description: Opcode ID for GetPreferredListSelection
        text:
          type: integer
      description: 'AT+CPLS? -- which preferred-PLMN list is currently active: 0=SIM/USIM
        (user-controlled), 1=operator-controlled, 2=HPLMN selector.'
    GetPreferredOperatorList_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CPOL?
          description: Opcode ID for GetPreferredOperatorList
        text:
          type: integer
      description: AT+CPOL? -- entries stored in the list GetPreferredListSelection
        points at. Like GetOperatorNames, typically returns several PreferredOperatorResult
        lines, one per stored entry, before OK.
    GetImsi_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CIMI
          description: Opcode ID for GetImsi
        text:
          type: integer
      description: 'AT+CIMI -- the SIM''s IMSI. Response is the raw digit string with
        no +CIMI: prefix at all, unlike most other query responses here -- see ImsiResult.'
    GetIccid_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CCID
          description: Opcode ID for GetIccid
        text:
          type: integer
      description: Reads the SIM's ICCID. Genuinely non-standardized across vendors
        (AT+CCID, AT+ICCID, AT+QCCID and others all exist) -- AT+CCID modeled here
        as one common form, not a universal one.
    GetSerialNumberLegacy_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+GSN
          description: Opcode ID for GetSerialNumberLegacy
        text:
          type: integer
      description: AT+GSN -- the older Hayes-style serial number query. Response is
        the raw IMEI digit string with no prefix, unlike GetSerialNumber's AT+CGSN
        which modern modules also usually support; both often return the same value.
    GetGprsRegistration_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGREG?
          description: Opcode ID for GetGprsRegistration
        text:
          type: integer
      description: AT+CGREG? -- packet-switched (GPRS/UMTS) registration status, analogous
        to GetNetworkRegistration's AT+CREG? for circuit-switched.
    GetEpsRegistration_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CEREG?
          description: Opcode ID for GetEpsRegistration
        text:
          type: integer
      description: AT+CEREG? -- LTE/EPS registration status, the AT+CREG?/AT+CGREG?
        equivalent for 4G.
    SetGprsAttach_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGATT=1
          description: Opcode ID for SetGprsAttach
        text:
          type: integer
      description: AT+CGATT=1 -- attach to the GPRS/packet-data service, a precondition
        for DefinePdpContext.
    DefinePdpContext_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: \"IP\"
          description: Opcode ID for DefinePdpContext
        prefix:
          type: integer
        cid:
          type: integer
        pdpType:
          type: integer
        apn:
          type: integer
      description: AT+CGDCONT=<cid>,<pdpType>,<apn> -- the first genuinely parameterized
        command here, showing delimiter-separated arguments rather than a single constValue
        line.
    Dial_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ATD
          description: Opcode ID for Dial
        prefix:
          type: integer
        phoneNumber:
          type: integer
      description: ATD<number> -- for a circuit-switched or legacy dial-up data call.
    HangUp_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: ATH
          description: Opcode ID for HangUp
        text:
          type: integer
      description: ATH.
    EnterDataMode_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CGDATA=\"PPP\",1
          description: Opcode ID for EnterDataMode
        text:
          type: integer
      description: AT+CGDATA=\"PPP\",1 -- switches this same link from AT command
        mode into raw PPP. See relatedInterfaces.
    SmsTextMode_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: AT+CMGF=1
          description: Opcode ID for SmsTextMode
        text:
          type: integer
      description: AT+CMGF=1 -- text mode rather than PDU mode, a precondition for
        SendSmsHeader as modeled here.
    SendSmsHeader_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: \"
          description: Opcode ID for SendSmsHeader
        prefix:
          type: integer
        phoneNumber:
          type: integer
        suffix:
          type: integer
      description: AT+CMGS=\"<number>\" -- the modem replies with a bare '> ' prompt
        (not modeled as its own response here -- it's a 2-character prompt, not a
        CRLF-terminated line, and this schema's message model assumes the latter),
        then waits for SendSmsBody.
    SendSmsBody_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 61
          description: Opcode ID for SendSmsBody
        messageText:
          type: integer
      description: The actual message text, sent only after SendSmsHeader's '> ' prompt.
        Terminated by Ctrl-Z (0x1A), NOT this interface's usual CRLF -- endDelimiterOverride
        exists specifically for this case. (Esc instead of Ctrl-Z cancels the send
        instead; not separately modeled here.)

```
