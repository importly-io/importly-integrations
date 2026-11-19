// Unit tests for the built node (run `npm test`, which builds first).
// They stub n8n's execute context and the Importly API, so no network or n8n is needed.
const { test } = require('node:test');
const assert = require('node:assert/strict');

const { Importly } = require('../dist/nodes/Importly/Importly.node.js');
const { ImportlyApi } = require('../dist/credentials/ImportlyApi.credentials.js');

const FAST = { pollInterval: 0.01, timeout: 10 };

/**
 * Builds a fake IExecuteFunctions.
 * - params: node parameters (shared by every item unless a function is given)
 * - api: (method, path, options) => { statusCode, body } for Importly calls
 */
function makeContext({ params, items = [{ json: {} }], api, files = {}, continueOnFail = false }) {
	const calls = [];
	return {
		calls,
		getInputData: () => items,
		getNode: () => ({ name: 'Importly', type: 'n8n-nodes-importly.importly', typeVersion: 1 }),
		getNodeParameter: (name, itemIndex, fallback) => {
			const value = typeof params === 'function' ? params(itemIndex)[name] : params[name];
			return value === undefined ? fallback : value;
		},
		continueOnFail: () => continueOnFail,
		getExecutionCancelSignal: () => undefined,
		helpers: {
			httpRequestWithAuthentication: async (credentialType, options) => {
				assert.equal(credentialType, 'importlyApi');
				const path = options.url.replace('https://api.importly.io', '');
				calls.push({ method: options.method, path, body: options.body, qs: options.qs });
				return api(options.method, path, options);
			},
			httpRequest: async (options) => {
				calls.push({ method: 'GET', download: options.url });
				const content = files[options.url];
				if (!content) throw new Error(`unexpected download ${options.url}`);
				return new TextEncoder().encode(content).buffer;
			},
			prepareBinaryData: async (buffer, fileName) => ({
				data: Buffer.from(buffer).toString('base64'),
				fileName,
				mimeType: 'application/octet-stream',
			}),
		},
	};
}

const ok = (data) => ({ statusCode: 200, body: { success: true, data } });

async function run(ctx) {
	return new Importly().execute.call(ctx);
}

test('credential sends the key as a Bearer token and tests against /balance', () => {
	const credential = new ImportlyApi();
	assert.equal(
		credential.authenticate.properties.headers.Authorization,
		'=Bearer {{$credentials.apiKey}}',
	);
	assert.equal(credential.test.request.url, '/balance');
	assert.equal(credential.properties[0].typeOptions.password, true);
});

test('Media > Import polls until completed and outputs the file as binary', async () => {
	let polls = 0;
	const ctx = makeContext({
		params: {
			resource: 'media',
			operation: 'import',
			url: 'https://www.tiktok.com/@user/video/123',
			waitForCompletion: true,
			downloadFile: true,
			binaryPropertyName: 'data',
			options: { ...FAST, format: 'audioOnly', videoQuality: '1080p', maxCostDollars: 0.2 },
		},
		api: (method, path) => {
			if (method === 'POST' && path === '/import') return ok({ jobId: 'job-1', status: 'queued' });
			if (path === '/import/status') {
				polls++;
				if (polls < 3) return ok({ jobId: 'job-1', status: 'running' });
				return ok({
					jobId: 'job-1',
					status: 'completed',
					result: {
						mediaUrl: 'https://files.example/clip.mp3',
						filename: 'clip.mp3',
						title: 'Clip',
					},
				});
			}
			throw new Error(`unexpected ${method} ${path}`);
		},
		files: { 'https://files.example/clip.mp3': 'AUDIO' },
	});

	const [output] = await run(ctx);
	assert.equal(polls, 3);
	assert.deepEqual(ctx.calls[0].body, {
		url: 'https://www.tiktok.com/@user/video/123',
		includeVideo: false,
		videoQuality: '1080p',
		maxCostDollars: 0.2,
	});
	assert.equal(output.length, 1);
	assert.equal(output[0].json.jobId, 'job-1');
	assert.equal(output[0].json.title, 'Clip');
	assert.equal(output[0].binary.data.fileName, 'clip.mp3');
	assert.equal(Buffer.from(output[0].binary.data.data, 'base64').toString(), 'AUDIO');
	assert.deepEqual(output[0].pairedItem, { item: 0 });
});

test('Media > Import with S3 copy sends store options and skips the download when turned off', async () => {
	const ctx = makeContext({
		params: {
			resource: 'media',
			operation: 'import',
			url: 'https://www.instagram.com/reel/abc/',
			waitForCompletion: true,
			downloadFile: false,
			options: { ...FAST, store: true, storagePath: 'reels', storageFilename: '' },
		},
		api: (method, path) =>
			method === 'POST'
				? ok({ jobId: 'job-2', status: 'queued' })
				: ok({
						jobId: 'job-2',
						status: 'completed',
						result: { mediaUrl: 'https://files.example/r.mp4', s3Storage: { key: 'reels/r.mp4' } },
					}),
	});
	const [output] = await run(ctx);
	assert.deepEqual(ctx.calls[0].body, {
		url: 'https://www.instagram.com/reel/abc/',
		store: true,
		storagePath: 'reels',
	});
	assert.equal(output[0].binary, undefined);
	assert.equal(output[0].json.s3Storage.key, 'reels/r.mp4');
	assert.ok(!ctx.calls.some((call) => call.download));
});

