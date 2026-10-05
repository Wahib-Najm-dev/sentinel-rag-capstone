"""Durable evaluation bookkeeping; no ML imports, API clients, or index access."""
from __future__ import annotations
import hashlib
import json
import math
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Callable

REFERENCE_HASH = '5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39'
METRICS = ('Faithfulness', 'Answer Relevancy', 'Context Precision', 'Context Recall')
IDS = ('q01','q03','q04','q08','q09','q11','q12','q13','q14','q15','q16','q17','q18','q19','q20','q23','q26','q27','q28','q30')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def references_valid(packet):
    unsigned = {k: v for k, v in packet.items() if k != 'reference_set_sha256'}
    if digest(unsigned) != REFERENCE_HASH or packet.get('reference_set_sha256') != REFERENCE_HASH:
        raise ValueError('Reference candidates differ from the source-reviewed frozen set.')
    if packet.get('required_metrics') != list(METRICS):
        raise ValueError('All four instructor-required metrics must remain present.')
    if tuple(row['id'] for row in packet['questions']) != IDS:
        raise ValueError('Do not replace or remove evaluation questions.')
    return {row['id']: row for row in packet['questions']}


def validate_record(row, refs):
    if row.get('id') not in refs or row.get('user_input') != refs[row['id']]['user_input']:
        raise ValueError('Recorded question is not an exact member of the frozen sample.')
    if not isinstance(row.get('response'), str) or not row['response'].strip():
        raise ValueError('Missing actual application answer.')
    contexts = row.get('retrieved_contexts')
    chunk_ids = row.get('retrieved_chunk_ids')
    if (not isinstance(contexts, list) or not 1 <= len(contexts) <= 5
            or any(not isinstance(c, str) or not c.strip() for c in contexts)
            or not isinstance(chunk_ids, list) or len(chunk_ids) != len(contexts)
            or any(not isinstance(c, str) or not c for c in chunk_ids)
            or len(set(chunk_ids)) != len(chunk_ids)):
        raise ValueError('Actual ranked contexts and matching unique chunk IDs are required.')
    # A reference field here is a provenance mistake: join references only at scoring time.
    if any(k in row for k in ('reference', 'gold_evidence', 'support_checks', 'scores')):
        raise ValueError('Record actual application output separately from references and scores.')


class BudgetExceeded(RuntimeError):
    pass


class UncertainRequest(RuntimeError):
    pass


class Ledger:
    """Reserve each network attempt durably BEFORE sending it; never retry silently.

    Keys represent question/metric/call ordinal, not just prompt hashes: three
    relevancy generations remain three independent requests. A crash after a
    request reservation is conservatively blocked for explicit reconciliation.
    This ledger must be kept private and persisted when moving machines.
    """
    def __init__(self, path: Path, config: dict, cap: int, interval=4.1,
                 clock: Callable = time.time, sleep: Callable = time.sleep):
        if type(cap) is not int or cap <= 0 or interval < 0:
            raise ValueError('Positive lifetime request cap and nonnegative interval required.')
        self.path, self.cap, self.interval = Path(path), cap, interval
        self.clock, self.sleep = clock, sleep
        if self.path.suffix != '.sqlite3' or self.path.name == 'chroma.sqlite3':
            raise ValueError('Use a separate evaluation-ledger.sqlite3, never the corpus database.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as c, c:
            existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if existing and existing != {'config', 'calls', 'values_cache'}:
                raise ValueError('Refusing to write evaluation tables into a different database.')
            c.executescript('''
            CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                payload TEXT NOT NULL, status TEXT NOT NULL, started REAL NOT NULL,
                finished REAL, response TEXT, response_hash TEXT, error_type TEXT);
            CREATE TABLE IF NOT EXISTS values_cache (key TEXT PRIMARY KEY, body TEXT NOT NULL, checksum TEXT NOT NULL);
            ''')
            full = canonical({'protocol': 'ragas-ledger-v1', 'config': config, 'lifetime_cap': cap, 'interval': interval})
            old = c.execute('SELECT body FROM config WHERE id=1').fetchone()
            if old and old[0] != full:
                raise ValueError('Run configuration or budget changed; do not reuse this ledger.')
            c.execute('INSERT OR IGNORE INTO config VALUES(1, ?)', (full,))

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=60)
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    def count(self):
        with closing(self.connect()) as c:
            return c.execute('SELECT count(*) FROM calls').fetchone()[0]

    def get(self, key):
        with closing(self.connect()) as c:
            row = c.execute('SELECT body,checksum FROM values_cache WHERE key=?', (key,)).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if digest(value) != row[1]:
            raise ValueError('Saved checkpoint checksum mismatch.')
        return value

    def save(self, key, value):
        body, checksum = canonical(value), digest(value)
        with closing(self.connect()) as c, c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT body FROM values_cache WHERE key=?', (key,)).fetchone()
            if old and old[0] != body:
                raise ValueError('Refusing to overwrite a frozen completed checkpoint: ' + key)
            c.execute('INSERT OR IGNORE INTO values_cache VALUES(?,?,?)', (key, body, checksum))

    def request(self, key, payload, send):
        body, fingerprint = canonical(payload), digest(payload)
        with closing(self.connect()) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT fingerprint,status,response,response_hash FROM calls WHERE key=?', (key,)).fetchone()
            if row:
                c.rollback()
                if row[0] != fingerprint:
                    raise ValueError('Prompt/schema/model changed for an existing request.')
                if row[1] == 'complete':
                    response = json.loads(row[2])
                    if digest(response) != row[3]:
                        raise ValueError('Saved provider response checksum mismatch.')
                    return response
                raise UncertainRequest('Reserved or failed request is not automatically repeated: ' + key)
            count, latest = c.execute('SELECT count(*),max(started) FROM calls').fetchone()
            if count >= self.cap:
                c.rollback()
                raise BudgetExceeded('Approved lifetime request limit reached.')
            # Serialize reservation times across threads/processes and restarts.
            now = self.clock()
            wait = max(0.0, (latest + self.interval - now) if latest is not None else 0.0)
            if wait:
                self.sleep(wait)
            started = self.clock()
            c.execute('INSERT INTO calls(key,fingerprint,payload,status,started) VALUES(?,?,?,?,?)',
                      (key, fingerprint, body, 'reserved', started))
            c.commit()
        try:
            response = send(payload)  # exactly one application-level HTTP attempt
            response_body = canonical(response)
        except Exception as exc:
            with closing(self.connect()) as c, c:
                c.execute('UPDATE calls SET status=?,finished=?,error_type=? WHERE key=?',
                          ('failed', self.clock(), type(exc).__name__, key))
            raise
        with closing(self.connect()) as c, c:
            c.execute('UPDATE calls SET status=?,finished=?,response=?,response_hash=? WHERE key=?',
                      ('complete', self.clock(), response_body, digest(response), key))
        return response


