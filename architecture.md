# SentinelRAG — System Architecture

# English Version

## 1. Architecture Overview

**Project Name:** SentinelRAG  
**Domain:** SOC Operations and Cybersecurity Incident Response  
**Author:** Wahib Najm Al-dain Al-Refaei  
**Primary Knowledge Language:** English  

SentinelRAG is an evidence-grounded Retrieval-Augmented Generation (RAG) system designed to help SOC and Incident Response professionals retrieve trusted cybersecurity guidance and generate answers based on retrieved evidence.

The architecture contains two main pipelines:

1. Offline Ingestion Pipeline
2. Online Query Pipeline

The implementation is intentionally lightweight and transparent so that retrieval, evaluation, and deployment remain easy to understand and reproduce.

---

## 2. High-Level Architecture

OFFLINE PIPELINE

Authoritative cybersecurity sources  
↓  
PDF / HTML / MITRE JSON extraction  
↓  
Text cleaning and metadata preservation  
↓  
Structure-aware recursive chunking  
↓  
~350 tokens per chunk + ~60-token overlap  
↓  
Deterministic chunk IDs  
↓  
E5 embeddings + BM25 lexical indexing  
↓  
ChromaDB + BM25 persistent indexes  

ONLINE PIPELINE

User question  
↓  
E5 query embedding  
↓  
Vector Top 20 + BM25 Top 20  
↓  
Reciprocal Rank Fusion  
↓  
Cohere reranking  
↓  
Top 5 evidence passages  
↓  
Cohere generation  
↓  
Evidence-grounded answer + sources + pages + scores

---

## 3. Source Collection

SentinelRAG currently uses **26 verified authoritative cybersecurity sources**.

The corpus contains:

- 17 PDF documents
- 8 HTML documents
- 1 structured MITRE ATT&CK JSON dataset

The main organizations are:

- NIST
- CISA
- OWASP
- MITRE ATT&CK

The complete source inventory is stored in:

`data/sources_manifest.csv`

### Why These Sources Were Chosen

Cybersecurity incident response is a high-impact domain where incorrect guidance can affect containment, investigation, evidence preservation, and recovery.

For that reason, SentinelRAG uses official standards, government cybersecurity guidance, and established security knowledge bases instead of random blogs or unverified tutorials.

---

## 4. Document Extraction

PDF files are extracted using `PyMuPDF`.

The system preserves:

- source ID
- source filename
- title
- page number
- document type
- extracted text

### Why PyMuPDF Was Chosen

Many NIST and CISA sources are long PDF documents.

Page-level attribution is important because users should be able to verify where retrieved evidence originated.

PyMuPDF provides efficient page-by-page extraction while preserving page information.

HTML sources are processed using `BeautifulSoup`.

Navigation menus, scripts, styles, headers, footers, breadcrumbs, and similar interface elements are removed so that retrieval focuses on actual cybersecurity content.

MITRE ATT&CK is processed from structured JSON/STIX data so techniques and detection strategies can be indexed separately with identifiers such as `T1055.011`.

---

## 5. Text Cleaning

SentinelRAG performs conservative text cleaning.

The pipeline removes unnecessary whitespace, broken formatting, and obvious website artifacts without aggressively rewriting technical content.

### Why Conservative Cleaning Was Chosen

Cybersecurity documents contain important identifiers, acronyms, protocol names, commands, procedures, and security terminology.

Aggressive cleaning could accidentally remove information that is useful for retrieval.

---

## 6. Chunking Strategy

SentinelRAG uses **structure-aware recursive chunking**.

Configuration:

- Maximum chunk size: approximately 350 tokens
- Overlap: approximately 60 tokens

Each chunk preserves metadata such as:

`chunk_id`, `source_id`, `source`, `title`, `page`, `section_id`, `chunk_index`, `token_count`, and `text`.

Chunk IDs are deterministic.

### Why Structure-Aware Recursive Chunking Was Chosen

Cybersecurity documents often contain procedures, numbered steps, controls, technical explanations, and incident-response recommendations.

A fixed-character splitter could cut an important procedure in the middle.

A sentence-only splitter could produce very inconsistent chunk sizes.

