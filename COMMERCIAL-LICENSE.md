# Commercial Use & Enterprise Engagements — QERRA-v2 Classical

Copyright © 2026 Marussa Metocharaki

> **Notice:** QERRA-v2 Classical is open-source software licensed under the [Apache License 2.0](LICENSE). 
> This document clarifies commercial usage rights, enterprise engagement models, and strict regulatory boundaries.
> Nothing herein constitutes legal advice. Integrators should consult their own legal and functional safety counsel.

---

## 1. Open Source Commercial Rights (Apache-2.0)

Under the **Apache License 2.0**, commercial use is fully permitted without royalty fees. 

You **do not** need a commercial waiver or custom licensing agreement to:
- Embed QERRA-v2 Classical components (`gate/`, `hsr/`, `ethical_core.py`, `values/`) inside proprietary, closed-source commercial robots or autonomous systems;
- Run QERRA as a local or networked service within internal industrial, healthcare, or corporate infrastructure;
- Build proprietary software that links with or extends QERRA modules.

### Conditions for Commercial Use:
Commercial users must comply with standard Apache-2.0 terms:
1. **Retain Copyright & Notices:** Keep all copyright headers (`Copyright © 2026 Marussa Metocharaki`) and the [NOTICE](hsr/NOTICE) file intact.
2. **State Modifications:** Prominently document if you modify any source files.
3. **Include the License:** Provide a copy of the Apache-2.0 license with your product distribution or documentation.

---

## 2. Enterprise Services & Bespoke Engagements

While the software is free, direct collaboration, specialized verification, and custom engineering are available directly from the author. 

Commercial entities seeking tailored adaptations of QERRA can engage for:

* **Custom Supervisory Gate Tuning:** Adapting the kinematic stopping envelope ($d_{stop}$), reaction times ($t_{react}$), and sensor corridor algorithms to proprietary AMR chassis, drive kinematics, and industrial laser scanners.
* **Hardware Interlock Integration:** Architecting fail-closed bridge interfaces between the software Gate and certified physical safety relays (Safety Torque Off / STO watchdogs).
* **Bespoke Vector Development:** Designing and calibrating domain-specific ethical (SEMEV) or values (THRIVE) vectors for specialized hospital, eldercare, or industrial environments.
* **Architecture Audits & Technical Reports:** In-depth review of autonomous behavior tree integration, IPC communication boundaries, and deterministic audit-log validation.
* **Sponsored Research & Benchmark Grants:** Commissioning targeted adversarial benchmarks or academic evaluation campaigns.

---

## 3. Strict Safety & Regulatory Boundaries

Commercial deployment must respect the following non-negotiable boundaries:

* **No Functional Safety Certification:** QERRA-v2 Classical is an early-stage research prototype. It is **not** certified under ISO 13849-1 (PL), IEC 61508 (SIL), ISO 13482, or IEC 62061. 
* **Integrator Responsibility:** The commercial integrator or robot manufacturer bears sole and absolute responsibility for:
  - Performing comprehensive risk assessments under ISO 12100;
  - Meeting legal obligations under the **EU Machinery Regulation (EU) 2023/1230** and the **EU AI Act (Regulation (EU) 2024/1689)**;
  - Integrating certified, independent hardware emergency-stop circuits and safety PLCs.
* **As-Is Warranty:** Consistent with Section 7 of the Apache-2.0 license, this software is provided "AS IS", without warranties or conditions of any kind.

---

## 4. Trademarks & Attribution

The Apache-2.0 license grants code usage rights, but **does not grant trademark rights**:
* The names **QERRA**, **QERRA-HSR**, **SEMEV-12**, and **QERRA-THRIVE** are proprietary project marks of Marussa Metocharaki.
* You may not use these marks in product marketing or company branding in a way that implies official endorsement, certification, or partnership without prior written consent.
* Accurate descriptive references (e.g., *"incorporating the open-source QERRA Supervisory Gate"*) are permitted and encouraged.

---

## 5. Contact & Inquiries

For commercial consulting, sponsored research, or bespoke integration inquiries:

* **Contact:** Marussa Metocharaki
* **Email:** [marunigno@gmail.com](mailto:marunigno@gmail.com)
* **Subject line:** `[Enterprise Inquiry] QERRA Integration`

Please include your organization name, target robotic platform/chassis, intended operational domain (e.g., healthcare logistics, industrial manufacturing), and proposed project timeline.