def snapshot_report(ledger, records, frozen_ids=IDS):
    result = []
    complete_questions = 0
    for qid in frozen_ids:
        metrics = {}
        for name in METRICS:
            item = ledger.get(f'result/{qid}/{name}')
            metrics[name] = item or {'status': 'pending', 'value': None}
        all_ok = all(v['status'] == 'complete' for v in metrics.values())
        complete_questions += int(all_ok)
        result.append({'id': qid, 'metrics': metrics})
    summary = {}
    for name in METRICS:
        vals = [r['metrics'][name]['value'] for r in result if r['metrics'][name]['status'] == 'complete']
        summary[name] = {'valid_count': len(vals), 'expected_count': len(frozen_ids),
                         'mean_over_valid': sum(vals) / len(vals) if vals else None}
    return {'protocol': 'sentinelrag-ragas-results-v1',
            'status': 'complete' if complete_questions == len(frozen_ids) else 'partial',
            'completed_questions': complete_questions, 'expected_questions': len(frozen_ids),
            'reference_set_sha256': REFERENCE_HASH,
            'reserved_judge_attempts': ledger.count(), 'summary': summary, 'questions': result,
            'note': 'Partial means are not a completed 20-question result. No composite score or invented pass threshold.'}


async def score_records(records, refs, metrics, judge, ledger, *, limit=1):
    if tuple(metrics) != METRICS or not 1 <= limit <= len(IDS):
        raise ValueError('All four metrics and a valid question limit are required.')
    by_id = {r['id']: r for r in records}
    if len(by_id) != len(records):
        raise ValueError('Duplicate recorded question IDs.')
    for row in records:
        validate_record(row, refs)
        ledger.save('input/' + row['id'], row)
    for qid in IDS[:limit]:
        if qid not in by_id:
            raise ValueError('Missing actual answer for ' + qid)
        row = by_id[qid]
        for name, metric in metrics.items():
            key = f'result/{qid}/{name}'
            if ledger.get(key):
                continue
            judge.begin(qid, name)
            kwargs = {'user_input': row['user_input']}
            if name in ('Faithfulness', 'Answer Relevancy'):
                kwargs['response'] = row['response']
            if name != 'Answer Relevancy':
                kwargs['retrieved_contexts'] = row['retrieved_contexts']
            if name in ('Context Precision', 'Context Recall'):
                kwargs['reference'] = refs[qid]['reference']
            start = time.perf_counter()
            # Exceptions propagate. Completed previous metrics remain persisted.
            score = float((await metric.ascore(**kwargs)).value)
            lower = -1 if name == 'Answer Relevancy' else 0
            if not math.isfinite(score) or not lower - 1e-10 <= score <= 1 + 1e-10:
                raise ValueError('Undefined/nonfinite/out-of-range metric: ' + name)
            # Keep the actual library result: do not clip cosine values to inflate them.
            ledger.save(key, {'status': 'complete', 'value': score,
                              'scoring_elapsed_seconds': time.perf_counter() - start})
    return snapshot_report(ledger, records)
