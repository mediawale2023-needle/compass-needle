# DPDP — Simple Action Checklist

> Plain-English version of `DPDP_COMPLIANCE.md`. No legal jargon.
> Goal: be a trustworthy keeper of citizens' personal data.
> 🔴 = do first (biggest fines / risk)  🟠 = do next  🟢 = nice finish
> Status: ✅ done · 🟡 in progress / partly done · ⬜ not started

| # | Status | The problem (plain English) | What we'll do to fix it | Urgency | Effort |
|---|---|---|---|---|---|
| 1 | 🟡 | We send people's private messages & letters to outside AI companies with no contract saying "delete this, don't train on it." | Sign a data agreement with the AI vendor (Sarvam, if Indian = bonus). Stop sending names/phones we don't need. **✅ Phone numbers are now removed from text before it goes to the AI. ⬜ Still to do: sign the vendor agreement; the scanned-letter reading still sends the photo.** | 🔴 | Low (paperwork) |
| 2 | ⬜ | All personal data sits in our database in plain readable text — a break-in exposes everything instantly. | Scramble (encrypt) phone numbers, messages, photos & scanned letters so they're useless without a key. | 🔴 | High |
| 3 | ⬜ | If data ever gets stolen, we have no alarm and no plan. The law says we must report it fast (~72 hrs). | Write a simple "what to do if hacked" plan + turn on alerts for unusual activity (e.g. bulk downloads). | 🔴 | Medium |
| 4 | ⬜ | We store everyone's data the second they message — we never ask permission. | One-time WhatsApp message: "We'll store your complaint to help you. Reply YES to continue." Record the YES. | 🔴 | Medium |
| 5 | ⬜ | People can't opt out once they're in the system. | Add a "STOP" command on WhatsApp that removes them and deletes their data. | 🟠 | Low |
| 6 | ⬜ | Citizens can't see, correct, or delete their own data — but the law gives them that right. | WhatsApp commands: "MY DATA" (see it), "CORRECT" (fix it), "DELETE ME" (remove it). | 🟠 | Medium |
| 7 | ⬜ | We keep data forever. "Deleted" cases are just hidden, not really gone. | Set a rule like "remove old resolved cases after X years" + make delete actually delete. | 🟠 | Medium |
| 8 | ⬜ | No privacy policy page, and no named person citizens can complain to. | Publish a plain privacy notice + name a "data protection contact" on the site & WhatsApp. | 🟠 | Low |
| 9 | ⬜ | We don't check age — if a child messages, we need a parent's OK. | Ask "Are you 18+?" at intake; handle under-18s differently. | 🟠 | Medium |
| 10 | ⬜ | Data may leave India when sent to foreign AI companies. | Use an Indian AI vendor (e.g. Sarvam) and confirm our servers are in India. | 🟢 | Low |
| 11 | ⬜ | We log who *changes* a case, but not who *reads* people's private data. | Record who viewed which citizen's record and when. | 🟢 | Medium |
| 12 | ⬜ | If we get large/sensitive enough, the law expects an officer, a formal review, and an annual audit. | Appoint a data protection officer; run a privacy review; schedule a yearly check. | 🟢 | Medium |

## Progress log
- **2026-06-03** — ✅ Phone-number redaction shipped: citizens' phone numbers (and Aadhaar-length digit runs) are stripped from message text and from WhatsApp queries before being sent to the AI. Pincodes, amounts, years and ward numbers are kept so case sorting still works. *(Part of item #1. Scanned-letter OCR and the vendor agreement are still open.)*

## The 30-second takeaway
> You built a **secure vault** (good locks, guards, no leaks so far). What's missing is the **trustworthy-keeper rulebook**: a contract with the AI company, locking the data itself, asking permission, letting people see/delete their data, and a plan for emergencies.

## Suggested order to actually do them
1. **Sign the AI vendor agreement** (#1) — fastest, removes the scariest exposure.
2. **Consent + STOP on WhatsApp** (#4, #5) — self-contained, high value.
3. **Privacy notice + contact person** (#8) — quick, makes you look serious.
4. **Encrypt the database** (#2) — the big one, biggest fine avoided.
5. **Citizen rights, retention, breach plan, children** (#6, #7, #3, #9).
6. **Polish** (#10, #11, #12).
