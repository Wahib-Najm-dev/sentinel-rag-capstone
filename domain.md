# SentinelRAG — Domain Definition

# English Version

## 1. Project Information

**Project Name:** SentinelRAG  
**Domain:** SOC Operations and Cybersecurity Incident Response  
**Author:** Wahib Najm Al-dain Al-Refaei  
**Primary Knowledge Language:** English  
**Repository:** https://github.com/Wahib-Najm-dev/sentinel-rag-capstone

---

## 2. Chosen Domain

SentinelRAG focuses on **Security Operations Center (SOC) operations and cybersecurity incident response**.

The project is an evidence-grounded Retrieval-Augmented Generation (RAG) assistant designed to help cybersecurity professionals retrieve relevant guidance from authoritative cybersecurity documents and use that evidence to answer operational security questions.

This domain was selected because SOC and incident-response work depends heavily on quickly finding reliable procedures, technical recommendations, defensive controls, detection guidance, forensic considerations, and recovery practices across many security publications.

A general-purpose language model may provide plausible but unsupported answers. SentinelRAG therefore retrieves evidence from a verified cybersecurity corpus before generating an answer.

---

## 3. Why This Domain Was Selected

Cybersecurity incident response is a suitable domain for a RAG system because the required knowledge is distributed across many standards, playbooks, frameworks, technical guides, and defensive knowledge bases.

A SOC analyst may need information about:

- ransomware containment;
- phishing response;
- logging requirements;
- malware handling;
- digital forensics;
- authentication incidents;
- credential attacks;
- threat intelligence;
- recovery procedures;
- MITRE ATT&CK techniques;
- detection strategies.

Searching these sources manually can require moving between many long documents and websites.

SentinelRAG is designed to make this knowledge searchable through one evidence-grounded interface while preserving the original source information.

---

## 4. Target Users

### Primary Users

The main intended users are:

- Junior SOC analysts
- Mid-level SOC analysts
- Incident Response analysts

### Secondary Users

The system may also support:

- Cybersecurity students
- Security engineers
- Defensive security practitioners
- Professionals studying incident response and security standards

SentinelRAG assists users in locating documented evidence. It does not replace experienced incident responders, forensic specialists, organizational security teams, or formal incident-response plans.

---

## 5. Supported Knowledge Areas

The knowledge corpus covers areas including:

- Incident response lifecycle
- Incident triage
- Ransomware response
- Ransomware protection
- Ransomware detection
- Ransomware recovery
- Phishing defense
- Malware incident handling
- Security logging
- Continuous monitoring
- Digital forensics
- Mobile device forensics
- Authentication security
- Multifactor authentication
- Credential stuffing
- Account recovery
- Session security
- API and REST security
- Zero Trust architecture
- Cyber threat information sharing
- Security testing and assessment
- Defensive security controls
- MITRE ATT&CK techniques
- MITRE ATT&CK detection strategies

---

## 6. Types of Questions Supported

SentinelRAG is intended to answer questions such as:

- What actions are recommended when responding to a ransomware incident?
- What guidance exists for recovering from destructive cybersecurity events?
- What logs are useful during incident investigation?
- How should phishing attacks be mitigated?
- What defensive measures help prevent credential stuffing?
- What guidance exists for authentication and multifactor authentication?
- What forensic considerations apply during incident response?
- What recommendations exist for cyber threat information sharing?
- What controls can help protect systems against ransomware?
- What does MITRE ATT&CK document about technique T1055.011?
- What detection strategies are associated with ATT&CK techniques?
- What guidance exists for security monitoring and recovery?

The exact answerable questions depend on the information contained in the verified corpus.

If sufficient evidence is not retrieved, SentinelRAG should clearly state that the available evidence is insufficient rather than inventing an answer.

---

## 7. Source Collection

SentinelRAG currently uses **26 verified authoritative cybersecurity sources**, satisfying the project requirement to collect between 20 and 50 high-quality documents.

