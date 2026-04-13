# Engineering Note: HX-9000 Overtemperature Incident & EDC Calibration Review

**Reference:** EN-2024-031
**System:** HX-9000 Hydraulic Unit — Bay 4, Plant 2
**Date:** 2024-03-05
**Author:** J. Alvarez, Senior Systems Engineer
**Reviewers:** K. Patel (Mechanical), R. Singh (Controls)
**Status:** Closed

---

## 1. Incident Summary

On 2024-03-04, the HX-9000 unit in Bay 4 triggered a FAULT-T02 (fluid temperature ≥ 80 °C)
at 09:49 local time, causing an automatic pump shutdown. The unit was offline for approximately
33 minutes before maintenance cleared the fault and restarted the system.

The same day, a secondary FAULT-S04 (sensor communication fault on PT-01) occurred at 13:55,
placing the unit in degraded-monitoring mode for approximately 18 minutes.

Neither incident resulted in physical damage or process quality deviation. The production
schedule absorbed the downtime without escalation.

---

## 2. Root Cause Analysis

### 2.1 FAULT-T02 — Overtemperature

The root cause was a blown thermal fuse on the heat exchanger cooling fan circuit (fuse F-FAN1,
rated 10 A). With the fan stopped, the heat exchanger lost approximately 60% of its cooling
capacity. Under the prevailing load (70 L/min, 180 bar), fluid temperature climbed from 51 °C
to 81 °C over approximately 25 minutes.

**Why did the fuse blow?** Examination of the replaced fuse showed signs of sustained overload
rather than a transient spike. The fan motor nameplate current is 7.2 A; however, the measured
inrush during recent cold starts has been recorded at 9.6 A (see BMS log 2024-02-28). Over time,
repeated inrush events at the upper boundary of the fuse rating caused thermal degradation and
eventual failure.

**Corrective action:** The 10 A fuse was replaced with a 12 A slow-blow (type-T) fuse, which is
rated for the motor's inrush profile while still protecting against short-circuit faults. The
appropriate fuse is: Littelfuse 312-series 12 A, 250 V, 5×20 mm, slow-blow.

### 2.2 FAULT-S04 — Sensor Communication Fault (PT-01)

The root cause was a loose wire termination at terminal block TB-3, pin 7. This is the positive
side of the 4–20 mA loop for pressure transducer PT-01. The terminal is located near a
vibration-prone pipe clamp, which likely worked the wire loose over time.

**Corrective action:** The wire was re-terminated and secured with a cable tie to reduce vibration
transmission. The TB-3 block will be added to the 500-hour inspection checklist.

---

## 3. Voltage Calibration Review

During the post-incident inspection, the EDC (Electronic Displacement Controller) voltage
calibration was checked. The last recorded calibration was 1,847 operating hours ago, which is
approaching the 2,000-hour calibration interval specified in the manual (Section 4.3).

### Calibration findings:
- Supply voltage at EDC: **24.1 VDC** (within spec, nominal 24 VDC, range 22.5–26.5 VDC)
- Zero-point output (R17 trimmer): **0.08 VDC** (spec: 0.00 ± 0.05 VDC) — **OUT OF SPEC**
- Full-scale output (R18 trimmer): **9.97 VDC** (spec: 10.00 ± 0.05 VDC) — within spec

The zero-point drift of 0.08 VDC means the pump has a small residual displacement command even
at zero setpoint. This can cause the pump to not fully de-stroke, resulting in marginally elevated
idle power consumption and heat generation.

### Calibration procedure performed:
1. Set displacement command to 0% from the SCU.
2. Adjusted R17 trimmer counterclockwise in small increments until output read **0.02 VDC**.
3. Set displacement command to 100%.
4. Verified R18 output: **9.99 VDC** — no adjustment needed.
5. Cycled displacement command from 0% to 100% three times; readings remained stable.
6. Recorded calibration in the maintenance log: next due at +2,000 operating hours.

---

## 4. Recommendations

1. **Immediate:** Add F-FAN1 fuse check to the monthly visual inspection round.
2. **Short-term (within 30 days):** Inspect all TB-3 terminals for tightness; add to 500-hour
   checklist for future service.
3. **Long-term:** Evaluate moving the TB-3 block away from the vibrating pipe clamp, or fitting
   vibration-damping mounts to the control panel at that location.
4. **Controls team:** Review the fan motor soft-start delay parameter in the SCU firmware.
   Introducing a 2-second ramp on fan start-up should reduce inrush and extend fuse life.

---

## 5. Sign-Off

| Role                  | Name        | Signature | Date       |
|-----------------------|-------------|-----------|------------|
| Author                | J. Alvarez  | JAL       | 2024-03-05 |
| Mechanical Review     | K. Patel    | KP        | 2024-03-05 |
| Controls Review       | R. Singh    | RS        | 2024-03-06 |
| Maintenance Manager   | D. Torres   | DT        | 2024-03-06 |

---

*This document is stored in the Engineering Document Management System under project HX9000-BAY4.*
*Questions: engineering-support@plant2.internal*
