/**
 * TypeScript State Schemas for Autonomous Agentic Coding System (Harness Pattern)
 */

export type SystemStatus = 
  | 'INITIALIZED'
  | 'SPECIFIED'
  | 'CODING'
  | 'GUARDRAIL_CHECK'
  | 'TESTING'
  | 'REVIEWING'
  | 'APPROVED'
  | 'FALLBACK_HUMAN'
  | 'COMMITTED';

export interface TestOutcome {
  passed: boolean;
  exitCode: number;
  passedCount: number;
  failedCount: number;
  stdout: string;
  stderr: string;
  errorLogs: string[];
}

export interface PatchRequirement {
  filePath: string;
  issueCategory: 'SYNTAX' | 'UNIT_TEST' | 'LINT' | 'SECURITY_VIOLATION' | 'LOGIC';
  lineNumber?: number;
  description: string;
  suggestedFix: string;
}

export interface ReviewCritique {
  approved: boolean;
  qualityScore: number; // Range: 0.0 to 1.0
  summary: string;
  requiredPatches: PatchRequirement[];
}

export interface SecurityVerdict {
  isSafe: boolean;
  violations: string[];
  blockedCalls: string[];
}

export interface TaskSpec {
  featureName: string;
  summary: string;
  filesToCreateOrModify: string[];
  architectureNotes: string;
  acceptanceCriteria: string[];
  testRequirements: string[];
}

export interface AgentState {
  featureRequest: string;
  taskSpec?: TaskSpec;
  codeArtifacts: Record<string, string>; // filePath -> content
  securityVerdict?: SecurityVerdict;
  testOutcome?: TestOutcome;
  reviewCritique?: ReviewCritique;
  attemptCount: number;
  maxRetries: number; // Default: 3
  status: SystemStatus;
  messages: Array<{ role: string; content: string }>;
}