The current corpus contains:

- 17 PDF documents
- 8 HTML documents
- 1 structured MITRE ATT&CK JSON dataset
- 26 verified sources in total

The main organizations represented in the corpus are:

- NIST — National Institute of Standards and Technology
- CISA — Cybersecurity and Infrastructure Security Agency
- OWASP — Open Worldwide Application Security Project
- MITRE ATT&CK

The detailed source inventory is maintained in:

`data/sources_manifest.csv`

The capstone requires 20–50 high-quality documents. SentinelRAG satisfies this with 26 verified authoritative cybersecurity sources.

---

## 8. Why These Sources Were Selected

### NIST

NIST was selected because it publishes authoritative cybersecurity standards, frameworks, and technical guidance.

The selected NIST publications provide coverage of areas such as:

- incident response;
- ransomware risk management;
- cybersecurity recovery;
- malware handling;
- digital forensics;
- log management;
- continuous monitoring;
- security testing;
- Zero Trust;
- cybersecurity risk management;
- cyber threat information sharing;
- mobile device forensics.

These documents are especially useful for policy-oriented, procedural, and standards-based cybersecurity questions.

### CISA

CISA was selected because it provides operational cybersecurity guidance intended for defenders and organizations responding to active threats.

The corpus includes guidance related to:

- ransomware;
- incident and vulnerability response;
- phishing.

This complements the standards-oriented NIST material with practical defensive guidance.

### OWASP

OWASP was selected because application security incidents are common in SOC environments.

The selected OWASP guidance covers:

- security logging;
- authentication;
- session management;
- credential stuffing;
- multifactor authentication;
- password recovery;
- REST and API security.

These sources help SentinelRAG answer application-security and identity-related defensive questions.

### MITRE ATT&CK

MITRE ATT&CK was selected because SOC analysts frequently work with attacker tactics, techniques, and detection strategies.

The structured ATT&CK dataset allows SentinelRAG to retrieve information about identifiers such as:

`T1055.011`

as well as related detection strategies.

This is particularly valuable for exact cybersecurity identifiers that may not be handled as effectively by purely semantic retrieval.

---

## 9. Corpus Quality Policy

The project uses authoritative and institutional sources as the core knowledge base.

Random blogs and unverified tutorials are not used as primary sources.

The corpus download and validation process checks that source files are available and usable before ingestion.

Current corpus validation result:

- Manifest sources: 26
- Valid sources: 26
- Invalid sources: 0
- Missing sources: 0

The source manifest provides reproducibility by recording the organization, title, URL, document format, local filename, and verification status.

---

## 10. Project Scope

SentinelRAG is a **defensive cybersecurity knowledge assistant**.

It is designed to:

- retrieve authoritative cybersecurity evidence;
- support SOC and incident-response research;
- help users locate documented defensive guidance;
- generate answers grounded in retrieved evidence;
- display source attribution;
- preserve useful source metadata;
- reduce unsupported model-generated claims.

The project focuses on knowledge retrieval and evidence-grounded answering rather than autonomous security operations.

---

## 11. Out of Scope

SentinelRAG is not intended to:

- replace an organization's official incident-response plan;
- replace professional incident responders;
- replace digital forensic specialists;
- make legal or regulatory decisions;
- automatically contain or remediate incidents;
- guarantee that general guidance applies to every organization;
- provide unsupported recommendations that are absent from the corpus;
- perform offensive cybersecurity operations.

---

## 12. Limitations

### Corpus Limitation

The system can only retrieve information that exists in the indexed corpus.

### Retrieval Limitation

Relevant information may exist in the corpus but may not always be ranked among the highest retrieval results.

### Currency Limitation

Cybersecurity guidance changes over time. New revisions or recommendations may supersede older publications.

### Organizational Context Limitation

Public standards and guidance cannot account for every organization's architecture, policies, regulatory obligations, risk tolerance, or incident-response procedures.

### Model Limitation