Recursive chunking first tries to preserve meaningful boundaries and only splits more aggressively when necessary.

This provides a better balance between context preservation and retrieval precision.

---

## 7. Why Approximately 350 Tokens Were Chosen

Chunks that are too large may contain several unrelated topics such as detection, containment, and recovery in one embedding.

That can reduce retrieval precision.

Chunks that are too small may separate an instruction from its explanation or supporting context.

Approximately 350 tokens provides enough context for technical cybersecurity guidance while remaining small enough for precise retrieval.

---

## 8. Why Approximately 60 Tokens of Overlap Were Chosen

Overlap helps preserve context when an important procedure crosses a chunk boundary.

Without overlap, related instructions may be separated.

A very large overlap would create unnecessary duplication, increase index size, increase embedding time, and produce nearly identical search results.

Approximately 60 tokens provides useful continuity without excessive duplication.

---

## 9. Deterministic Chunk IDs

Chunk IDs are generated deterministically.

### Why This Is Important

The project later evaluates retrieval using Golden Questions and Recall@5.

Stable chunk IDs allow the same relevant chunks to be referenced after rebuilding the index.

They also help with reproducibility, debugging, and duplicate detection.

---

## 10. Embedding Model

SentinelRAG uses:

`intfloat/multilingual-e5-small`

Embedding dimension:

`384`

Documents use:

`passage: ...`

Queries use:

`query: ...`

Embeddings are normalized.

### Why multilingual-e5-small Was Chosen

The model was selected because it is designed for retrieval and works well with separate query and passage representations.

Semantic retrieval is important in cybersecurity because a user may ask:

"How should an infected system be isolated?"

while a source may use wording such as:

"containment of compromised hosts."

The meaning is related even when the wording differs.

The model is also small enough to run on CPU, which is important for Railway deployment with limited resources.

Its multilingual capability also provides flexibility if Arabic questions are supported later.

### Why a Larger Model Was Not Chosen

Larger embedding models may require significantly more memory and compute.

SentinelRAG prioritizes a stable, lightweight deployment, so a smaller local model is more suitable for this project.

---

## 11. Vector Database

SentinelRAG uses:

`ChromaDB`

The persistent index is stored under:

`data/index/`

The collection name is:

`sentinelrag_chunks`

Cosine distance is used for vector retrieval.

---

## 12. Why ChromaDB Was Chosen

ChromaDB was selected because it fits the actual scale and requirements of SentinelRAG.

The current pipeline contains:

- 26 documents
- 3737 extracted units
- 5802 chunks
- 5802 embeddings

This is a moderate corpus and does not require a distributed vector database.

ChromaDB provides:

- persistent storage
- vector similarity search
- metadata storage
- simple Python integration
- local reproducibility

Metadata is especially important for SentinelRAG because retrieved evidence must retain information such as source filename, document title, page number, and ATT&CK section ID.

### Why ChromaDB Instead of FAISS

FAISS provides efficient vector similarity search, but SentinelRAG also needs convenient persistence and metadata handling.

ChromaDB provides vector search, persistence, and metadata management together, reducing implementation complexity.

### Why ChromaDB Instead of Elasticsearch / OpenSearch

Elasticsearch and OpenSearch are powerful but introduce additional infrastructure and operational complexity.

For approximately 5802 chunks, that complexity is unnecessary.

BM25 already provides the lexical-search component separately.

### Why ChromaDB Instead of a Managed Vector Database

A hosted vector database would introduce extra credentials, network dependency, possible cost, and more deployment configuration.

For this academic project and corpus size, local persistent ChromaDB is simpler and easier to reproduce.

---

## 13. BM25 Lexical Index

SentinelRAG uses:

`rank-bm25`

BM25 is built using the exact same chunks stored in ChromaDB.

The persistent index is stored in:

`data/index/bm25_index.pkl`

### Why BM25 Is Needed

Vector search is strong for semantic similarity, but cybersecurity also contains exact technical identifiers such as:

- T1055.011
- CVE identifiers
- OAuth
- MFA
- malware names
- protocol names
- security acronyms

BM25 complements semantic retrieval by providing strong exact-term and lexical matching.

