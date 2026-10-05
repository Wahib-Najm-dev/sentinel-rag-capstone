"""Score SAVED real application outputs; default is validation only, zero API calls.

This program does not capture application answers or modify production. Read
 docs/ragas_runner.md before explicit reference approval and a paid pilot.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.ragas_execution import (IDS, METRICS, REFERENCE_HASH, Ledger,
    canonical, digest, references_valid, validate_record, score_records, snapshot_report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--answers', type=Path, required=True)
    parser.add_argument('--state', type=Path, default=ROOT / '.cache/ragas-evaluation/evaluation-ledger.sqlite3')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--approve-reference-hash')
    parser.add_argument('--reviewer', default='')
    parser.add_argument('--judge-model', default='')
    parser.add_argument('--max-judge-requests', type=int, default=0)
    parser.add_argument('--limit', type=int, choices=range(1,21), default=1)
    args = parser.parse_args()
    refs = references_valid(json.loads(args.references.read_text(encoding='utf-8')))
    saved = json.loads(args.answers.read_text(encoding='utf-8'))
    if saved.get('protocol') != 'sentinelrag-recorded-answers-v1':
        raise ValueError('A genuine recorded-answer package is required, not reference drafts.')
    provenance = saved.get('provenance', {})
    for key in ('pipeline_commit', 'index_sha256', 'golden_git_blob', 'generator_model', 'retrieval_config', 'capture_method'):
        if not provenance.get(key):
            raise ValueError('Missing captured-output provenance: ' + key)
    packet = json.loads(args.references.read_text(encoding='utf-8'))
    if provenance['index_sha256'] != packet['index_sha256'] or provenance['golden_git_blob'] != packet['golden_git_blob']:
        raise ValueError('Answers came from a different index/Golden Set.')
    if provenance['retrieval_config'] != {'vector_top_k':25,'bm25_top_k':20,'rrf_k':60,'top_n':5}:
        raise ValueError('Captured retrieval configuration changed.')
    if provenance['pipeline_commit'] != packet['source_commit']:
        raise ValueError('Capture must use the frozen source snapshot; record deployed versions separately.')
    records = saved.get('questions', [])
    for record in records:
        validate_record(record, refs)
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('Duplicate output records.')
    if not set(IDS[:args.limit]).issubset({r['id'] for r in records}):
        raise ValueError('Actual outputs for the selected pilot/resume range are missing.')
    print('REFERENCES_AND_OUTPUT_STRUCTURE=PASSED')
    print('REQUIRED_METRICS=' + ', '.join(METRICS))
    print('RECORDED_ANSWERS=' + str(len(records)))
    if not args.run:
        print('MODE=VALIDATION_ONLY; COHERE_CALLS=0; RAGAS_SCORES=NOT_RUN')
        return 0
    if os.getenv('RAILWAY_SERVICE_ID'):
        raise ValueError('Do not load evaluation dependencies/models inside the Railway application.')
    if args.approve_reference_hash != REFERENCE_HASH or not args.reviewer.strip():
        raise ValueError('Explicit reference-set approval and real reviewer identity are required.')
    if not args.judge_model or args.max_judge_requests < 1:
        raise ValueError('Explicit judge model and lifetime request budget are required.')
    if not os.getenv('COHERE_API_KEY', '').strip():
        raise ValueError('Set COHERE_API_KEY privately in this evaluation process.')
    if version('ragas') != '0.4.3':
        raise ValueError('Use the isolated evaluation environment with ragas==0.4.3.')
    # Import expensive optional components only AFTER all validation/approval gates.
    from scripts.ragas_cohere import CohereJudge, CohereHTTP, E5Embeddings, create_metrics
    from embedding_service import E5Runtime, BACKEND
    config = {'reference_hash': REFERENCE_HASH, 'reviewer_attestation': args.reviewer.strip(),
              'provenance': provenance, 'judge_model': args.judge_model, 'ragas': '0.4.3',
              'embedding_backend': BACKEND, 'metrics': list(METRICS), 'strictness':3,
              'runner_code_sha256': {name: digest((ROOT / 'scripts' / name).read_text(encoding='utf-8'))
                 for name in ('evaluate_ragas.py','ragas_execution.py','ragas_cohere.py')},
              'package_versions': {n: version(n) for n in ('ragas','pydantic','numpy','openvino','tokenizers')}}
    ledger = Ledger(args.state, config, args.max_judge_requests)
    runtime = E5Runtime()
    judge = CohereJudge(ledger, CohereHTTP(os.environ['COHERE_API_KEY']), args.judge_model)
    embeddings = E5Embeddings(ledger, runtime.embed, BACKEND)
    metrics = create_metrics(judge, embeddings)
    report_path = args.state.parent / 'ragas_results.json'
    error = None
    try:
        asyncio.run(score_records(records, refs, metrics, judge, ledger, limit=args.limit))
    except Exception as exc:
        error = type(exc).__name__
        print('STOPPED=' + error + '; completed calls preserved. Do not delete the ledger.')
    report = snapshot_report(ledger, records)
    report['configuration'] = config
    report['last_error_type'] = error
    report['reference_review_attestation'] = 'User-supplied reviewer identity, not independently verified.'
    temporary = report_path.with_suffix('.tmp')
    temporary.write_text(canonical(report) + '\n', encoding='utf-8')
    temporary.replace(report_path)
    print('JUDGE_ATTEMPTS=' + str(ledger.count()))
    print('REPORT_STATUS=' + report['status'])
    print('COMPLETED_QUESTIONS=' + str(report['completed_questions']) + '/20')
    return 1 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