A language model may still misunderstand or incorrectly summarize retrieved evidence. Therefore, evidence and source information should remain visible to users.

### Evaluation Limitation

System quality must be demonstrated using measured retrieval and generation evaluation rather than assumed from implementation alone.

---

## 13. Safety Boundaries

SentinelRAG follows these principles:

- Answers should be grounded in retrieved authoritative evidence.
- Source information should be visible to users.
- Sources and page numbers must not be invented.
- Statistics, thresholds, procedures, and recommendations must not be fabricated.
- The system should clearly state when evidence is insufficient.
- Defensive guidance should be prioritized.
- General guidance should not be represented as organization-specific policy.
- SentinelRAG should not be represented as a substitute for professional incident-response judgment.
- The system should not claim guaranteed security outcomes.

---

## 14. Phase 1 Completion Status

The first project phase currently includes:

- Defined cybersecurity domain
- Defined target users
- Defined supported question categories
- Defined source policy
- Defined project scope
- Defined limitations
- Defined safety boundaries
- 26 verified authoritative sources
- Reproducible source manifest
- Public GitHub repository

---

# النسخة العربية

## 1. معلومات المشروع

**اسم المشروع:** SentinelRAG  
**المجال:** عمليات مركز العمليات الأمنية والاستجابة للحوادث السيبرانية  
**المؤلف:** Wahib Najm Al-dain Al-Refaei  
**اللغة الأساسية لمصادر المعرفة:** الإنجليزية  
**مستودع المشروع:** https://github.com/Wahib-Najm-dev/sentinel-rag-capstone

---

## 2. المجال المختار

يركز مشروع SentinelRAG على **عمليات مركز العمليات الأمنية (SOC) والاستجابة للحوادث السيبرانية**.

المشروع عبارة عن مساعد يعتمد على تقنية الاسترجاع المعزز بالتوليد (RAG)، وقد تم تصميمه لمساعدة المختصين في الأمن السيبراني على استرجاع الإرشادات ذات الصلة من مصادر أمنية موثوقة ثم استخدام هذه الأدلة للإجابة عن الأسئلة التشغيلية المتعلقة بالأمن السيبراني.

تم اختيار هذا المجال لأن عمل محلل SOC والاستجابة للحوادث يعتمد بدرجة كبيرة على الوصول السريع إلى الإجراءات الموثوقة والتوصيات التقنية والضوابط الدفاعية وإرشادات الكشف والأدلة الجنائية الرقمية وإجراءات التعافي الموجودة في عدد كبير من المنشورات الأمنية.

قد يقدم النموذج اللغوي العام إجابات تبدو منطقية ولكنها غير مدعومة بمصدر. لذلك يقوم SentinelRAG أولًا باسترجاع الأدلة من Corpus أمني موثوق قبل توليد الإجابة.

---

## 3. سبب اختيار هذا المجال

يُعد مجال الاستجابة للحوادث السيبرانية مناسبًا جدًا لأنظمة RAG لأن المعرفة المطلوبة موزعة بين عدد كبير من المعايير والأدلة وخطط الاستجابة والأطر الأمنية وقواعد المعرفة التقنية.

قد يحتاج محلل SOC إلى معلومات متعلقة بـ:

- احتواء هجمات الفدية؛
- الاستجابة للتصيد الاحتيالي؛
- السجلات الأمنية؛
- التعامل مع البرمجيات الخبيثة؛
- الأدلة الجنائية الرقمية؛
- حوادث المصادقة؛
- هجمات بيانات الاعتماد؛
- استخبارات التهديدات؛
- إجراءات التعافي؛
- تقنيات MITRE ATT&CK؛
- استراتيجيات الكشف.

البحث اليدوي عن هذه المعلومات قد يتطلب التنقل بين عدد كبير من الوثائق الطويلة والمواقع المختلفة.

لذلك تم تصميم SentinelRAG لجعل هذه المعرفة قابلة للبحث من خلال واجهة واحدة مع الحفاظ على معلومات المصدر الأصلي.