Therefore:

E5 + ChromaDB → semantic retrieval  
BM25 → lexical retrieval

Using both is more suitable for cybersecurity than relying on only one retrieval method.

---

## 14. BM25 Tokenization

The tokenizer lowercases text while preserving useful compound identifiers such as:

`T1055.011`  
`CVE-2025-1234`  
`oauth/token`

This is important because splitting cybersecurity identifiers into unrelated pieces could weaken exact retrieval.

---

## 15. Why Both Indexes Use the Same Chunks

Chunks are generated once and used for both:

E5 → ChromaDB  
BM25 → Lexical Index

This prevents the two retrieval systems from using different document segmentation.

It also allows the same deterministic chunk IDs to be used during hybrid retrieval and evaluation.

---

## 16. Clean Rebuild Strategy

The ingestion script rebuilds the indexes cleanly.

For ChromaDB, the previous collection is removed and rebuilt.

For BM25, the lexical index is rebuilt from the same current chunks.

### Why Clean Rebuilding Was Chosen

The corpus is small enough that rebuilding is practical.

This prevents stale chunks, duplicate vectors, deleted documents remaining in the index, and mismatches between ChromaDB and BM25.

Correctness and reproducibility are more important than incremental-indexing complexity for this capstone.

---

## 17. Verified Ingestion Results

The implemented ingestion pipeline produced:

Documents processed: 26  
Units extracted: 3737  
Chunks generated: 5802  
Chroma chunks stored: 5802  
BM25 chunks indexed: 5802  
Unique chunk IDs: 5802  

Persistence verification produced:

Chroma count: 5802  
BM25 count: 5802  
Counts match: True  

These are measured results from the implemented pipeline.

---

## 18. Hybrid Retrieval

For each question, SentinelRAG retrieves:

Vector Top 20  
+  
BM25 Top 20

The results are merged using:

`Reciprocal Rank Fusion (RRF)`

### Why RRF Was Chosen

Vector similarity scores and BM25 scores use different scales and cannot be compared directly.

RRF uses result ranks instead of trying to normalize unrelated score values.

A chunk that ranks highly in both systems receives stronger fused priority.

This is particularly suitable for cybersecurity because some questions depend on semantic meaning while others depend on exact identifiers.

---

## 19. Reranking

After RRF, the fused candidates are sent to Cohere reranking.

Production is designed to use:

`Cohere rerank-v3.5`

The final system keeps exactly:

`Top 5 evidence passages`

### Why Remote Reranking Was Chosen

Loading a local CrossEncoder together with the E5 embedding model could consume too much memory in a small Railway container.

The architecture therefore uses:

Local E5 embeddings  
+  
Remote Cohere reranking

This reduces local memory usage while retaining a dedicated relevance-ranking stage.

---

## 20. Generation

The final five evidence passages are sent to the generation model.

The model must:

- answer only from retrieved evidence
- avoid inventing information
- say when evidence is insufficient
- cite evidence using numbered references
- avoid inventing sources or pages
- avoid unsupported statistics, thresholds, or recommendations

This design reduces unsupported model-generated claims.

---

## 21. Authentication

The application uses shared-password authentication.

The password comes from:

`APP_PASSWORD`

Secrets are never hard-coded in the repository.

---

## 22. User Interface

The application uses Streamlit.

The final interface is designed to show:

- project information
- predefined questions
- custom questions
- evidence-grounded answers
- response latency
- exactly five evidence passages
- source names
- page or section information
- relevance scores
- evidence excerpts

---

## 23. Deployment

SentinelRAG is designed for:

- Python 3.11
- Docker
- Railway
- Streamlit

The local E5 model remains CPU-compatible, while Cohere handles remote reranking and generation.

Environment variables are used for secrets.

---

## 24. Evaluation

Retrieval will be evaluated using 30 manually verified Golden Questions.

Main metric:

`Recall@5`

Target:

`Recall@5 >= 80%`

Generation will later be evaluated on 20 questions using RAGAS.

Planned RAGAS metrics include:

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

Only measured results will be reported.

---

## 25. Architecture Priorities

SentinelRAG prioritizes:

