export interface DetectionConfig {
  block_confidence: number;
  flag_confidence: number;
  updated_at?: string;
}

export interface DetectionConfigUpdate {
  block_confidence: number;
  flag_confidence: number;
}

export async function getDetectionConfig(): Promise<DetectionConfig> {
  throw new Error('Not implemented');
}

export async function updateDetectionConfig(
  data: DetectionConfigUpdate
): Promise<DetectionConfig> {
  throw new Error('Not implemented');
}