---

## 4. المستخدمون المستهدفون

### المستخدمون الأساسيون

المستخدمون الأساسيون للنظام هم:

- محللو SOC المبتدئون
- محللو SOC في المستوى المتوسط
- محللو الاستجابة للحوادث

### المستخدمون الثانويون

يمكن أن يستفيد من النظام أيضًا:

- طلاب الأمن السيبراني
- مهندسو الأمن
- العاملون في الأمن الدفاعي
- المهتمون بدراسة الاستجابة للحوادث والمعايير الأمنية

يساعد SentinelRAG المستخدمين في الوصول إلى الأدلة الموثقة، لكنه لا يستبدل خبراء الاستجابة للحوادث أو المتخصصين في الأدلة الجنائية الرقمية أو فرق الأمن داخل المؤسسات أو خطط الاستجابة الرسمية الخاصة بالمؤسسة.

---

## 5. مجالات المعرفة التي يغطيها النظام

يغطي Corpus الخاص بالمشروع مجالات منها:

- دورة حياة الاستجابة للحوادث
- فرز الحوادث وتحليلها
- الاستجابة لبرمجيات الفدية
- الحماية من برمجيات الفدية
- اكتشاف برمجيات الفدية
- التعافي من برمجيات الفدية
- الدفاع ضد التصيد الاحتيالي
- التعامل مع حوادث البرمجيات الخبيثة
- السجلات الأمنية
- المراقبة المستمرة
- الأدلة الجنائية الرقمية
- الأدلة الجنائية للأجهزة المحمولة
- أمن المصادقة
- المصادقة متعددة العوامل
- هجمات Credential Stuffing
- استعادة الحسابات
- أمن الجلسات
- أمن REST وواجهات API
- بنية Zero Trust
- مشاركة معلومات التهديدات السيبرانية
- الاختبارات والتقييمات الأمنية
- الضوابط الأمنية الدفاعية
- تقنيات MITRE ATT&CK
- استراتيجيات الكشف في MITRE ATT&CK

---

## 6. أنواع الأسئلة التي يدعمها النظام

تم تصميم SentinelRAG للإجابة عن أسئلة مثل:

- ما الإجراءات الموصى بها عند الاستجابة لهجوم Ransomware؟
- ما الإرشادات المتوفرة للتعافي من الأحداث السيبرانية المدمرة؟
- ما أنواع السجلات المفيدة أثناء التحقيق في الحوادث؟
- كيف يمكن الحد من هجمات التصيد الاحتيالي؟
- ما التدابير الدفاعية التي تساعد في منع Credential Stuffing؟
- ما الإرشادات المتعلقة بالمصادقة والمصادقة متعددة العوامل؟
- ما الاعتبارات المتعلقة بالأدلة الجنائية الرقمية أثناء الاستجابة للحوادث؟
- ما التوصيات المتعلقة بمشاركة معلومات التهديدات السيبرانية؟
- ما الضوابط التي تساعد على حماية الأنظمة من برمجيات الفدية؟
- ماذا توثق MITRE ATT&CK عن التقنية T1055.011؟
- ما استراتيجيات الكشف المرتبطة بتقنيات ATT&CK؟
- ما الإرشادات المتعلقة بالمراقبة الأمنية والتعافي؟

تعتمد الأسئلة التي يستطيع النظام الإجابة عنها فعليًا على المعلومات الموجودة داخل Corpus الموثق.

إذا لم يتم العثور على أدلة كافية، فيجب على SentinelRAG التصريح بعدم كفاية الأدلة بدلًا من اختراع إجابة.

---

## 7. جمع المصادر

يستخدم SentinelRAG حاليًا **26 مصدرًا موثوقًا وعالي الجودة في الأمن السيبراني**، وبذلك يحقق شرط المشروع الذي يطلب جمع ما بين 20 و50 وثيقة عالية الجودة.

يتكون Corpus الحالي من:

