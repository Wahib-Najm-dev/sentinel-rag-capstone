# SentinelRAG — Domain Definition

## Project Overview

**Project Name:** SentinelRAG  
**Domain:** SOC Operations and Cybersecurity Incident Response  
**Author:** Wahib Najm Al-dain Al-Refaei  
**Primary Language:** English

SentinelRAG is an evidence-grounded Retrieval-Augmented Generation (RAG) assistant designed to help cybersecurity professionals quickly retrieve authoritative guidance for Security Operations Center (SOC) activities and cybersecurity incident response.

The system retrieves relevant evidence from trusted cybersecurity documents and uses that evidence to generate grounded answers with visible source attribution. It is designed to reduce unsupported model-generated claims by requiring answers to be based on retrieved evidence.

## Target Users

### Primary Users

- Junior SOC Analysts
- Mid-level SOC Analysts
- Incident Response Analysts

These users often need to locate incident-handling procedures, containment guidance, recovery steps, and security recommendations quickly while investigating security events.

### Secondary Users

- Cybersecurity students
- Security engineers
- Security practitioners studying incident response procedures

## Supported Knowledge Areas

SentinelRAG focuses on operational cybersecurity guidance related to:

- Security incident identification and triage
- Phishing incidents
- Ransomware incidents
- Malware incidents
- Credential compromise
- Web application security incidents
- Incident containment
- Threat eradication
- System recovery
- Security logging and monitoring
- Incident reporting and documentation
- Incident response lifecycle and procedures
- Relevant defensive security controls
- SOC and incident-response best practices

## Supported Question Types

The system is intended to answer evidence-based questions such as:

- What steps should an analyst take after identifying a phishing incident?
- What containment actions are recommended during a ransomware incident?
- How should compromised credentials be handled?
- What evidence should be collected during incident response?
- What guidance is provided for recovering systems after an incident?
- What logging and monitoring practices support incident detection?
- What incident-response procedures are recommended by authoritative cybersecurity organizations?

The final supported questions will depend on the content actually present in the project's verified document corpus.

## Source Policy

The knowledge base will contain approximately 20–50 high-quality documents relevant to SOC operations and cybersecurity incident response.

Core sources should come from authoritative organizations such as:

- National Institute of Standards and Technology (NIST)
- Cybersecurity and Infrastructure Security Agency (CISA)
- Open Worldwide Application Security Project (OWASP)
- MITRE
- Other recognized government agencies, standards organizations, universities, and trusted cybersecurity institutions when directly relevant to the project scope

Random blogs, unverified tutorials, and low-authority content will not be used as core knowledge sources.

Every source must be verified before it is included in the corpus.

## Scope

SentinelRAG is a defensive cybersecurity knowledge assistant.

The system focuses on retrieving and explaining documented guidance that supports SOC operations and incident-response workflows.

The system is not intended to replace organizational incident-response plans, security professionals, forensic investigation, or organization-specific decision-making.

## Limitations

SentinelRAG can only answer reliably when relevant evidence exists in its indexed corpus.

Its knowledge is limited by:

- The documents included in the corpus
- The quality and currency of those documents
- Retrieval performance
- The scope of the selected authoritative sources
- Information explicitly available in retrieved evidence

If sufficient evidence cannot be retrieved, the system should clearly state that the available evidence is insufficient rather than inventing an answer.

The system does not guarantee that its guidance applies to every organization's infrastructure, legal obligations, policies, or threat environment.

## Safety Boundaries

SentinelRAG is intended for defensive cybersecurity and incident-response use.

The assistant should:

- Ground answers in retrieved authoritative evidence.
- Clearly expose the supporting sources and evidence passages.
- Avoid inventing procedures, statistics, thresholds, or recommendations.
- State when the retrieved evidence is insufficient.
- Prefer defensive incident-response guidance over unsupported operational assumptions.
- Avoid presenting generated output as a substitute for organization-specific policies or professional judgment.

Potentially sensitive security actions should remain grounded in the authoritative source material contained in the corpus.

## Success Criteria

The project will be considered technically successful when it demonstrates:

- A corpus of 20–50 verified authoritative documents
- A reproducible ingestion pipeline
- Hybrid vector and BM25 retrieval
- Reciprocal Rank Fusion (RRF)
- Cohere reranking
- Five final evidence passages per query
- Evidence-grounded answer generation
- Recall@5 of at least 80% on 30 manually verified golden questions
- RAGAS evaluation on 20 questions
- Visible source attribution and evidence in the user interface
- Password authentication
- A publicly accessible deployed application
- Documented architecture, evaluation, cost analysis, and real-user testing