test('webhook mode returns the job ID right away and passes the webhook URL', async () => {
	const ctx = makeContext({
		params: {
			resource: 'transcript',
			operation: 'get',
			url: 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
			waitForCompletion: false,
			webhookUrl: 'https://n8n.example/webhook-waiting/42',
			options: { provider: 'captions', language: 'en' },
		},
		api: () => ok({ jobId: 'job-3', status: 'queued', message: 'Transcription has been queued.' }),
	});
	const [output] = await run(ctx);
	assert.equal(ctx.calls.length, 1);
	assert.deepEqual(ctx.calls[0].body, {
		url: 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
		language: 'en',
		webhookUrl: 'https://n8n.example/webhook-waiting/42',
	});
	assert.equal(output[0].json.jobId, 'job-3');
	assert.equal(output[0].json.status, 'queued');
});

test('Transcript > Get returns text and segments, and can drop the segments', async () => {
	const result = {
		text: 'hello world',
		language: 'en',
		source: 'platform_captions',
		data: { segments: [{ start: 0, end: 1, text: 'hello world' }] },
	};
	const api = (method) =>
		method === 'POST'
			? ok({ jobId: 'job-4', status: 'queued' })
			: ok({ jobId: 'job-4', status: 'completed', result });

	const withSegments = await run(
		makeContext({
			params: {
				resource: 'transcript',
				operation: 'get',
				url: 'https://youtu.be/x',
				waitForCompletion: true,
				options: { ...FAST, provider: 'importly' },
			},
			api,
		}),
	);
	assert.equal(withSegments[0][0].json.text, 'hello world');
	assert.equal(withSegments[0][0].json.data.segments.length, 1);

	const ctx = makeContext({
		params: {
			resource: 'transcript',
			operation: 'get',
			url: 'https://youtu.be/x',
			waitForCompletion: true,
			options: { ...FAST, includeSegments: false },
		},
		api,
	});
	const withoutSegments = await run(ctx);
	assert.equal(withoutSegments[0][0].json.data, undefined);
	assert.equal(ctx.calls[0].body.provider, undefined);
});

test('Metadata > Get simplifies the raw metadata by default', async () => {
	const ctx = makeContext({
		params: {
			resource: 'metadata',
			operation: 'get',
			url: 'https://youtu.be/x',
			waitForCompletion: true,
			simplify: true,
			options: FAST,
		},
		api: (method) =>
			method === 'POST'
				? ok({ jobId: 'job-5', status: 'queued' })
				: ok({
						jobId: 'job-5',
						status: 'completed',
						result: {
							id: 'x',
							title: 'Me at the zoo',
							duration: 19,
							formats: [{ format_id: '140' }],
							view_count: 5,
						},
					}),
	});
	const [output] = await run(ctx);
	assert.deepEqual(output[0].json, {
		jobId: 'job-5',
		id: 'x',
		title: 'Me at the zoo',
		duration: 19,
		view_count: 5,
	});
	assert.equal(ctx.calls[0].path, '/metadata');
	assert.equal(ctx.calls[1].path, '/metadata/status');
});

test('Metadata > Get Basic uses the basic endpoints', async () => {
	const ctx = makeContext({
		params: {
			resource: 'metadata',
			operation: 'getBasic',
			url: 'https://youtu.be/x',
			waitForCompletion: true,
			options: FAST,
		},
		api: (method) =>
			method === 'POST'
				? ok({ jobId: 'job-6', status: 'queued' })
				: ok({
						jobId: 'job-6',
						status: 'completed',
						result: { title: 'T', duration: 1, thumbnail: 'https://i/t.jpg' },
					}),
	});
	const [output] = await run(ctx);
	assert.equal(ctx.calls[0].path, '/metadata/basic');
	assert.equal(ctx.calls[1].path, '/metadata/basic/status');
	assert.equal(output[0].json.title, 'T');
});

test('a failed job throws with Importly’s message and code', async () => {
	const ctx = makeContext({
		params: {
			resource: 'metadata',
			operation: 'getBasic',
			url: 'https://youtu.be/gone',
			waitForCompletion: true,
			options: FAST,
		},
		api: (method) =>
			method === 'POST'
				? ok({ jobId: 'job-7', status: 'queued' })
				: ok({
						jobId: 'job-7',
						status: 'failed',
						message: 'Source video is unavailable.',
						code: 'VIDEO_UNAVAILABLE',
					}),
	});
	await assert.rejects(run(ctx), (error) => {
		assert.equal(error.message, 'Source video is unavailable.');
		assert.match(error.description, /VIDEO_UNAVAILABLE/);
		assert.match(error.description, /job-7/);
		return true;
	});
});