- 17 وثيقة PDF
- 8 صفحات HTML
- مجموعة بيانات MITRE ATT&CK منظمة بصيغة JSON
- إجمالي 26 مصدرًا موثقًا

الجهات الرئيسية الموجودة في Corpus هي:

- NIST
- CISA
- OWASP
- MITRE ATT&CK

يتم الاحتفاظ بالقائمة التفصيلية للمصادر في:

`data/sources_manifest.csv`

ويشترط المشروع استخدام ما بين 20 و50 مصدرًا عالي الجودة، ويحقق SentinelRAG ذلك باستخدام 26 مصدرًا موثقًا من جهات موثوقة.

---

## 8. سبب اختيار هذه المصادر

### NIST

تم اختيار NIST لأنها تنشر معايير وأطرًا وإرشادات تقنية رسمية في الأمن السيبراني.

وتوفر المصادر المختارة منها تغطية لمجالات مثل:

- الاستجابة للحوادث؛
- إدارة مخاطر برمجيات الفدية؛
- التعافي السيبراني؛
- التعامل مع البرمجيات الخبيثة؛
- الأدلة الجنائية الرقمية؛
- إدارة السجلات؛
- المراقبة المستمرة؛
- الاختبارات الأمنية؛
- Zero Trust؛
- إدارة المخاطر السيبرانية؛
- مشاركة معلومات التهديدات؛
- الأدلة الجنائية للأجهزة المحمولة.

وهذا يجعلها مناسبة جدًا للأسئلة المتعلقة بالمعايير والإجراءات والسياسات الأمنية.

### CISA

تم اختيار CISA لأنها توفر إرشادات تشغيلية ودفاعية للمؤسسات والفرق التي تتعامل مع التهديدات السيبرانية.

وتغطي المصادر الموجودة منها موضوعات مثل:

- Ransomware؛
- الاستجابة للحوادث والثغرات؛
- التصيد الاحتيالي.

وهذا يكمل مصادر NIST ذات الطابع المعياري بإرشادات دفاعية أكثر عملية.

### OWASP

تم اختيار OWASP لأن حوادث أمن تطبيقات الويب والمصادقة تشكل جزءًا مهمًا من عمل فرق SOC.

وتغطي المصادر المختارة:

- Logging؛
- Authentication؛
- Session Management؛
- Credential Stuffing؛
- MFA؛
- استعادة كلمات المرور؛
- REST وAPI Security.

وهذا يساعد النظام في الإجابة عن الأسئلة المتعلقة بأمن التطبيقات والهوية.

### MITRE ATT&CK

تم اختيار MITRE ATT&CK لأن محللي SOC يتعاملون بشكل متكرر مع تكتيكات وتقنيات المهاجمين واستراتيجيات الكشف.

وتسمح البيانات المنظمة للنظام باسترجاع معلومات دقيقة عن معرفات مثل:

`T1055.011`

بالإضافة إلى استراتيجيات الكشف المرتبطة بها.

وهذا مهم جدًا للمصطلحات والمعرفات التقنية الدقيقة في الأمن السيبراني.

---

## 9. سياسة جودة Corpus

يعتمد المشروع على المصادر الرسمية والمؤسسات الموثوقة باعتبارها قاعدة المعرفة الأساسية.

ولا يتم استخدام المدونات العشوائية أو الشروحات غير الموثوقة كمصادر أساسية.

تقوم عملية تنزيل وفحص Corpus بالتحقق من صلاحية الملفات قبل إدخالها إلى نظام RAG.

نتيجة التحقق الحالية:

- عدد المصادر في Manifest: 26
- المصادر الصالحة: 26
- المصادر غير الصالحة: 0
- المصادر المفقودة: 0

يساعد `sources_manifest.csv` على إعادة إنتاج Corpus لأنه يسجل اسم الجهة والعنوان والرابط ونوع الملف والاسم المحلي وحالة التحقق.

---

## 10. نطاق المشروع

