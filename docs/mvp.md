# MVP User Flow & Output Format

## MVP User Flow

1. **Entry** — User opens the app and sees a single input (e.g. “Describe how you’re feeling or your question”).
2. **Input** — User submits free-text (symptoms, question, or both). No required fields; optional context (e.g. age, duration) can be included.
3. **Triage** — System checks input against emergency triggers (see [safety.md](safety.md)). If triggered → response MUST start with the **Emergency warning** block; otherwise → no emergency block.
4. **Response generation** — System produces one structured response following the **Exact final output format** below. No multi-turn clarification required for MVP (single response per submit).
5. **Display** — Response is shown in the UI with sections rendered in order. Emergency warning (if present) is visually prominent (e.g. banner/alert at top).
6. **Repeat** — User may submit another message (new flow from step 2). No conversation memory required for MVP.

---

## Exact Final Output Format

Every response MUST be structured with the following sections, in this order. Section titles are literal; content is filled per case.

| # | Section title (exact) | When present | Content |
|---|------------------------|--------------|---------|
| 0 | **Emergency warning** | Only when emergency triggers are detected | Fixed wording per [safety.md](safety.md). Shown above all other sections. |
| 1 | **Summary** | Always | 1–2 sentences: what the user described and what this response addresses. No diagnosis. |
| 2 | **General information** | Always | Brief, factual, non-personalized info about the topic (e.g. common causes, typical course). No “you have X.” |
| 3 | **What you can do** | When applicable (e.g. mild, self-care topics) | General self-care / lifestyle suggestions only. No medication dosing or “take X.” |
| 4 | **When to see a doctor** | Always | Clear criteria (symptoms, duration, red flags) and “consult a healthcare provider for your situation.” |
| 5 | **Disclaimer** | Always | Short “not medical advice” + “cannot diagnose or prescribe” + “consult a qualified healthcare provider.” |

**Rules:**

- Sections 1, 2, 4, 5 are always present. Section 0 only if emergency; section 3 only when appropriate (e.g. omit for emergency-only replies).
- No extra sections. No diagnosis, no personalized treatment, no medication recommendations.
- All content must comply with [safety.md](safety.md) (prohibited outputs, response template requirements).

---

## Example 1: Mild cold

### Conversation

**User:**  
I’ve had a runny nose and a bit of a sore throat for two days. No fever. What could it be and what can I do?

**System:** *(single response in exact format below)*

---

### Final output (exact format)

---

**Summary**  
You’re describing a runny nose and mild sore throat for two days with no fever. Below is general information and self-care guidance only; this is not a diagnosis.

**General information**  
Runny nose and sore throat are often caused by viral upper respiratory infections (e.g. common cold). Symptoms usually peak in a few days and improve within 1–2 weeks. Many people manage them with rest and simple self-care.

**What you can do**  
- Rest and stay hydrated.  
- Gargling with warm salt water may ease throat discomfort.  
- Using a humidifier or steam may help congestion.  
- Honey (e.g. in tea) may soothe the throat for adults; avoid in infants under 1 year.  

This is general guidance only. I cannot recommend specific medicines or doses; ask a pharmacist or doctor if you’re considering any product.

**When to see a doctor**  
See a healthcare provider if: symptoms worsen or last more than ~10 days; you develop high fever, difficulty breathing, severe throat pain, or trouble swallowing; or you have other concerns. Always consult a doctor for your situation.

**Disclaimer**  
This is general information only, not medical advice. I cannot diagnose conditions or recommend specific treatments. Always consult a qualified healthcare provider for your situation.

---

## Example 2: Chest pain

### Conversation

**User:**  
I have pressure in my chest and it’s hard to take a deep breath. Started about an hour ago.

**System:** *(single response in exact format below; emergency warning shown first)*

---

### Final output (exact format)

---

**Emergency warning**  
This may be a medical emergency. Please call emergency services (e.g. 911 / your local emergency number) or go to the nearest emergency department immediately. This system cannot provide emergency care.

---

**Summary**  
You’ve described chest pressure and difficulty taking a deep breath for about an hour. Below is limited general context only; you should seek emergency evaluation as above.

**General information**  
Chest pressure and shortness of breath can have many causes, including serious heart or lung conditions that need urgent evaluation. Only a healthcare professional can assess you in person and determine the cause. Do not wait to see if symptoms go away before seeking care.

**When to see a doctor**  
In your situation, you should seek emergency care now (call emergency services or go to the nearest emergency department). Do not use this response in place of in-person evaluation.

**Disclaimer**  
This is general information only, not medical advice. I cannot diagnose conditions or recommend specific treatments. Always consult a qualified healthcare provider—and in this case, seek emergency care immediately.

---

*MVP responses must follow this structure and these examples in spirit. See [safety.md](safety.md) for full safety and compliance rules.*
