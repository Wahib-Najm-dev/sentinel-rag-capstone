# SentinelRAG Real-User Testing

## Purpose

Validate the usability, authentication flow, answer quality, and evidence presentation of SentinelRAG with three real users.

## Test Environment

- Application: SentinelRAG
- Interface: Streamlit
- Authentication: Password-protected
- Retrieval: Vector Top-25 + BM25 Top-20 + RRF
- Reranking: Cohere rerank-v3.5
- Final evidence: Top-5
- Test mode: Local application
- User identities: Anonymized

---

## Tester 1

- Tester ID: U01
- Login successful: Yes
- Logout completed before next tester: Yes
- Question asked:
  What steps should a SOC team take to contain a ransomware incident while preserving evidence for investigation?
- Answer useful: Partially
- Evidence easy to understand: Yes
- Interface easy to use: Yes
- Overall rating: 3.5 / 5

### Positive feedback

The answer was comprehensive and relied directly on trusted CISA guidance. It covered important containment and evidence-preservation actions such as forensic image capture and network isolation.

### Issues reported

The answer repeated several points almost verbatim and did not reorganize the evidence into a clear sequence of actions for a SOC team responding specifically to ransomware.

### Improvement opportunity

Improve answer synthesis so retrieved evidence is paraphrased and organized into a clear operational sequence such as:
1. Immediate containment
2. Evidence preservation
3. Scope assessment
4. Eradication preparation
5. Recovery coordination

---

## Tester 2

- Tester ID: U02
- Login successful: Yes
- Logout completed before next tester: Yes
- Question asked:
  Which security events should a web application log to help detect attacks and support incident investigations?
- Answer useful: Yes
- Evidence easy to understand: Yes
- Interface easy to use: Yes
- Overall rating: 4.5 / 5

### Positive feedback

The answer was comprehensive and covered major web-application security events including authentication, authorization, session management, and application errors using standard sources such as OWASP. The concluding guidance correctly emphasized recording the key event attributes: When, Where, Who, and What.

### Issues reported

The answer used very concise headings without enough quick practical examples showing how the logged events could help detect attacks.

### Improvement opportunity

Add short operational examples where supported by evidence, such as:
- repeated authentication failures for brute-force or credential attacks
- input-validation failures as indicators of malicious requests
- privilege changes for authorization abuse
- session anomalies for session attacks

---

## Tester 3

- Tester ID: U03
- Login successful: Yes
- Logout completed before next tester: Yes
- Question asked:
  What behaviors and telemetry can defenders monitor to detect process injection techniques on Windows?
- Answer useful: Yes
- Evidence easy to understand: Yes
- Interface easy to use: Yes
- Overall rating: 4.0 / 5

### Positive feedback

The answer was technically accurate and focused on Process Injection. It identified relevant Windows API activity such as VirtualAllocEx, WriteProcessMemory, and CreateRemoteThread, as well as registry changes and suspicious API-call sequences.

### Issues reported

Some included behaviors were too general and not specific enough to Process Injection, such as process/service termination and absence of telemetry associated with defensive-tool disruption. The answer also repeatedly used similar sentence openings instead of grouping observations into clear categories.

### Improvement opportunity

Organize technical detection guidance into categories such as:
- API Monitoring
- Memory Analysis
- Process Relationships
- Registry / Persistence Context
- Telemetry Sources

Also prioritize evidence that is specifically related to Process Injection over broader defensive-evasion behaviors.

---

## Testing Summary

- Total testers: 3
- Successful logins: 3 / 3
- Successful logout-and-new-login cycles: 3 / 3
- Successful question-answer sessions: 3 / 3
- Average rating: 4.0 / 5
- Authentication failures during testing: 0

### Common positive feedback

- Answers were technically grounded in authoritative cybersecurity sources.
- Retrieved evidence was useful and understandable.
- The interface and authentication flow were easy to use.
- Coverage across CISA, OWASP, and MITRE ATT&CK was useful.

### Common issues

- Some answers repeated retrieved wording instead of synthesizing it.
- Some responses could be organized more clearly for operational use.
- Practical examples were sometimes too limited.
- Some retrieved evidence was broader than the exact question scope.

### Planned improvements

1. Strengthen the answer-generation prompt to reduce repetition.
2. Require clearer operational organization.
3. Prefer concise synthesis rather than repeating retrieved passages.
4. Add short practical examples only when directly supported by evidence.
5. Emphasize the most question-specific evidence and avoid overly broad evidence where possible.

### Final Phase 4 status

Phase 4 real-user testing completed successfully with three real users. All three users authenticated successfully, completed a question-answer session, reviewed evidence, logged out, and provided feedback. The average rating was 4.0 / 5.
