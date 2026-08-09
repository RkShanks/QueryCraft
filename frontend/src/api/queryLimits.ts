import { client } from './generated/client.gen';

export interface QueryLimitsResponse {
  max_question_length: number;
}

function parseQueryLimits(responseBody: unknown): QueryLimitsResponse {
  if (responseBody === null || typeof responseBody !== 'object') {
    throw new Error('invalid_query_limits');
  }
  const maxQuestionLength = (responseBody as Record<string, unknown>).max_question_length;
  if (
    typeof maxQuestionLength !== 'number' ||
    !Number.isInteger(maxQuestionLength) ||
    maxQuestionLength <= 0
  ) {
    throw new Error('invalid_query_limits');
  }
  return { max_question_length: maxQuestionLength };
}

export async function getQueryLimits(): Promise<QueryLimitsResponse> {
  const response = await client.get({
    url: '/query/limits',
    throwOnError: true,
  });
  return parseQueryLimits(response.data);
}
