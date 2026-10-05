"""Build source-reviewed reference candidates, never paid scores or human approvals."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.prepare_ragas import GOLDEN_BLOB, canonical_digest, load_golden, make_packet, select_questions
from scripts.export_ragas_reference_context import INDEX_SHA256, read_sources

METRICS = ['Faithfulness', 'Answer Relevancy', 'Context Precision', 'Context Recall']
DRAFT_SHA256 = 'f7a7800ca4f6358cebfe896a9a45aada56d61997c6fef68394095ea8855183d1'


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def build_candidates(spec: dict, drafts: dict, packet: dict, context: list[dict], golden: list[dict]) -> dict:
    check(spec.get('protocol') == 'ragas20-source-review-spec-v1', 'Unexpected review protocol')
    check(spec.get('required_metrics') == METRICS, 'All four instructor-required metrics must be present')
    check(spec.get('human_approval') == {'status': 'pending', 'reviewed_by': None}, 'This step cannot grant human approval')
    check(spec.get('paid_execution_authorized') is False, 'This step cannot authorize paid execution')
    check(spec.get('original_drafts_sha256') == DRAFT_SHA256, 'Original drafts must remain frozen')
    check(spec.get('index_sha256') == packet.get('index_sha256') == INDEX_SHA256, 'Index snapshot mismatch')
    check(spec.get('golden_git_blob') == packet.get('golden_git_blob') == GOLDEN_BLOB, 'Golden blob mismatch')
    check(packet.get('golden_semantic_sha256') == canonical_digest(golden), 'Golden content mismatch')
    for field in ('golden_git_blob', 'golden_semantic_sha256', 'index_sha256', 'selection_seed'):
        check(drafts.get(field) == packet.get(field), 'Draft provenance mismatch: ' + field)
    expected = select_questions(golden)
    ids = [r['id'] for r in expected]
    check(len(ids) == 20, 'Exactly 20 questions are required')
    check([r.get('id') for r in packet.get('questions', [])] == ids, 'Packet sample changed')
    check([r.get('id') for r in drafts.get('questions', [])] == ids, 'Draft sample changed')
    check(set(spec.get('assistant_review_notes', {})) == set(ids), 'Each reference needs a review note')
    replacements = spec.get('reference_replacements', {})
    supplements = spec.get('supplementary_reference_chunks', {})
    check(set(replacements).issubset(ids) and set(supplements).issubset(ids), 'Unknown amendment ID')
    evidence = {}
    for chunk in [e for r in packet['questions'] for e in r['gold_evidence']] + context:
        text = chunk.get('text')
        check(isinstance(text, str) and bool(text.strip()), 'Empty evidence')
        check(hashlib.sha256(text.encode()).hexdigest() == chunk.get('text_sha256'), 'Evidence text hash mismatch')
        cid = chunk['chunk_id']
        if cid in evidence:
            check(evidence[cid]['text'] == text and evidence[cid]['source_id'] == chunk['source_id'], 'Conflicting source copies')
        evidence[cid] = chunk
    out = []
    cited = set()
    for original, row, draft in zip(expected, packet['questions'], drafts['questions']):
        qid = original['id']
        check(row['user_input'] == original['question'], 'Question text changed')
        for field in ('gold_chunk_ids', 'gold_source_ids'):
            check(row[field] == original[field], 'Golden labels changed')
        check(draft['supporting_chunk_ids'] == original['gold_chunk_ids'], 'Draft gold IDs changed')
        extra = supplements.get(qid, [])
        check(isinstance(extra, list) and len(extra) == len(set(extra)), 'Repeated supplementary evidence')
        check(not set(extra).intersection(original['gold_chunk_ids']), 'Supplementary evidence duplicates Golden Labels')
        support = []
        for cid in original['gold_chunk_ids'] + extra:
            check(cid in evidence, 'Missing supporting chunk: ' + cid)
            chunk = evidence[cid]
            check(chunk['source_id'] in original['gold_source_ids'], 'Supplement must come from the same original source')
            anchor = spec.get('source_anchors', {}).get(cid)
            check(isinstance(anchor, str) and bool(anchor.strip()), 'Missing source anchor')
            check(anchor in ' '.join(chunk['text'].split()), 'Source anchor not found')
            support.append({'chunk_id': cid, 'source_id': chunk['source_id'], 'text_sha256': chunk['text_sha256'],
                            'anchor': anchor, 'role': 'reference_only_supplement' if cid in extra else 'original_gold'})
            cited.add(cid)
        reference = replacements.get(qid, draft['reference_draft'])
        check(isinstance(reference, str) and bool(reference.strip()), 'Empty reference')
        out.append({'id': qid, 'user_input': original['question'], 'gold_chunk_ids': original['gold_chunk_ids'],
                    'gold_source_ids': original['gold_source_ids'], 'reference': reference,
                    'support_checks': support, 'assistant_review_note': spec['assistant_review_notes'][qid],
                    'review_status': 'pending_human_approval'})
    check(set(spec['source_anchors']) == cited, 'Missing or unused source anchors')
    result = {'protocol': 'ragas20-reference-candidates-v2', 'status': 'assistant_reviewed_pending_human_approval',
              'required_metrics': METRICS, 'requirement_confirmation': spec['requirement_confirmation'],
              'source_commit': spec['source_commit'], 'golden_git_blob': GOLDEN_BLOB,
              'golden_semantic_sha256': packet['golden_semantic_sha256'], 'index_sha256': INDEX_SHA256,
              'selection_seed': packet['selection_seed'], 'review_spec_sha256': canonical_digest(spec),
              'original_drafts_sha256': DRAFT_SHA256,
              'review_method': 'Assistant source review with exact-text traceability; automated anchor checks do not prove entailment or complete coverage.',
              'human_approval': {'status': 'pending', 'reviewed_by': None},
              'paid_execution_authorized': False, 'scores': None, 'questions': out}
    result['reference_set_sha256'] = canonical_digest(result)
    return result


def export_review(result: dict, evidence: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in ('ragas20_reference_candidates.json', 'ragas20_reference_candidates.md', 'ragas20_review_evidence.json')]
    check(not any(p.exists() for p in paths), 'Do not overwrite an existing reviewed candidate set')
    used = sorted({e['chunk_id'] for r in result['questions'] for e in r['support_checks']})
    bundle = {'index_sha256': INDEX_SHA256, 'purpose': 'Reference review only; not Golden Label changes',
              'evidence': [evidence[cid] for cid in used]}
    paths[0].write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    paths[2].write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md = ['# SentinelRAG: 20 source-reviewed reference candidates', '',
          'Assistant-reviewed; human approval is pending. NOT a score report. No provider requests were made.', '',
          'Required metrics: ' + ', '.join(METRICS) + '.', '',
          'Reference set SHA-256: `' + result['reference_set_sha256'] + '`', '',
          'Full verbatim evidence is included in ragas20_review_evidence.json. The two supplementary passages are reference-only; Golden Labels are unchanged.', '']
    for row in result['questions']:
        md.extend(['## ' + row['id'] + ': ' + row['user_input'], '', row['reference'], '',
                   '**Review note:** ' + row['assistant_review_note'], '', '**Source support:**'])
        for s in row['support_checks']:
            e = evidence[s['chunk_id']]
            page = e.get('page')
            page = 'not applicable' if page is None or page == -1 else str(page)
            md.append('- `' + s['chunk_id'] + '` | ' + s['source_id'] + ' | extracted page ' + page + ' | ' + s['role'] + '\n  Anchor: ' + s['anchor'])
        md.append('')
    paths[1].write_text('\n'.join(md), encoding='utf-8')


def main() -> None:
    golden = load_golden(ROOT / 'data/eval/golden_questions.json')
    path = ROOT / 'data/eval/ragas20_reference_drafts.json'
    raw = path.read_bytes().replace(b'\r\n', b'\n')
    check(hashlib.sha256(raw).hexdigest() == DRAFT_SHA256, 'Original draft bytes changed')
    drafts = json.loads(raw)
    spec = json.loads((ROOT / 'data/eval/ragas20_reference_review_spec.json').read_text(encoding='utf-8'))
    packet = make_packet(golden, ROOT / 'data/index/chroma.sqlite3')
    context = read_sources(ROOT / 'data/index/chroma.sqlite3')
    result = build_candidates(spec, drafts, packet, context, golden)
    evidence = {e['chunk_id']: e for r in packet['questions'] for e in r['gold_evidence']}
    evidence.update({e['chunk_id']: e for e in context})
    export_review(result, evidence, ROOT / '.cache/ragas-review')
    print('SOURCE_REVIEW_CANDIDATES=20')
    print('REFERENCE_EVIDENCE=35_ORIGINAL_PLUS_2_SUPPLEMENTARY')
    print('ALL_FOUR_REQUIRED_METRICS=PRESENT')
    print('REFERENCE_SET_SHA256=' + result['reference_set_sha256'])
    print('GOLDEN_LABELS=UNCHANGED; INDEX=READ_ONLY; COHERE_CALLS=0; RAGAS_SCORES=NOT_RUN')
    print('HUMAN_APPROVAL=PENDING; PAID_EXECUTION=NOT_AUTHORIZED')


if __name__ == '__main__':
    main()
