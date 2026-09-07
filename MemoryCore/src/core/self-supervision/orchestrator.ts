import type { FeedbackSidecarStore } from "./sidecar-store.js";
import { abstentionDraft, createSelfSupervisionSignal, type SignalDraft } from "./signal-factory.js";
import type { SelfSupervisionSignal, StructuredRecallTrace } from "./types.js";

export interface SelfSupervisionSignalGenerator {
  readonly id: string;
  generate(trace: StructuredRecallTrace): Promise<SignalDraft>;
}
export class SelfSupervisionOrchestrator {
  constructor(
    private readonly generator: SelfSupervisionSignalGenerator,
    private readonly sidecar: FeedbackSidecarStore,
    private readonly now: () => string = () => new Date().toISOString()
  ) {}

  async process(trace: StructuredRecallTrace): Promise<SelfSupervisionSignal> {
    let draft: SignalDraft;
    try {
      draft = await this.generator.generate(trace);
    } catch (error) {
      draft = abstentionDraft(`generator_failure:${this.generator.id}:${(error as Error).message}`);
    }
    let signal: SelfSupervisionSignal;
    try {
      signal = createSelfSupervisionSignal(trace, draft, this.now());
    } catch (error) {
      signal = createSelfSupervisionSignal(
        trace,
        abstentionDraft(`invalid_generator_output:${this.generator.id}:${(error as Error).message}`),
        this.now()
      );
    }
    await this.sidecar.append(signal);
    return signal;
  }
}