SentinelRAG هو **مساعد معرفي للأمن السيبراني الدفاعي**.

وهو مصمم من أجل:

- استرجاع الأدلة الأمنية الموثوقة؛
- دعم أعمال البحث الخاصة بـSOC والاستجابة للحوادث؛
- مساعدة المستخدم في العثور على الإرشادات الدفاعية الموثقة؛
- توليد إجابات تعتمد على الأدلة المسترجعة؛
- إظهار المصادر المستخدمة؛
- الحفاظ على Metadata المهمة للمصادر؛
- تقليل الادعاءات غير المدعومة التي قد يولدها النموذج.

يركز المشروع على استرجاع المعرفة وتوليد إجابات موثقة، وليس على تنفيذ العمليات الأمنية تلقائيًا.

---

## 11. ما يقع خارج نطاق المشروع

لا يهدف SentinelRAG إلى:

- استبدال خطة الاستجابة للحوادث الخاصة بالمؤسسة؛
- استبدال خبراء الاستجابة للحوادث؛
- استبدال خبراء الأدلة الجنائية الرقمية؛
- اتخاذ قرارات قانونية أو تنظيمية؛
- تنفيذ احتواء أو معالجة للحوادث تلقائيًا؛
- ضمان أن الإرشادات العامة مناسبة لكل مؤسسة؛
- تقديم توصيات لا توجد في Corpus؛
- تنفيذ عمليات هجومية في الأمن السيبراني.

---

## 12. القيود

### قيود Corpus

لا يستطيع النظام استرجاع معلومات غير موجودة داخل Corpus المفهرس.

### قيود الاسترجاع

قد تكون المعلومة موجودة في Corpus ولكن لا تظهر دائمًا ضمن النتائج الأعلى ترتيبًا.

### قيود حداثة المعلومات

يتطور الأمن السيبراني بسرعة، وقد تظهر إصدارات أو توصيات أحدث من بعض الوثائق المستخدمة.

### قيود سياق المؤسسة

لا تستطيع المعايير العامة أخذ بنية وسياسات والتزامات ومخاطر كل مؤسسة في الاعتبار.

### قيود النموذج

قد يسيء النموذج اللغوي تفسير أو تلخيص الأدلة المسترجعة، ولذلك يجب عرض الأدلة والمصادر للمستخدم.

### قيود التقييم

لا يجوز افتراض جودة النظام من مجرد نجاح التنفيذ، بل يجب قياسها باستخدام اختبارات فعلية مثل Recall@5 وRAGAS.

---

## 13. حدود السلامة

يتبع SentinelRAG المبادئ التالية:

- يجب أن تعتمد الإجابات على أدلة موثوقة تم استرجاعها.
- يجب إظهار معلومات المصادر للمستخدم.
- لا يجوز اختراع أسماء المصادر أو أرقام الصفحات.
- لا يجوز اختراع الإحصائيات أو الحدود أو الإجراءات أو التوصيات.
- يجب التصريح بوضوح عند عدم كفاية الأدلة.
- يجب إعطاء الأولوية للإرشادات الدفاعية.
- لا يجوز تقديم الإرشادات العامة على أنها سياسة خاصة بمؤسسة معينة.
- لا يجب تقديم النظام على أنه بديل للحكم المهني لخبراء الاستجابة للحوادث.
- لا يجب ادعاء تحقيق نتائج أمنية مضمونة.

---

## 14. حالة إنجاز المرحلة الأولى

تشمل المرحلة الأولى حاليًا:

- تحديد مجال الأمن السيبراني
- تحديد المستخدمين المستهدفين
- تحديد أنواع الأسئلة
- تحديد سياسة المصادر
- تحديد نطاق المشروع
- تحديد القيود
- تحديد حدود السلامة
- جمع 26 مصدرًا موثوقًا
- إنشاء Source Manifest قابل لإعادة الإنتاج
- إنشاء وربط مستودع GitHub عام