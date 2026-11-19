import type {
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	JsonObject,
} from 'n8n-workflow';
import { NodeApiError, NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

import { fieldProperties, operationProperties, resourceProperty } from './descriptions';
import type { JobKind } from './GenericFunctions';
import {
	getJobStatus,
	importlyApiRequest,
	simplifyMetadata,
	startJob,
	waitForJob,
} from './GenericFunctions';

/** How many items run at once. Each item is one Importly job. */
const CONCURRENCY = 5;

// Programmatic style: starting a job and then polling its status endpoint until it
// finishes (two dependent calls with a wait loop), plus downloading the finished file
// as binary data, can't be expressed with declarative routing.
export class Importly implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Importly',
		name: 'importly',
		icon: { light: 'file:../../icons/importly.svg', dark: 'file:../../icons/importly.dark.svg' },
		group: ['transform'],
		version: [1],
		subtitle: '={{ $parameter["operation"] + ": " + $parameter["resource"] }}',
		description:
			'Turn any video or audio link into files, transcripts and metadata: YouTube, TikTok, Instagram, X, podcasts and 1,000+ other sites',
		defaults: {
			name: 'Importly',
		},
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		usableAsTool: true,
		credentials: [
			{
				name: 'importlyApi',
				required: true,
			},
		],
		properties: [resourceProperty, ...operationProperties, ...fieldProperties],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const results: INodeExecutionData[][] = new Array(items.length);

		const runItem = async (itemIndex: number): Promise<INodeExecutionData[]> => {
			try {
				return await executeItem.call(this, itemIndex);
			} catch (error) {
				if (this.continueOnFail()) {
					return [
						{
							json: {
								error: (error as Error).message,
								description: (error as NodeOperationError).description,
							},
							pairedItem: { item: itemIndex },
						},
					];
				}
				if (error instanceof NodeApiError) {
					throw new NodeApiError(this.getNode(), error as unknown as JsonObject, { itemIndex });
				}
				throw new NodeOperationError(this.getNode(), error as Error, { itemIndex });
			}
		};

		// Run items in small batches so a list of links doesn't wait on each job in turn.
		for (let start = 0; start < items.length; start += CONCURRENCY) {
			const batch: number[] = [];
			for (let i = start; i < Math.min(start + CONCURRENCY, items.length); i++) batch.push(i);
			const batchResults = await Promise.all(batch.map(async (i) => await runItem(i)));
			batch.forEach((itemIndex, position) => {
				results[itemIndex] = batchResults[position];
			});
		}

		return [results.flat()];
	}
}

