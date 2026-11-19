import type {
	IDataObject,
	IExecuteFunctions,
	IHttpRequestMethods,
	IHttpRequestOptions,
	JsonObject,
} from 'n8n-workflow';
import { NodeApiError, NodeOperationError, sleep } from 'n8n-workflow';

export const BASE_URL = 'https://api.importly.io';

export type JobKind = 'import' | 'transcript' | 'metadata' | 'basicMetadata';

/** Where each kind of job starts and where its status lives. */
export const JOB_ENDPOINTS: Record<JobKind, { start: string; status: string }> = {
	import: { start: '/import', status: '/import/status' },
	transcript: { start: '/transcribe', status: '/transcribe/status' },
	metadata: { start: '/metadata', status: '/metadata/status' },
	basicMetadata: { start: '/metadata/basic', status: '/metadata/basic/status' },
};

interface FullResponse {
	statusCode: number;
	body: IDataObject;
}

/**
 * Calls the Importly API with the stored API key. Importly answers with
 * `{ success, data }` or `{ success: false, error, code, documentationUrl }`;
 * on an error status this throws a NodeApiError carrying that message.
 */
export async function importlyApiRequest(
	this: IExecuteFunctions,
	method: IHttpRequestMethods,
	endpoint: string,
	itemIndex: number,
	options: { body?: IDataObject; qs?: IDataObject } = {},
): Promise<IDataObject> {
	const requestOptions: IHttpRequestOptions = {
		method,
		url: `${BASE_URL}${endpoint}`,
		json: true,
		returnFullResponse: true,
		ignoreHttpStatusErrors: true,
	};
	if (options.body) requestOptions.body = options.body;
	if (options.qs) requestOptions.qs = options.qs;

	let response: FullResponse;
	try {
		response = (await this.helpers.httpRequestWithAuthentication.call(
			this,
			'importlyApi',
			requestOptions,
		)) as FullResponse;
	} catch (error) {
		throw new NodeApiError(this.getNode(), error as JsonObject, { itemIndex });
	}

	const body = (response.body ?? {}) as IDataObject;
	if (response.statusCode >= 400 || body.success === false) {
		throw new NodeApiError(this.getNode(), body as JsonObject, {
			itemIndex,
			httpCode: String(response.statusCode),
			message:
				typeof body.error === 'string' ? body.error : `Importly returned ${response.statusCode}`,
			description: describeError(body),
		});
	}
	return body;
}

function describeError(body: IDataObject): string | undefined {
	const parts: string[] = [];
	if (typeof body.code === 'string') parts.push(`Code: ${body.code}`);
	if (typeof body.documentationUrl === 'string') parts.push(`More: ${body.documentationUrl}`);
	return parts.length ? parts.join('. ') : undefined;
}

/** Starts a job and returns the queued response's `data` ({ jobId, status, message }). */
export async function startJob(
	this: IExecuteFunctions,
	kind: JobKind,
	body: IDataObject,
	itemIndex: number,
): Promise<IDataObject> {
	const response = await importlyApiRequest.call(
		this,
		'POST',
		JOB_ENDPOINTS[kind].start,
		itemIndex,
		{
			body,
		},
	);
	return (response.data ?? {}) as IDataObject;
}

export async function getJobStatus(
	this: IExecuteFunctions,
	kind: JobKind,
	jobId: string,
	itemIndex: number,
): Promise<IDataObject> {
	const response = await importlyApiRequest.call(
		this,
		'GET',
		JOB_ENDPOINTS[kind].status,
		itemIndex,
		{
			qs: { id: jobId },
		},
	);
	return (response.data ?? {}) as IDataObject;
}

/**
 * Polls a job until it is `completed` or `failed`, or until the timeout.
 * Returns the final status data. A failed job throws a NodeOperationError
 * with Importly's message, code and documentation link.
 */
export async function waitForJob(
	this: IExecuteFunctions,
	kind: JobKind,
	jobId: string,
	itemIndex: number,
	pollIntervalSeconds: number,
	timeoutSeconds: number,
): Promise<IDataObject> {
	const deadline = Date.now() + timeoutSeconds * 1000;
	const cancelSignal = this.getExecutionCancelSignal?.();

	while (true) {
		if (cancelSignal?.aborted) {
			throw new NodeOperationError(this.getNode(), 'The execution was cancelled', { itemIndex });
		}

		let status: IDataObject | undefined;
		try {
			status = await getJobStatus.call(this, kind, jobId, itemIndex);
		} catch (error) {
			// A rate limit while polling isn't fatal: wait and try again.
			const isRateLimited = error instanceof NodeApiError && error.httpCode === '429';
			if (!isRateLimited)
				throw new NodeApiError(this.getNode(), error as JsonObject, { itemIndex });
		}

		if (status?.status === 'completed') return status;
		if (status?.status === 'failed') {
			const description = [
				typeof status.code === 'string' ? `Code: ${status.code}` : '',
				typeof status.documentationUrl === 'string' ? `More: ${status.documentationUrl}` : '',
				`Job ID: ${jobId}`,
			]
				.filter(Boolean)
				.join('. ');
			throw new NodeOperationError(
				this.getNode(),
				typeof status.message === 'string' ? status.message : 'The Importly job failed',
				{ itemIndex, description },
			);
		}

		if (Date.now() + pollIntervalSeconds * 1000 > deadline) {
			throw new NodeOperationError(
				this.getNode(),
				`The job was still running after ${timeoutSeconds} seconds`,
				{
					itemIndex,
					description: `It keeps running. Read it later with Job > Get Status and Job ID ${jobId}, raise the timeout, or turn off "Wait for Completion" and use a webhook.`,
				},
			);
		}
		await sleep(pollIntervalSeconds * 1000);
	}
}

/** Keeps the fields people use from the ~80-field raw metadata. */
export function simplifyMetadata(raw: IDataObject): IDataObject {
	const keys = [
		'id',
		'title',
		'description',
		'uploader',
		'uploader_id',
		'channel',
		'channel_url',
		'upload_date',
		'timestamp',
		'duration',
		'view_count',
		'like_count',
		'comment_count',
		'thumbnail',
		'tags',
		'categories',
		'webpage_url',
	];
	const simplified: IDataObject = {};
	for (const key of keys) {
		if (raw[key] !== undefined && raw[key] !== null) simplified[key] = raw[key];
	}
	return simplified;
}
