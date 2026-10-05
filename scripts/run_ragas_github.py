"""GitHub Actions RAGAS evaluator for SentinelRAG.

Runs the frozen application retrieval locally with the prebuilt OpenVINO E5
artifact, sends Cohere requests only through the durable Ledger, and evaluates
exactly the four instructor-required RAGAS metrics.

This script never selects questions based on scores and never modifies Golden
Labels or the corpus index.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import http.client
import json
import os
import ssl
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ragas_execution import IDS, METRICS, Ledger, canonical, references_valid, score_records

REFERENCE_HASH = "5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39"
INDEX_SHA256 = "bab9519517382c1161d05fe0d68857d02b0123c099c1615486e159921d22064c"
PIPELINE_COMMIT = "8309d67b917945f75692931aca77c68915a72c19"
RETRIEVAL_CONFIG = {"vector_top_k":25,"bm25_top_k":20,"rrf_k":60,"top_n":5}
GENERATOR_MODEL = "command-r7b-12-2024"
RERANK_MODEL = "rerank-v3.5"
JUDGE_MODEL = "command-r7b-12-2024"
REQUESTS_PER_QUESTION = 13
ALLOWED_SCOPES = {"q01":1, "all20":20}
CONFIRMATIONS = {"q01":"APPROVE-Q01-13", "all20":"APPROVE-ALL20-260"}


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def load_system_prompt() -> str:
    tree=ast.parse((ROOT/"src/llm.py").read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SYSTEM_PROMPT" for t in node.targets):
            value=node.value
            if (isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute)
                    and value.func.attr=="strip" and isinstance(value.func.value,ast.Constant)
                    and isinstance(value.func.value.value,str) and not value.args and not value.keywords):
                return value.func.value.value.strip()
    raise ValueError("Could not safely extract the frozen application SYSTEM_PROMPT.")


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


def extract_generation(response: dict) -> tuple[str,list,object]:
    # Match the deployed app: any non-empty returned text is accepted, even if
    # Cohere reports a token-limit finish reason. The finish reason is retained.
    blocks=response.get("message",{}).get("content") or []
    answer="\n".join(
        block.get("text","") for block in blocks
        if isinstance(block,dict) and block.get("type")=="text" and block.get("text")
    ).strip()
    if not answer:
        raise ValueError("Cohere returned an empty application answer.")
    citations=response.get("message",{}).get("citations") or []
    if not isinstance(citations,list):
        raise ValueError("Invalid citation structure.")
    return answer,citations,response.get("finish_reason")


def rerank_evidence(candidates: list[dict], response: dict) -> list[dict]:
    rows=response.get("results")
    if not isinstance(rows,list) or len(rows)!=5:
        raise ValueError("Expected exactly five rerank results.")
    used=set(); out=[]
    for rank,row in enumerate(rows,1):
        index=row.get("index"); score=row.get("relevance_score")
        if type(index) is not int or not 0<=index<len(candidates) or index in used:
            raise ValueError("Invalid or duplicate rerank result index.")
        if not isinstance(score,(int,float)):
            raise ValueError("Invalid rerank score.")
        used.add(index)
        item=dict(candidates[index])
        if not str(item.get("text","")).strip() or not str(item.get("chunk_id","")).strip():
            raise ValueError("Empty reranked evidence.")
        item["rerank_rank"]=rank
        item["rerank_score"]=float(score)
        out.append(item)
    return out


class CohereChatHTTP:
    def __init__(self,key: str):
        if not key.strip():
            raise ValueError("COHERE_API_KEY is required.")
        self.key=key.strip()

    def __call__(self,payload):
        conn=http.client.HTTPSConnection("api.cohere.com",timeout=120,context=ssl.create_default_context())
        try:
            conn.request("POST","/v2/chat",body=canonical(payload).encode(),
                         headers={"Authorization":"Bearer "+self.key,"Content-Type":"application/json",
                                  "Accept":"application/json","X-Client-Name":"SentinelRAG-GitHub-RAGAS"})
            response=conn.getresponse()
            raw=response.read(4*1024*1024+1)
            if response.status!=200:
                raise RuntimeError(f"Cohere Chat HTTP {response.status}; no automatic retry.")
            if len(raw)>4*1024*1024:
                raise ValueError("Oversized Cohere chat response.")
            return json.loads(raw)
        finally:
            conn.close()


class CohereRerankHTTP:
    def __init__(self,key: str):
        if not key.strip():
            raise ValueError("COHERE_API_KEY is required.")
        self.key=key.strip()

    def __call__(self,payload):
        conn=http.client.HTTPSConnection("api.cohere.com",timeout=120,context=ssl.create_default_context())
        try:
            conn.request("POST","/v2/rerank",body=canonical(payload).encode(),
                         headers={"Authorization":"Bearer "+self.key,"Content-Type":"application/json",
                                  "Accept":"application/json","X-Client-Name":"SentinelRAG-GitHub-RAGAS"})
            response=conn.getresponse()
            raw=response.read(4*1024*1024+1)
            if response.status!=200:
                raise RuntimeError(f"Cohere Rerank HTTP {response.status}; no automatic retry.")
            if len(raw)>4*1024*1024:
                raise ValueError("Oversized Cohere rerank response.")
            return json.loads(raw)
        finally:
            conn.close()


def load_references() -> dict:
    path=ROOT/".cache/ragas-review/ragas20_reference_candidates.json"
    packet=json.loads(path.read_text(encoding="utf-8"))
    refs=references_valid(packet)
    approval=json.loads((ROOT/"data/eval/ragas20_reference_approval.json").read_text(encoding="utf-8"))
    if approval.get("status")!="approved" or approval.get("reference_set_sha256")!=REFERENCE_HASH:
        raise ValueError("Frozen references are not approved.")
    if approval.get("scope")!="reference_answers_only":
        raise ValueError("Unexpected reference approval scope.")
    return refs


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    body=json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n"
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(body,encoding="utf-8")
    temp.replace(path)


def markdown_report(report: dict, provider_attempts: int, scope: str) -> str:
    lines=[
        "# SentinelRAG RAGAS evaluation",
        "",
        f"Scope: **{scope}**",
        f"Status: **{report['status']}**",
        f"Completed questions: **{report['completed_questions']}/{report['expected_questions']}**",
        f"Reserved Cohere attempts in durable ledger: **{provider_attempts}**",
        "",
        "## Required metrics",
        "",
        "| Metric | Valid / Expected | Mean |",
        "|---|---:|---:|",
    ]
    for name in METRICS:
        row=report["summary"][name]
        value=row["mean_over_valid"]
        rendered="N/A" if value is None else f"{value:.6f}"
        lines.append(f"| {name} | {row['valid_count']} / {row['expected_count']} | {rendered} |")
    lines.extend(["","## Per-question scores","",
                  "| Question | Faithfulness | Answer Relevancy | Context Precision | Context Recall |",
                  "|---|---:|---:|---:|---:|"])
    for row in report["questions"]:
        vals=[]
        for name in METRICS:
            item=row["metrics"][name]
            vals.append("N/A" if item["value"] is None else f"{item['value']:.6f}")
        lines.append("| "+row["id"]+" | "+" | ".join(vals)+" |")
    lines.extend(["",
        "> Partial means are not the completed 20-question result. No composite pass threshold was invented.",
        ""])
    return "\n".join(lines)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope",choices=sorted(ALLOWED_SCOPES),required=True)
    parser.add_argument("--confirm",required=True)
    parser.add_argument("--state-dir",type=Path,default=ROOT/".ragas-state")
    args=parser.parse_args()

    if args.confirm != CONFIRMATIONS[args.scope]:
        raise ValueError("Evaluation confirmation string does not match the requested scope.")
    count=ALLOWED_SCOPES[args.scope]
    cap=REQUESTS_PER_QUESTION*count

    refs=load_references()
    if tuple(refs)!=IDS:
        raise ValueError("Frozen question order changed.")
    index=ROOT/"data/index/chroma.sqlite3"
    if sha256_file(index)!=INDEX_SHA256:
        raise ValueError("Tracked Chroma snapshot changed.")

    key=os.getenv("COHERE_API_KEY","")
    if not key.strip():
        raise ValueError("GitHub Actions secret COHERE_API_KEY is missing.")

    # Compile the approved local E5 model from tracked artifacts. No HF API,
    # PyTorch, Transformers, ONNX Runtime or paid embeddings are used.
    from embedding_service import BACKEND as E5_BACKEND, E5Runtime
    e5=E5Runtime()
    e5.embed("GitHub Actions RAGAS readiness check")

    import src.retrieval as retrieval
    retrieval.embed_query_runtime=e5.embed
    retrieval.get_chroma_client.cache_clear()
    retrieval.get_chroma_collection.cache_clear()
    retrieval.get_bm25_index.cache_clear()

    prompt=load_system_prompt()
    config={
        "protocol":"sentinelrag-github-ragas-v1",
        "scope":args.scope,
        "question_ids":list(IDS[:count]),
        "reference_set_sha256":REFERENCE_HASH,
        "pipeline_snapshot":PIPELINE_COMMIT,
        "index_sha256":INDEX_SHA256,
        "retrieval_config":RETRIEVAL_CONFIG,
        "generator_model":GENERATOR_MODEL,
        "reranker_model":RERANK_MODEL,
        "judge_model":JUDGE_MODEL,
        "ragas_version":"0.4.3",
        "embedding_backend":E5_BACKEND,
        "required_metrics":list(METRICS),
    }
    ledger=Ledger(args.state_dir/"evaluation-ledger.sqlite3",config,cap,interval=4.1)
    chat=CohereChatHTTP(key)
    rerank=CohereRerankHTTP(key)

    records=[]
    for qid in IDS[:count]:
        saved=ledger.get("record/"+qid)
        if saved is not None:
            records.append(saved)
            continue
        question=refs[qid]["user_input"]
        candidates=ledger.get("candidates/"+qid)
        if candidates is None:
            candidates=retrieval.hybrid_retrieve(question,vector_top_k=25,bm25_top_k=20)
            if not candidates:
                raise ValueError("Hybrid retrieval returned no candidates for "+qid)
            ledger.save("candidates/"+qid,candidates)

        rerank_payload={"model":RERANK_MODEL,"query":question,
                        "documents":[x["text"] for x in candidates],"top_n":5}
        reranked=ledger.request("app/"+qid+"/rerank",rerank_payload,rerank)
        evidence=rerank_evidence(candidates,reranked)
        ledger.save("evidence/"+qid,evidence)

        generation_payload={
            "model":GENERATOR_MODEL,"temperature":0.1,"max_tokens":550,
            "messages":[{"role":"system","content":prompt},{"role":"user","content":question}],
            "documents":[{"id":f"evidence_{i}","data":{"text":format_document(item,i)}}
                         for i,item in enumerate(evidence,1)],
        }
        generated=ledger.request("app/"+qid+"/generation",generation_payload,chat)
        answer,citations,finish_reason=extract_generation(generated)
        record={
            "id":qid,"user_input":question,"response":answer,
            "retrieved_contexts":[x["text"] for x in evidence],
            "retrieved_chunk_ids":[x["chunk_id"] for x in evidence],
            "retrieved_evidence":[
                {k:x.get(k) for k in ("chunk_id","source_id","title","page","section_id","rerank_rank","rerank_score")}
                for x in evidence
            ],
            "candidate_count":len(candidates),"citations":citations,
            "generation_finish_reason":finish_reason,
        }
        ledger.save("record/"+qid,record)
        records.append(record)

    # Import RAGAS adapters only after all offline/source/secret gates pass.
    from scripts.ragas_cohere import CohereJudge, E5Embeddings, create_metrics
    judge=CohereJudge(ledger,chat,JUDGE_MODEL)
    embeddings=E5Embeddings(ledger,e5.embed,E5_BACKEND)
    metrics=create_metrics(judge,embeddings)
    report=asyncio.run(score_records(records,refs,metrics,judge,ledger,limit=count))
    report["provider_attempts"]=ledger.count()
    report["provider_attempt_cap"]=cap
    report["scope"]=args.scope
    report["models"]={"generator":GENERATOR_MODEL,"reranker":RERANK_MODEL,"judge":JUDGE_MODEL}
    report["retrieval_config"]=RETRIEVAL_CONFIG
    report["embedding_backend"]=E5_BACKEND
    report["pipeline_snapshot"]=PIPELINE_COMMIT
    report["index_sha256"]=INDEX_SHA256

    atomic_json(args.state_dir/"ragas_report.json",report)
    (args.state_dir/"ragas_report.md").write_text(
        markdown_report(report,ledger.count(),args.scope),encoding="utf-8"
    )
    atomic_json(args.state_dir/"recorded_answers.json",{
        "protocol":"sentinelrag-recorded-answers-v1","scope":args.scope,
        "questions":records,"reference_set_sha256":REFERENCE_HASH,
        "references_injected_into_capture":False,"scores":None,
    })
    print("RAGAS_SCOPE="+args.scope,flush=True)
    print("COMPLETED_QUESTIONS="+str(report["completed_questions"]),flush=True)
    print("COHERE_ATTEMPTS="+str(ledger.count())+"/"+str(cap),flush=True)
    print("RAGAS_SUMMARY="+canonical(report["summary"]),flush=True)
    print("RESULT_JSON="+str(args.state_dir/"ragas_report.json"),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