async function executeItem(
	this: IExecuteFunctions,
	itemIndex: number,
): Promise<INodeExecutionData[]> {
	const resource = this.getNodeParameter('resource', itemIndex) as string;
	const operation = this.getNodeParameter('operation', itemIndex) as string;
	const pairedItem = { item: itemIndex };

	if (resource === 'account' && operation === 'getBalance') {
		const response = await importlyApiRequest.call(this, 'GET', '/balance', itemIndex);
		return [{ json: (response.data ?? {}) as IDataObject, pairedItem }];
	}

	if (resource === 'job' && operation === 'getStatus') {
		const jobType = this.getNodeParameter('jobType', itemIndex) as JobKind;
		const jobId = (this.getNodeParameter('jobId', itemIndex) as string).trim();
		const status = await getJobStatus.call(this, jobType, jobId, itemIndex);
		return [{ json: status, pairedItem }];
	}

	const kind = jobKindFor(resource, operation);
	if (!kind) {
		throw new NodeOperationError(
			this.getNode(),
			`The operation "${operation}" isn't supported for "${resource}"`,
			{ itemIndex },
		);
	}

	const url = (this.getNodeParameter('url', itemIndex) as string).trim();
	if (!/^https?:\/\//i.test(url)) {
		throw new NodeOperationError(this.getNode(), 'Media URL must start with http:// or https://', {
			itemIndex,
		});
	}
	const waitForCompletion = this.getNodeParameter('waitForCompletion', itemIndex, true) as boolean;
	const options = this.getNodeParameter('options', itemIndex, {}) as IDataObject;

	const body = buildJobBody(kind, url, options);
	if (!waitForCompletion) {
		const webhookUrl = (this.getNodeParameter('webhookUrl', itemIndex, '') as string).trim();
		if (webhookUrl) body.webhookUrl = webhookUrl;
	}

	const queued = await startJob.call(this, kind, body, itemIndex);
	const jobId = String(queued.jobId ?? '');

	if (!waitForCompletion) {
		return [
			{ json: { jobId, status: queued.status ?? 'queued', message: queued.message }, pairedItem },
		];
	}

	const final = await waitForJob.call(
		this,
		kind,
		jobId,
		itemIndex,
		Number(options.pollInterval ?? 5),
		Number(options.timeout ?? (kind === 'import' || kind === 'transcript' ? 600 : 120)),
	);
	const result = (final.result ?? {}) as IDataObject;

	if (kind === 'metadata') {
		const simplify = this.getNodeParameter('simplify', itemIndex, true) as boolean;
		return [{ json: { jobId, ...(simplify ? simplifyMetadata(result) : result) }, pairedItem }];
	}

	if (kind === 'transcript') {
		const includeSegments = options.includeSegments !== false;
		const transcript: IDataObject = { jobId, ...result };
		if (!includeSegments) delete transcript.data;
		return [{ json: transcript, pairedItem }];
	}

	if (kind === 'import') {
		const json: IDataObject = { jobId, ...result };
		const downloadFile = this.getNodeParameter('downloadFile', itemIndex, true) as boolean;
		if (!downloadFile || typeof result.mediaUrl !== 'string') return [{ json, pairedItem }];

		const binaryPropertyName = this.getNodeParameter(
			'binaryPropertyName',
			itemIndex,
			'data',
		) as string;
		const file = (await this.helpers.httpRequest({
			method: 'GET',
			url: result.mediaUrl,
			encoding: 'arraybuffer',
			json: false,
		})) as ArrayBuffer;
		const filename = typeof result.filename === 'string' ? result.filename : `${jobId}`;
		const binaryData = await this.helpers.prepareBinaryData(Buffer.from(file), filename);
		return [{ json, binary: { [binaryPropertyName]: binaryData }, pairedItem }];
	}

	return [{ json: { jobId, ...result }, pairedItem }];
}

function jobKindFor(resource: string, operation: string): JobKind | undefined {
	if (resource === 'media' && operation === 'import') return 'import';
	if (resource === 'transcript' && operation === 'get') return 'transcript';
	if (resource === 'metadata' && operation === 'get') return 'metadata';
	if (resource === 'metadata' && operation === 'getBasic') return 'basicMetadata';
	return undefined;
}

/** Maps the node's options onto the Importly request body for each job kind. */
export function buildJobBody(kind: JobKind, url: string, options: IDataObject): IDataObject {
	const body: IDataObject = { url };

	if (kind === 'import') {
		if (options.format === 'audioOnly') body.includeVideo = false;
		if (options.format === 'videoOnly') body.includeAudio = false;
		copyIfSet(options, body, [
			'videoQuality',
			'audioQuality',
			'maxCostDollars',
			'transcriptLanguage',
		]);
		if (options.includeTranscript === true) body.includeTranscript = true;
		if (options.store === true) {
			body.store = true;
			copyIfSet(options, body, ['storagePath', 'storageFilename']);
		}
	}

	if (kind === 'transcript') {
		copyIfSet(options, body, ['language', 'maxCostDollars']);
		if (typeof options.provider === 'string' && options.provider !== 'captions') {
			body.provider = options.provider;
		}
	}

	return body;
}

function copyIfSet(from: IDataObject, to: IDataObject, keys: string[]): void {
	for (const key of keys) {
		const value = from[key];
		if (value === undefined || value === null || value === '') continue;
		to[key] = value;
	}
}
