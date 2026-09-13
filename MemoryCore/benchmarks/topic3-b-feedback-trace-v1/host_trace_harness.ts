/** One deterministic local host-path event; no model, network, or production writes. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import { writeMemory } from '../../src/core/record/l1-writer.js';
import { VectorStore, buildFtsQuery } from '../../src/core/store/sqlite.js';
import {
  applyStructuredRecallBudget,
  createRecallShadowDraft,
  JsonlRecallShadowObserver,
  type RecallSearchFacts,
} from '../../src/core/self-supervision/recall-shadow-adapter.js';
import { OpenClawRecallTurnBridge } from '../../src/core/self-supervision/openclaw-recall-turn-bridge.js';
import {
  decisionTraceFromRecallObservation,
  JsonlFeedbackTraceStore,
  observeFeedback,
  recordMemoryAssertion,
  recordOutcome,
} from '../support/memory-feedback/index.js';

const [output] = process.argv.slice(2);
assert(output, 'usage: tsx host_trace_harness.ts OUTPUT_DIRECTORY');
await mkdir(output);

const memory = new VectorStore(join(output, 'memory.sqlite'), 0);
memory.init();
try {
  const stored = await writeMemory({
    baseDir: output,
    sessionKey: 'development-session',
    sessionId: 'development-session',
    userId: 'development-user',
    agentId: 'host-trace-harness',
    vectorStore: memory,
    memory: {
      content: 'The demo service uses port 8080.',
      type: 'work_fact',
      priority: 80,
      scene_name: 'development',
      source_message_ids: ['source-old-port'],
      metadata: {},
    },
    decision: { record_id: 'memory-port-8080', action: 'store', target_ids: [] },
  });
  assert(stored);
  const query = buildFtsQuery('demo service port');
  assert(query);
  const [recalled] = await memory.searchL1Fts(query, 1, { userId: 'development-user' });
  assert(recalled);

  const renderedMemory = `- [fact|development] ${recalled.content}`;
  const prependContext = `<relevant-memories>\n${renderedMemory}\n</relevant-memories>`;
  const candidates = applyStructuredRecallBudget([{
    row: recalled,
    retrievalRank: 1,
    score: recalled.score,
    stage: 'l1_keyword',
    renderedText: renderedMemory,
  }], {});
  const search: RecallSearchFacts = {
    strategy: 'keyword', status: 'completed', failureCode: null, queryEligible: true,
    configuredMaxResults: 1, configuredScoreThreshold: 0,
    rawCandidateCount: 1, scoreFilteredCount: 0, rankPrunedCount: 0,
    selectedCandidateCount: 1, smallCorpusThresholdBypass: false,
  };
  let tick = 0;
  const clock = () => new Date(1700000000000 + tick++ * 1000);
  const bridge = new OpenClawRecallTurnBridge({
    observer: new JsonlRecallShadowObserver(output),
    taskRunIdFactory: () => 'development-task-1',
    clock,
  });
  const turn = bridge.beginTurn({ sessionKey: 'development-session', sessionId: 'development-session' });
  turn.shadowTap.onDraft(createRecallShadowDraft({
    traceId: turn.shadowTap.traceId,
    capturedAt: turn.shadowTap.capturedAt!,
    sessionKey: 'development-session',
    sessionId: 'development-session',
    taskRunId: turn.taskRunId,
    actorId: 'development-user',
    query: 'Which port does the demo service use?',
    expectedPrependContext: prependContext,
    search,
    limits: {},
    candidates,
  }));
  assert(bridge.recordHookReturn({
    sessionKey: 'development-session', taskRunId: turn.taskRunId, prependContext,
  }));

  const prompt = `Answer using relevant memory.\n${prependContext}\nQuestion: Which port?`;
  const observation = bridge.onLlmInput({ sessionKey: 'development-session', prompt });
  assert(observation);
  const spanStart = prompt.indexOf(renderedMemory);
  assert(spanStart >= 0);
  const decision = decisionTraceFromRecallObservation({
    observation,
    policyVersion: 'openclaw-recall:deterministic-development-v1',
    propensity: 1,
    prompt,
    promptMemorySpans: [{ memoryId: recalled.record_id, start: spanStart, end: spanStart + renderedMemory.length }],
    outputIds: ['assistant-output-1'],
    contextEventIds: ['user-request-1'],
  });

  const ledger = new JsonlFeedbackTraceStore(output);
  ledger.append(decision);
  const ended = bridge.endTurn({
    sessionKey: 'development-session',
    messages: [{ id: 'assistant-output-1', role: 'assistant', content: 'The service uses port 8080.' }],
  });
  assert.equal(ended?.assistantText, 'The service uses port 8080.');

  const feedback = observeFeedback({
    id: 'feedback-1',
    decisionId: decision.id,
    observationType: 'explicit_correction',
    targetType: 'answer_span',
    targetIds: ['assistant-output-1:port'],
    claimText: 'Use port 9090 now, not 8080.',
    scope: 'service=demo',
    authority: 'explicit_user',
    confidence: 1,
    sourceEventIds: ['user-feedback-1'],
    observedAt: new Date(1700000004000).toISOString(),
  });
  ledger.append(feedback);
  const assertion = recordMemoryAssertion({
    id: 'assertion-demo-port-9090',
    subject: 'demo-service', predicate: 'port', value: 9090, scope: 'service=demo',
    validFrom: new Date(1700000004000).toISOString(), validTo: null,
    recordedAt: new Date(1700000005000).toISOString(), supersededAt: null,
    status: 'verified', authority: 'explicit_user', sourceEventIds: ['user-feedback-1'],
    supportedByClaimIds: [feedback.id], contradictsAssertionIds: [],
  });
  ledger.append(assertion);
  const outcome = recordOutcome({
    id: 'outcome-1', decisionId: decision.id, result: 'failure', reward: 0,
    metrics: { expectedPort: 9090, answerPort: 8080, checkerPass: false },
    source: 'deterministic-development-checker',
    observedAt: new Date(1700000006000).toISOString(), delayed: true,
  });
  ledger.append(outcome);

  const replay = new JsonlFeedbackTraceStore(output).replay();
  assert(replay.ok);
  assert.deepEqual(replay.learningSamples, [{
    decisionId: decision.id, feedbackClaimIds: [feedback.id], outcomeIds: [outcome.id],
  }]);
  const summary = {
    protocol: 'topic3-b-host-trace-closure-v1',
    retrieval: { strategy: 'fts', candidateIds: decision.candidateMemoryIds },
    decision: { id: decision.id, action: decision.action, selectedMemoryIds: decision.selectedMemoryIds,
      policyVersion: decision.policyVersion, propensity: decision.propensity,
      promptMemorySpans: decision.promptMemorySpans, outputIds: decision.outputIds },
    feedback: { id: feedback.id, targetType: feedback.targetType, authority: feedback.authority,
      sourceEventIds: feedback.sourceEventIds },
    assertion: { id: assertion.id, status: assertion.status, supportedByClaimIds: assertion.supportedByClaimIds },
    outcome: { id: outcome.id, result: outcome.result, reward: outcome.reward, source: outcome.source },
    replay,
    scope: 'Deterministic isolated local host path with real SQLite L1 write/search and byte-acknowledged prompt exposure. '
      + 'Scripted assistant/user text and checker; no model, network, production write, learned policy, or B gain.',
  };
  await writeFile(join(output, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
  console.log(JSON.stringify(summary));
} finally {
  memory.close();
}