- authoritative evidence
- retrieval accuracy
- reproducibility
- deterministic chunk IDs
- source attribution
- lightweight deployment
- transparent implementation
- measurable evaluation
- defensive cybersecurity use

---

# النسخة العربية

## 1. نظرة عامة على المعمارية

**اسم المشروع:** SentinelRAG  
**المجال:** عمليات مركز العمليات الأمنية والاستجابة للحوادث السيبرانية  
**المؤلف:** Wahib Najm Al-dain Al-Refaei  
**اللغة الأساسية للمصادر:** الإنجليزية  

SentinelRAG هو نظام يعتمد على تقنية الاسترجاع المعزز بالتوليد RAG، وقد تم تصميمه لمساعدة محللي SOC والاستجابة للحوادث في استرجاع الإرشادات الأمنية الموثوقة وتوليد إجابات تعتمد على الأدلة المسترجعة.

تنقسم المعمارية إلى مسارين رئيسيين:

1. مسار الاستيعاب Offline Ingestion
2. مسار الاستعلام Online Query

تم تصميم النظام بمعمارية خفيفة وواضحة حتى تكون عمليات الاسترجاع والتقييم والنشر سهلة الفهم وإعادة الإنتاج.

---

## 2. المخطط العام للمعمارية

OFFLINE PIPELINE

مصادر أمن سيبراني موثوقة  
↓  
استخراج PDF / HTML / MITRE JSON  
↓  
تنظيف النص والحفاظ على Metadata  
↓  
Structure-Aware Recursive Chunking  
↓  
حوالي 350 Token لكل Chunk + حوالي 60 Token Overlap  
↓  
Deterministic Chunk IDs  
↓  
E5 Embeddings + BM25  
↓  
ChromaDB + BM25 Index  

ONLINE PIPELINE

سؤال المستخدم  
↓  
E5 Query Embedding  
↓  
Vector Top 20 + BM25 Top 20  
↓  
Reciprocal Rank Fusion  
↓  
Cohere Reranking  
↓  
أفضل 5 أدلة  
↓  
Cohere Generation  
↓  
إجابة مبنية على الأدلة + المصادر + الصفحات + الدرجات

---

## 3. جمع المصادر

يستخدم SentinelRAG حاليًا **26 مصدرًا موثوقًا في الأمن السيبراني**.

يتكون Corpus من:

- 17 ملف PDF
- 8 مصادر HTML
- مجموعة بيانات MITRE ATT&CK واحدة بصيغة JSON

وتشمل الجهات الرئيسية:

- NIST
- CISA
- OWASP
- MITRE ATT&CK

يتم حفظ تفاصيل المصادر في:

`data/sources_manifest.csv`

### لماذا تم اختيار هذه المصادر؟

الاستجابة للحوادث السيبرانية مجال حساس، وقد تؤثر المعلومات غير الصحيحة على الاحتواء والتحقيق والحفاظ على الأدلة والتعافي.

لذلك يعتمد المشروع على المصادر الرسمية والمؤسسات الأمنية المعروفة بدل المدونات العشوائية والمصادر غير الموثوقة.

---

## 4. استخراج الوثائق

يتم استخراج ملفات PDF باستخدام:

`PyMuPDF`

مع الحفاظ على:

- Source ID
- اسم الملف
- العنوان
- رقم الصفحة
- نوع الوثيقة
- النص

### لماذا اخترنا PyMuPDF؟

الكثير من مصادر NIST وCISA عبارة عن وثائق PDF طويلة.

ومن المهم أن يستطيع المستخدم معرفة الصفحة التي جاء منها الدليل.

يوفر PyMuPDF استخراجًا فعالًا لكل صفحة مع الاحتفاظ برقم الصفحة، ولذلك يناسب مشروع SentinelRAG أكثر من تحويل الوثيقة كاملة إلى نص واحد.

تتم معالجة HTML باستخدام:

`BeautifulSoup`

ويتم حذف القوائم وScripts وStyles وHeaders وFooters والعناصر غير المرتبطة بالمحتوى الأساسي.

أما MITRE ATT&CK فيتم استخراجه من بيانات JSON/STIX المنظمة حتى يمكن فهرسة كل Technique وDetection Strategy بشكل مستقل مع معرفات مثل:

`T1055.011`

---

## 5. تنظيف النصوص

يقوم SentinelRAG بتنظيف محافظ للنص.

تتم إزالة المسافات الزائدة والتنسيقات المكسورة والعناصر غير المهمة من صفحات الويب دون إعادة كتابة المحتوى التقني بشكل مفرط.

### لماذا اخترنا التنظيف المحافظ؟

تحتوي وثائق الأمن السيبراني على معرفات واختصارات وأسماء بروتوكولات وأوامر وإجراءات مهمة.

التنظيف المفرط قد يحذف معلومات مفيدة لعملية الاسترجاع.

---

## 6. استراتيجية التقطيع

يستخدم SentinelRAG:

**Structure-Aware Recursive Chunking**

بالإعدادات التالية:

Maximum Chunk Size: حوالي 350 Token  
Overlap: حوالي 60 Token

ويحتوي كل Chunk على Metadata مثل:

`chunk_id`, `source_id`, `source`, `title`, `page`, `section_id`, `chunk_index`, `token_count`, و`text`.

كما أن Chunk IDs ثابتة وحتمية.

---

## 7. لماذا اخترنا Structure-Aware Recursive Chunking؟

تحتوي وثائق الأمن السيبراني على إجراءات متعددة الخطوات وقوائم وضوابط وشروحات تقنية وتوصيات.

التقسيم باستخدام عدد ثابت من الأحرف قد يقطع الإجراء في المنتصف.

أما التقسيم حسب الجمل فقط فقد ينتج Chunks بأحجام غير متوازنة.

Recursive Chunking يحاول المحافظة على الحدود الطبيعية للنص أولًا ثم يستخدم تقسيمات أصغر عند الحاجة.

وهذا يوفر توازنًا جيدًا بين الحفاظ على السياق ودقة الاسترجاع.

---

## 8. لماذا اخترنا حوالي 350 Token؟

Chunks الكبيرة جدًا قد تحتوي على موضوعات مختلفة مثل Detection وContainment وRecovery داخل Embedding واحد، مما يقلل دقة الاسترجاع.

أما Chunks الصغيرة جدًا فقد تفصل التعليمات عن تفسيرها أو سياقها.

حوالي 350 Token يوفر مساحة كافية للاحتفاظ بمقطع تقني مترابط مع إبقاء الاسترجاع دقيقًا.

---

## 9. لماذا اخترنا Overlap بحوالي 60 Token؟

يساعد Overlap على الحفاظ على السياق إذا تم تقسيم إجراء مهم بين Chunkين.

لكن استخدام Overlap كبير جدًا سيؤدي إلى تكرار النص وزيادة حجم Index وزمن Embedding وعدد النتائج المتشابهة.

لذلك يوفر 60 Token توازنًا مناسبًا.

---

## 10. Deterministic Chunk IDs

يحصل كل Chunk على معرف ثابت.

### لماذا هذا مهم؟

سيتم استخدام Golden Questions وRecall@5 في التقييم.

إذا تغيرت Chunk IDs بعد كل تشغيل لـIngestion فلن تكون بيانات التقييم قابلة لإعادة الاستخدام.

المعرفات الثابتة تساعد أيضًا في Debugging واكتشاف التكرار وإعادة إنتاج النتائج.

---

## 11. نموذج Embedding

يستخدم SentinelRAG:

`intfloat/multilingual-e5-small`

عدد الأبعاد:

`384`

تستخدم الوثائق:

`passage: ...`

وتستخدم الأسئلة:

`query: ...`

كما يتم Normalization للمتجهات.

---

## 12. لماذا اخترنا multilingual-e5-small؟

تم اختيار النموذج لأنه مصمم لمهام Retrieval ويستخدم Query وPassage بشكل واضح.

البحث الدلالي مهم في الأمن السيبراني لأن المستخدم قد يستخدم كلمات مختلفة عن الموجودة داخل الوثيقة مع بقاء المعنى نفسه.

كما أن النموذج خفيف نسبيًا ويمكن تشغيله على CPU، وهو أمر مهم للنشر على Railway بموارد محدودة.

