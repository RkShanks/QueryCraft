import {
  getDetectionConfig as getCanonicalDetectionConfig,
  updateDetectionConfig as updateCanonicalDetectionConfig,
} from './generated/sdk.gen';
import type {
  DetectionThresholdRead,
  DetectionThresholdUpdate,
} from './generated/types.gen';

export type DetectionConfig = DetectionThresholdRead;
export type DetectionConfigUpdate = DetectionThresholdUpdate;

export async function getDetectionConfig(signal?: AbortSignal): Promise<DetectionConfig> {
  const response = await getCanonicalDetectionConfig({ throwOnError: true, signal });
  return response.data;
}

export async function updateDetectionConfig(
  data: DetectionConfigUpdate
): Promise<DetectionConfig> {
  const response = await updateCanonicalDetectionConfig({
    body: data,
    throwOnError: true,
  });
  return response.data;
}