test('Continue On Fail outputs the error per item instead of stopping', async () => {
	const ctx = makeContext({
		items: [{ json: {} }, { json: {} }],
		params: (i) => ({
			resource: 'metadata',
			operation: 'getBasic',
			url: i === 0 ? 'https://youtu.be/ok' : 'not a url',
			waitForCompletion: true,
			options: FAST,
		}),
		continueOnFail: true,
		api: (method) =>
			method === 'POST'
				? ok({ jobId: 'job-8', status: 'queued' })
				: ok({ jobId: 'job-8', status: 'completed', result: { title: 'OK' } }),
	});
	const [output] = await run(ctx);
	assert.equal(output.length, 2);
	assert.equal(output[0].json.title, 'OK');
	assert.match(output[1].json.error, /must start with http/);
	assert.deepEqual(output[1].pairedItem, { item: 1 });
});

test('times out with the job ID when the job keeps running', async () => {
	const ctx = makeContext({
		params: {
			resource: 'media',
			operation: 'import',
			url: 'https://youtu.be/long',
			waitForCompletion: true,
			options: { pollInterval: 0.01, timeout: 0.05 },
		},
		api: (method) =>
			method === 'POST'
				? ok({ jobId: 'job-9', status: 'queued' })
				: ok({ jobId: 'job-9', status: 'running' }),
	});
	await assert.rejects(run(ctx), (error) => {
		assert.match(error.message, /still running/);
		assert.match(error.description, /job-9/);
		return true;
	});
});

test('API errors surface Importly’s error message', async () => {
	const ctx = makeContext({
		params: {
			resource: 'media',
			operation: 'import',
			url: 'https://youtu.be/x',
			waitForCompletion: true,
			options: FAST,
		},
		api: () => ({
			statusCode: 402,
			body: {
				success: false,
				error: 'Insufficient balance. Please add credits to your account.',
				code: 'INSUFFICIENT_BALANCE',
			},
		}),
	});
	await assert.rejects(run(ctx), (error) => {
		assert.equal(error.message, 'Insufficient balance. Please add credits to your account.');
		assert.equal(error.httpCode, '402');
		return true;
	});
});

test('a rate limit while polling waits and keeps going', async () => {
	let polls = 0;
	const ctx = makeContext({
		params: {
			resource: 'metadata',
			operation: 'getBasic',
			url: 'https://youtu.be/x',
			waitForCompletion: true,
			options: FAST,
		},
		api: (method) => {
			if (method === 'POST') return ok({ jobId: 'job-10', status: 'queued' });
			polls++;
			if (polls === 1)
				return {
					statusCode: 429,
					body: { success: false, error: 'Rate limit exceeded', code: 'RATE_LIMITED' },
				};
			return ok({ jobId: 'job-10', status: 'completed', result: { title: 'After limit' } });
		},
	});
	const [output] = await run(ctx);
	assert.equal(output[0].json.title, 'After limit');
});

test('Job > Get Status and Account > Get Balance read the matching endpoints', async () => {
	const statusCtx = makeContext({
		params: { resource: 'job', operation: 'getStatus', jobType: 'transcript', jobId: ' job-11 ' },
		api: () => ok({ jobId: 'job-11', status: 'running' }),
	});
	const [statusOutput] = await run(statusCtx);
	assert.equal(statusCtx.calls[0].path, '/transcribe/status');
	assert.deepEqual(statusCtx.calls[0].qs, { id: 'job-11' });
	assert.equal(statusOutput[0].json.status, 'running');

	const balanceCtx = makeContext({
		params: { resource: 'account', operation: 'getBalance' },
		api: () => ok({ balance: 2.97, currency: 'USD' }),
	});
	const [balanceOutput] = await run(balanceCtx);
	assert.deepEqual(balanceOutput[0].json, { balance: 2.97, currency: 'USD' });
});

test('keeps item order when several links run at once', async () => {
	const urls = Array.from({ length: 7 }, (_, i) => `https://youtu.be/v${i}`);
	const ctx = makeContext({
		items: urls.map(() => ({ json: {} })),
		params: (i) => ({
			resource: 'metadata',
			operation: 'getBasic',
			url: urls[i],
			waitForCompletion: true,
			options: FAST,
		}),
		api: (method, path, options) => {
			if (method === 'POST') return ok({ jobId: options.body.url, status: 'queued' });
			return ok({ jobId: options.qs.id, status: 'completed', result: { title: options.qs.id } });
		},
	});
	const [output] = await run(ctx);
	assert.deepEqual(
		output.map((item) => item.json.title),
		urls,
	);
	assert.deepEqual(
		output.map((item) => item.pairedItem.item),
		[0, 1, 2, 3, 4, 5, 6],
	);
});