وكونه Multilingual يوفر مرونة إذا تم دعم الأسئلة العربية مستقبلًا.

### لماذا لم نستخدم نموذجًا أكبر؟

النماذج الأكبر تحتاج إلى ذاكرة ومعالجة أكبر.

SentinelRAG يحتاج إلى Deployment مستقر وخفيف، ولذلك تم اختيار نموذج أصغر وأكثر ملاءمة لبيئة Railway.

---

## 13. قاعدة البيانات المتجهية

يستخدم SentinelRAG:

`ChromaDB`

ويتم حفظ الفهرس داخل:

`data/index/`

واسم Collection:

`sentinelrag_chunks`

ويتم استخدام Cosine Distance.

---

## 14. لماذا اخترنا ChromaDB؟

تم اختيار ChromaDB لأنها مناسبة لحجم المشروع ومتطلباته.

ينتج Ingestion الحالي:

- 26 وثيقة
- 3737 وحدة مستخرجة
- 5802 Chunk
- 5802 Embedding

هذا الحجم لا يحتاج إلى Vector Database موزعة.

توفر ChromaDB:

- Persistent Storage
- Vector Search
- Metadata
- Python Integration بسيطة
- سهولة إعادة تشغيل المشروع محليًا

كما أن Metadata مهمة جدًا لأن SentinelRAG يحتاج إلى الاحتفاظ باسم المصدر والعنوان والصفحة وATT&CK Section ID مع كل نتيجة.

### لماذا ChromaDB بدل FAISS؟

FAISS ممتاز في البحث المتجهي، لكن ChromaDB توفر أيضًا Persistence وMetadata Management بصورة مباشرة.

وهذا يجعل تنفيذ المشروع أبسط.

### لماذا ChromaDB بدل Elasticsearch / OpenSearch؟

هذه الأنظمة قوية ولكنها تحتاج إلى Infrastructure وإعدادات أكثر.

مع 5802 Chunk تقريبًا لا نحتاج إلى هذا التعقيد.

كما أن BM25 يوفر البحث النصي بشكل مستقل.

### لماذا ChromaDB بدل خدمة Vector Database سحابية؟

الخدمة السحابية ستضيف Credentials وNetwork Dependency وتكلفة محتملة وإعدادات Deployment إضافية.

بالنسبة لحجم SentinelRAG، ChromaDB المحلية أبسط وأكثر قابلية لإعادة الإنتاج.

---

## 15. BM25

يستخدم SentinelRAG:

`rank-bm25`

ويتم بناء BM25 على نفس الـChunks الموجودة في ChromaDB.

يتم حفظ Index في:

`data/index/bm25_index.pkl`

### لماذا نستخدم BM25؟

Vector Search جيد في Semantic Similarity، لكن الأمن السيبراني يحتوي على معرفات دقيقة مثل:

- T1055.011
- CVE
- OAuth
- MFA
- أسماء Malware
- أسماء Protocols

BM25 ممتاز في المطابقة النصية الدقيقة.

لذلك:

E5 + ChromaDB → Semantic Retrieval  
BM25 → Lexical Retrieval

ويعد استخدام الاثنين معًا أفضل لهذا المجال من استخدام أحدهما فقط.

---

## 16. BM25 Tokenization

يقوم Tokenizer بتحويل النص إلى Lowercase مع الحفاظ على معرفات مثل:

`T1055.011`  
`CVE-2025-1234`  
`oauth/token`

وذلك حتى لا يتم تفكيك المعرفات التقنية المهمة أثناء البحث.

---

## 17. لماذا يستخدم ChromaDB وBM25 نفس Chunks؟

يتم إنشاء Chunks مرة واحدة ثم تستخدم في كلا الفهرسين.

وهذا يمنع اختلاف Segmentation بين Vector Search وBM25.

كما يسمح باستخدام نفس Chunk IDs أثناء Hybrid Retrieval والتقييم.

---

## 18. Clean Rebuild

عند تشغيل Ingestion يتم إعادة بناء Chroma وBM25 من جديد.

### لماذا اخترنا ذلك؟

