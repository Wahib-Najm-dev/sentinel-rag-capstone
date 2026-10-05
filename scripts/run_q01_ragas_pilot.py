"""Run exactly the approved q01 SentinelRAG + four-metric RAGAS pilot.

The same durable Ledger accounts for BOTH application Cohere calls and RAGAS
judge calls. Lifetime cap: 13. There are no Cohere SDK calls and no automatic
provider retries. Query embeddings use the existing private E5 service.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import http.client
import json
import os
import ssl
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT_QID = "q01"
PILOT_CAP = 13
REFERENCE_HASH = "5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39"
PIPELINE_COMMIT = "8309d67b917945f75692931aca77c68915a72c19"
INDEX_SHA256 = "bab9519517382c1161d05fe0d68857d02b0123c099c1615486e159921d22064c"
RETRIEVAL_CONFIG = {"vector_top_k":25,"bm25_top_k":20,"rrf_k":60,"top_n":5}
APPROVED_AT = "2026-10-05T05:05:55Z"
EXPECTED_MODELS = {"generator":"command-r7b-12-2024","reranker":"rerank-v3.5","judge":"command-r7b-12-2024"}
EXPECTED_PRODUCTION_PACKAGES = {
    "chromadb":"1.5.9","rank-bm25":"0.2.2","requests":"2.34.2",
    "numpy":"2.4.6","python-dotenv":"1.2.4",
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False)


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def load_system_prompt() -> str:
    tree=ast.parse((ROOT/"src/llm.py").read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SYSTEM_PROMPT" for t in node.targets):
            value=node.value
            if (isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute)
                    and value.func.attr=="strip" and isinstance(value.func.value,ast.Constant)
                    and isinstance(value.func.value.value,str) and not value.args and not value.keywords):
                return value.func.value.value.strip()
    raise ValueError("Could not extract frozen SYSTEM_PROMPT safely.")


def load_inputs():
    from scripts.prepare_ragas import GOLDEN_BLOB, load_golden, select_questions
    if GOLDEN_BLOB != "c908c6dce6434f7259db3af8991da7d8b41c563d":
        raise ValueError("Golden blob changed.")
    approval=json.loads((ROOT/"data/eval/ragas20_reference_approval.json").read_text(encoding="utf-8"))
    if approval != {
        "protocol":"ragas20-reference-approval-v1",
        "status":"approved",
        "reference_set_sha256":REFERENCE_HASH,
        "approved_by":"project_owner",
        "approval_source":"ChatGPT conversation",
        "approval_message":"يعتمد",
        "approval_timestamp_utc":APPROVED_AT,
        "scope":"reference_answers_only",
        "human_expert_review_claimed":False,
        "paid_or_trial_api_execution_authorized":False,
        "note":"This records the project owner's approval of the frozen 20 reference answers only. It is not authorization to spend API quota and does not claim independent expert review."
    }:
        raise ValueError("Reference approval record changed.")
    spec=json.loads((ROOT/"data/eval/ragas20_reference_review_spec.json").read_text(encoding="utf-8"))
    question=select_questions(load_golden(ROOT/"data/eval/golden_questions.json"))[0]
    if question["id"] != PILOT_QID:
        raise ValueError("q01 is no longer first in the frozen pilot sample.")
    reference=spec.get("reference_replacements",{}).get(PILOT_QID)
    if not isinstance(reference,str) or not reference.strip():
        raise ValueError("Approved q01 reference missing.")
    return question, reference


def format_document(evidence: dict, number: int) -> str:
    page=evidence.get("page")
    if page is None: page="N/A"
    section=evidence.get("section_id") or "N/A"
    return (
        f"Evidence {number}\n"
        f"Source ID: {evidence.get('source_id','')}\n"
        f"Title: {evidence.get('title','')}\n"
        f"Page: {page}\n"
        f"Section: {section}\n\n"
        f"{evidence.get('text','')}"
    )


class CoherePost:
    def __init__(self, key: str, endpoint: str):
        if not key.strip() or endpoint not in ("/v2/chat","/v2/rerank"):
            raise ValueError("Explicit Cohere key and approved endpoint required.")
        self.key, self.endpoint=key.strip(),endpoint

    def __call__(self,payload):
        conn=http.client.HTTPSConnection("api.cohere.com",timeout=120,context=ssl.create_default_context())
        try:
            conn.request("POST",self.endpoint,body=canonical(payload).encode(),
                         headers={"Authorization":"Bearer "+self.key,"Content-Type":"application/json",
                                  "Accept":"application/json","X-Client-Name":"SentinelRAG-q01-pilot"})
            response=conn.getresponse()
            raw=response.read(4*1024*1024+1)
            if response.status != 200:
                raise RuntimeError(f"Cohere HTTP {response.status}; no automatic retry.")
            if len(raw)>4*1024*1024:
                raise ValueError("Oversized Cohere response.")
            return json.loads(raw)
        finally:
            conn.close()


def build_evidence(candidates, response):
    rows=response.get("results")
    if not isinstance(rows,list) or len(rows)!=5:
        raise ValueError("Expected exactly five rerank results.")
    evidence=[]
    used=set()
    for rank,row in enumerate(rows,1):
        index=row.get("index")
        score=row.get("relevance_score")
        if type(index) is not int or not 0<=index<len(candidates) or index in used:
            raise ValueError("Invalid/duplicate rerank result index.")
        if not isinstance(score,(int,float)):
            raise ValueError("Invalid rerank score.")
        used.add(index)
        item=dict(candidates[index])
        if not str(item.get("text","")).strip() or not str(item.get("chunk_id","")).strip():
            raise ValueError("Empty reranked evidence.")
        item["pre_rerank_index"]=index
        item["rerank_rank"]=rank
        item["rerank_score"]=float(score)
        evidence.append(item)
    return evidence


def extract_answer(response):
    if response.get("finish_reason") != "COMPLETE":
        raise ValueError("Application generation did not finish completely.")
    content=response.get("message",{}).get("content",[])
    answer="\n".join(x.get("text","") for x in content if isinstance(x,dict) and x.get("type")=="text").strip()
    if not answer:
        raise ValueError("Empty application answer.")
    citations=response.get("message",{}).get("citations") or []
    if not isinstance(citations,list):
        raise ValueError("Invalid citation structure.")
    return answer,citations


def validate_offline():
    from importlib.metadata import version
    question,reference=load_inputs()
    if sha256_file(ROOT/"data/index/chroma.sqlite3") != INDEX_SHA256:
        raise ValueError("Index snapshot mismatch.")
    for package,expected in EXPECTED_PRODUCTION_PACKAGES.items():
        if version(package) != expected:
            raise ValueError(f"Pilot package mismatch: {package}={version(package)}, expected {expected}")
    if version("ragas")!="0.4.3":
        raise ValueError("ragas==0.4.3 required.")
    prompt=load_system_prompt()
    if not prompt or question["id"]!=PILOT_QID or not reference.strip():
        raise ValueError("Frozen pilot input validation failed.")
    return question,reference,prompt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only",action="store_true")
    args=parser.parse_args()
    question,reference,prompt=validate_offline()
    print("OFFLINE_INPUT_VALIDATION=PASSED",flush=True)
    print("PILOT_QID=q01; REQUIRED_METRICS=Faithfulness,Answer Relevancy,Context Precision,Context Recall",flush=True)
    print("LIFETIME_COHERE_REQUEST_CAP=13",flush=True)
    if args.validate_only:
        print("MODE=VALIDATION_ONLY; COHERE_CALLS=0",flush=True)
        return 0

    if os.getenv("PILOT_EXECUTE")!="q01-approved-13":
        raise ValueError("Explicit q01 execution gate is not enabled.")
    if os.getenv("EMBEDDING_PROVIDER")!="remote":
        raise ValueError("Pilot must use the private remote embedding service.")
    key=os.getenv("COHERE_API_KEY","")
    if not key.strip():
        raise ValueError("COHERE_API_KEY missing.")
    state_dir=Path(os.getenv("PILOT_STATE_DIR","/pilot"))
    state_dir.mkdir(parents=True,exist_ok=True)

    from scripts.ragas_execution import Ledger, METRICS, score_records
    from scripts.ragas_cohere import CohereJudge, E5Embeddings, create_metrics
    from src.embedding_client import embed_query_runtime
    from src.retrieval import hybrid_retrieve

    config={
        "protocol":"sentinelrag-q01-pilot-v1","qid":PILOT_QID,
        "reference_hash":REFERENCE_HASH,"reference_approved_at":APPROVED_AT,
        "pipeline_commit":PIPELINE_COMMIT,"index_sha256":INDEX_SHA256,
        "retrieval_config":RETRIEVAL_CONFIG,"models":EXPECTED_MODELS,
        "ragas":"0.4.3","embedding_backend":"sentinel-embed/openvino-fp16-weights-f32-inference",
        "metrics":list(METRICS),"max_cohere_attempts":PILOT_CAP,
    }
    ledger=Ledger(state_dir/"q01-pilot-ledger.sqlite3",config,PILOT_CAP,interval=4.1)
    send_chat=CoherePost(key,"/v2/chat")
    send_rerank=CoherePost(key,"/v2/rerank")

    candidates=ledger.get("capture/q01/candidates")
    if candidates is None:
        candidates=hybrid_retrieve(question["question"])
        if not isinstance(candidates,list) or not candidates:
            raise ValueError("Hybrid retrieval returned no candidates.")
        ledger.save("capture/q01/candidates",candidates)

    rerank_payload={"model":EXPECTED_MODELS["reranker"],"query":question["question"],
                    "documents":[x["text"] for x in candidates],"top_n":5}
    rerank_response=ledger.request("capture/q01/rerank",rerank_payload,send_rerank)
    evidence=build_evidence(candidates,rerank_response)
    ledger.save("capture/q01/evidence",evidence)

    documents=[{"id":f"evidence_{i}","data":{"text":format_document(item,i)}} for i,item in enumerate(evidence,1)]
    generation_payload={
        "model":EXPECTED_MODELS["generator"],"temperature":0.1,"max_tokens":550,
        "messages":[{"role":"system","content":prompt},{"role":"user","content":question["question"]}],
        "documents":documents,
    }
    generated=ledger.request("capture/q01/generation",generation_payload,send_chat)
    answer,citations=extract_answer(generated)
    record={
        "id":PILOT_QID,"user_input":question["question"],"response":answer,
        "retrieved_contexts":[x["text"] for x in evidence],
        "retrieved_chunk_ids":[x["chunk_id"] for x in evidence],
        "candidate_count":len(candidates),"citations":citations,
    }
    ledger.save("capture/q01/record",record)

    judge=CohereJudge(ledger,send_chat,EXPECTED_MODELS["judge"])
    embeddings=E5Embeddings(ledger,embed_query_runtime,"sentinel-embed/openvino-fp16-weights-f32-inference")
    metrics=create_metrics(judge,embeddings)
    refs={PILOT_QID:{"id":PILOT_QID,"user_input":question["question"],"reference":reference}}
    report=__import__("asyncio").run(score_records([record],refs,metrics,judge,ledger,limit=1))
    q01=report["questions"][0]
    if q01["id"]!=PILOT_QID or not all(q01["metrics"][name]["status"]=="complete" for name in METRICS):
        raise ValueError("Pilot did not complete all four required metrics.")
    if ledger.count()!=PILOT_CAP:
        raise ValueError(f"Unexpected Cohere attempt count {ledger.count()}, expected exactly {PILOT_CAP}.")

    result={
        "protocol":"sentinelrag-q01-pilot-result-v1","status":"complete",
        "qid":PILOT_QID,"cohere_attempts":ledger.count(),"cohere_request_cap":PILOT_CAP,
        "models":EXPECTED_MODELS,"retrieval_config":RETRIEVAL_CONFIG,
        "reference_set_sha256":REFERENCE_HASH,"pipeline_commit":PIPELINE_COMMIT,
        "index_sha256":INDEX_SHA256,"answer":answer,
        "retrieved_chunk_ids":record["retrieved_chunk_ids"],
        "metrics":q01["metrics"],"partial_20_question_summary":report["summary"],
        "note":"Pilot q01 is one of the frozen 20 and must be reused when the full run resumes. This is not yet the completed 20-question report.",
    }
    path=state_dir/"q01_pilot_result.json"
    body=canonical(result)+"\n"
    if path.exists() and path.read_text(encoding="utf-8")!=body:
        raise ValueError("Refusing to overwrite a different pilot result.")
    path.write_text(body,encoding="utf-8")
    print("PILOT_STATUS=COMPLETE",flush=True)
    print("COHERE_ATTEMPTS=13/13",flush=True)
    print("Q01_METRICS="+canonical({k:v["value"] for k,v in q01["metrics"].items()}),flush=True)
    print("RESULT_PATH="+str(path),flush=True)
    # Keep the successful one-off service inspectable until ChatGPT reads and deletes it.
    while True:
        time.sleep(3600)


if __name__=="__main__":
    raise SystemExit(main())
