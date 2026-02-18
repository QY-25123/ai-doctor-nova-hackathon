# Safety Guidelines

## 1. Scope

- **This system is not for medical diagnosis.** It does not replace licensed healthcare providers, clinical evaluation, or diagnostic tests.
- Use is limited to: general health information, wellness guidance, and support for understanding health topics. It must not be used to diagnose conditions, prescribe treatment, or make clinical decisions.
- Any output that could be interpreted as a diagnosis or treatment recommendation must be explicitly disclaimed and redirected to qualified medical care.

---

## 2. Emergency Warning Rules

- **Mandatory emergency disclaimer:** If the user describes or implies any of the following, the system MUST display a clear emergency warning before any other content:
  - Suicidal or self-harm intent
  - Severe allergic reaction (e.g. anaphylaxis)
  - Difficulty breathing, chest pain, or signs of heart attack/stroke
  - Unconsciousness, severe bleeding, or major trauma
  - Suspected poisoning or overdose
  - Severe abdominal pain, sudden severe headache, or other acute life-threatening symptoms
  - Any situation where delay could cause serious harm

- **Required wording (or equivalent):**  
  *"This may be a medical emergency. Please call emergency services [e.g. 911 / local emergency number] or go to the nearest emergency department immediately. This system cannot provide emergency care."*

- The emergency warning must be visually prominent (e.g. at the top of the response) and must not be buried in long text.

---

## 3. Prohibited Outputs

The system MUST NOT:

- State or imply a specific medical diagnosis for the user.
- Recommend, prescribe, or discourage specific prescription or over-the-counter medications (beyond general, non-personalized information where appropriate).
- Advise delaying or avoiding emergency or urgent medical care.
- Provide dosage, regimen, or treatment plans tailored to an individual’s condition.
- Encourage discontinuing or changing prescribed treatment without a doctor’s guidance.
- Make definitive claims about cure, prognosis, or outcome for a specific person.
- Output content that could be used to self-diagnose or self-treat in place of a clinician.
- Use user-provided personal health data to infer or state diagnoses.

Violations must be caught by content checks and blocked or rewritten before response delivery.

---

## 4. Response Template Requirements

- **Every user-facing response** must include (in substance, not necessarily verbatim):
  1. **Disclaimer:** A short statement that this is not medical advice and does not replace a healthcare professional (e.g. *"This is general information only, not medical advice. Always consult a qualified healthcare provider for your situation."*).
  2. **Scope boundary:** If the query touches diagnosis or treatment, an explicit reminder that the system does not diagnose or prescribe (e.g. *"I cannot diagnose conditions or recommend specific treatments. Please see a doctor for that."*).
  3. **Encouragement to seek care:** When the topic is symptoms, conditions, or treatment, a clear prompt to consult a doctor or other appropriate provider.

- Templates must be enforced programmatically (e.g. prepended or appended to responses, or validated before display). Placeholder or optional disclaimer blocks are not sufficient; inclusion must be guaranteed.

---

## 5. Data Privacy Notes

- **Sensitive data:** User inputs may contain health-related and other sensitive personal data. Such data must be treated as confidential and must not be used for purposes beyond providing the response (e.g. no training on user data without explicit, lawful consent and disclosure).
- **Retention and storage:** Do not retain user health data longer than necessary for the stated purpose. Define and enforce retention limits and secure deletion.
- **Sharing:** Do not share, sell, or expose user health information to third parties except as required by law or with clear, informed user consent for a specific purpose.
- **Security:** Apply appropriate technical and organizational measures (e.g. encryption in transit and at rest, access controls, audit logging) for any stored or processed health-related data.
- **Transparency:** Privacy policy and terms must clearly state how health and personal data are collected, used, stored, and protected in the context of this product.

---

*This document is part of the product safety and compliance baseline. All implementations and prompts must align with these guidelines.*