حجم Corpus صغير بما يكفي لجعل إعادة البناء الكامل عملية.

وهذا يمنع:

- Stale Chunks
- Duplicate Vectors
- بقاء وثائق محذوفة
- اختلاف Chroma عن BM25

وفي مشروع أكاديمي، Reproducibility وCorrectness أهم من تعقيد Incremental Indexing.

---

## 19. نتائج Ingestion الفعلية

أنتج النظام:

Documents processed: 26  
Units extracted: 3737  
Chunks generated: 5802  
Chroma chunks stored: 5802  
BM25 chunks indexed: 5802  
Unique chunk IDs: 5802  

وبعد إعادة فتح Index:

Chroma count: 5802  
BM25 count: 5802  
Counts match: True  

وهذه نتائج تم قياسها فعليًا.

---

## 20. Hybrid Retrieval

لكل سؤال سيتم استرجاع:

Vector Top 20  
+  
BM25 Top 20

ثم يتم الدمج باستخدام:

`Reciprocal Rank Fusion`

### لماذا RRF؟

درجات Vector Search وBM25 تستخدم مقاييس مختلفة ولا يمكن مقارنتها مباشرة.

RRF يعتمد على Rank بدل مقارنة Scores المختلفة.

إذا ظهر Chunk في ترتيب مرتفع في النظامين فإنه يحصل على أولوية أكبر.

وهذا مناسب للأمن السيبراني لأن بعض الأسئلة تعتمد على المعنى وبعضها يعتمد على معرفات دقيقة.

---

## 21. Reranking

بعد RRF سيتم استخدام:

`Cohere rerank-v3.5`

وسيتم الاحتفاظ بأفضل:

`Top 5 Evidence Passages`

### لماذا Cohere Reranking عن بعد؟

تحميل Local CrossEncoder بجانب E5 قد يستهلك ذاكرة كبيرة داخل Railway.

لذلك تستخدم المعمارية:

Local E5  
+  
Remote Cohere Reranking

وذلك لتقليل استهلاك الذاكرة المحلية.

---

## 22. Generation

سيتم إرسال أفضل خمسة أدلة فقط إلى LLM.

ويجب أن يقوم النموذج بـ:

- الإجابة من الأدلة فقط
- عدم اختراع المعلومات
- التصريح إذا كانت الأدلة غير كافية
- استخدام Citations
- عدم اختراع المصادر أو الصفحات
- عدم اختراع إحصائيات أو توصيات غير موجودة

---

## 23. Authentication

يستخدم التطبيق Password مشتركًا من:

`APP_PASSWORD`

ولا يتم Hard-Code لأي Password أو API Key داخل المشروع.

---

## 24. واجهة المستخدم

يستخدم SentinelRAG:

`Streamlit`

وستعرض الواجهة:

- معلومات المشروع
- أسئلة جاهزة
- سؤال مخصص
- الإجابة
- Latency
- خمسة أدلة
- أسماء المصادر
- الصفحات أو الأقسام
- Relevance Scores
- Evidence Excerpts

---

## 25. Deployment

تم تصميم النظام للنشر باستخدام:

- Python 3.11
- Docker
- Railway
- Streamlit

يعمل E5 محليًا على CPU، بينما تستخدم Cohere لـReranking وGeneration.

ويتم تخزين Secrets داخل Environment Variables.

---

## 26. Evaluation

سيتم اختبار Retrieval باستخدام 30 Golden Questions تم التحقق منها يدويًا.

المقياس:

`Recall@5`

والهدف:

`Recall@5 >= 80%`

كما سيتم تقييم Generation على 20 سؤالًا باستخدام RAGAS.

وستشمل المقاييس:

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

ولن يتم تسجيل أي نتائج غير مقاسة فعليًا.

---

## 27. أولويات المعمارية

تعطي معمارية SentinelRAG الأولوية إلى:

- الاعتماد على مصادر موثوقة
- Grounding بالأدلة
- دقة الاسترجاع
- Reproducibility
- Deterministic Chunk IDs
- Source Attribution
- Lightweight Deployment
- وضوح التنفيذ
- Measurable Evaluation
- الاستخدام الدفاعي للأمن السيبراني