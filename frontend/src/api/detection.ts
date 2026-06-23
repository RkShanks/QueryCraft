import { client } from './generated/client.gen';

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
  const res = await client.get({
    url: '/admin/detection/config',
    throwOnError: true,
  });
  return res.data as DetectionConfig;
}

export async function updateDetectionConfig(
  data: DetectionConfigUpdate
): Promise<DetectionConfig> {
  const res = await client.put({
    url: '/admin/detection/config',
    body: data,
    throwOnError: true,
  });
  return res.data as DetectionConfig;
}
