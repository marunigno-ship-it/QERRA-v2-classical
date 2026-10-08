# Commercial Licensing — QERRA-v2 Classical

Copyright © 2026 Marussa Metocharaki

> **This page is a notice and an invitation, not a license grant.**
> A commercial license exists only as a written agreement signed by the copyright holder.
> For open-source use, the licenses in `LICENSE` (AGPL-3.0) and `hsr/LICENSE` (Apache-2.0) apply.
> Nothing here is legal advice. Please have your own lawyer review how a license applies to your product.

---

## 1. What is licensed how

| Component | Location | Open-source license |
|---|---|---|
| **QERRA-HSR** — physical safety reflex (pure Python, standard library only) | `hsr/` | **Apache License 2.0** (`hsr/LICENSE`, `hsr/NOTICE`) |
| **Everything else** — SEMEV-12 (`ethical_core.py`, `vectors.py`), QERRA-THRIVE (`values/`), API (`app.py`), ROS 2 bridge, Behavior Tree nodes, controllers, documentation | all other paths | **GNU AGPL-3.0** (`LICENSE`) |

Versions published before `hsr/LICENSE` was added remain available under AGPL-3.0.

## 2. Do I need a commercial license?

**You do not need one if you:**
- use only `hsr/` (Apache-2.0 allows commercial and closed-source use, with attribution);
- use the AGPL-3.0 parts for research, evaluation, personal use, or internal use that you do not distribute or offer to others over a network;
- build an open-source product and comply with AGPL-3.0, including publishing the complete corresponding source.

**You probably do need one if you want to:**
- ship the AGPL-3.0 parts inside a closed-source robot, device, or software product;
- run them as part of a hosted or networked service without offering that service's source code to its users;
- combine them with proprietary code that you do not want to publish.

AGPL-3.0 obligations depend on how exactly your system is built and deployed. If in doubt, ask.

## 3. What a commercial license can cover

Terms are negotiated case by case. Things I am willing to discuss:
- a non-exclusive license to the AGPL-3.0 components for a named product or deployment, without the AGPL source-offer obligations;
- term, number of robots or deployments, and territory;
- optional integration support, validation support, and updates.

## 4. What it does not include

- **No safety certification and no safety assurance.** QERRA-v2 Classical is an early research prototype. It is not a certified safety system and not a medical device (see `LIMITATIONS.md`). A commercial license does not change that. The licensee remains responsible for risk assessment, safety validation, and regulatory conformity of its own product (for example under the EU Machinery Regulation (EU) 2023/1230 and the EU AI Act), and for using certified hardware safety functions such as emergency stops.
- **Third-party components.** Dependencies and model weights (for example sentence-transformers, PyTorch, the all-MiniLM-L6-v2 model, FastAPI, py_trees) keep their own licenses. This license does not cover them.
- **Names and trademarks.** Rights to use the names QERRA, SEMEV-12, and QERRA-THRIVE are not granted unless agreed in writing.
- **Exclusivity.** Licenses are non-exclusive unless agreed in writing.
- **Warranty.** Software is provided "as is" unless a signed agreement says otherwise.

## 5. How to ask

Email **marunigno@gmail.com** with the subject **"QERRA commercial license"** and include:
1. your organization and a contact person;
2. your product, and how QERRA components would be used (embedded on a robot, cloud service, internal tool, research);
3. whether your product is open-source or closed-source;
4. the number of robots or deployments, and your timeline.

I am a solo maintainer. I reply on a best-effort basis and give no response-time guarantee unless we agree one in writing.

## 6. Contributors

To keep dual licensing possible, contributions to the AGPL-3.0 parts are accepted only under a signed contributor agreement that allows me to relicense them. Contributions to `hsr/` are accepted under Apache-2.0. Please open an issue before sending a pull request.
